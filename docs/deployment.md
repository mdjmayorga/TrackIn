# Guía de despliegue

Para el **Centro de Competencias**, que asume la puesta en producción de TrackIn
después de la práctica (`TASK-09`). Dice qué entrega el proyecto, qué hay que
decidir y hacer en el servidor, y qué queda fuera del alcance de la práctica.

Para levantar TrackIn en un equipo de trabajo, sin servidor, ver el
[manual de instalación local](manual-instalacion.md).

> **Estado (06/11/2026).** Las imágenes se construyeron y el stack se levantó
> completo en un equipo con Docker, siguiendo el §7 al pie de la letra
> (`PROD-03` y `PROD-04` de [backlog_produccion.md](backlog/backlog_produccion.md)):
> los cuatro servicios arrancan y los tres con chequeo de salud quedan
> `healthy`. Lo que sigue sin probarse es el servidor real, con su red, su
> nombre y su HTTPS.

---

## 1. Qué queda fuera del alcance de la práctica

El SRS §1.2.2 excluye explícitamente el despliegue y lo deja al Centro de
Competencias. Esta guía deja todo listo para hacerlo, pero estas decisiones y
tareas **no las resuelve TrackIn**:

| Exclusión del SRS §1.2.2 | Qué significa para el despliegue | Qué entrega el proyecto |
|---|---|---|
| Despliegue a producción en la infraestructura de Gutis | Elegir el servidor, instalarlo, administrarlo y operarlo | Los artefactos de contenedor (§4) y esta guía |
| Servidor web productivo, balanceo de carga y terminación SSL | El certificado y el HTTPS van en el proxy corporativo, delante de TrackIn | Un solo puerto HTTP a publicar (§3) |
| Autenticación corporativa (Active Directory / SSO) | Los usuarios son propios de TrackIn | Usuarios, roles y sesiones propios (`US-42`); se administran desde el panel |
| Sistema de colas distribuido | No hay cola: el rastreo es un proceso aparte | El `worker`, un solo proceso |
| Monitoreo, logging centralizado y alertas | Nadie mira los logs ni recibe alertas, salvo que TI lo configure | `/health` con el estado de cada fuente (§9) y los logs de cada contenedor |
| Integración automática directa con SAP S/4HANA | SAP no está conectado | El receptor de pedidos, apagado por omisión (`US-65`, `US-66`), y el contrato en `docs/integraciones/sap/` |
| Contratación de licencias de APIs comerciales | La cuenta y los créditos de ShipsGo son de Gutis | El control de créditos (`US-57`) |

Tampoco son de TrackIn, aunque el SRS no las nombre:

- Los **respaldos programados** y su retención: §8 da los comandos; la tarea
  programada y dónde se guardan, TI.
- La **custodia de los secretos** (§5): TrackIn los lee del entorno; dónde se
  guardan, TI.
- Quién **mantiene** el sistema: actualizaciones, cuentas de usuario, créditos de
  ShipsGo.

---

## 2. Decisiones previas con TI

- [ ] **Servidor:** Linux con Docker (lo recomendado, §6) o Windows sin Docker
      (§10).
- [ ] **Tamaño:** 2 vCPU, 4 GB de RAM y 40 GB de disco alcanzan con holgura: el
      historial de posiciones crece menos de 1 GB al año (`TASK-10`).
- [ ] **Nombre DNS** (provisorio: `trackin.gutis.com`) y **certificado TLS**,
      en el proxy corporativo.
- [ ] **Salida a internet** desde el servidor (§3).
- [ ] **Respaldos:** frecuencia, retención y dónde se guardan.
- [ ] **Secretos:** dónde vive `.env.produccion`.
- [ ] **Quién administra** el servidor y TrackIn, y con qué ventana de
      mantenimiento.

---

## 3. Arquitectura en el servidor

Cuatro contenedores en una red interna, **un solo puerto publicado**:

```
navegador ──HTTPS──▶ proxy corporativo (TLS) ──HTTP──▶ :8080 frontend (nginx)
                                                          │  /          → el panel (estáticos)
                                                          │  /api/, /health → backend:8000
                                                          ▼
                                     backend (API, uvicorn) ──▶ postgres (PostGIS)
                                     worker (rastreo)       ──▶ postgres
                                     worker ──HTTPS──▶ ShipsGo, TICA
```

