"""Pruebas del parseo de AISStream — RF-06 (`US-02`).

Ninguna toca la red: el módulo es puro. Y no es una comodidad de diseño, es la
única forma de probarlo hoy — el riesgo **R1** deja la cuenta sin entregar datos
desde el 19/08/2026, así que una prueba contra el socket real no correría.

Buena parte de estas pruebas se corre contra los **161 mensajes reales** que el
spike capturó el 18/08. Los casos sintéticos existen solo para lo que la captura
no contiene: la velocidad centinela y los mensajes deformes.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib

import pytest

from app.services.rastreo import aisstream
from app.services.rastreo.aisstream import (
    EstaticoAIS,
    MensajeIlegible,
    PosicionAIS,
    clasificar_cierre,
    parsear,
    parsear_instante,
    resolver_eta,
    suscripcion,
)

CAPTURA = (
    pathlib.Path(__file__).resolve().parents[1]
    / "scripts"
    / "spikes"
    / "aisstream"
    / "output"
    / "02_caribbean_raw_personal.jsonl"
)

CARIBE = [[[9.0, -84.0], [16.0, -59.0]]]


def _mensajes() -> list[dict]:
    """Los 161 mensajes crudos de la captura del 18/08/2026."""
    return [
        json.loads(linea)
        for linea in CAPTURA.read_text(encoding="utf-8").splitlines()
        if linea.strip()
    ]


@pytest.fixture(scope="module")
def captura() -> list[dict]:
    if not CAPTURA.exists():  # pragma: no cover - la evidencia está versionada
        pytest.skip(f"Falta la captura del spike: {CAPTURA}")
    return _mensajes()


# --- El instante viene en formato Go, no ISO -------------------------------


def test_fromisoformat_no_sirve_para_este_formato() -> None:
    """Deja constancia de por qué hay un parser propio: espacio en vez de `T`,
    sufijo `UTC` textual y nueve dígitos de fracción."""
    with pytest.raises(ValueError):
        dt.datetime.fromisoformat("2026-08-18 20:18:15.331999764 +0000 UTC")


def test_el_instante_se_parsea_con_nanosegundos() -> None:
    instante = parsear_instante("2026-08-18 20:18:15.331999764 +0000 UTC")
    assert instante == dt.datetime(2026, 8, 18, 20, 18, 15, 331999, tzinfo=dt.UTC)


def test_la_fraccion_se_trunca_y_no_se_redondea() -> None:
    """Son nanosegundos de una marca de recepción: redondear hacia arriba podría
    empujar la lectura al segundo siguiente sin ganar nada."""
    assert parsear_instante("2026-08-18 20:18:15.999999999 +0000 UTC").microsecond == 999999


@pytest.mark.parametrize(
    "bruto",
    [
        "2026-08-18 20:18:15.331999764 +0000 UTC",  # 9 dígitos
        "2026-08-18 20:18:15.33199976 +0000 UTC",  # 8 dígitos
        "2026-08-18 20:18:15.331999 +0000 UTC",  # 6 dígitos
        "2026-08-18 20:18:15 +0000 UTC",  # sin fracción
        "2026-08-18T20:18:15Z",  # ISO, por si algún día cambia
    ],
)
def test_las_variantes_de_fraccion_de_la_captura_se_parsean(bruto: str) -> None:
    """La captura trae 9, 8 y 6 dígitos: los tres largos existen de verdad."""
    assert parsear_instante(bruto).tzinfo is not None


def test_un_instante_ilegible_se_rechaza() -> None:
    with pytest.raises(MensajeIlegible, match="formato"):
        parsear_instante("ayer por la tarde")


def test_todos_los_instantes_de_la_captura_se_parsean(captura: list[dict]) -> None:
    for mensaje in captura:
        assert parsear_instante(mensaje["MetaData"]["time_utc"]).tzinfo is not None


# --- Los centinelas de AIS no son datos ------------------------------------


def test_el_rumbo_centinela_no_se_guarda(captura: list[dict]) -> None:
    """`TrueHeading = 511` aparece en 44 de las 115 posiciones de la captura."""
    for mensaje in captura:
        lectura = parsear(mensaje)
        if isinstance(lectura, PosicionAIS):
            assert lectura.rumbo_grados != 511


def test_el_curso_centinela_violaria_el_check_de_la_base(captura: list[dict]) -> None:
    """`Cog = 360` está en 11 mensajes y `historial_tracking` exige `rumbo < 360`:
    guardarlo no daría un dato falso, daría un `IntegrityError`."""
    con_centinela = [
        m
        for m in captura
        if (m["Message"].get(m["MessageType"]) or {}).get("Cog") == aisstream.CENTINELA_CURSO
    ]
    assert con_centinela, "La captura debería traer mensajes con Cog=360"

    for mensaje in con_centinela:
        lectura = parsear(mensaje)
        assert isinstance(lectura, PosicionAIS)
        assert lectura.rumbo_grados is None or lectura.rumbo_grados < 360


def test_ningun_rumbo_de_la_captura_rompe_el_check(captura: list[dict]) -> None:
    for mensaje in captura:
        lectura = parsear(mensaje)
        if isinstance(lectura, PosicionAIS) and lectura.rumbo_grados is not None:
            assert 0 <= lectura.rumbo_grados < 360


def test_la_velocidad_centinela_no_se_guarda() -> None:
    """102.3 nudos son las 1023 décimas de «no disponible». La captura no trae
    ninguno, así que este caso es sintético a propósito."""
    mensaje = {
        "MessageType": "PositionReport",
        "MetaData": {"MMSI": 311001711, "time_utc": "2026-08-18 20:18:16.3 +0000 UTC"},
        "Message": {
            "PositionReport": {
                "Latitude": 11.0,
                "Longitude": -74.0,
                "Sog": aisstream.CENTINELA_VELOCIDAD,
                "Cog": 90.0,
                "Valid": True,
            }
        },
    }
    lectura = parsear(mensaje)
    assert isinstance(lectura, PosicionAIS)
    assert lectura.velocidad_nudos is None
    assert lectura.rumbo_grados == 90.0


def test_el_rumbo_cae_al_heading_cuando_el_curso_no_esta() -> None:
    mensaje = {
        "MessageType": "PositionReport",
        "MetaData": {"MMSI": 311001711, "time_utc": "2026-08-18 20:18:16.3 +0000 UTC"},
        "Message": {
            "PositionReport": {
                "Latitude": 11.0,
                "Longitude": -74.0,
                "Cog": aisstream.CENTINELA_CURSO,
                "TrueHeading": 275,
                "Valid": True,
            }
        },
    }
    lectura = parsear(mensaje)
    assert isinstance(lectura, PosicionAIS)
    assert lectura.rumbo_grados == 275.0


# --- Los cuatro tipos que interesan ----------------------------------------


def test_la_captura_trae_los_cuatro_tipos_utiles(captura: list[dict]) -> None:
    """El criterio original nombraba dos de los cuatro y dejaba fuera 59 de 161."""
    tipos = {m["MessageType"] for m in captura}
    assert aisstream.TIPOS_CON_POSICION.issubset(tipos)
    assert aisstream.TIPOS_ESTATICOS.issubset(tipos)


def test_class_b_se_parsea_igual_que_class_a(captura: list[dict]) -> None:
    """No se filtra por tipo: se persiste lo que corresponde a un elemento
    activo, y Class B no coincide por sí solo."""
    clase_b = [m for m in captura if m["MessageType"] == "StandardClassBPositionReport"]
    assert len(clase_b) == 39
    for mensaje in clase_b:
        assert isinstance(parsear(mensaje), PosicionAIS)


def test_los_estaticos_no_traen_posicion(captura: list[dict]) -> None:
    """Son 39, y su posición solo está en `MetaData` —con el `UnknownMessage`
    son los 40 mensajes de la captura sin coordenadas en el cuerpo—. El objeto
    estático ni siquiera expone coordenadas: no debe poder mover el mapa."""
    estaticos = [m for m in captura if m["MessageType"] in aisstream.TIPOS_ESTATICOS]
    assert len(estaticos) == 39
    for mensaje in estaticos:
        lectura = parsear(mensaje)
        assert isinstance(lectura, EstaticoAIS)
        assert not hasattr(lectura, "latitud")


def test_los_tipos_que_no_interesan_devuelven_none(captura: list[dict]) -> None:
    """Estación base, ayudas a la navegación y lo no decodificado: 7 de 161.
    `None` no es un error, es tráfico legítimo que no nos sirve."""
    ignorados = [
        m
        for m in captura
        if m["MessageType"] not in aisstream.TIPOS_CON_POSICION | aisstream.TIPOS_ESTATICOS
    ]
    assert len(ignorados) == 7
    for mensaje in ignorados:
        assert parsear(mensaje) is None


def test_la_captura_entera_se_procesa_sin_excepciones(captura: list[dict]) -> None:
    """La prueba de integración del parser: 161 mensajes reales, ninguno rompe."""
    posiciones = estaticos = ignorados = 0
    for mensaje in captura:
        lectura = parsear(mensaje)
        if isinstance(lectura, PosicionAIS):
            posiciones += 1
        elif isinstance(lectura, EstaticoAIS):
            estaticos += 1
        else:
            ignorados += 1

    assert posiciones == 115
    assert estaticos == 39
    assert ignorados == 7
    assert posiciones + estaticos + ignorados == 161


def test_el_payload_crudo_se_conserva_entero(captura: list[dict]) -> None:
    """RNF-13: sin el crudo no se puede auditar ni reprocesar."""
    mensaje = next(m for m in captura if m["MessageType"] == "PositionReport")
    lectura = parsear(mensaje)
    assert isinstance(lectura, PosicionAIS)
    assert lectura.payload == mensaje


def test_el_mmsi_va_como_texto(captura: list[dict]) -> None:
    """`elementos_rastreados.tracking_externo` es `VARCHAR(50)`."""
    lectura = parsear(next(m for m in captura if m["MessageType"] == "PositionReport"))
    assert isinstance(lectura, PosicionAIS)
    assert isinstance(lectura.mmsi, str)
    assert lectura.mmsi.isdigit()


def test_el_estado_de_navegacion_se_guarda_como_texto(captura: list[dict]) -> None:
    """Un `5` no le dice nada a quien audita; `AMARRADO` sí."""
    estados = {
        lectura.estado_navegacion
        for m in captura
        if isinstance(lectura := parsear(m), PosicionAIS) and lectura.estado_navegacion
    }
    assert "EN_NAVEGACION_A_MOTOR" in estados
    assert "AMARRADO" in estados


def test_los_nombres_vienen_rellenos_y_se_recortan(captura: list[dict]) -> None:
    """`'MARISOL             '` y `'MARISOL'` son el mismo buque."""
    con_relleno = [
        m
        for m in captura
        if m["MessageType"] == "ShipStaticData"
        and (m["Message"]["ShipStaticData"].get("Name") or "").endswith(" ")
    ]
    assert con_relleno, "La captura debería traer nombres rellenos a ancho fijo"
    for mensaje in con_relleno:
        lectura = parsear(mensaje)
        assert isinstance(lectura, EstaticoAIS)
        assert lectura.nombre == lectura.nombre.strip()


def test_el_imo_se_extrae_de_los_estaticos_completos(captura: list[dict]) -> None:
    lecturas = [
        lectura
        for m in captura
        if m["MessageType"] == "ShipStaticData" and isinstance(lectura := parsear(m), EstaticoAIS)
    ]
    assert any(lectura.imo for lectura in lecturas)


# --- La ETA de AIS no lleva año -------------------------------------------


def test_la_eta_sin_declarar_es_none() -> None:
    """Once de diecinueve la traen en ceros. Guardarla sería inventar un dato."""
    assert (
        resolver_eta(
            {"Day": 0, "Hour": 0, "Minute": 0, "Month": 0}, referencia=dt.datetime.now(dt.UTC)
        )
        is None
    )


def test_la_eta_declarada_toma_el_ano_mas_cercano() -> None:
    """La captura trae una ETA del 18/08 14:20 en un mensaje del 18/08 20:18:
    ya vencida por seis horas. «La próxima ocurrencia» la habría mandado a 2027."""
    referencia = dt.datetime(2026, 8, 18, 20, 18, tzinfo=dt.UTC)
    eta = resolver_eta({"Month": 8, "Day": 18, "Hour": 14, "Minute": 20}, referencia=referencia)
    assert eta == dt.datetime(2026, 8, 18, 14, 20, tzinfo=dt.UTC)


def test_la_eta_de_enero_vista_en_diciembre_cae_en_el_ano_siguiente() -> None:
    referencia = dt.datetime(2026, 12, 28, tzinfo=dt.UTC)
    eta = resolver_eta({"Month": 1, "Day": 4, "Hour": 6, "Minute": 0}, referencia=referencia)
    assert eta == dt.datetime(2027, 1, 4, 6, 0, tzinfo=dt.UTC)


def test_la_eta_de_diciembre_vista_en_enero_cae_en_el_ano_anterior() -> None:
    referencia = dt.datetime(2026, 1, 3, tzinfo=dt.UTC)
    eta = resolver_eta({"Month": 12, "Day": 28, "Hour": 6, "Minute": 0}, referencia=referencia)
    assert eta == dt.datetime(2025, 12, 28, 6, 0, tzinfo=dt.UTC)


@pytest.mark.parametrize(
    "eta",
    [
        {"Month": 13, "Day": 1, "Hour": 0, "Minute": 0},  # mes imposible
        {"Month": 1, "Day": 0, "Hour": 0, "Minute": 0},  # día no disponible
        {"Month": 1, "Day": 1, "Hour": 24, "Minute": 0},  # hora no disponible
        {"Month": 1, "Day": 1, "Hour": 0, "Minute": 60},  # minuto no disponible
        None,
        "mañana",
    ],
)
def test_las_etas_invalidas_o_centinela_son_none(eta) -> None:
    assert resolver_eta(eta, referencia=dt.datetime(2026, 8, 18, tzinfo=dt.UTC)) is None


def test_el_29_de_febrero_no_revienta() -> None:
    """Dos de los tres años candidatos no lo tienen."""
    referencia = dt.datetime(2024, 2, 20, tzinfo=dt.UTC)
    assert resolver_eta(
        {"Month": 2, "Day": 29, "Hour": 12, "Minute": 0}, referencia=referencia
    ) == (dt.datetime(2024, 2, 29, 12, 0, tzinfo=dt.UTC))


def test_las_etas_de_la_captura_se_resuelven_o_se_descartan(captura: list[dict]) -> None:
    declaradas = [
        lectura.eta
        for m in captura
        if m["MessageType"] == "ShipStaticData" and isinstance(lectura := parsear(m), EstaticoAIS)
    ]
    assert sum(eta is not None for eta in declaradas) == 7
    assert sum(eta is None for eta in declaradas) == 12


# --- Mensajes deformes -----------------------------------------------------


@pytest.mark.parametrize(
    ("mensaje", "error"),
    [
        ({}, "MessageType"),
        ({"MessageType": "PositionReport"}, "MetaData"),
        ({"MessageType": "PositionReport", "Message": {}, "MetaData": {}}, "cuerpo"),
        (
            {
                "MessageType": "PositionReport",
                "Message": {"PositionReport": {"Latitude": 1, "Longitude": 1}},
                "MetaData": {},
            },
            "MMSI",
        ),
        (
            {
                "MessageType": "PositionReport",
                "Message": {"PositionReport": {"Latitude": 1, "Longitude": 1}},
                "MetaData": {"MMSI": 123456789},
            },
            "time_utc",
        ),
    ],
)
def test_un_mensaje_deforme_se_rechaza_con_motivo(mensaje: dict, error: str) -> None:
    """Se rechaza el mensaje, no la suscripción: el bucle lo registra y sigue."""
    with pytest.raises(MensajeIlegible, match=error):
        parsear(mensaje)


def test_un_mensaje_marcado_invalido_se_descarta() -> None:
    """AISStream marca así lo que decodificó a medias. Meterlo en la bitácora
    sería ensuciar justo lo que existe para auditar."""
    mensaje = {
        "MessageType": "PositionReport",
        "MetaData": {"MMSI": 311001711, "time_utc": "2026-08-18 20:18:16.3 +0000 UTC"},
        "Message": {"PositionReport": {"Latitude": 11.0, "Longitude": -74.0, "Valid": False}},
    }
    assert parsear(mensaje) is None


def test_una_posicion_fuera_de_rango_se_rechaza() -> None:
    mensaje = {
        "MessageType": "PositionReport",
        "MetaData": {"MMSI": 311001711, "time_utc": "2026-08-18 20:18:16.3 +0000 UTC"},
        "Message": {"PositionReport": {"Latitude": 91.0, "Longitude": 200.0, "Valid": True}},
    }
    with pytest.raises(MensajeIlegible, match="coordenadas"):
        parsear(mensaje)


# --- La suscripción se valida antes de mandarse ---------------------------


def test_la_suscripcion_lleva_clave_y_cajas() -> None:
    peticion = suscripcion("clave-de-prueba", cajas=CARIBE)
    assert peticion == {"APIKey": "clave-de-prueba", "BoundingBoxes": CARIBE}


def test_la_suscripcion_admite_filtro_por_mmsi() -> None:
    peticion = suscripcion("clave", cajas=CARIBE, mmsis=[311001711])
    assert peticion["FiltersShipMMSI"] == ["311001711"]


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"api_key": "", "cajas": CARIBE}, "API key"),
        ({"api_key": "   ", "cajas": CARIBE}, "API key"),
        ({"api_key": "k", "cajas": []}, "bounding box"),
        ({"api_key": "k", "cajas": [[[9.0, -84.0]]]}, "dos esquinas"),
        ({"api_key": "k", "cajas": [[[999.0, -84.0], [16.0, -59.0]]]}, "fuera de rango"),
    ],
)
def test_una_suscripcion_invalida_falla_antes_de_gastar_la_conexion(kwargs, error: str) -> None:
    """El spike midió que una suscripción malformada y una credencial inválida
    producen el **mismo** cierre. Validando acá, un cierre inmediato solo puede
    ser la credencial, y `clasificar_cierre` puede afirmarlo."""
    with pytest.raises(ValueError, match=error):
        suscripcion(**kwargs)


# --- Clasificación del cierre ---------------------------------------------


def test_un_cierre_inmediato_es_la_credencial() -> None:
    """El spike lo midió en 747 ms. No hay código ni motivo en el cierre: lo
    único que lo distingue es cuándo ocurre."""
    assert clasificar_cierre(segundos_conectado=0.75) == "credencial_invalida"


def test_un_cierre_despues_de_recibir_es_transitorio() -> None:
    assert clasificar_cierre(segundos_conectado=600.0) == "conexion_perdida"


def test_el_motivo_de_credencial_esta_en_el_vocabulario_permanente() -> None:
    """Si el motivo no fuera uno de los que `US-03` conoce, se reintentaría en
    bucle contra una credencial que no va a mejorar."""
    from app.services.resiliencia import MOTIVOS_PERMANENTES, ClaseFallo, clasificar

    assert clasificar_cierre(segundos_conectado=0.5) in MOTIVOS_PERMANENTES
    assert clasificar(clasificar_cierre(segundos_conectado=0.5)) is ClaseFallo.PERMANENTE
    assert clasificar(clasificar_cierre(segundos_conectado=99.0)) is ClaseFallo.TRANSITORIO


# --- Ramas defensivas ------------------------------------------------------


def test_una_velocidad_negativa_se_descarta() -> None:
    """AIS no transmite velocidades negativas; si aparece una, el decodificador
    se equivocó y `velocidad >= 0` del `CHECK` la rechazaría igual."""
    mensaje = {
        "MessageType": "PositionReport",
        "MetaData": {"MMSI": 311001711, "time_utc": "2026-08-18 20:18:16.3 +0000 UTC"},
        "Message": {
            "PositionReport": {"Latitude": 11.0, "Longitude": -74.0, "Sog": -3.0, "Valid": True}
        },
    }
    lectura = parsear(mensaje)
    assert isinstance(lectura, PosicionAIS)
    assert lectura.velocidad_nudos is None


def test_una_eta_con_campos_no_numericos_se_descarta() -> None:
    assert (
        resolver_eta(
            {"Month": 8, "Day": 18, "Hour": "catorce", "Minute": 20},
            referencia=dt.datetime(2026, 8, 18, tzinfo=dt.UTC),
        )
        is None
    )


def test_el_29_de_febrero_sin_ningun_ano_bisiesto_candidato_es_none() -> None:
    """2025, 2026 y 2027 no son bisiestos: los tres candidatos son imposibles y
    la ETA se descarta en vez de inventar una fecha cercana."""
    referencia = dt.datetime(2026, 6, 1, tzinfo=dt.UTC)
    assert (
        resolver_eta({"Month": 2, "Day": 29, "Hour": 12, "Minute": 0}, referencia=referencia)
        is None
    )


def test_el_mmsi_tambien_se_lee_cuando_viene_como_texto() -> None:
    """`MMSI_String` llega como número en la captura, pero el nombre del campo
    anuncia que podría no hacerlo."""
    mensaje = {
        "MessageType": "PositionReport",
        "MetaData": {"MMSI_String": " 311001711 ", "time_utc": "2026-08-18 20:18:16.3 +0000 UTC"},
        "Message": {"PositionReport": {"Latitude": 11.0, "Longitude": -74.0, "Valid": True}},
    }
    lectura = parsear(mensaje)
    assert isinstance(lectura, PosicionAIS)
    assert lectura.mmsi == "311001711"
