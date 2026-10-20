# TrackIn

Dashboard web para el seguimiento logístico de compras internacionales de
**Laboratorios Gutis**. Centraliza el estado de los pedidos de importación,
calcula cuándo estará disponible cada uno en planta y los ubica sobre mapas
marítimos y aéreos, sustituyendo el seguimiento manual sobre hojas de cálculo.

> **Estado (20/10/2026):** Sprint 6 de 7, más el cierre (16–21 nov).
>
> - **Backend completo:** carga del Z-tracking, rastreo con ShipsGo y TICA,
>   fecha proyectada, semáforo, ciclo de vida del pedido hasta su cierre,
>   auditoría y autenticación por roles.
> - **Frontend:** login, dashboard (KPIs, próximos arribos, filtros y grilla),
>   detalle del pedido con sus acciones y carga del Z-tracking desde la interfaz.
> - **Pendiente:** bandeja de arribos, alta en ShipsGo desde el sistema, saldo de
>   créditos, mapas (Sprint 7), pruebas de punta a punta y manuales (cierre).
>
> El estado al día de cada historia está en
> [docs/backlog/backlog_trackin.md](docs/backlog/backlog_trackin.md).

**Autor:** Mariano Mayorga Halabi
**Contexto:** Práctica Profesional, Ingeniería en Computación
Instituto Tecnológico de Costa Rica (TEC), período 2026-II.

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic |
| Worker de rastreo | Proceso Python aparte (`python -m app.workers`) |
| Base de datos | PostgreSQL 16 + PostGIS 3.6 |
| Frontend | React 19 + TypeScript, Vite, TailwindCSS 3, Leaflet |
| Datos remotos | TanStack Query, axios |
| Testing | pytest (backend), vitest + Testing Library (frontend) |
| Calidad | ruff + black + mypy (backend), ESLint + Prettier (frontend) |

### Fuentes de datos

| Fuente | Para qué |
|---|---|
| **Z-tracking** (Excel exportado de SAP) | Entrada de los pedidos. Lo sube Compras desde la interfaz; no hay API de SAP (decisión del 07/10) |
| **ShipsGo** (REST, de pago por crédito) | Rastreo marítimo por BL o contenedor y aéreo por MAWB: hitos, ETA, puerto, nave y vuelos |
| **TICA** (consulta pública de Hacienda) | Confirma el arribo de las guías aéreas hijas (HAWB) por el manifiesto de carga |
| AISStream (WebSocket) | Respaldo de posición para el mapa marítimo |
| OpenSky Network | **En pausa:** su licencia exige un acuerdo escrito para uso empresarial |

Detalle en [docs/api-references.md](docs/api-references.md) y en el SRS
([docs/srs/](docs/srs/)).

---

## Prerequisitos

| Herramienta | Versión | Verificar con |
|---|---|---|
| Python | 3.12 | `python --version` |
| Node.js | 20 o superior (probado con 24 LTS) | `node --version` |
| PostgreSQL + PostGIS | 16 + 3.6, **instalación nativa** | `pg_ctl --version` |
| Git | 2.40 | `git --version` |

> **Desarrollo sin Docker.** El equipo de desarrollo de Gutis no puede correr
> contenedores: todo runtime de Linux en Windows necesita WSL2 o Hyper-V, que
> exigen permisos de administrador. El stack corre de forma nativa, con
> PostgreSQL y PostGIS en binarios portables. Cómo se instalaron, en
> [docs/deployment.md](docs/deployment.md) §«Entorno de desarrollo sin Docker»;
> la decisión, en [docs/architecture.md](docs/architecture.md) §2.3 y en el
> SRS §9.3.
>
> Los `docker-compose.yml` y los `Dockerfile` **no se usan en desarrollo**. Se
> conservan como artefacto para el despliegue en servidor, que hace el Centro de
> Competencias fuera del alcance de la práctica.

---

## Setup

### 1. Clonar y configurar variables de entorno

```bash
git clone https://github.com/mdjmayorga/trackIn.git
cd trackIn
```

La configuración vive en **`backend/.env`**, copiada de la plantilla de la raíz
(en PowerShell):

```powershell
Copy-Item .env.example backend\.env
```

Definir al menos `POSTGRES_PASSWORD`, `SECRET_KEY` y, para rastrear,
`SHIPSGO_API_TOKEN`. Si queda algún `<placeholder>` de la plantilla, el backend
no arranca y dice cuál falta.

> **No crear un `.env` en la raíz.** Lo usaba docker-compose y tiene mayor
> precedencia que `backend/.env`: taparía la configuración local sin avisar.
> Ningún `.env` se commitea; están en `.gitignore`.

### 2. Levantar la base de datos

La base **no arranca sola** al encender el equipo: sin permisos de
administrador no se puede registrar como servicio de Windows. Hay que
levantarla en cada sesión de trabajo, **desde PowerShell**:

```powershell
& "$HOME\pgsql\bin\pg_ctl.exe" -D "$HOME\pgsql\data" -l "$HOME\pgsql\data\server.log" start
```

Para detenerla:

