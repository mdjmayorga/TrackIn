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

- Los **respaldos programados**: §8 da los scripts y la retención; la tarea
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
| `tile.openstreetmap.org` (sin subdominio; con el plan B, `tiles.stadiamaps.com`, §5) | El **navegador** de cada usuario | Los mapas salen sin fondo |

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
| `frontend/nginx.conf` | Sirve el panel, reenvía la API, acepta archivos de hasta 20 MB (la carga del Z-tracking) y cachea los assets. No anuncia su versión (`server_tokens off`) |
| `frontend/nginx-seguridad.conf` | Las cabeceras de seguridad del panel (§4.1). Se copia a `/etc/nginx/snippets/` y se incluye en cada bloque de `nginx.conf` |
| `scripts/init-db/01-extensions.sql` | Activa PostGIS al crear la base por primera vez |
| `.env.produccion.example` | La plantilla de variables del servidor (§5) |

**Actualizados el 03/11/2026.** Eran del Sprint 0: faltaba el `worker`, la API
recibía las claves de AISStream y OpenSky (reemplazadas por ShipsGo) en vez de
la de ShipsGo, y la URL de la API del panel iba como variable de ejecución,
cuando Vite la fija al construir.

### 4.1 Lo que cambia en producción (`PROD-11`)

| Qué | En producción | Por qué |
|---|---|---|
| `/docs`, `/redoc`, `/openapi.json` | **Apagados** con `ENVIRONMENT=production` (siguen en desarrollo) | Describirían cada ruta de la API. nginx ya no los reenvía, pero apagarlos no depende de cómo se publique el contenedor |
| `Content-Security-Policy` | Solo corren los scripts del propio panel; de afuera, solo los mosaicos del mapa (imágenes, del dominio de `VITE_MOSAICOS_URL`) y el mapa de ShipsGo (iframe) | El token de sesión vive en el navegador: un script ajeno podría leerlo |
| `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options` y `frame-ancestors`, `Permissions-Policy` | Puestas en todas las respuestas | Cabeceras básicas. `Referrer-Policy` manda el origen a otros sitios porque el mapa de ShipsGo lo usa para validar «Allowed HTTP Origins» |
| Versión de nginx | No se anuncia | — |
| Logs de los contenedores | Se rotan: cinco archivos de 10 MB por servicio (`x-logs` en `docker-compose.yml`) | Sin tope, el driver `json-file` crece hasta llenar el disco |
| Reinicio del servidor | Los cuatro servicios tienen `restart: unless-stopped` | TrackIn vuelve solo, **si Docker arranca con el sistema**: `sudo systemctl enable docker` |

**El fondo del mapa se ajusta solo; una API en otro dominio, no.** Al construir la
imagen, el `Dockerfile` pone en `img-src` el dominio de `VITE_MOSAICOS_URL`, así que
pasar al plan B (§5) no exige tocar la política. Una API en otro dominio
(`VITE_API_URL`) sí: hay que agregarla a `connect-src` en
`frontend/nginx-seguridad.conf` y reconstruir el panel (`docker compose build
frontend`). El síntoma de olvidarlo es un mapa gris
o un panel que no carga datos, con un error «Content Security Policy» en la consola
del navegador (F12). El 10/11/2026 pasó en una prueba: un bundle compilado con el
`.env` de desarrollo (`VITE_API_URL=http://localhost:8000`) decía que el backend no
estaba corriendo, con el backend sano. En el servidor no ocurre mientras
`VITE_API_URL` quede vacía, que es lo recomendado (§5).

**HSTS** (`Strict-Transport-Security`) no lo pone TrackIn: va en el proxy que
termina el TLS.

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

### Avisos por correo (solo los lee `scripts/vigilar_salud.sh`, §9)

| Variable | Qué es |
|---|---|
| `AVISO_SMTP_URL` | El servidor de correo que indique TI: `smtp://host:25` (relé interno), `smtp://host:587` o `smtps://host:465`. **Vacía:** el aviso queda solo en el log |
| `AVISO_SMTP_USUARIO`, `AVISO_SMTP_CLAVE` | Si el servidor de correo pide usuario. La clave no aparece en `ps` mientras se envía |
| `AVISO_DE` | El remitente, por ejemplo `trackin@gutis.com` |
| `AVISO_PARA` | Los destinatarios, separados por coma |
| `AVISO_FUENTE_HORAS` | Cuántas horas puede estar degradada una fuente antes de avisar (1) |

### Panel (se fijan al construir la imagen)

