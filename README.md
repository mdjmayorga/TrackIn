# TrackIn

Dashboard web para el seguimiento logístico de compras internacionales de
**Laboratorios Gutis**. Centraliza el estado de los pedidos de importación y los
ubica en tiempo real sobre mapas marítimos y aéreos, sustituyendo el
seguimiento manual sobre hojas de cálculo.

> **Estado:** Sprint 0 — entorno de desarrollo. Todavía no hay lógica de
> negocio implementada; el análisis de requerimientos arranca en Sprint 1.

**Autor:** Mariano Mayorga Halabi
**Contexto:** Práctica Profesional, Ingeniería en Computación
Instituto Tecnológico de Costa Rica (TEC), período 2026-II.

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic |
| Base de datos | PostgreSQL 16 + PostGIS 3.4 |
| Frontend | React 19 + TypeScript, Vite, TailwindCSS, Leaflet |
| Datos remotos | TanStack Query, axios |
| Contenedores | Docker + Docker Compose |
| Testing | pytest (backend), vitest + Testing Library (frontend) |
| Calidad | ruff + black + mypy (backend), ESLint + Prettier (frontend) |

APIs externas previstas para sprints posteriores: **AISStream** (WebSocket,
tracking marítimo) y **OpenSky Network** (REST, tracking aéreo). Ver
[docs/api-references.md](docs/api-references.md).

---

## Prerequisitos

| Herramienta | Versión mínima | Verificar con |
|---|---|---|
| Python | 3.12 | `python --version` |
| Node.js | 20 (probado con 24 LTS) | `node --version` |
| Docker Desktop | 4.x con Compose v2 | `docker compose version` |
| Git | 2.40 | `git --version` |

---

## Setup

### 1. Clonar y configurar variables de entorno

```bash
git clone https://github.com/mdjmayorga/trackIn.git
cd trackIn
```

```bash
cp .env.example .env
```

Editar `.env` y definir al menos `POSTGRES_PASSWORD` y `SECRET_KEY` con valores
aleatorios. En PowerShell:

```bash
Copy-Item .env.example .env
```

> `.env` está en `.gitignore` y **nunca** debe commitearse.

### 2. Levantar la base de datos

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres
```

Verificar que PostGIS quedó activo:

```bash
docker compose exec postgres psql -U trackin -d trackin_dev -c "SELECT postgis_version();"
```

### 3. Backend

```bash
cd backend && python -m venv .venv
```

Activarlo — PowerShell: `.\.venv\Scripts\Activate.ps1`; bash: `source .venv/bin/activate`.

```bash
pip install -r requirements-dev.txt
```

```bash
uvicorn app.main:app --reload
```

La API queda en <http://localhost:8000>, con Swagger en `/docs`.

### 4. Frontend

```bash
cd frontend && npm install
```

```bash
npm run dev
```

El dashboard queda en <http://localhost:5173>.

### Alternativa: todo con Docker

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

---

## Comandos frecuentes

### Backend (desde `backend/`, con el venv activo)

```bash
pytest
```

| Comando | Qué hace |
|---|---|
| `pytest` | Corre los tests con reporte de cobertura |
| `pytest -m "not integration"` | Solo los tests que no necesitan base de datos |
| `ruff check app tests` | Lint |
| `ruff check --fix app tests` | Lint con corrección automática |
| `black app tests` | Formatea |
| `mypy app` | Chequeo de tipos |
| `alembic revision --autogenerate -m "mensaje"` | Genera una migración |
| `alembic upgrade head` | Aplica las migraciones pendientes |

### Frontend (desde `frontend/`)

| Comando | Qué hace |
|---|---|
| `npm run dev` | Dev server con hot reload |
| `npm run build` | Build de producción |
| `npm run typecheck` | Chequeo de tipos |
| `npm run lint` | ESLint |
| `npm run format` | Prettier |
| `npm test` | Tests con vitest |
| `npm run test:coverage` | Tests con cobertura |

### Docker

| Comando | Qué hace |
|---|---|
| `docker compose ... up -d` | Levanta el stack en segundo plano |
| `docker compose ... logs -f backend` | Sigue los logs del backend |
| `docker compose ... down` | Baja el stack (conserva los datos) |
| `docker compose ... down -v` | Baja el stack y **borra la base** |

---

## Estructura del repositorio

```
trackin/
├── backend/            API FastAPI
│   ├── app/
│   │   ├── api/        Routers y endpoints HTTP
│   │   ├── core/       Configuración transversal
│   │   ├── db/         Engine, sesiones y base declarativa
│   │   ├── models/     Modelos ORM (Sprint 1-2)
│   │   ├── schemas/    Contratos Pydantic de la API (Sprint 1)
│   │   └── services/   Lógica de negocio y clientes externos
│   ├── alembic/        Migraciones de base de datos
│   └── tests/
├── frontend/           Dashboard React
│   └── src/
│       ├── components/ Componentes reutilizables
│       ├── pages/      Vistas (Dashboard, Pedidos, Mapas)
│       ├── services/   Cliente HTTP de la API
│       ├── hooks/      Custom hooks
│       ├── types/      Tipos TypeScript
│       └── utils/
├── docs/               Documentación técnica
├── scripts/            Utilidades e inicialización de la base
└── .github/workflows/  Integración continua
```

---

## Documentación

| Documento | Contenido |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Arquitectura del sistema |
| [docs/data-model.md](docs/data-model.md) | Modelo de datos y diagrama ER |
| [docs/api-references.md](docs/api-references.md) | APIs externas y reglas de negocio |
| [docs/deployment.md](docs/deployment.md) | Despliegue |
| [backend/README.md](backend/README.md) | Detalle del backend |
| [frontend/README.md](frontend/README.md) | Detalle del frontend |

---

## Licencia

Software propietario de Laboratorios Gutis S.A. Ver [LICENSE](LICENSE).