| Servicio | Imagen | Qué hace | Puerto |
|---|---|---|---|
| `postgres` | `postgis/postgis:16-3.6` | La base, con PostGIS | Ninguno publicado |
| `backend` | `trackin-backend` (etapa `runtime`) | La API que consulta el panel | Ninguno publicado |
| `worker` | La misma imagen, `python -m app.workers` | Lee ShipsGo y TICA, detecta arribos y recalcula | Ninguno |
| `frontend` | `trackin-frontend` (nginx) | Sirve el panel y reenvía `/api/` y `/health` a la API | `TRACKIN_PUERTO` (8080) |

Que el panel y la API compartan origen evita CORS y deja un único punto a
proteger. El `worker` va aparte de la API por diseño (`TASK-20`,
[architecture.md](architecture.md) §1.4): reiniciar uno no corta el otro.

**Salida a internet que necesita el servidor** (HTTPS, puerto 443):

| Destino | Quién lo usa | Si está bloqueado |
|---|---|---|
| `api.shipsgo.com` | `worker` y `backend` | No hay rastreo de BL, contenedores ni MAWB |
| `ticaconsultas.hacienda.go.cr` | `worker` | No se siguen las guías hijas (HAWB) |
| `embed.shipsgo.com` | El **navegador** de cada usuario | El detalle usa el mapa propio |
| `*.tile.openstreetmap.org` | El **navegador** de cada usuario | Los mapas salen sin fondo |

Los dos últimos los pide el navegador, no el servidor: la red de los usuarios
tiene que dejarlos pasar.

---

## 4. Artefactos de contenedor

| Archivo | Qué es |
|---|---|
| `docker-compose.yml` | El stack de servidor: los cuatro servicios, la red y el volumen de la base |
| `docker-compose.dev.yml` | Override de desarrollo con contenedores: puertos al host, código montado, pgAdmin. **No se usa en el servidor** |
| `backend/Dockerfile` | Imagen de la API y del worker. Etapas `deps` (compila), `builder` (desarrollo) y `runtime` (servidor: sin herramientas de desarrollo, usuario no-root, `HEALTHCHECK` sobre `/health`) |
| `backend/.dockerignore` | Deja fuera el `.venv`, las pruebas, las grabaciones de los spikes y cualquier `.env` |
| `frontend/Dockerfile` | Imagen del panel. Construye el bundle con Node 22 y lo sirve con nginx 1.27, con `HEALTHCHECK` sobre `127.0.0.1` (no `localhost`, que en alpine resuelve a IPv6 y nginx escucha en IPv4) |
| `frontend/nginx.conf` | Sirve el panel, reenvía la API, acepta archivos de hasta 20 MB (la carga del Z-tracking) y cachea los assets |
| `scripts/init-db/01-extensions.sql` | Activa PostGIS al crear la base por primera vez |
| `.env.produccion.example` | La plantilla de variables del servidor (§5) |

**Actualizados el 03/11/2026.** Eran del Sprint 0: faltaba el `worker`, la API
recibía las claves de AISStream y OpenSky (reemplazadas por ShipsGo) en vez de
la de ShipsGo, y la URL de la API del panel iba como variable de ejecución,
cuando Vite la fija al construir.

---

## 5. Variables de entorno

Se copian de `.env.produccion.example` a `.env.produccion`, en la raíz del
repositorio, y se pasan con `--env-file`. **`.env.produccion` no se sube al
repositorio.**

### API y worker (las comparten)

| Variable | Obligatoria | Qué es |
|---|---|---|
| `POSTGRES_PASSWORD` | **Sí** | Contraseña de la base. Larga y aleatoria |
| `SECRET_KEY` | **Sí** | Firma las sesiones. Cambiarla cierra todas las sesiones |
| `POSTGRES_USER` | No (`trackin`) | Usuario de la base |
| `POSTGRES_DB` | No (`trackin`) | Nombre de la base |
| `ENVIRONMENT` | No (`production`) | Con `production`, TrackIn no arranca con la clave o la contraseña de desarrollo |
| `DEBUG` | No (`false`) | Dejar en `false` |
| `BACKEND_CORS_ORIGINS` | No | El dominio público con `https`. El panel no lo necesita (mismo origen) |
| `SHIPSGO_API_TOKEN` | No | Token de la **API** de ShipsGo. Sin él, el sistema funciona pero no rastrea |
| `SAP_INTEGRACION_CLAVE` | No | La clave que SAP manda en `X-API-Key`. Sin ella, el receptor responde 503 |

Para generar las dos obligatorias:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