```powershell
& "$HOME\pgsql\bin\pg_ctl.exe" -D "$HOME\pgsql\data" stop
```

> Desde Git Bash, `pg_ctl start` se queda con la consola, y al cerrarla se cae
> la base. Desde PowerShell queda desacoplada.

Verificar que PostGIS está activo:

```powershell
& "$HOME\pgsql\bin\psql.exe" -h localhost -U trackin -d trackin_dev -c "SELECT postgis_version();"
```

Hay dos bases: `trackin_dev`, con los datos de trabajo, y `trackin_test`, que
usan las pruebas. Cómo crear la de pruebas está en
[backend/README.md](backend/README.md).

### 3. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
alembic upgrade head
```

El backend son **dos procesos**, cada uno en su consola con el entorno activo:

```powershell
uvicorn app.main:app --reload    # API
```

```powershell
python -m app.workers            # worker de rastreo
```

La API queda en <http://localhost:8000>, con Swagger en `/docs`. El worker no
abre puertos. Corre aparte para que el `--reload` de la API no corte el
rastreo (ver [docs/architecture.md](docs/architecture.md) §1.4).

El primer usuario Administrador se crea desde la consola:

```powershell
python scripts\crear_usuario.py admin "Nombre Apellido" ADMINISTRADOR
```

### 4. Frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

El dashboard queda en <http://localhost:5173>. Se entra con un usuario creado
en el paso anterior.

---

## Comandos frecuentes

### Backend (desde `backend/`, con el venv activo)

| Comando | Qué hace |
|---|---|
| `pytest` | Corre las pruebas con cobertura, sobre `trackin_test` |
| `pytest -m "not integration"` | Solo las pruebas que no necesitan base de datos |
| `ruff check app tests` | Lint |
| `black app tests` | Formatea |
| `mypy app` | Chequeo de tipos (bloqueante en CI) |
| `alembic upgrade head` | Aplica las migraciones pendientes a `trackin_dev` |
| `python -m app.workers --una-vez` | Un solo ciclo de rastreo y termina |
| `python scripts/recalcular.py` | Recalcula fecha y estado de todos los pedidos activos |

La lista completa, con los scripts de carga y de mantenimiento, está en
[backend/README.md](backend/README.md).

### Frontend (desde `frontend/`)

| Comando | Qué hace |
|---|---|
| `npm run dev` | Dev server con hot reload |
| `npm run build` | Build de producción |
| `npm run typecheck` | Chequeo de tipos |
| `npm run lint` | ESLint |
| `npm run format` | Prettier |
| `npm test` | Pruebas con vitest |
| `npm run test:coverage` | Pruebas con cobertura (CI exige 70 %) |

---

## Estructura del repositorio

```
trackin/
├── backend/              API FastAPI y worker de rastreo
│   ├── app/
│   │   ├── api/          Endpoints HTTP (auth, pedidos, cargas, destinos, usuarios, health)
│   │   ├── core/         Configuración
│   │   ├── db/           Engine, sesiones y base declarativa
│   │   ├── models/       Modelos ORM
│   │   ├── schemas/      Contratos Pydantic de la API
│   │   ├── services/     Reglas de negocio, ingesta y clientes de las fuentes
│   │   └── workers/      Ciclo periódico de rastreo
│   ├── alembic/          Migraciones de base de datos
│   ├── scripts/          Carga, recálculo, usuarios y consultas manuales
│   └── tests/
├── frontend/             Dashboard React
│   └── src/
│       ├── auth/         Sesión y rutas protegidas
│       ├── components/   Componentes reutilizables
│       ├── pages/        Login, Dashboard, DetallePedido, Cargas
│       ├── services/     Cliente HTTP de la API
│       ├── hooks/        Custom hooks
│       ├── types/        Tipos TypeScript
│       └── utils/
├── docs/                 Documentación técnica, SRS, backlog, ADR e informes
├── scripts/              Utilidades del repositorio e inicialización de la base
└── .github/workflows/    Integración continua
```

---

## Documentación

| Documento | Contenido |
|---|---|
| [docs/backlog/backlog_trackin.md](docs/backlog/backlog_trackin.md) | Backlog, sprints y decisiones con usuarios |
| [docs/srs/](docs/srs/) | Especificación de requisitos (SRS) |
| [docs/architecture.md](docs/architecture.md) | Arquitectura del sistema |
| [docs/data-model.md](docs/data-model.md) | Modelo de datos y diagrama ER |
| [docs/data-dictionary.md](docs/data-dictionary.md) | Diccionario de datos |
| [docs/api-references.md](docs/api-references.md) | Fuentes externas y reglas de negocio |
| [docs/deployment.md](docs/deployment.md) | Entorno de desarrollo nativo y despliegue |
| [docs/adr/](docs/adr/) | Registro de decisiones de arquitectura |
| [GLOSSARY.md](GLOSSARY.md) | Glosario del dominio |
| [backend/README.md](backend/README.md) | Detalle del backend |
| [frontend/README.md](frontend/README.md) | Detalle del frontend |

---

## Licencia

Software propietario de Laboratorios Gutis S.A. Ver [LICENSE](LICENSE).