| Variable | Qué es |
|---|---|
| `VITE_API_URL` | **Vacía** (recomendado): el panel llama a la API en su mismo origen. Solo se completa si la API vive en otro dominio |
| `VITE_SHIPSGO_EMBED_TOKEN` | Opcional: el mapa en vivo de ShipsGo en el detalle. Es otro token, no el de la API, y va en el navegador: el dominio público tiene que estar en «Allowed HTTP Origins» de la cuenta de ShipsGo |
| `VITE_MOSAICOS_URL` | **Vacía** (recomendado): el fondo de los mapas sale de OpenStreetMap, `https://tile.openstreetmap.org/{z}/{x}/{y}.png`. Solo se cambia para el plan B (abajo). Tiene que ser `https://` con un dominio fijo, sin `{s}`: si no, la imagen no se construye y dice por qué |
| `VITE_MOSAICOS_ATRIBUCION` | **Vacía**: la de OpenStreetMap. Con el plan B, la del proveedor (abajo) |
| `TRACKIN_PUERTO` | El puerto del servidor donde escucha el panel (8080). El proxy con TLS apunta acá |

> Las `VITE_*` quedan **dentro del bundle**: cambiarlas exige
> `docker compose build frontend`, no basta reiniciar. Y cualquiera que abra el
> panel puede leerlas: nunca poner ahí un secreto. La clave de Stadia del plan B es
> la excepción aceptada: el proveedor la diseñó para ir en el navegador, y lo que se
> arriesga es la cuota del plan.

### Plan B del fondo de los mapas: Stadia Maps (`PROD-05`)

OpenStreetMap no tiene SLA y puede bloquear sin aviso, sobre todo a usos
comerciales (investigación del 06/11/2026 en
[produccion-mosaicos-y-https.md](analisis/produccion-mosaicos-y-https.md)). Si el
fondo de los mapas deja de cargar y la consola del navegador (F12) muestra errores
de `tile.openstreetmap.org` (403, 418 o 429), se pasa al plan B:

1. Crear una cuenta en Stadia Maps con el plan **Starter** (USD 20 al mes). **El plan
   gratuito no sirve: prohíbe el uso comercial.**
2. Crear una **API key** en el panel de Stadia. Para una intranet hace falta la
   clave: la autenticación por dominio usa `Origin`/`Referer`, y Stadia no dice que
   sirva con nombres internos.
3. En `.env.produccion`:

   ```bash
   VITE_MOSAICOS_URL=https://tiles.stadiamaps.com/tiles/osm_bright/{z}/{x}/{y}{r}.png?api_key=LA_CLAVE
   VITE_MOSAICOS_ATRIBUCION=&copy; <a href="https://stadiamaps.com/">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>
   ```

   `osm_bright` es el estilo más parecido al de OpenStreetMap, y el panel le aplica
   el mismo filtro gris oscuro. La atribución es obligatoria y va visible en el
   mapa.
4. Reconstruir y levantar el panel. La política de seguridad toma el dominio nuevo
   sola:

   ```bash
   docker compose --env-file .env.produccion build frontend
   docker compose --env-file .env.produccion up -d frontend
   ```

5. Pedir a TI que deje pasar `tiles.stadiamaps.com` desde la red de los usuarios
   (§3).

Para volver a OpenStreetMap: dejar las dos variables vacías y repetir el paso 4.

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
git checkout v1.0.0                              # la versión a desplegar (§9)
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

Dos scripts, que se corren desde la raíz del repositorio (`PROD-07`). La hora de la
tarea programada y el destino de la copia fuera del servidor los decide TI.

### Respaldar: `scripts/respaldar.sh`

```bash
bash scripts/respaldar.sh                    # respaldo programado
bash scripts/respaldar.sh antes-de-v1.1.0    # con nombre: antes de actualizar (§9)
```

Deja un `pg_dump -Fc` en `respaldos/trackin-AAAAMMDD-HHMMSS.dump`, comprueba que
`pg_restore` lo pueda leer y **borra los programados de más de 14 días**. Los que
llevan nombre (`trackin-antes-de-...`) no se borran solos: se borran a mano cuando ya
no hacen falta. Si algo falla, termina con código distinto de 0 y no borra nada.

| Variable | Omisión | Para qué |
|---|---|---|
| `RESPALDOS_DIR` | `respaldos` | Dónde quedan los respaldos (ya está en `.gitignore`) |
| `RESPALDOS_DIAS` | `14` | Retención de los programados (D17) |
| `RESPALDOS_COPIA` | vacía | Carpeta fuera del servidor (un recurso de red montado) donde además se copia cada respaldo |
| `ENV_FILE` | `.env.produccion` | De ahí toma el usuario y la base |

Para programarlo todos los días a las 02:00, con `crontab -e` del usuario que
administra Docker (ajustar la ruta del repositorio y la copia):

```cron
0 2 * * * cd /opt/trackin && RESPALDOS_COPIA=/mnt/respaldos/trackin bash scripts/respaldar.sh >> respaldos/respaldar.log 2>&1
```

