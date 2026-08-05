# TrackIn — Backend

API REST de TrackIn, en FastAPI con SQLAlchemy 2.0 asíncrono sobre
PostgreSQL 16 + PostGIS 3.4.

> Sprint 0: solo el esqueleto. No hay modelos, endpoints de negocio ni
> integraciones con APIs externas todavía.

## Setup

Desde `backend/`:

```bash
python -m venv .venv
```

Activar — PowerShell: `.\.venv\Scripts\Activate.ps1`; bash: `source .venv/bin/activate`.

```bash
pip install -r requirements-dev.txt
```

Levantar el servidor (necesita PostgreSQL corriendo; ver el README raíz):

```bash
uvicorn app.main:app --reload
```

| URL | Qué es |
|---|---|
| <http://localhost:8000/health> | Health check |
| <http://localhost:8000/docs> | Swagger UI |
| <http://localhost:8000/redoc> | ReDoc |
| <http://localhost:8000/openapi.json> | Esquema OpenAPI |

## Configuración

Las settings se leen del entorno mediante `app/core/config.py`
(pydantic-settings), con esta precedencia de menor a mayor:

1. `backend/.env` — overrides locales opcionales, ver `.env.example`
2. `.env` de la raíz del repo — el principal, el mismo que usa docker-compose
3. variables de entorno reales — lo que inyecta docker-compose en el contenedor

Dos detalles que no son obvios:

- **`POSTGRES_HOST` cambia según dónde corre el proceso.** `localhost` si
  corrés uvicorn en tu máquina; `postgres` si corre dentro de la red de
  compose. El `docker-compose.yml` ya lo sobreescribe para el servicio backend.
- **`BACKEND_CORS_ORIGINS` se declara como string CSV**, no como lista. Ante un
  campo de tipo complejo, pydantic-settings intenta `json.loads()` sobre el
  valor del entorno *antes* de correr cualquier validador, y falla con un CSV.
  La lista ya parseada se expone en `settings.cors_origins`.

## Estructura

```
app/
├── main.py         Creación de la app, CORS, routers, lifespan
├── api/            Capa HTTP
│   ├── health.py   GET /health
│   └── router.py   Router agregador de /api/v1
├── core/
│   └── config.py   Settings
├── db/
│   ├── base.py     Base declarativa + naming convention
│   └── session.py  Engine async, sessionmaker, dependencia get_db
├── models/         Modelos ORM            (Sprint 1-2)
├── schemas/        Contratos Pydantic     (Sprint 1)
└── services/       Lógica de negocio      (Sprint 2+)
```

Los endpoints de `api/` no deben contener reglas de negocio: delegan en
`services/`.

## Comandos

| Comando | Qué hace |
|---|---|
| `pytest` | Tests con cobertura |
| `pytest -m "not integration"` | Solo lo que no necesita base de datos |
| `pytest --no-cov -q` | Rápido, sin cobertura |
| `ruff check app tests` | Lint |
| `ruff check --fix app tests` | Lint con autofix |
| `black app tests` | Formatea |
| `mypy app` | Tipos |

Los tests marcados `integration` requieren PostgreSQL levantado; sin él se
saltan solos en vez de fallar.

## Migraciones (Alembic)

Configurado con la plantilla **async**: usa el mismo driver `asyncpg` que la
app, así que no hace falta instalar `psycopg2`.

```bash
alembic revision --autogenerate -m "descripcion del cambio"
```

```bash
alembic upgrade head
```

```bash
alembic downgrade -1
```

Notas:

- La URL de conexión **no** está en `alembic.ini`: `alembic/env.py` la inyecta
  desde `app.core.config` para no versionar credenciales.
- Todo modelo nuevo debe importarse en `app/models/__init__.py` o el
  `--autogenerate` no lo va a ver.
- Las tablas de sistema de PostGIS (`spatial_ref_sys`, `geometry_columns`,
  `geography_columns`) están excluidas del autogenerate; si no, Alembic propone
  borrarlas en cada migración.
- **Siempre revisar la migración generada antes de aplicarla.** El autogenerate
  acierta con las tablas y columnas, pero no con renombres ni con cambios de
  tipo que requieran conversión de datos.

## Notas de configuración

- `TCH` (flake8-type-checking) está **desactivado** en `pyproject.toml` a
  propósito: movería imports como `AsyncSession` a bloques `if TYPE_CHECKING`,
  y FastAPI resuelve las anotaciones en runtime para armar la inyección de
  dependencias. Con esa regla aplicada, `Depends(get_db)` deja de funcionar.
- `/health` responde 200 aunque la base esté caída, reportando
  `status: "degraded"`. Es intencional: distingue "el proceso murió" de "la
  base no responde". Con Postgres caído la respuesta tarda ~3 s, que es el
  timeout de conexión de asyncpg.
