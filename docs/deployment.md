# Despliegue

> **Estado: pendiente.** El destino de despliegue todavía no está definido con
> el área de TI de Laboratorios Gutis. Este documento se completa al acercarse
> la entrega final.

## Definiciones pendientes

- [ ] Dónde corre: ¿servidor on-premise de Gutis, VM, o nube?
- [ ] Quién administra el servidor y con qué ventana de mantenimiento
- [ ] Nombre DNS y certificado TLS
- [ ] Política de respaldos de PostgreSQL (frecuencia, retención, restauración)
- [ ] Dónde se guardan los secretos de producción (no en `.env` plano)
- [ ] Monitoreo y alertas
- [ ] Estrategia de actualización sin downtime

## Diferencias entre desarrollo y producción

Lo que ya está resuelto en los archivos de compose:

| Aspecto | Desarrollo | Producción |
|---|---|---|
| Archivos | `docker-compose.yml` + `docker-compose.dev.yml` | solo `docker-compose.yml` |
| Etapa de imagen | `builder` | `runtime` |
| Backend | uvicorn con `--reload` | uvicorn sin reload, usuario no-root |
| Frontend | dev server de Vite | bundle estático servido por nginx |
| Puertos | publicados al host | solo los necesarios |
| pgAdmin | incluido | **no se incluye** |
| `DEBUG` | `true` | `false` |

## Entorno de desarrollo sin Docker (equipo de Gutis)

En el equipo de desarrollo asignado por Laboratorios Gutis **Docker no puede
correr**. No es un problema de instalación: Docker Desktop 4.85 está instalado,
pero en Windows todo runtime de contenedores Linux —Docker Desktop, Podman,
Rancher— depende de WSL2 o Hyper-V, y ambas son características de Windows que
solo se habilitan con permisos de administrador. WSL no está instalado y TI no
pudo habilitarlo. No existe alternativa en espacio de usuario.

El stack corre entonces de forma nativa. Los archivos de compose siguen siendo
válidos y son el artefacto de despliegue para el servidor.

| Componente | Cómo corre en el equipo de Gutis |
|---|---|
| PostgreSQL 16.14 + PostGIS 3.6.2 | Binarios portables en `C:\Users\<usuario>\pgsql`, sin servicio de Windows |
| Backend | `uvicorn` desde el `.venv` de `backend/` |
| Frontend | `npm run dev` (Vite) |
| pgAdmin | Incluido en los binarios de EDB, o cualquier cliente SQL |

Origen de los binarios (ninguno requiere administrador):

- PostgreSQL: `https://get.enterprisedb.com/postgresql/postgresql-16.14-1-windows-x64-binaries.zip`
- PostGIS: `https://download.osgeo.org/postgis/windows/pg16/postgis-bundle-pg16-3.6.2x64.zip`

El bundle de PostGIS se descomprime **encima** del directorio de PostgreSQL.
`initdb` se ejecutó con `-E UTF8 --locale=C`, los mismos parámetros que
`POSTGRES_INITDB_ARGS` en `docker-compose.yml`, para que el ordenamiento de
índices sea idéntico al del contenedor.

Arrancar y detener la base:

```bash
"$HOME/pgsql/bin/pg_ctl" -D "$HOME/pgsql/data" -l "$HOME/pgsql/server.log" start
```

```bash
"$HOME/pgsql/bin/pg_ctl" -D "$HOME/pgsql/data" stop
```

La base **no arranca sola al encender el equipo**: sin permisos de
administrador no se puede registrar como servicio de Windows. Hay que
levantarla a mano en cada sesión de trabajo.

`POSTGRES_HOST=localhost` en el `.env` ya es el valor correcto para este modo.

## Checklist previo a producción

- [ ] `SECRET_KEY` y `POSTGRES_PASSWORD` regenerados (no los de desarrollo)
- [ ] `ENVIRONMENT=production` y `DEBUG=false`
- [ ] `BACKEND_CORS_ORIGINS` restringido al dominio real (nunca `*`)
- [ ] `VITE_API_URL` apuntando a la URL pública de la API
      — recordar que Vite la embebe **en tiempo de build**: cambiarla exige
      reconstruir la imagen del frontend, no basta reiniciar el contenedor
- [ ] Migraciones aplicadas (`alembic upgrade head`)
- [ ] Postgres **no** expuesto a la red pública
- [ ] Respaldo automático verificado con una restauración de prueba
- [ ] Credenciales de AISStream y OpenSky de producción cargadas

## Build de las imágenes

```bash
docker compose build
```

```bash
docker compose --env-file .env.production up -d
```

## Migraciones

```bash
docker compose run --rm backend alembic upgrade head
```