Si TI prefiere tomar la copia con su propia herramienta, `RESPALDOS_COPIA` queda
vacía y TI respalda la carpeta `respaldos/`.

### Restaurar: `scripts/restaurar.sh`

```bash
bash scripts/restaurar.sh respaldos/trackin-20261124-020000.dump
```

**Reemplaza la base entera** por la del respaldo, y pide escribir `restaurar` para
seguir (`--si` lo salta, para usarlo en un script). En orden:

1. Comprueba que el archivo se pueda leer. Si no, no toca nada.
2. Respalda la base actual como `trackin-antes-de-restaurar-...dump`, por si el
   archivo elegido no era el correcto.
3. Detiene la API y el worker, borra y recrea la base, y restaura en una sola
   transacción: o entra todo, o la base queda vacía y el script lo dice.
4. Muestra cuántos pedidos, cuentas y entradas de bitácora volvieron, levanta la
   API y el worker y espera a que `/health` diga `"ok"`.

Lo registrado después del respaldo restaurado se pierde.

**Un respaldo no está verificado hasta que se restaura una vez.** Hacerlo antes
de la salida (`PROD-18`), y anotar cuánto tardó. El 10/11/2026 se probó en
desarrollo, contra el Postgres nativo, con una copia de la base (115 pedidos, 3
cuentas, 17 entradas de bitácora): respaldar, borrar la base, restaurar y volvieron
completos, con la migración `0034` y PostGIS; la base de 115 pedidos ocupa 120 KB
y tarda unos 15 segundos en restaurarse.

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
- Si el contenedor `worker` no corre, `/health` **no lo nota**: las fuentes solo
  dejan de actualizarse. Se ve en `docker compose ps`.

### Vigilancia con aviso (`PROD-08`)

Para enterarse de un problema antes de que lo note Compras. Hay dos caminos, según
lo que tenga TI.

**Si TI tiene una herramienta de monitoreo** (Zabbix, Uptime Kuma, PRTG u otra), se
le entrega esto y la configura TI:

| Qué | Valor |
|---|---|
| URL | `http://<servidor>:8080/health` (o el nombre público, por el proxy), cada 5 minutos, con 15 s de espera |
| Alarma: no responde | Error de conexión, tiempo agotado o código distinto de 200 |
| Alarma: base | `database` distinto de `"up"` |
| Alarma: fuente | Algún elemento de `fuentes` con `degradada: true` y `antiguedad_s` mayor que 3600 (o nulo) |
| Alarma: créditos | `creditos_shipsgo.nivel` distinto de `"OK"` (`SIN_PAQUETE`, `POR_VENCER`, `BAJO`, `AGOTADO`, `VENCIDO`) |
| Alarma: worker | El contenedor `trackin-worker` no está en estado `running` (desde Docker, no desde `/health`) |

**Si no la tiene**, `scripts/vigilar_salud.sh` hace lo mismo desde el servidor y
avisa por correo:

1. TI indica el servidor de correo (un relé interno o una cuenta SMTP) y se
   completan las variables `AVISO_*` de `.env.produccion` (§5): `AVISO_SMTP_URL`,
   `AVISO_SMTP_USUARIO` y `AVISO_SMTP_CLAVE` si pide usuario, `AVISO_DE` y
   `AVISO_PARA` (uno o varios, separados por coma).
2. Probarlo a mano: `bash scripts/vigilar_salud.sh`. Con todo bien no imprime
   nada. Para ver llegar un correo, detener el worker
   (`docker compose --env-file .env.produccion stop worker`), correrlo, y volver a
   levantarlo (`up -d worker`) y correrlo otra vez: llegan el aviso y el «resuelto».
3. Programarlo cada 5 minutos con `crontab -e`, igual que el respaldo (§8):

   ```cron
   */5 * * * * cd /opt/trackin && bash scripts/vigilar_salud.sh >> vigilancia/vigilar.log 2>&1
   ```

Cómo se comporta:

- **Avisa una vez** cuando aparece un problema y **otra vez cuando se resuelve**.
  Mientras sigue igual, no repite. Si cambia (los créditos pasan de `BAJO` a
  `AGOTADO`), vuelve a avisar.
- Si `/health` no responde, lo que ya estaba mal sigue contando como pendiente: no
  se da por resuelto lo que no se pudo revisar.
- Si el correo no sale, termina con error y **reintenta en la próxima corrida**: no
  da por avisado lo que no llegó.
- Sin `AVISO_SMTP_URL`, el aviso queda solo en `vigilancia/vigilar.log`.
- El estado (qué ya se avisó) vive en `vigilancia/problemas`. Borrarlo hace que en la
  próxima corrida se vuelva a avisar todo lo que siga mal.