`docker-compose.yml` fija además `POSTGRES_HOST=postgres` y
`INGESTA_ADAPTADOR=ninguno` (los pedidos entran por la carga del Excel desde el
panel). Si falta una obligatoria, `docker compose` no arranca y la nombra; si
falta o está mal otra cosa, la API no arranca y lista **todos** los problemas
juntos.

### Panel (se fijan al construir la imagen)

| Variable | Qué es |
|---|---|
| `VITE_API_URL` | **Vacía** (recomendado): el panel llama a la API en su mismo origen. Solo se completa si la API vive en otro dominio |
| `VITE_SHIPSGO_EMBED_TOKEN` | Opcional: el mapa en vivo de ShipsGo en el detalle. Es otro token, no el de la API, y va en el navegador: el dominio público tiene que estar en «Allowed HTTP Origins» de la cuenta de ShipsGo |
| `TRACKIN_PUERTO` | El puerto del servidor donde escucha el panel (8080). El proxy con TLS apunta acá |

> Las `VITE_*` quedan **dentro del bundle**: cambiarlas exige
> `docker compose build frontend`, no basta reiniciar. Y cualquiera que abra el
> panel puede leerlas: nunca poner ahí un secreto.

---

## 6. Dependencias

**En el servidor:** Docker Engine 24 o superior con el plugin `compose` v2.24 o
superior (el override de desarrollo usa `!override`), y Git para obtener el
código. Nada más: Python, Node y PostgreSQL vienen en las imágenes.

**En las imágenes:**

| Componente | Versión | Dónde |
|---|---|---|
| Python | 3.12 | `backend/Dockerfile` (`python:3.12-slim`) |
| PostgreSQL + PostGIS | 16 + 3.6 | `postgis/postgis:16-3.6` |
| Node | 22 (solo para construir) | `frontend/Dockerfile` |
| nginx | 1.27 | `frontend/Dockerfile` |
| Librerías de Python | FastAPI 0.115, SQLAlchemy 2.0 (asyncpg), Alembic 1.14, GeoAlchemy2, Pydantic 2.9, httpx, argon2-cffi, pandas y openpyxl | `backend/requirements.txt` |
| Librerías del panel | React 19, react-leaflet 5, TanStack Query, axios, Tailwind 3 | `frontend/package-lock.json` |

**Servicios externos:** ShipsGo (cuenta de Gutis, con créditos para dar de
alta embarques) y el sitio público de TICA (sin credenciales).

---

## 7. Primer despliegue

Desde la raíz del repositorio, en el servidor:

```bash
git clone https://github.com/mdjmayorga/TrackIn.git && cd TrackIn
cp .env.produccion.example .env.produccion       # y completarlo (§5)

docker compose --env-file .env.produccion build
docker compose --env-file .env.produccion up -d postgres
docker compose --env-file .env.produccion run --rm backend alembic upgrade head
docker compose --env-file .env.produccion run --rm backend \
    python scripts/crear_usuario.py admin "Nombre Apellido" ADMINISTRADOR
docker compose --env-file .env.produccion up -d
```

- `alembic upgrade head` crea las tablas y siembra los maestros: países,
  destinos y parámetros. **Va antes de levantar la API y el worker.**
- `crear_usuario.py` crea el primer Administrador y pide su contraseña sin
  mostrarla. Los demás usuarios se crean desde el panel.

**Verificación:**

1. `docker compose --env-file .env.produccion ps`: los cuatro servicios
   `running`; `backend` y `frontend`, además, `healthy`.
2. `curl http://localhost:8080/health` responde `"status":"ok"` y
   `"database":"up"`. A los pocos minutos, `"fuentes"` muestra `shipsgo` con
   `"degradada": false` (si hay token).
3. En el navegador, por el dominio público: el inicio de sesión, y entrar con el
   Administrador.

**En el panel, una sola vez:**

1. **Usuarios:** las cuentas de Compras, Logística y Planificación.
2. **Altas en ShipsGo → Registrar paquete comprado:** los créditos de la cuenta.
   Sin eso, `/health` dice `"SIN_PAQUETE"` y TrackIn no puede avisar antes de
   que se agoten.
3. **Cargas:** subir el Z-tracking vigente con la plantilla.
4. Si SAP va a enviar pedidos: **Configuración → Integración con SAP** para
   encender la escucha, y entregar `SAP_INTEGRACION_CLAVE` al equipo de SAP por
   un canal seguro. El contrato está en `docs/integraciones/sap/`.

---

## 8. Respaldos y restauración

Un respaldo es un `pg_dump` de la base. **La tarea programada y dónde se guarda
la decide TI**; esto es lo que hay que programar:

