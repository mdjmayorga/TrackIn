"""Dominios cerrados del modelo de datos.

Fuente única de verdad para los valores admitidos en cada columna de dominio.
Los `CHECK` de los modelos se construyen a partir de estas tuplas, de modo que
agregar un valor sea un cambio en un solo lugar.

Se declaran como `VARCHAR` + `CHECK` y no como `ENUM` nativo de Postgres: un
`ENUM` exige `ALTER TYPE` para crecer, lo que en Alembic produce migraciones no
reversibles; un `CHECK` se reemplaza en un `downgrade` limpio.
Ver `docs/data-model.md` §Convenciones.
"""

from __future__ import annotations

from typing import Final


def check_in(columna: str, valores: tuple[str, ...]) -> str:
    """Devuelve la expresión SQL `columna IN (...)` para un `CheckConstraint`."""
    listado = ", ".join(f"'{v}'" for v in valores)
    return f"{columna} IN ({listado})"


# --- Vía de transporte ------------------------------------------------------
# TERRESTRE se incorpora el 03/09/2026: el Z-tracking real lo trae en las
# compras regionales (Guatemala, México). No es rastreable por ShipsGo, pero el
# dato existe y el modelo debe poder representarlo (RN-17).
VIAS_TRANSPORTE: Final[tuple[str, ...]] = ("AEREO", "MARITIMO", "TERRESTRE")

# --- Estado: dos dimensiones (data-model §1.4) ------------------------------
# RECIBIDO_EN_PLANTA se agrega el 04/09/2026: la carga llega a planta pero no
# se puede usar hasta que Control de Calidad la libere (US-47).
ETAPAS_VIAJE: Final[tuple[str, ...]] = (
    "SIN_TRACKING",
    "EN_ORIGEN",
    "EN_TRANSITO",
    "EN_DESTINO",
    "EN_PROCESO_ADUANAL",
    "RECIBIDO_EN_PLANTA",
)

ESTADOS_CUMPLIMIENTO: Final[tuple[str, ...]] = ("A_TIEMPO", "EN_RIESGO", "RETRASADO")

ESTADOS_TERMINALES: Final[tuple[str, ...]] = ("CERRADO", "CANCELADO")

# El estado único que exige RF-11 se deriva de las dos dimensiones anteriores.
ESTADOS_CALCULADOS: Final[tuple[str, ...]] = (
    *ETAPAS_VIAJE,
    *ESTADOS_CUMPLIMIENTO,
    *ESTADOS_TERMINALES,
)

MOTIVOS_CIERRE: Final[tuple[str, ...]] = (
    "RECEPCION_CONFORME",
    "CIERRE_FORZADO",
    "CANCELACION",
)

# --- Referencia de rastreo externo ------------------------------------------
# Ampliado el 04/09/2026 con los tipos del contrato de captura (TASK-30):
# lo que ShipsGo admite como clave de alta — `booking_number` y
# `container_number` en /ocean/shipments, `awb_number` en /air/shipments.
TIPOS_TRACKING: Final[tuple[str, ...]] = (
    "MMSI",
    "IMO",
    "BUQUE",
    "VUELO",
    "CONTENEDOR",
    "BL",
    "BOOKING",
    "MAWB",
)

# --- Roles (RNF-05) ---------------------------------------------------------
# ADMINISTRADOR entra el 03/09/2026: con autenticación real el rol sí restringe,
# lo que revierte la decisión B9 tomada cuando no había login.
ROLES: Final[tuple[str, ...]] = (
    "COMPRAS",
    "LOGISTICA",
    "PLANIFICACION",
    "ADMINISTRADOR",
)

# --- Auditoría (RF-14) ------------------------------------------------------
TIPOS_INTERVENCION: Final[tuple[str, ...]] = (
    "CONFIRMACION_DESEMBARCO",
    "PASO_A_ADUANAL",
    "RECEPCION_PLANTA",
    "LIBERACION_CALIDAD",
    "TRANSBORDO",
    "AJUSTE_MANUAL",
    "CIERRE_FORZADO",
    "ASOCIACION_TRACKING",
)

# --- Parámetros del sistema -------------------------------------------------
TIPOS_DATO_PARAMETRO: Final[tuple[str, ...]] = (
    "ENTERO",
    "DECIMAL",
    "BOOLEANO",
    "TEXTO",
)

# --- Campos que aporta el Z-tracking (03/09/2026) ---------------------------
TIPOS_PROVEEDOR: Final[tuple[str, ...]] = ("LOCAL", "INTERNACIONAL")


__all__ = [
    "ESTADOS_CALCULADOS",
    "ESTADOS_CUMPLIMIENTO",
    "ESTADOS_TERMINALES",
    "ETAPAS_VIAJE",
    "MOTIVOS_CIERRE",
    "ROLES",
    "TIPOS_DATO_PARAMETRO",
    "TIPOS_INTERVENCION",
    "TIPOS_PROVEEDOR",
    "TIPOS_TRACKING",
    "VIAS_TRANSPORTE",
    "check_in",
]
