"""Modelos ORM de SQLAlchemy.

Cada modelo se define en su propio módulo y se importa acá, de modo que
`import app.models` alcance para que Alembic vea todo el metadata al hacer
`--autogenerate`. Pendiente de Sprint 1-2 (modelo de datos).

Ejemplo de lo que vendrá:
    from app.models.pedido import Pedido
    from app.models.embarque import Embarque

    __all__ = ["Embarque", "Pedido"]
"""

__all__: list[str] = []
