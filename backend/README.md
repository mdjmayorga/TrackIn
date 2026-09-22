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
    ├── resiliencia.py     Política de reintento, agnóstica del transporte
    ├── salud_fuentes.py   Estado por fuente + umbrales de parametros_sistema
    └── rastreo/           Fuentes externas, una por proveedor
        ├── aisstream.py     Parseo de AIS (puro, sin red)
        └── colector_ais.py  Suscripción WebSocket + persistencia
```

Los endpoints de `api/` no deben contener reglas de negocio: delegan en
`services/`.

## Comandos

| Comando | Qué hace |
|---|---|
| `python scripts/cargar_semilla.py` | Carga en la base los pedidos de la fuente configurada |
| `python scripts/cargar_semilla.py --resumen` | Muestra qué hay en la base, sin escribir |
| `python scripts/cargar_semilla.py --limpiar` | Deja la base en un estado conocido y recarga |
| `python scripts/cargar_semilla.py --sin-ausentes` | Carga sin marcar como ausente lo que no venga (carga parcial) |

La fuente sale de `INGESTA_ADAPTADOR`. Para cargar el archivo real de Logística
(`US-31`), en `backend/.env`:

```
INGESTA_ADAPTADOR=ztracking
ZTRACKING_RUTA=../docs/analisis/2026-Agosto-WK36.xlsx
```

Una errata en `INGESTA_ADAPTADOR`, o `ztracking` sin `ZTRACKING_RUTA`, **impiden
arrancar**: la configuración que no se puede cumplir se detiene en el arranque
en vez de dejar el sistema en pie sin fuente de pedidos.
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
- **Una fuente externa caída NO degrada `/health`** (`US-03`). Se reporta en el
  campo `fuentes` —con el motivo del fallo y la antigüedad del último dato
  bueno—, pero `status` sigue mirando solo a la base. El dashboard lee de la
  base y no de la fuente, así que una API de terceros no puede tumbar la
  respuesta. La lista viene vacía mientras ningún adaptador esté conectado
  (`TASK-28`), igual que `ingesta: null`.
- **El colector de AIS no se puede probar en vivo** y es a propósito que no haga
  falta: el riesgo **R1** deja la cuenta de AISStream sin entregar datos desde
  el 19/08/2026. El parseo se prueba contra los 161 mensajes reales que capturó
  el spike, en `scripts/spikes/aisstream/output/`, y el bucle contra un
  transporte inyectado. Ninguna prueba de `US-02` toca la red.
- **El cargador es idempotente y no toca los maestros.** La clave natural es
  `(oc_numero, posicion_oc)`, así que correrlo dos veces no duplica. `--limpiar`
  borra pedidos y elementos rastreados, pero **no** destinos, países ni
  parámetros —vienen de las migraciones— ni `historial_tracking`, que es
  *append-only* por disparador (RNF-13).
- **Sobre la semilla entran 6 de 8 líneas**, y las otras dos se rechazan con su
  motivo: una vía `PENDIENTE`, que no es una vía, y una terrestre sin destino
  posible en el maestro. No es un fallo del cargador: es RN-17 funcionando, y
  esas dos líneas imitan defectos reales de la muestra del 03/09.
