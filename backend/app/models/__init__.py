"""Modelos ORM de SQLAlchemy.

Cada modelo vive en su propio módulo y se importa acá, de modo que
`import app.models` alcance para que Alembic vea todo el metadata al hacer
`--autogenerate`.

Las once entidades de `TASK-01`, en orden de dependencia:

1. Catálogos sin dependencias: `MaestroPais`, `MaestroDestino`, `Proveedor`,
   `Material`, `Usuario`.
2. Rastreo: `ElementoRastreado` y su bitácora `HistorialTracking`.
3. Central: `PedidoTransito` y la asociativa de tramos
   `PedidoElementoRastreado`.
4. Operación: `AuditoriaIntervencion` y `ParametroSistema`.

Ver `docs/data-model.md` para la justificación de cada decisión de diseño.
"""

from app.models.auditoria_intervencion import AuditoriaIntervencion
from app.models.elemento_rastreado import ElementoRastreado
from app.models.historial_tracking import HistorialTracking
from app.models.maestro_destino import MaestroDestino
from app.models.maestro_pais import AliasPais, MaestroPais
from app.models.material import Material
from app.models.parametro_sistema import ParametroSistema
from app.models.pedido_elemento_rastreado import PedidoElementoRastreado
from app.models.pedido_transito import PedidoTransito
from app.models.proveedor import Proveedor
from app.models.usuario import Usuario

__all__ = [
    "AliasPais",
    "AuditoriaIntervencion",
    "ElementoRastreado",
    "HistorialTracking",
    "MaestroDestino",
    "MaestroPais",
    "Material",
    "ParametroSistema",
    "PedidoElementoRastreado",
    "PedidoTransito",
    "Proveedor",
    "Usuario",
]