### Versiones

El servidor corre siempre **una etiqueta de git** `vX.Y.Z`, nunca la rama `main`:
así se sabe qué corre y se puede volver atrás. Qué trae cada versión, y qué
migración, está en [CHANGELOG.md](../CHANGELOG.md).

| Para | Cómo |
|---|---|
| Ver qué versión corre | `curl http://localhost:8080/health` (campo `version`), o el pie del menú **Configuración** del panel |
| Ver qué etiqueta está en la carpeta | `git describe --tags` |
| Ver qué migración tiene la base | `docker compose --env-file .env.produccion run --rm backend alembic current` |

### Actualizar a una versión nueva

```bash
# 1. Respaldar (§8) y anotar el archivo: es lo que permite volver atrás.
bash scripts/respaldar.sh antes-de-vX.Y.Z

# 2. Traer la versión y construirla.
git fetch --tags
git checkout vX.Y.Z
docker compose --env-file .env.produccion build

# 3. Migrar y recrear los servicios.
docker compose --env-file .env.produccion run --rm backend alembic upgrade head
docker compose --env-file .env.produccion up -d

# 4. Verificar.
curl http://localhost:8080/health                # "version" tiene que decir X.Y.Z
```

`up -d` recrea la API, el **worker** y el panel con la imagen nueva: el worker
tiene que reiniciarse en cada actualización, o sigue aplicando las reglas
anteriores.

### Volver a la versión anterior

Si la versión nueva falla, se vuelve a la etiqueta anterior. Lo que decide cómo
es **si la versión nueva traía una migración** (lo dice su entrada en el
[CHANGELOG](../CHANGELOG.md), o comparar `alembic current` antes y después):

- **Sin migración nueva:** basta con el código.

  ```bash
  git checkout vX.Y.(Z-1)
  docker compose --env-file .env.produccion build
  docker compose --env-file .env.produccion up -d
  ```

- **Con migración nueva:** el código viejo no entiende la base nueva. Hay que
  volver el código **y** restaurar el respaldo del paso 1 (§8). Se pierde lo que se
  haya registrado entre la actualización y la vuelta atrás: por eso conviene
  actualizar fuera del horario de uso y decidir rápido.

  ```bash
  git checkout vX.Y.(Z-1)
  docker compose --env-file .env.produccion build
  docker compose --env-file .env.produccion stop backend worker
  docker compose --env-file .env.produccion exec -T postgres \
      pg_restore -U trackin -d trackin --clean --if-exists < trackin-antes-de-vX.Y.Z.dump
  docker compose --env-file .env.produccion up -d
  ```

  No se usa `alembic downgrade`: las 34 migraciones lo tienen escrito, pero
  ninguna prueba lo ejercita, y diez de ellas siembran o transforman datos. El
  respaldo, en cambio, se restaura probado (§8).

### Publicar una versión nueva

Lo hace quien desarrolla, desde su equipo, con el CI en verde:

1. Subir la versión en `backend/app/__init__.py`, `backend/pyproject.toml` y
   `frontend/package.json` (y `package-lock.json`, con `npm install`). La prueba
   `tests/test_version.py` falla si quedan distintas.
2. Agregar la entrada en [CHANGELOG.md](../CHANGELOG.md), con la migración más
   reciente.
3. Hacer el commit, crear la etiqueta y subirla:

   ```bash
   git tag -a vX.Y.Z -m "TrackIn vX.Y.Z"
   git push origin vX.Y.Z
   ```

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
- [ ] HTTPS en el proxy corporativo, con HSTS
- [ ] Docker arranca con el sistema (`systemctl enable docker`) y TrackIn vuelve
      solo tras reiniciar el servidor
- [ ] Desde un equipo de la red: `/docs` no muestra la API, y la consola del
      navegador (F12) no tiene errores «Content Security Policy» con el mapa y el
      detalle abiertos (§4.1)
- [ ] Migraciones aplicadas y primer Administrador creado
- [ ] `/health` con la base `"up"` y ShipsGo sin degradar
- [ ] Paquete de créditos de ShipsGo registrado
- [ ] Salida a internet a `api.shipsgo.com` y a TICA verificada desde el servidor
- [ ] Respaldo programado **y restaurado una vez**
- [ ] `/health` vigilado: por la herramienta de TI o por `vigilar_salud.sh` en
      cron, con un aviso de prueba recibido (§9)
- [ ] Si se usa el mapa embebido: el dominio público en «Allowed HTTP Origins» de
      ShipsGo, y `embed.shipsgo.com` permitido en la red de los usuarios
- [ ] Si SAP va a enviar: `SAP_INTEGRACION_CLAVE` entregada por canal seguro y
      la escucha encendida desde el panel
- [ ] Quién mantiene el sistema, acordado
