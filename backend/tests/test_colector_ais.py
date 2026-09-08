"""Pruebas del colector de AISStream — RF-06 (`US-02`).

El bucle se prueba con un transporte de mentira, y no por comodidad: el riesgo
**R1** deja la cuenta sin entregar datos desde el 19/08/2026, así que una prueba
contra el socket real no correría. El transporte inyectable es lo que permite
que la historia tenga pruebas antes de que R1 se resuelva.

Las que persisten van marcadas `integration`; las del bucle no tocan la base.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest

from app.models.elemento_rastreado import ElementoRastreado
from app.services.rastreo import aisstream
from app.services.rastreo.colector_ais import (
    DESCARTE_SIN_DATO_UTIL,
    DESCARTE_SIN_ELEMENTO,
    ColectorAIS,
    buscar_elemento,
    procesar_mensaje,
)
from app.services.resiliencia import ClaseFallo, EstadoFuente, PoliticaReintento

CARIBE = [[[9.0, -84.0], [16.0, -59.0]]]
MMSI = "311001711"


def _crudo(
    *,
    tipo: str = "PositionReport",
    mmsi: str = MMSI,
    instante: str = "2026-08-18 20:18:16.319595413 +0000 UTC",
    **cuerpo: object,
) -> str:
    """Un mensaje de AISStream con la forma real, serializado como llega."""
    base: dict[str, object] = {"Latitude": 11.07302, "Longitude": -74.23296, "Valid": True}
    base.update(cuerpo)
    return json.dumps(
        {
            "MessageType": tipo,
            "MetaData": {"MMSI": int(mmsi), "ShipName": "CSL KULEANA", "time_utc": instante},
            "Message": {tipo: base},
        }
    )


class ConexionFalsa:
    """Transporte de mentira: entrega lo que se le dio y anota qué le hicieron."""

    def __init__(self, mensajes: list[str], *, al_terminar: Exception | None = None) -> None:
        self._mensajes = mensajes
        self._al_terminar = al_terminar
        self.enviado: list[str] = []
        self.abortada = False
        self.cerrada_negociando = False

    async def enviar(self, texto: str) -> None:
        self.enviado.append(texto)

    async def __aiter__(self):
        for mensaje in self._mensajes:
            yield mensaje
        if self._al_terminar is not None:
            raise self._al_terminar

    async def abortar(self) -> None:
        self.abortada = True

    async def close(self) -> None:  # pragma: no cover - no debe llamarse nunca
        self.cerrada_negociando = True


class RelojFalso:
    """Devuelve los instantes que se le indiquen, en orden."""

    def __init__(self, marcas: list[float]) -> None:
        self._marcas = list(marcas)
        self._ultima = 0.0

    def __call__(self) -> float:
        if self._marcas:
            self._ultima = self._marcas.pop(0)
        return self._ultima


def _colector(
    conexiones: list[ConexionFalsa],
    *,
    estado: EstadoFuente | None = None,
    marcas: list[float] | None = None,
    dormidas: list[float] | None = None,
) -> ColectorAIS:
    pendientes = list(conexiones)

    async def abrir() -> ConexionFalsa:
        if not pendientes:
            raise AssertionError("El colector abrió más conexiones de las previstas.")
        return pendientes.pop(0)

    async def dormir(segundos: float) -> None:
        if dormidas is not None:
            dormidas.append(segundos)

    return ColectorAIS(
        api_key="clave-de-prueba",
        cajas=CARIBE,
        abrir=abrir,
        estado=estado or EstadoFuente(nombre="aisstream"),
        dormir=dormir,
        reloj=RelojFalso(marcas or [0.0, 600.0]),
    )


async def _recolectar(colector: ColectorAIS, *, ciclos: int = 1) -> list[object]:
    recibidas: list[object] = []

    async def procesar(lectura: object) -> None:
        recibidas.append(lectura)

    await colector.ejecutar(procesar, ciclos=ciclos)
    return recibidas


# --- La suscripción --------------------------------------------------------


def test_una_suscripcion_invalida_falla_al_construir_el_colector() -> None:
    """Antes de gastar una conexión: un cierre por suscripción malformada es
    indistinguible de uno por credencial, y el diagnóstico sería imposible."""
    with pytest.raises(ValueError, match="bounding box"):
        ColectorAIS(api_key="k", cajas=[], abrir=None)  # type: ignore[arg-type]


async def test_la_suscripcion_se_envia_al_conectar() -> None:
    conexion = ConexionFalsa([_crudo()])
    await _recolectar(_colector([conexion]))

    assert json.loads(conexion.enviado[0]) == {
        "APIKey": "clave-de-prueba",
        "BoundingBoxes": CARIBE,
    }


# --- El flujo normal -------------------------------------------------------


async def test_las_posiciones_llegan_parseadas_al_consumidor() -> None:
    recibidas = await _recolectar(_colector([ConexionFalsa([_crudo(Sog=12.5, Cog=87.0)])]))

    (lectura,) = recibidas
    assert isinstance(lectura, aisstream.PosicionAIS)
    assert lectura.mmsi == MMSI
    assert lectura.velocidad_nudos == 12.5
    assert lectura.rumbo_grados == 87.0


async def test_los_tipos_que_no_interesan_no_llegan_al_consumidor() -> None:
    """Estación base y ayudas a la navegación son tráfico legítimo del stream
    que a TrackIn no le sirve. No se propagan y no son un error."""
    conexion = ConexionFalsa([_crudo(tipo="BaseStationReport"), _crudo()])
    recibidas = await _recolectar(_colector([conexion]))
    assert len(recibidas) == 1


async def test_un_mensaje_ilegible_no_tumba_la_suscripcion() -> None:
    """Un frame corrupto es problema de la fuente. Se registra y se sigue."""
    conexion = ConexionFalsa(["{esto no es json", json.dumps({"sin": "tipo"}), _crudo()])
    recibidas = await _recolectar(_colector([conexion]))

    assert len(recibidas) == 1
    assert isinstance(recibidas[0], aisstream.PosicionAIS)


async def test_el_transporte_se_aborta_y_nunca_se_cierra_negociando() -> None:
    """El `close()` negociado se cuelga con volumen alto (Fase 0 del spike)."""
    conexion = ConexionFalsa([_crudo()])
    await _recolectar(_colector([conexion]))

    assert conexion.abortada
    assert not conexion.cerrada_negociando


# --- Principio 1 de `US-03`: el silencio no es una caída -------------------


async def test_un_mensaje_que_no_interesa_cuenta_como_contacto_exitoso() -> None:
    """Recibir tráfico ajeno prueba que la fuente está viva. Tratarlo como
    fallo es el error que hizo parecer roto al spike TG-10."""
    estado = EstadoFuente(nombre="aisstream")
    estado.registrar_fallo(
        instante=dt.datetime.now(dt.UTC), clase=ClaseFallo.TRANSITORIO, motivo="tiempo_agotado"
    )

    await _recolectar(_colector([ConexionFalsa([_crudo(tipo="BaseStationReport")])], estado=estado))

    assert estado.ultimo_contacto_ok is not None


async def test_una_conexion_larga_sin_mensajes_no_dispara_reconexion_por_silencio() -> None:
    """No hay watchdog por ausencia de datos, y es deliberado: la zona que le
    interesa a TrackIn **no tiene cobertura**, así que reconectar por silencio
    reconectaría para siempre. Solo una conexión, aunque no llegue nada."""
    conexion = ConexionFalsa([])
    dormidas: list[float] = []
    await _recolectar(_colector([conexion], marcas=[0.0, 3600.0], dormidas=dormidas), ciclos=1)

    assert conexion.abortada
    assert dormidas == []  # no esperó nada: no hubo fallo previo que reintentar


# --- Principio 2: el cierre inmediato es la credencial --------------------


async def test_un_cierre_inmediato_se_clasifica_como_credencial_y_detiene_todo() -> None:
    """El spike lo midió en 747 ms, sin close frame ni código: lo único que lo
    distingue de un corte de red es cuándo ocurre."""
    estado = EstadoFuente(nombre="aisstream")
    colector = _colector([ConexionFalsa([])], estado=estado, marcas=[0.0, 0.7])

    # Dos ciclos, pero el segundo no debe llegar a abrir conexión.
    await _recolectar(colector, ciclos=2)

    assert estado.motivo_ultimo_fallo == "credencial_invalida"
    assert estado.clase_ultimo_fallo is ClaseFallo.PERMANENTE
    assert estado.degradada
    assert not estado.debe_reintentar


async def test_no_llegar_a_conectar_NO_es_la_credencial() -> None:
    """Una red caída dura cero segundos igual que un rechazo de credencial. Si
    se clasificara por la duración sin distinguir, un corte de red apagaría la
    fuente para siempre — el error caro que `US-03` advierte."""
    estado = EstadoFuente(nombre="aisstream")

    async def abrir():
        raise OSError("La red no responde")

    colector = ColectorAIS(
        api_key="k",
        cajas=CARIBE,
        abrir=abrir,
        estado=estado,
        dormir=_sin_dormir,
        reloj=RelojFalso([0.0, 0.0]),
    )
    await colector.ejecutar(_nada, ciclos=1)

    assert estado.motivo_ultimo_fallo == "conexion_rechazada"
    assert estado.clase_ultimo_fallo is ClaseFallo.TRANSITORIO
    assert estado.debe_reintentar


async def _sin_dormir(segundos: float) -> None:
    return None


async def _nada(lectura: object) -> None:
    return None


# --- Principio 3: transitorio con la espera de `US-03` --------------------


async def test_una_caida_despues_de_recibir_es_transitoria_y_reconecta() -> None:
    estado = EstadoFuente(nombre="aisstream")
    conexiones = [
        ConexionFalsa([_crudo()], al_terminar=ConnectionResetError("se cayó")),
        ConexionFalsa([_crudo(instante="2026-08-18 21:00:00.0 +0000 UTC")]),
    ]
    dormidas: list[float] = []
    recibidas = await _recolectar(
        _colector(conexiones, estado=estado, marcas=[0.0, 600.0, 600.0, 1200.0], dormidas=dormidas),
        ciclos=2,
    )

    assert len(recibidas) == 2  # reconectó y siguió consumiendo
    assert conexiones[0].abortada and conexiones[1].abortada
    assert len(dormidas) == 1  # esperó una vez, antes del segundo intento


async def test_la_espera_sale_de_la_politica_y_no_del_colector() -> None:
    """El criterio viejo pedía backoff propio de 1 s con techo de 60 s. Ahora la
    espera la manda `US-03`, que la lee de `parametros_sistema` (RF-24)."""
    estado = EstadoFuente(
        nombre="aisstream",
        politica=PoliticaReintento(espera_inicial_s=7, factor=3, ruido=0, intentos_maximos=9),
    )
    conexiones = [
        ConexionFalsa([], al_terminar=ConnectionResetError("corte")),
        ConexionFalsa([], al_terminar=ConnectionResetError("otro corte")),
        ConexionFalsa([]),
    ]
    dormidas: list[float] = []
    await _recolectar(
        _colector(
            conexiones,
            estado=estado,
            marcas=[0.0, 600.0] * 3,
            dormidas=dormidas,
        ),
        ciclos=3,
    )

    assert dormidas == [7.0, 21.0]


async def test_agotados_los_intentos_el_colector_se_detiene() -> None:
    """Nunca un bucle cerrado, que es el tercer principio de `US-03`."""
    estado = EstadoFuente(
        nombre="aisstream", politica=PoliticaReintento(intentos_maximos=2, ruido=0)
    )
    conexiones = [
        ConexionFalsa([], al_terminar=ConnectionResetError("uno")),
        ConexionFalsa([], al_terminar=ConnectionResetError("dos")),
    ]
    # Se piden cinco ciclos pero solo hay dos conexiones: si intentara una
    # tercera, `abrir` levantaría AssertionError.
    await _recolectar(
        _colector(conexiones, estado=estado, marcas=[0.0, 600.0] * 2, dormidas=[]), ciclos=5
    )

    assert estado.fallos_consecutivos == 2
    assert estado.degradada


async def test_el_colector_usa_el_registro_global_por_defecto() -> None:
    """Para que `/health` vea la fuente sin que nadie la cablee a mano."""
    from app.services.salud_fuentes import registro as registro_salud

    registro_salud.olvidar_todo()
    try:
        colector = ColectorAIS(api_key="k", cajas=CARIBE, abrir=_nada)  # type: ignore[arg-type]
        assert colector.estado is registro_salud.estado("aisstream")
        assert [f["fuente"] for f in registro_salud.resumen()] == ["aisstream"]
    finally:
        registro_salud.olvidar_todo()


# --- Persistencia ----------------------------------------------------------


@pytest.fixture
async def buque(sesion) -> ElementoRastreado:
    """Un elemento rastreado activo para el MMSI de las pruebas."""
    elemento = ElementoRastreado(
        tipo_tracking_externo="MMSI", tracking_externo=MMSI, via_transporte="MARITIMO"
    )
    sesion.add(elemento)
    await sesion.flush()
    return elemento


def _posicion(**kwargs) -> aisstream.PosicionAIS:
    base = {
        "mmsi": MMSI,
        "instante": dt.datetime(2026, 8, 18, 20, 18, tzinfo=dt.UTC),
        "latitud": 11.07302,
        "longitud": -74.23296,
        "velocidad_nudos": 12.5,
        "rumbo_grados": 87.0,
        "estado_navegacion": "EN_NAVEGACION_A_MOTOR",
        "nombre": "CSL KULEANA",
        "payload": {"crudo": True},
    }
    return aisstream.PosicionAIS(**{**base, **kwargs})


@pytest.mark.integration
class TestPersistencia:
    async def test_una_posicion_de_un_buque_seguido_se_guarda(self, sesion, buque) -> None:
        resultado = await procesar_mensaje(sesion, _posicion())

        assert resultado.aplicado
        assert buque.ultima_actualizacion_api == dt.datetime(2026, 8, 18, 20, 18, tzinfo=dt.UTC)
        assert buque.velocidad_actual is not None

    async def test_un_buque_que_no_seguimos_se_descarta(self, sesion) -> None:
        """El bounding box trae todo el tráfico de la zona: lo normal es que la
        enorme mayoría de los buques no sea nuestra. No es un error."""
        resultado = await procesar_mensaje(sesion, _posicion(mmsi="999999999"))

        assert not resultado.aplicado
        assert resultado.motivo == DESCARTE_SIN_ELEMENTO

    async def test_un_buque_inactivo_no_se_sigue(self, sesion, buque) -> None:
        """`US-11` desactiva el elemento al arribar para no gastar cuota."""
        buque.activo = False
        await sesion.flush()

        resultado = await procesar_mensaje(sesion, _posicion())
        assert resultado.motivo == DESCARTE_SIN_ELEMENTO

    async def test_el_submuestreo_de_us_04_sigue_mandando(self, sesion, buque) -> None:
        """Un buque emite AIS cada pocos segundos; el intervalo lo filtra."""
        assert await procesar_mensaje(sesion, _posicion())
        segunda = _posicion(instante=dt.datetime(2026, 8, 18, 20, 18, 30, tzinfo=dt.UTC))

        resultado = await procesar_mensaje(sesion, segunda)

        assert not resultado.aplicado
        assert resultado.motivo == "submuestreo"

    async def test_un_mensaje_fuera_de_orden_no_retrocede_el_mapa(self, sesion, buque) -> None:
        """`posicion_actual` es la copia que lee el dashboard: solo avanza."""
        await procesar_mensaje(sesion, _posicion())
        vigente = buque.ultima_actualizacion_api

        # Una hora antes, lo bastante lejos para pasar el submuestreo.
        await procesar_mensaje(
            sesion, _posicion(instante=dt.datetime(2026, 8, 18, 19, 0, tzinfo=dt.UTC))
        )

        assert buque.ultima_actualizacion_api == vigente

    async def test_un_estatico_actualiza_la_eta_sin_tocar_la_posicion(self, sesion, buque) -> None:
        await procesar_mensaje(sesion, _posicion())
        posicion_antes = buque.posicion_actual

        estatico = aisstream.EstaticoAIS(
            mmsi=MMSI,
            instante=dt.datetime(2026, 8, 18, 20, 19, tzinfo=dt.UTC),
            imo="9582348",
            nombre="CSL KULEANA",
            destino="CARTAGENA",
            eta=dt.datetime(2026, 8, 21, 22, 15, tzinfo=dt.UTC),
            payload={"crudo": True},
        )
        resultado = await procesar_mensaje(sesion, estatico)

        assert resultado.aplicado
        assert buque.eta_api == dt.datetime(2026, 8, 21, 22, 15, tzinfo=dt.UTC)
        assert buque.posicion_actual is posicion_antes

    async def test_un_estatico_sin_eta_no_aporta_nada_hoy(self, sesion, buque) -> None:
        """El modelo no tiene columna para nombre, IMO ni destino: sin ETA, el
        mensaje no tiene dónde ir. Queda anotado como deuda en el backlog."""
        estatico = aisstream.EstaticoAIS(
            mmsi=MMSI,
            instante=dt.datetime(2026, 8, 18, 20, 19, tzinfo=dt.UTC),
            imo="9582348",
            nombre="CSL KULEANA",
            destino="CARTAGENA",
            eta=None,
            payload={"crudo": True},
        )
        resultado = await procesar_mensaje(sesion, estatico)

        assert not resultado.aplicado
        assert resultado.motivo == DESCARTE_SIN_DATO_UTIL

    async def test_buscar_elemento_devuelve_none_si_no_hay(self, sesion) -> None:
        assert await buscar_elemento(sesion, "000000000") is None


async def test_la_cancelacion_se_propaga_y_no_cuenta_como_fallo() -> None:
    """Apagar el worker no es que la fuente se haya caído. Si se registrara
    como fallo, un reinicio ordenado gastaría intentos de la política."""
    import asyncio

    estado = EstadoFuente(nombre="aisstream")

    async def abrir():
        raise asyncio.CancelledError

    colector = ColectorAIS(
        api_key="k", cajas=CARIBE, abrir=abrir, estado=estado, dormir=_sin_dormir
    )

    with pytest.raises(asyncio.CancelledError):
        await colector.ejecutar(_nada, ciclos=1)

    assert estado.fallos_consecutivos == 0
    assert not estado.degradada


def test_la_fabrica_de_conexiones_reales_devuelve_un_invocable() -> None:
    """No conecta: solo comprueba que el cableado con `websockets` existe."""
    from app.services.rastreo.colector_ais import abrir_websocket

    assert callable(abrir_websocket())
