"""Lectura de los umbrales ajustables — RF-24 / RNF-07 / RNF-15.

`parametros_sistema` existe para que los umbrales se cambien **sin desplegar
código**. Este módulo es el único que los lee, y lo hace con una regla que vale
la pena hacer explícita: **cada parámetro declara su valor por defecto acá**, en
`CATALOGO`, y la fila de la base solo lo sobreescribe.

La consecuencia es que el sistema arranca y funciona con la tabla vacía. Importa
por dos motivos: la migración no tiene que sembrar nada para que el código sea
correcto, y un parámetro nuevo no rompe un despliegue viejo. La fila se siembra
igual —es lo que hace que el valor sea *descubrible* para quien administra—, pero
el código no depende de que exista.

Los valores por defecto que salen de una decisión documentada la citan. Los que
son provisionales lo dicen, porque hay varios esperando respuesta de Logística.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parametro_sistema import ParametroSistema

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Parametro:
    """Definición de un umbral: su valor por defecto y qué significa."""

    clave: str
    defecto: Any
    tipo_dato: str
    descripcion: str


#: Todos los parámetros que el sistema conoce. Ampliar acá y sembrar en una
#: migración; nunca leer una clave que no esté declarada.
CATALOGO: Final[dict[str, Parametro]] = {
    "intervalo_minimo_persistencia_s": Parametro(
        clave="intervalo_minimo_persistencia_s",
        defecto=300,
        tipo_dato="ENTERO",
        descripcion=(
            "Segundos mínimos entre dos posiciones guardadas del mismo elemento. "
            "Decisión del 25/08/2026: el crecimiento del historial se ataca con "
            "este parámetro desde el Sprint 3, no subiendo TASK-10 de prioridad."
        ),
    ),
    "radio_geocerca_km": Parametro(
        clave="radio_geocerca_km",
        defecto=50,
        tipo_dato="ENTERO",
        descripcion=(
            "Radio por defecto de la geocerca de arribo (RN-05). Lo sobreescribe "
            "maestro_destinos.radio_geocerca_km cuando el destino define el suyo."
        ),
    ),
    "umbral_riesgo_dias": Parametro(
        clave="umbral_riesgo_dias",
        defecto=2,
        tipo_dato="ENTERO",
        descripcion=(
            "Días de margen por debajo de los cuales un pedido pasa a EN_RIESGO "
            "(RN-07/RN-08). Son días y no horas porque ambas fechas son DATE."
        ),
    ),
    "ventana_calidad_habiles_min": Parametro(
        clave="ventana_calidad_habiles_min",
        defecto=7,
        tipo_dato="ENTERO",
        descripcion=(
            "Días hábiles mínimos de la liberación de Control de Calidad (RN-19, "
            "reunión con Planeación del 04/09/2026)."
        ),
    ),
    "ventana_calidad_habiles_max": Parametro(
        clave="ventana_calidad_habiles_max",
        defecto=15,
        tipo_dato="ENTERO",
        descripcion="Días hábiles máximos de la liberación de Calidad (RN-19).",
    ),
    "velocidad_minima_eta_nudos": Parametro(
        clave="velocidad_minima_eta_nudos",
        defecto=Decimal("1.0"),
        tipo_dato="DECIMAL",
        descripcion=(
            "Por debajo de esta velocidad no se estima ETA y el pedido se marca "
            "«ETA no estimable» (RN-16). **Provisional**: pendiente de Logística."
        ),
    ),
    "velocidad_maxima_arribo_nudos": Parametro(
        clave="velocidad_maxima_arribo_nudos",
        defecto=Decimal("3.0"),
        tipo_dato="DECIMAL",
        descripcion=(
            "Por encima de esta velocidad una nave dentro de la geocerca NO se da "
            "por arribada: va de paso (RN-05). **Provisional**: pendiente de "
            "Logística."
        ),
    ),
    # --- Planificación de las consultas (`US-07`, RF-08) --------------------
    # El primer criterio de la historia exige que la frecuencia se cambie **sin
    # reiniciar el servicio**, así que el planificador relee estos valores en
    # cada tic en vez de capturarlos al arrancar.
    "frecuencia_aerea_min": Parametro(
        clave="frecuencia_aerea_min",
        defecto=60,
        tipo_dato="ENTERO",
        descripcion=(
            "Minutos entre consultas de un envío aéreo, dentro de la ventana "
            "activa. **Provisional**: el valor bueno depende del ritmo al que "
            "ShipsGo Air refresca los hitos CIMP, que no se ha medido."
        ),
    ),
    "frecuencia_maritima_min": Parametro(
        clave="frecuencia_maritima_min",
        defecto=360,
        tipo_dato="ENTERO",
        descripcion=(
            "Minutos entre consultas de un envío marítimo. Seis horas por "
            "defecto: un buque tarda semanas y los hitos son escasos. Consultar "
            "**no cuesta crédito** (el crédito se gasta en el alta), así que el "
            "límite real es el de tasa, no el presupuesto."
        ),
    ),
    "ventana_aerea_inicio_h": Parametro(
        clave="ventana_aerea_inicio_h",
        defecto=6,
        tipo_dato="ENTERO",
        descripcion=(
            "Hora local a la que arranca la ventana activa del sondeo aéreo "
            "(segundo criterio de `US-07`). Fuera de la ventana se suspende."
        ),
    ),
    "ventana_aerea_fin_h": Parametro(
        clave="ventana_aerea_fin_h",
        defecto=22,
        tipo_dato="ENTERO",
        descripcion="Hora local a la que termina la ventana activa del sondeo aéreo.",
    ),
    "maduracion_reintento_s": Parametro(
        clave="maduracion_reintento_s",
        defecto=120,
        tipo_dato="ENTERO",
        descripcion=(
            "Segundos antes de reconsultar un embarque **dado de alta pero sin "
            "datos todavía**. `TASK-28` midió que a los 45 s devolvía `NEW` y a "
            "los ~90 s estaba completo; 120 s da margen sin desperdiciar el tic."
        ),
    ),
    "altas_maximas_dia": Parametro(
        clave="altas_maximas_dia",
        defecto=5,
        tipo_dato="ENTERO",
        descripcion=(
            "Altas diarias por encima de las cuales el planificador avisa. Es "
            "**lo que cuesta dinero**: a 2 USD el crédito, cinco en un día son "
            "el 10 % de los 50 créditos comprados el 23/09/2026. Bajó de 20, "
            "que era una intuición de cuando no había presupuesto contra el "
            "cual medirla (migración `0011`)."
        ),
    ),
    # --- Resiliencia de las fuentes externas (`US-03`, RF-09 / RNF-12) ------
    # Los cinco describen la misma política de espera creciente, y son
    # parámetros y no constantes por el sexto criterio de la historia: los
    # umbrales tienen que poder ajustarse sin desplegar código. Importa más
    # acá que en otros lados, porque el valor bueno de cada uno depende del
    # proveedor que termine contratándose y hoy no se conoce (`TASK-28`).
    "resiliencia_espera_inicial_s": Parametro(
        clave="resiliencia_espera_inicial_s",
        defecto=5,
        tipo_dato="ENTERO",
        descripcion=(
            "Segundos de espera antes del primer reintento a una fuente externa "
            "que falló de forma transitoria (RF-09)."
        ),
    ),
    "resiliencia_factor_espera": Parametro(
        clave="resiliencia_factor_espera",
        defecto=Decimal("2.0"),
        tipo_dato="DECIMAL",
        descripcion=(
            "Factor por el que se multiplica la espera en cada reintento "
            "consecutivo. Con 2.0 la secuencia es 5, 10, 20, 40 s."
        ),
    ),
    "resiliencia_espera_maxima_s": Parametro(
        clave="resiliencia_espera_maxima_s",
        defecto=300,
        tipo_dato="ENTERO",
        descripcion=(
            "Tope de la espera creciente. Sin él, una caída larga deja el "
            "siguiente reintento a horas de distancia."
        ),
    ),
    "resiliencia_intentos_maximos": Parametro(
        clave="resiliencia_intentos_maximos",
        defecto=5,
        tipo_dato="ENTERO",
        descripcion=(
            "Fallos transitorios seguidos tras los cuales la fuente se marca "
            "degradada y se deja de reintentar. Es lo que impide el bucle cerrado."
        ),
    ),
    "resiliencia_ruido_espera": Parametro(
        clave="resiliencia_ruido_espera",
        defecto=Decimal("0.2"),
        tipo_dato="DECIMAL",
        descripcion=(
            "Fracción de la espera que se reparte al azar, para que los elementos "
            "rastreados no reintenten todos en el mismo instante tras una caída "
            "general. En 0 el reintento es determinista."
        ),
    ),
}


def _convertir(bruto: str, tipo_dato: str, clave: str) -> Any:
    """Pasa el texto de la columna al tipo declarado.

    Un valor mal escrito **no tumba nada**: se registra y se usa el defecto. Es
    la misma lógica que el registro de fuentes: una errata en una fila de
    configuración no debe dejar el sistema sin arrancar.
    """
    try:
        if tipo_dato == "ENTERO":
            return int(bruto)
        if tipo_dato == "DECIMAL":
            return Decimal(bruto)
        if tipo_dato == "BOOLEANO":
            return bruto.strip().lower() in {"true", "t", "1", "si", "sí"}
        return bruto
    except (ValueError, InvalidOperation):
        logger.warning(
            "Parámetro %r: %r no es un %s válido; se usa el valor por defecto.",
            clave,
            bruto,
            tipo_dato,
        )
        return CATALOGO[clave].defecto


async def obtener(sesion: AsyncSession, clave: str) -> Any:
    """Valor vigente del parámetro: el de la base, o el defecto del catálogo."""
    if clave not in CATALOGO:
        raise KeyError(
            f"Parámetro {clave!r} no declarado en CATALOGO. "
            f"Declarados: {', '.join(sorted(CATALOGO))}."
        )
    definicion = CATALOGO[clave]

    fila = await sesion.scalar(select(ParametroSistema).where(ParametroSistema.clave == clave))
    if fila is None:
        logger.debug("Parámetro %r sin fila; se usa el defecto.", clave)
        return definicion.defecto
    return _convertir(fila.valor, definicion.tipo_dato, clave)


async def obtener_entero(sesion: AsyncSession, clave: str) -> int:
    """`obtener` con el tipo estrechado, para quien necesita un `int`."""
    return int(await obtener(sesion, clave))


async def obtener_decimal(sesion: AsyncSession, clave: str) -> Decimal:
    return Decimal(await obtener(sesion, clave))


__all__ = [
    "CATALOGO",
    "Parametro",
    "obtener",
    "obtener_decimal",
    "obtener_entero",
]
