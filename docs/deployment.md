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