```bash
docker compose --env-file .env.produccion exec -T postgres \
    pg_dump -U trackin -d trackin -Fc > trackin-$(date +%Y%m%d-%H%M).dump
```

Restaurar, sobre una base vacía (por ejemplo, en un servidor de prueba):

```bash
docker compose --env-file .env.produccion up -d postgres
docker compose --env-file .env.produccion exec -T postgres \
    pg_restore -U trackin -d trackin --clean --if-exists < trackin-AAAAMMDD-HHMM.dump
docker compose --env-file .env.produccion up -d
```

**Un respaldo no está verificado hasta que se restaura una vez.** Hacerlo antes
de la salida, y anotar cuánto tardó.

El volumen `trackin_postgres_data` es la base: `docker compose down` lo
conserva; **`docker compose down -v` lo borra**.

---

## 9. Operación

| Para | Comando |
|---|---|
| Ver el estado | `docker compose --env-file .env.produccion ps` y `curl http://localhost:8080/health` |
| Ver los logs | `docker compose --env-file .env.produccion logs -f backend worker` |
| Reiniciar el rastreo | `docker compose --env-file .env.produccion restart worker` |
| Crear un usuario desde la consola | `docker compose --env-file .env.produccion run --rm backend python scripts/crear_usuario.py <usuario> "<Nombre>" <ROL>` |

**Qué mirar en `/health`:**

- `database`: tiene que decir `"up"`.
- `fuentes[].degradada`: `true` significa que ShipsGo o TICA no responden. Con
  errores de red, el worker reintenta solo cada 5 minutos; con un token inválido
  (401) no reintenta: corregir el token y reiniciar el `worker`.
- `creditos_shipsgo.nivel`: avisa cuando quedan pocos créditos de ShipsGo.

### Actualizar a una versión nueva

```bash
git pull
docker compose --env-file .env.produccion build
docker compose --env-file .env.produccion run --rm backend alembic upgrade head
docker compose --env-file .env.produccion up -d
```

Respaldar antes (§8). `up -d` recrea la API, el **worker** y el panel con la
imagen nueva: el worker tiene que reiniciarse en cada actualización, o sigue
aplicando las reglas anteriores.

---

## 10. Alternativa: servidor Windows sin Docker

Si TI ofrece un servidor Windows sin Docker, TrackIn corre de forma nativa como
en el [manual de instalación local](manual-instalacion.md), con estas
diferencias:

- En un servidor sí hay administrador: PostgreSQL, la API y el worker se
  registran como **servicios de Windows** para que arranquen solos (PostgreSQL
  con `pg_ctl register`; la API y el worker con un envoltorio de servicios como
  WinSW o NSSM).
- La API sin `--reload`: `.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.
- `backend\.env` con los valores de §5 (`ENVIRONMENT=production`, claves
  nuevas).
- El panel se construye una vez (`npm run build`, con `VITE_API_URL` vacía) y la
  carpeta `frontend\dist` la sirve IIS o nginx para Windows, con las mismas
  reglas de `frontend/nginx.conf`: reenviar `/api/` y `/health` a
  `127.0.0.1:8000`, devolver `index.html` para cualquier otra ruta y aceptar
  archivos de 20 MB.
- Respaldos con `pg_dump.exe` desde el Programador de tareas.

---

## 11. Checklist antes de la salida

- [ ] `SECRET_KEY` y `POSTGRES_PASSWORD` generados para el servidor, no los de
      desarrollo
- [ ] `ENVIRONMENT=production` y `DEBUG=false`
- [ ] `.env.produccion` guardado donde TI guarda los secretos
- [ ] La base y la API sin puertos publicados; solo `TRACKIN_PUERTO`, y solo
      hacia el proxy
- [ ] HTTPS en el proxy corporativo
- [ ] Migraciones aplicadas y primer Administrador creado
- [ ] `/health` con la base `"up"` y ShipsGo sin degradar
- [ ] Paquete de créditos de ShipsGo registrado
- [ ] Salida a internet a `api.shipsgo.com` y a TICA verificada desde el servidor
- [ ] Respaldo programado **y restaurado una vez**
- [ ] Si se usa el mapa embebido: el dominio público en «Allowed HTTP Origins» de
      ShipsGo, y `embed.shipsgo.com` permitido en la red de los usuarios
- [ ] Si SAP va a enviar: `SAP_INTEGRACION_CLAVE` entregada por canal seguro y
      la escucha encendida desde el panel
- [ ] Quién mantiene el sistema, acordado
