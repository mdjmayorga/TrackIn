# Backlog de puesta en producción - TrackIn

Desde hoy hasta la **salida a producción**: TrackIn accesible por HTTPS en la red interna de Gutis, con datos reales, respaldado, vigilado y traspasado al Centro de Competencias.

**Generado:** 6 de noviembre de 2026. **Ejecutor:** Mariano Mayorga, con TI de Gutis para el servidor, la red y el DNS. **Ventana:** preparación del 06/11 al 20/11, en paralelo con el cierre de la práctica; ejecución en la **extensión opcional del cronograma** (23/11 al 04/12)

> **Por qué existe.** Al inicio de la práctica se acordó que, si sobraba tiempo, se
> evaluaría poner TrackIn en producción. El SRS §1.2.2 deja el despliegue fuera del
> alcance y `TASK-09` entregó la [guía de despliegue](../deployment.md) para que lo
> asuma el Centro de Competencias. Al 06/11 el producto está prácticamente cerrado
> (ver [backlog_trackin.md](backlog_trackin.md)), así que este backlog convierte esa guía
> en trabajo planificado. **No modifica el alcance de la práctica**: es la extensión.

> Este backlog se escribió a mano, aparte del backlog principal (que se genera desde un
> script), para no mezclar el alcance de la práctica con la extensión.

## Definition of Done (aplica a todo este backlog)

- Lo hecho está verificado **en el servidor**, no solo en un equipo de desarrollo
- Lo que cambia en el código pasa el CI y queda en la rama principal
- Lo que cambia en la operación queda escrito en `docs/deployment.md` o en el manual de operación (`PROD-28`)
- Ningún secreto queda en el repositorio, en un issue ni en un chat

---

## Decisiones de partida

Salieron del interrogatorio del 06/11/2026 y **Mariano las confirmó ese mismo día**, todas
con la opción recomendada salvo D23 y D24. Greivin ya estaba al tanto de la puesta en
producción en la extensión (D25). Quedan por validar con Compras D4, D16 y D20 (`PROD-02`),
y con TI lo que dependa de su respuesta (`PROD-01`: D2, D9 y el monitoreo de D18). Si alguna
cambia, cambian las tareas que la citan.

| # | Decisión | Opción tomada | Tareas que dependen |
|---|---|---|---|
| D1 | Alcance de la red | Solo la **red interna** de Gutis; desde afuera, por la VPN corporativa | `PROD-16`, `PROD-17` |
| D2 | Servidor | **Máquina virtual Linux con Docker** de TI: 2 vCPU, 4 GB de RAM, 40 GB de disco ([ADR 0002](../adr/0002-produccion-en-maquina-virtual-linux-de-la-red-interna.md)) | `PROD-13`, `PROD-15` |
| D3 | Quién y cuándo | Lo ejecuta Mariano en la extensión; TI pone la infraestructura; salida antes del 04/12 | Todo el backlog |
| D4 | Datos iniciales | **Base vacía**: migraciones, cuentas nuevas, primera carga real del Z-tracking vigente y altas en ShipsGo | `PROD-20`, `PROD-22` |
| D5 | Formato | Este archivo, IDs `PROD-xx`, sin issues en GitHub | — |
| D6 | Nivel de producción | Con respaldos restaurados una vez, monitoreo de `/health` y procedimiento de actualización | `PROD-07`, `PROD-08`, `PROD-18`, `PROD-19` |
| D7 | Nombre | `trackin.gutis.com` (provisorio) en el **DNS interno** | `PROD-16` |
| D8 | HTTPS | **Obligatorio desde el primer día**, con un certificado que emite TI. La pantalla de planta mantiene el monitor encendido con la API Wake Lock, que el navegador solo habilita con HTTPS (o en `localhost`); por HTTP la pantalla completa sí funciona, pero el monitor se apaga **sin ningún aviso**. Ninguna autoridad pública emite certificados para nombres `.local` ni para IP privadas: el nombre tiene que colgar de un dominio real de Gutis, con un certificado público validado por DNS o uno de la autoridad interna distribuida a los equipos | `PROD-16` |
| D9 | Dónde termina el HTTPS | En el **proxy corporativo** si existe; si no, en el nginx del contenedor `frontend` | `PROD-10`, `PROD-16` |
| D10 | Salida a internet | Una **lista blanca**: el servidor a `api.shipsgo.com` y TICA; los navegadores a los mosaicos del mapa y a `embed.shipsgo.com` | `PROD-17` |
| D11 | Mosaicos del mapa | **Seguir con OpenStreetMap**, con la URL sin subdominio y fuera del código, y **Stadia Maps Starter** (USD 20 al mes) listo como plan B. Investigado el 06/11 en [produccion-mosaicos-y-https.md](../analisis/produccion-mosaicos-y-https.md) | `PROD-05` |
| D12 | Cuenta de ShipsGo | **Solo producción da de alta**: el token vive solo en el servidor ([ADR 0003](../adr/0003-solo-produccion-da-de-alta-en-shipsgo.md)) | `PROD-12` |
| D13 | Mapa embebido de ShipsGo | Se mantiene, autorizando el dominio de producción | `PROD-23` |
| D14 | API de SAP | Se despliega con la escucha **apagada** | `PROD-15` |
| D15 | Ensayo | Un **ensayo general en el propio servidor** con datos de prueba; después se reinicia la base. Sin entorno de pruebas aparte | `PROD-20` |
| D16 | Cuentas | La compartida de Compras, personales para Logística y Planificación, una de planta, el Administrador de Mariano y uno de respaldo para TI | `PROD-21` |
| D17 | Respaldos | `pg_dump` diario, **14 días** de retención, una copia fuera del servidor y una restauración probada antes de la salida | `PROD-07`, `PROD-18` |
| D18 | Monitoreo | El de TI si existe; si no, un chequeo de `/health` cada 5 minutos con aviso por correo | `PROD-08`, `PROD-19` |
| D19 | Actualizaciones | Imágenes construidas **en el servidor desde una etiqueta de git** `vX.Y.Z`; volver a la etiqueta anterior si algo falla | `PROD-06`, `PROD-28` |
| D20 | Piloto | **Una semana** usando TrackIn junto al Excel, con criterios de salida acordados con Compras | `PROD-26` |
| D21 | Traspaso | Manual de operación y una sesión de traspaso con el Centro de Competencias | `PROD-28`, `PROD-29` |
| D22 | Destinatario en TI | Por completar al enviar el correo | `PROD-01` |
| D23 | Reunión con TI | **Solo por correo**, sin ofrecer reunión | `PROD-01` |
| D24 | Plazos pedidos a TI | Respuesta el **13/11** y máquina virtual lista el **20/11**, una semana antes de lo recomendado, para tener margen | `PROD-01`, `PROD-13` |
| D25 | Supervisor | Greivin ya sabe que la puesta en producción va en la extensión; el correo a TI va con copia a él | `PROD-01`, `PROD-02` |

---

## Tabla resumen

| ID | Título | Tipo | Fase | MoSCoW | Horas | Depende de | Quién |
|---|---|---|---|---|---|---|---|
| `PROD-01` | Pedir a TI el servidor, el DNS, el certificado y la salida a internet | Task | 0 | **Must** | 3h | — | Mariano + TI |
| `PROD-02` | Confirmar las decisiones de partida con el supervisor y Compras | Task | 0 | **Must** | 2h | — | Mariano |
| `PROD-03` | Ensayo local del stack de contenedores, de punta a punta ✅ | Task | 0 | **Must** | 6h | — | Mariano |
| `PROD-04` | Corregir lo que encuentre el ensayo local ✅ | Task | 0 | **Must** | 4h | `PROD-03` | Mariano |
| `PROD-05` | Mosaicos del mapa: URL sin subdominio, configurable y con plan B | Task | 0 | **Should** | 3h | — | Mariano |
| `PROD-06` | Versionar: etiqueta `v1.0.0`, notas de versión y vuelta atrás | Task | 0 | **Must** | 2h | `PROD-04` | Mariano |
| `PROD-07` | Scripts de respaldo con retención y de restauración | Story | 0 | **Must** | 4h | `PROD-03` | Mariano |
| `PROD-08` | Chequeo de `/health` con aviso | Story | 0 | **Should** | 4h | `PROD-03` | Mariano |
| `PROD-09` | Asistente de instalación del servidor | Task | 0 | **Should** | 3h | `PROD-03` | Mariano |
| `PROD-10` | HTTPS en el nginx de TrackIn (solo si no hay proxy corporativo) | Story | 0 | **Could** | 4h | `PROD-01` | Mariano |
| `PROD-11` | Endurecer la configuración de producción | Task | 0 | **Should** | 3h | `PROD-03` | Mariano |
| `PROD-12` | Sacar el token de ShipsGo de los equipos de desarrollo | Task | 0 | **Must** | 1h | — | Mariano |
| `PROD-13` | Preparar la máquina virtual | Task | 1 | **Must** | 3h | `PROD-01` | TI + Mariano |
| `PROD-14` | Generar y custodiar los secretos de producción | Task | 1 | **Must** | 1h | `PROD-13` | Mariano + TI |
| `PROD-15` | Primer despliegue en el servidor | Task | 1 | **Must** | 4h | `PROD-06`, `PROD-14` | Mariano |
| `PROD-16` | HTTPS y nombre interno, con contexto seguro verificado | Task | 1 | **Must** | 3h | `PROD-15` | TI + Mariano |
| `PROD-17` | Verificar la salida a internet desde el servidor y desde planta | Task | 1 | **Must** | 2h | `PROD-15` | Mariano + TI |
| `PROD-18` | Respaldo programado y restauración probada | Task | 1 | **Must** | 3h | `PROD-07`, `PROD-15` | Mariano + TI |
| `PROD-19` | Monitoreo activo | Task | 1 | **Should** | 2h | `PROD-08`, `PROD-16` | Mariano + TI |
| `PROD-20` | Ensayo general en el servidor y reinicio de la base | Task | 1 | **Must** | 4h | `PROD-16`, `PROD-17`, `PROD-18` | Mariano |
| `PROD-21` | Crear las cuentas reales | Task | 2 | **Must** | 2h | `PROD-20` | Mariano |
| `PROD-22` | Créditos, primera carga real y altas en ShipsGo | Task | 2 | **Must** | 3h | `PROD-20`, `PROD-12` | Mariano + Compras |
| `PROD-23` | Autorizar el dominio en el mapa embebido de ShipsGo | Task | 2 | **Should** | 1h | `PROD-16` | Mariano |
| `PROD-24` | Dejar la pantalla de planta funcionando | Task | 2 | **Should** | 2h | `PROD-21`, `PROD-16` | Mariano + planta |
| `PROD-25` | Inducción de los usuarios con el manual | Task | 2 | **Should** | 3h | `PROD-21` | Mariano |
| `PROD-26` | Piloto de una semana con criterios de salida | Story | 3 | **Must** | 6h | `PROD-22` | Mariano + Compras |
| `PROD-27` | Correcciones del piloto | Task | 3 | **Must** | 8h | `PROD-26` | Mariano |
| `PROD-28` | Manual de operación para el Centro de Competencias | Task | 3 | **Must** | 6h | `PROD-18`, `PROD-19` | Mariano |
| `PROD-29` | Sesión de traspaso y acta | Task | 3 | **Must** | 3h | `PROD-28` | Mariano + Centro de Competencias |
| `PROD-30` | Cerrar el checklist de salida y declarar la salida a producción | Task | 3 | **Must** | 1h | `PROD-26`, `PROD-29` | Mariano |

**Total: 96 h.** Fase 0: 39 h; fase 1: 22 h; fase 2: 11 h; fase 3: 24 h.

---

## Capacidad y calendario

| Fase | Fechas | Horas | Capacidad | Comentario |
|---|---|---|---|---|
| **0. Preparación sin servidor** | 06/11 al 20/11 | 39 h (22 h de `Must`) | Lo que deje libre el cierre | El cierre ya adelantó `TASK-06`, `TASK-07` y `TASK-09`; quedan las capturas del manual y el informe final, que **tienen prioridad** |
| **1. Servidor** | 23/11 al 26/11 | 22 h | 26 h | Arranca solo si TI entregó la máquina virtual |
| **2. Salida** | 27/11 al 30/11 | 11 h | 13 h | La primera carga real se coordina con Compras |
| **3. Piloto y traspaso** | 30/11 al 04/12 | 24 h | 26 h | El piloto corre en paralelo con el manual de operación |

**Nota sobre la fase 0.** Las `Must` de la fase 0 suman 22 h (`PROD-01`, `02`, `03`, `04`, `06`, `07`, `12`). Si el cierre no deja más tiempo, las `Should` y la `Could` pasan a la fase 1 y la fase 1 se sobrecarga: en ese caso se recorta `PROD-25` (la inducción se hace con el manual) y `PROD-19` queda a cargo de TI.

**Ruta crítica.** `PROD-01` → `PROD-13` → `PROD-15` → `PROD-16` → `PROD-20` → `PROD-22` → `PROD-26` → `PROD-30`. El primer eslabón depende de TI, no de TrackIn: **`PROD-01` tiene que salir esta semana.** Si la máquina virtual no está el 23/11, la salida se corre lo mismo que se demore, y el piloto ya no entra antes del 04/12.

### Riesgos

| Riesgo | Efecto | Qué se hace |
|---|---|---|
| R1. TI no entrega la máquina virtual a tiempo | Se corre toda la fase 1 | Pedirla ya, para el 20/11 y no el 23/11 (`PROD-01`, D24): hay tres días hábiles de margen; mientras, todo lo que se puede probar se prueba en el ensayo local (`PROD-03`) |
| R2. TI solo tiene servidores Windows | Cambia D2 | La guía ya cubre la variante sin Docker (§10); suma unas 6 h a `PROD-15` |
| R3. Las imágenes nunca se construyeron | El primer `docker compose build` falla en el servidor | **Cerrado el 06/11** por `PROD-03`: se construyen y el stack funciona; quedó un solo defecto (el chequeo de salud del panel), para `PROD-04` |
| R4. El Z-tracking llega con pocas referencias | Desde el 04/11 la línea sin referencia no entra: el panel arranca con pocos pedidos | Pedir a Compras, antes de `PROD-22`, que complete BL o guía madre en SAP |
| R5. Un equipo de desarrollo gasta créditos reales | El saldo no coincide y se pierden créditos | `PROD-12` ([ADR 0003](../adr/0003-solo-produccion-da-de-alta-en-shipsgo.md)) |
| R6. La red de planta bloquea los mosaicos o `embed.shipsgo.com` | Mapas sin fondo o sin mapa en vivo | `PROD-17` lo verifica desde un equipo de planta; `PROD-05` evalúa alternativas |
| R7. Nadie asume la operación después del 04/12 | El sistema queda sin dueño | `PROD-01` y `PROD-29` lo nombran por escrito; sin ese nombre no se declara la salida (`PROD-30`) |

---

## Detalle por fase

### Fase 0: preparación sin servidor (06/11 al 20/11)

#### `PROD-01` — Pedir a TI el servidor, el DNS, el certificado y la salida a internet

Como responsable de TrackIn, quiero una solicitud formal a TI con todo lo que hace falta, para que la infraestructura esté lista el 23/11.

**Criterios de aceptación**

- Dada la solicitud, cuando TI la recibe, entonces pide en un solo documento: la máquina virtual (D2), el nombre interno (D7), el certificado y quién termina el HTTPS (D8, D9), la lista blanca de salida (D10, con los cuatro destinos de `docs/deployment.md` §3), dónde se guardan los respaldos y los secretos (D17), el monitoreo disponible (D18) y quién administra el servidor
- Dada la respuesta de TI, cuando llega, entonces queda anotada aquí con la fecha comprometida de entrega de la máquina virtual
- Dado que TI no tiene Linux, cuando lo responde, entonces se reabre D2 y el [ADR 0002](../adr/0002-produccion-en-maquina-virtual-linux-de-la-red-interna.md)

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Must** |
| Estimación | 3 h |
| Origen | `docs/deployment.md` §2 «Decisiones previas con TI» |
| Etiquetas | `infraestructura,ti,ruta-critica` |

> **06/11/2026: correo listo para enviar** en [correo_ti_produccion.md](correo_ti_produccion.md),
> con los nueve pedidos, ajustado con D1 a D25: solo por correo, respuesta el 13/11 y
> máquina virtual el 20/11. Suma a la lista blanca dos destinos que la guía no tenía y que
> el servidor necesita para instalar: `github.com` (el código) y Docker Hub (las imágenes
> base). **Falta:** poner el destinatario en TI (D22) y enviarlo.

#### `PROD-02` — Confirmar las decisiones de partida con el supervisor y Compras

Como responsable de TrackIn, quiero las decisiones D1 a D21 confirmadas por quien corresponde, para no construir sobre supuestos.

**Criterios de aceptación**

- Dadas D1, D3, D6 y D21, cuando se revisan con el supervisor, entonces quedan confirmadas o cambiadas, con la fecha
- Dadas D4, D16 y D20, cuando se revisan con Compras, entonces quedan confirmadas, y los criterios de salida del piloto quedan acordados (`PROD-26`)
- Dada una decisión que cambia, cuando se registra, entonces se actualizan las tareas que la citan

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Must** |
| Estimación | 2 h |
| Origen | Interrogatorio del 06/11/2026 |
| Etiquetas | `decision` |

> **06/11/2026: confirmadas por Mariano** D1 a D25; la parte del supervisor no hace falta
> (D25). **Falta:** validar con Compras D4, D16 (y los nombres de las cuentas) y D20, con
> los criterios de salida del piloto.

#### `PROD-03` — Ensayo local del stack de contenedores, de punta a punta

Como responsable de TrackIn, quiero construir y levantar las imágenes de producción en un equipo propio, para que el primer `docker compose build` no sea en el servidor.

**Criterios de aceptación**

- Dado `docker-compose.yml` con un `.env.produccion` de ensayo, cuando corro `build` y `up -d`, entonces los cuatro servicios quedan `running` y `backend` y `frontend`, además, `healthy`
- Dado el stack levantado, cuando sigo `docs/deployment.md` §7 al pie de la letra, entonces migraciones, primer Administrador, inicio de sesión por `http://localhost:8080`, una carga del Z-tracking y un ciclo del worker funcionan
- Dado el panel servido por nginx, cuando lo recorro, entonces la grilla, los mapas, el detalle, la carga de un archivo de 15 MB y las acciones funcionan por el mismo origen, sin errores de CORS en la consola
- Dado `ENVIRONMENT=production`, cuando la API arranca con la `SECRET_KEY` de desarrollo, entonces se niega a arrancar
- Dado lo que no funcionó, cuando termina el ensayo, entonces cada problema queda listado para `PROD-04`

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Must** |
| Estimación | 6 h |
| Origen | Riesgo R3: «No se construyeron imágenes» (`docs/deployment.md`, estado al 03/11). Este equipo sí corre Docker |
| Etiquetas | `contenedores,ensayo,ruta-critica` |

> **✅ Hecha el 06/11/2026**, en este equipo (Docker 28.0.4, compose 2.34), con `.env.ensayo`
> (ignorado por git, secretos nuevos, **sin token de ShipsGo**: [ADR 0003](../adr/0003-solo-produccion-da-de-alta-en-shipsgo.md)).
> Se siguió `docs/deployment.md` §7 tal cual. Riesgo R3 cerrado: las imágenes se construyen.
>
> | Criterio | Resultado |
> |---|---|
> | `build` y `up -d` | ✅ Las dos imágenes se construyen sin errores: `trackin-backend` 729 MB, `trackin-frontend` 75 MB. Los cuatro servicios arrancan; `postgres` y `backend`, `healthy` |
> | `frontend` `healthy` | ❌ **Queda `unhealthy`** aunque sirve bien. Su `HEALTHCHECK` consulta `http://localhost/`, que dentro del contenedor resuelve a IPv6 (`::1`), y nginx escucha solo en IPv4: «Connection refused». Con `127.0.0.1` responde. Va a `PROD-04` |
> | Guía §7 | ✅ Migraciones hasta `0034`, primer Administrador, `/health` con la base `"up"`, PostGIS 3.6 y `"SIN_PAQUETE"`. El worker arranca, avisa que no tiene token y corre su ciclo con TICA |
> | Panel por el mismo origen | ✅ Inicio de sesión, panel, mosaicos del mapa, detalle de un pedido y entrada directa a `/pedidos/1` (nginx devuelve `index.html`), sin errores en la consola |
> | Carga del Z-tracking | ✅ La plantilla descargada por nginx, con una línea con contenedor y otra sin referencia: entra una y se rechaza la otra. El WK38 de septiembre se rechaza entero, como corresponde: es anterior a las columnas de documento de embarque |
> | Archivo de 15 MB | ✅ Pasa nginx (la API lo rechaza por no ser un Excel, que era lo esperado con un archivo aleatorio). Uno de 22 MB lo corta nginx con 413: el límite de 21 MB funciona |
> | Acciones | ✅ Registrar ETA desde la API: guarda y recalcula |
> | Clave de desarrollo | ✅ Con `ENVIRONMENT=production` y la `SECRET_KEY` de desarrollo, la API no arranca y dice por qué |
> | Persistencia | ✅ `docker compose down` y `up -d`: el pedido y la cuenta siguen. Un `pg_dump` de esta base pesa 88 KB |
>
> **Hallazgos para las tareas siguientes:**
>
> - `PROD-04`: el `HEALTHCHECK` del `frontend` (una línea en `frontend/Dockerfile`: `127.0.0.1` en vez de `localhost`).
> - `PROD-06`: `/health` y el arranque dicen **versión `0.1.0`**; la versión no se actualizó nunca.
> - `PROD-11`: nginx anuncia su versión (`Server: nginx/1.27.5`) y no manda cabeceras de seguridad. La documentación de la API (`/docs`, `/openapi.json`) **no** queda expuesta: nginx solo reenvía `/api/` y `/health`. Las sesiones no van en cookies sino en un token que el panel guarda en `sessionStorage` (o `localStorage` con «Recordar sesión»): el criterio de las cookies se reemplaza por uno sobre el token.
> - La imagen del backend pesa 729 MB (pandas, GeoAlchemy2 y compañía). No bloquea; se puede achicar después.
>
> El stack de ensayo sigue en este equipo: `docker compose --env-file .env.ensayo down -v` lo borra con su base.

#### `PROD-04` — Corregir lo que encuentre el ensayo local

Como responsable de TrackIn, quiero corregidos los problemas del ensayo local, para llegar al servidor con artefactos probados.

**Criterios de aceptación**

- Dado cada problema de `PROD-03`, cuando se corrige, entonces el cambio pasa el CI y la guía de despliegue refleja lo nuevo
- Dado el ensayo repetido desde cero (`docker compose down -v` y vuelta a empezar), cuando termina, entonces no aparece ningún problema nuevo

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Must** |
| Estimación | 4 h (reserva) |
| Origen | `PROD-03` |
| Etiquetas | `contenedores` |

> **✅ Hecha el 06/11/2026, en 1 h de las 4 de reserva.** El ensayo dejó un solo defecto:
> el `HEALTHCHECK` de `frontend/Dockerfile` pasa a consultar `127.0.0.1` en vez de
> `localhost`. Ensayo repetido desde cero (`down -v`, `build`, migraciones, Administrador,
> `up -d`, carga de la plantilla): `postgres`, `backend` y `frontend` quedan `healthy`, la
> carga entra igual y no hay errores en los logs. La guía de despliegue actualizó su estado
> (ya no dice que las imágenes no se construyeron) y la descripción del `Dockerfile` del
> panel.
>
> **CI:** el CI no construye imágenes (corre pruebas, lint y tipos del backend y del panel),
> así que el cambio no lo afecta; la verificación de este cambio es el ensayo. Que el CI
> construya las imágenes en cada cambio sería una mejora aparte: evitaría que un
> `Dockerfile` se rompa sin que nadie lo note hasta el servidor.

#### `PROD-05` — Mosaicos del mapa: URL sin subdominio, configurable y con plan B

Como usuario del panel, quiero que el fondo de los mapas cargue siempre, para que la pantalla de planta no quede en gris.

**Criterios de aceptación**

- Dada la URL de los mosaicos, cuando se cambia, entonces es `https://tile.openstreetmap.org/{z}/{x}/{y}.png`, **sin** el subdominio `{s}`, que la política vigente ya no recomienda
- Dada la URL y su atribución, cuando salen del código (`MOSAICOS` en `frontend/src/components/MapaBase.tsx`), entonces se configuran con variables `VITE_*` con el valor de OpenStreetMap por omisión, y pasar al plan B es cambiar esas variables y reconstruir el panel, sin tocar el código
- Dado el plan B (Stadia Maps Starter), cuando se documenta en la guía de despliegue, entonces dice qué variables cambiar, que pide una clave y que el plan gratuito no sirve (prohíbe el uso comercial)
- Dada la lista blanca, cuando se pide a TI (`PROD-01`), entonces dice `tile.openstreetmap.org`, no `*.tile.openstreetmap.org`, y `docs/deployment.md` §3 se corrige igual
- Dada la pantalla de planta, cuando se mide un día, entonces confirma que el refresco automático no vuelve a pedir mosaicos (pide datos a la API), que es lo que deja el uso dentro de la política

> **06/11/2026: investigado** en [produccion-mosaicos-y-https.md](../analisis/produccion-mosaicos-y-https.md).
> El uso de TrackIn cumple la política (atribución visible, navegador, caché, volumen
> bajo), pero el servicio no tiene SLA, puede bloquear sin aviso y advierte que a los
> servicios comerciales se les puede retirar el acceso: por eso el plan B queda listo.

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Should** |
| Estimación | 3 h |
| Origen | D11. Investigación en `docs/analisis/produccion-mosaicos-y-https.md` |
| Etiquetas | `mapas,frontend` |

#### `PROD-06` — Versionar: etiqueta `v1.0.0`, notas de versión y vuelta atrás

Como técnico del Centro de Competencias, quiero saber qué versión corre en el servidor y cómo volver a la anterior, para actualizar sin miedo.

**Criterios de aceptación**

- Dado el código que pasó `PROD-04`, cuando se etiqueta, entonces existe `v1.0.0` en GitHub con notas de versión: qué hace el sistema, la migración más reciente (`0034` o la que corresponda) y los cambios respecto del Informe 2
- Dada la guía de despliegue, cuando describe la actualización, entonces usa `git checkout vX.Y.Z` en vez de `git pull`, y explica cómo volver a la etiqueta anterior **y** qué hacer con la base si la versión nueva traía una migración (restaurar el respaldo previo, `PROD-07`)
- Dado `/health` o el pie del panel, cuando se consulta, entonces dice qué versión corre

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Must** |
| Estimación | 2 h |
| Origen | D19 |
| Etiquetas | `versionado,documentacion` |

#### `PROD-07` — Scripts de respaldo con retención y de restauración

Como técnico del Centro de Competencias, quiero respaldar y restaurar la base con un solo comando, para no depender de recordar los parámetros de `pg_dump`.

**Criterios de aceptación**

- Dado `scripts/respaldar.sh`, cuando corre, entonces deja un `pg_dump -Fc` con fecha en el directorio configurado, borra los de más de 14 días y termina con código distinto de 0 si algo falla
- Dado `scripts/restaurar.sh <archivo>`, cuando corre, entonces detiene `backend` y `worker`, restaura sobre la base, los vuelve a levantar y verifica `/health`
- Dado el ensayo local (`PROD-03`), cuando se respalda, se borra la base y se restaura, entonces los pedidos, las cuentas y la bitácora vuelven completos
- Dada la copia fuera del servidor, cuando TI define el destino, entonces el script la deja allí (o queda documentado cómo la toma TI)

| | |
|---|---|
| Tipo | Story |
| MoSCoW | **Must** |
| Estimación | 4 h |
| Origen | D17, `docs/deployment.md` §8 |
| Etiquetas | `respaldos,operacion` |

#### `PROD-08` — Chequeo de `/health` con aviso

Como responsable de TrackIn, quiero enterarme si el sistema cae o ShipsGo deja de responder, para no descubrirlo cuando Compras pregunta.

**Criterios de aceptación**

- Dado que TI tiene una herramienta de monitoreo, cuando se le entrega la especificación (URL de `/health`, qué campos mirar y los umbrales), entonces TI la configura y esta tarea solo la documenta
- Dado que no la tiene, cuando corre `scripts/vigilar_salud.sh` cada 5 minutos, entonces avisa por correo si `/health` no responde, si `database` no es `"up"`, si una fuente lleva más de una hora degradada o si `creditos_shipsgo.nivel` pide atención; y no repite el mismo aviso en cada corrida
- Dado el aviso, cuando el problema se resuelve, entonces llega un segundo correo que lo dice

| | |
|---|---|
| Tipo | Story |
| MoSCoW | **Should** |
| Estimación | 4 h |
| Origen | D18, `docs/deployment.md` §9 «Qué mirar en `/health`» |
| Etiquetas | `monitoreo,operacion` |

#### `PROD-09` — Asistente de instalación del servidor

Como técnico que instala TrackIn, quiero un asistente que me lleve paso a paso por lo que solo una persona puede hacer, para no saltarme nada del primer despliegue.

**Criterios de aceptación**

- Dado `scripts/asistente_produccion.sh`, cuando lo corro en el servidor, entonces me guía por los pasos de `PROD-13` a `PROD-18`, verifica lo que se puede verificar (Docker, compose, `.env.produccion` completo, salida a internet, `/health`) y se detiene con un mensaje claro si algo falla
- Dado un paso que ya está hecho, cuando lo vuelvo a correr, entonces lo detecta y lo salta
- Dado un secreto, cuando el asistente lo genera, entonces lo escribe en `.env.produccion` y nunca lo muestra en pantalla

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Should** |
| Estimación | 3 h |
| Origen | Habilitador de `PROD-13` a `PROD-18` |
| Etiquetas | `operacion,automatizacion` |

> **06/11/2026: primera versión hecha** en [`scripts/asistente_produccion.sh`](../../scripts/asistente_produccion.sh). Falta probarla en el ensayo local (`PROD-03`) y en el servidor.

#### `PROD-10` — HTTPS en el nginx de TrackIn (solo si no hay proxy corporativo)

Como usuario de la red, quiero entrar a TrackIn por HTTPS aunque TI no tenga un proxy, para que la conexión sea segura y la pantalla de planta funcione.

**Criterios de aceptación**

- Dado que `PROD-01` confirma que no hay proxy corporativo, cuando se activa esta tarea, entonces el contenedor `frontend` escucha en 443 con el certificado y la llave que entrega TI, montados como archivos (no dentro de la imagen), y redirige 80 a 443
- Dado el certificado, cuando vence, entonces la guía dice cómo reemplazarlo sin reconstruir la imagen
- Dado que sí hay proxy, cuando `PROD-01` lo confirma, entonces esta tarea se cancela

| | |
|---|---|
| Tipo | Story |
| MoSCoW | **Could** |
| Estimación | 4 h |
| Origen | D9 |
| Etiquetas | `https,contenedores,condicional` |

#### `PROD-11` — Endurecer la configuración de producción

Como responsable de TrackIn, quiero revisada la configuración que cambia entre desarrollo y producción, para no salir con valores de desarrollo.

**Criterios de aceptación**

- Dado `/docs` y `/openapi.json` de la API, cuando se consultan en producción, entonces se decide y aplica si quedan accesibles (recomendado: solo para el Administrador, o apagados)
- Dado el token de sesión (va en `sessionStorage` o `localStorage`, no en cookies: `PROD-03`), cuando se revisa, entonces el panel no carga scripts de terceros que puedan leerlo, y nginx manda una `Content-Security-Policy` que lo limite, compatible con los mosaicos y el mapa embebido
- Dado `server_tokens`, cuando nginx responde, entonces no anuncia su versión
- Dado nginx, cuando responde, entonces agrega las cabeceras de seguridad básicas (`X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options` o `frame-ancestors`) sin romper el mapa embebido de ShipsGo
- Dados los logs, cuando corren semanas, entonces Docker los rota (`max-size` y `max-file` en `docker-compose.yml`) y no llenan el disco
- Dado `restart: unless-stopped` en los cuatro servicios, cuando el servidor se reinicia, entonces TrackIn vuelve solo

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Should** |
| Estimación | 3 h |
| Origen | Checklist de `docs/deployment.md` §11 y revisión del 06/11 |
| Etiquetas | `seguridad,contenedores` |

#### `PROD-12` — Sacar el token de ShipsGo de los equipos de desarrollo

Como responsable de los créditos de ShipsGo, quiero que solo producción pueda dar de alta, para no gastar créditos reales en pruebas.

**Criterios de aceptación**

- Dado el día de la salida, cuando se registra el paquete en producción, entonces el `SHIPSGO_API_TOKEN` se borra de los `.env` de los dos equipos de desarrollo
- Dado un equipo de desarrollo sin token, cuando se corren las pruebas, entonces pasan (usan los payloads grabados)
- Dado `docs/manual-instalacion.md`, cuando habla del token, entonces advierte que la cuenta es una sola y remite al [ADR 0003](../adr/0003-solo-produccion-da-de-alta-en-shipsgo.md)

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Must** |
| Estimación | 1 h |
| Origen | D12 |
| Etiquetas | `shipsgo,creditos` |

### Fase 1: servidor (23/11 al 26/11)

#### `PROD-13` — Preparar la máquina virtual

Como técnico que instala TrackIn, quiero la máquina virtual lista para Docker, para desplegar sin pelear con el sistema operativo.

**Criterios de aceptación**

- Dada la máquina virtual de TI, cuando se prepara, entonces tiene Docker Engine 24 o superior, el plugin `compose` 2.24 o superior y Git (`docs/deployment.md` §6)
- Dado el firewall, cuando se revisa, entonces solo acepta el puerto del panel (y SSH para quien administra) desde la red interna
- Dado el repositorio, cuando se clona, entonces queda en la etiqueta `v1.0.0` (`PROD-06`) en una ruta que TI conoce
- Dado el reloj, cuando se revisa, entonces está sincronizado (NTP) y en la zona horaria correcta: las fechas del panel dependen de él

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Must** |
| Estimación | 3 h |
| Origen | D2 |
| Etiquetas | `infraestructura,ti,ruta-critica` |

#### `PROD-14` — Generar y custodiar los secretos de producción

Como responsable de TrackIn, quiero secretos nuevos y guardados donde TI guarda los suyos, para que nadie más los tenga.

**Criterios de aceptación**

- Dado `.env.produccion`, cuando se completa, entonces `POSTGRES_PASSWORD` y `SECRET_KEY` son nuevos, generados en el servidor, y ninguno coincide con los de desarrollo
- Dado `SHIPSGO_API_TOKEN`, cuando se copia al servidor, entonces se hace por un canal seguro y no queda en ningún chat ni correo
- Dado `.env.produccion`, cuando queda listo, entonces solo lo puede leer el usuario que corre Docker, y TI tiene una copia en su custodia (D17)

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Must** |
| Estimación | 1 h |
| Origen | `docs/deployment.md` §5 |
| Etiquetas | `seguridad,secretos` |

#### `PROD-15` — Primer despliegue en el servidor

Como técnico que instala TrackIn, quiero el stack corriendo en el servidor, para empezar a verificarlo por la red.

**Criterios de aceptación**

- Dado `docs/deployment.md` §7, cuando se sigue en el servidor, entonces se cumplen sus tres verificaciones
- Dada la integración con SAP, cuando se revisa en el panel, entonces la escucha está apagada (D14)
- Dado lo que la guía no decía o decía mal, cuando aparece, entonces se corrige en la guía el mismo día

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Must** |
| Estimación | 4 h |
| Origen | `docs/deployment.md` §7 |
| Etiquetas | `despliegue,ruta-critica` |

#### `PROD-16` — HTTPS y nombre interno, con contexto seguro verificado

Como usuario de la red de Gutis, quiero entrar a `https://trackin.gutis.com` sin advertencias del navegador, para confiar en el sistema.

**Criterios de aceptación**

- Dado un equipo de la red, cuando abro el nombre interno, entonces el navegador muestra el candado sin advertencias (el certificado es de una autoridad en la que confían los equipos de Gutis)
- Dado `http://`, cuando lo abro, entonces redirige a `https://`
- Dada la pantalla de planta, cuando activo **Pantalla completa**, entonces el monitor no se apaga (la API de pantalla permanente está disponible porque el contexto es seguro)
- Dado un equipo conectado por la VPN, cuando abro el nombre, entonces también entra (D1)
- Dado `BACKEND_CORS_ORIGINS`, cuando se completa, entonces tiene el dominio con `https`

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Must** |
| Estimación | 3 h |
| Origen | D7, D8, D9 |
| Etiquetas | `https,dns,ti,ruta-critica` |

#### `PROD-17` — Verificar la salida a internet desde el servidor y desde planta

Como responsable de TrackIn, quiero comprobado que cada destino externo responde desde donde se usa, para no descubrir un bloqueo el día de la salida.

**Criterios de aceptación**

- Dado el servidor, cuando consulto `api.shipsgo.com` y TICA desde el contenedor `worker`, entonces responden
- Dado un equipo de la red de planta, cuando abro el panel, entonces los mapas tienen fondo (mosaicos de `PROD-05`) y el detalle de un pedido con referencia muestra el mapa de ShipsGo
- Dado un bloqueo, cuando aparece, entonces se pide a TI con el destino exacto y queda anotado

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Must** |
| Estimación | 2 h |
| Origen | D10, `docs/deployment.md` §3 |
| Etiquetas | `red,ti` |

#### `PROD-18` — Respaldo programado y restauración probada

Como técnico del Centro de Competencias, quiero respaldos diarios que ya se restauraron una vez, para saber que sirven.

**Criterios de aceptación**

- Dado `scripts/respaldar.sh` (`PROD-07`), cuando se programa, entonces corre todos los días a una hora sin uso y deja la copia fuera del servidor (D17)
- Dado un respaldo del servidor, cuando se restaura (en el ensayo de `PROD-20`, antes de reiniciar la base), entonces el sistema vuelve completo, y queda anotado cuánto tardó
- Dado un respaldo que falla, cuando pasa, entonces lo avisa el monitoreo (`PROD-19`)

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Must** |
| Estimación | 3 h |
| Origen | D17, `docs/deployment.md` §8 |
| Etiquetas | `respaldos,ti` |

#### `PROD-19` — Monitoreo activo

Como responsable de TrackIn, quiero el monitoreo de `PROD-08` funcionando en el servidor, para enterarme de una caída antes que los usuarios.

**Criterios de aceptación**

- Dado el monitoreo, cuando detengo el contenedor `backend` a propósito, entonces llega el aviso en menos de 10 minutos, y al levantarlo, el de recuperación
- Dado el aviso, cuando llega, entonces va a quien opera el sistema (Mariano durante la extensión, después quien nombre `PROD-29`)

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Should** |
| Estimación | 2 h |
| Origen | D18 |
| Etiquetas | `monitoreo,ti` |

#### `PROD-20` — Ensayo general en el servidor y reinicio de la base

Como responsable de TrackIn, quiero recorrer el sistema completo en el servidor con datos de prueba, para que la salida no sea la primera vez.

**Criterios de aceptación**

- Dado el servidor con HTTPS, cuando cargo un Z-tracking de prueba, entonces se cumple el recorrido de `TASK-06` por la red: carga, rastreo, grilla, mapas, detalle, acciones y cierre
- Dada la restauración de `PROD-18`, cuando se prueba, entonces se hace aquí, con estos datos
- Dado el ensayo terminado, cuando se reinicia la base (`docker compose down -v`, `up -d postgres`, `alembic upgrade head`, primer Administrador), entonces producción arranca vacía (D4, D15) y **no se gastó ningún crédito** en el ensayo

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Must** |
| Estimación | 4 h |
| Origen | D15 |
| Etiquetas | `ensayo,ruta-critica` |

### Fase 2: salida (27/11 al 30/11)

#### `PROD-21` — Crear las cuentas reales

Como Administrador, quiero las cuentas de cada rol creadas, para que cada persona entre con la suya.

**Criterios de aceptación**

- Dadas las cuentas de D16, cuando se crean desde **Configuración → Usuarios**, entonces existen con su rol y una contraseña inicial
- Dada cada contraseña inicial, cuando se entrega, entonces va por un medio seguro y la persona la cambia al entrar (`US-61`)
- Dado el Administrador de respaldo de TI, cuando se crea, entonces TI confirma que entra

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Must** |
| Estimación | 2 h |
| Origen | D16, `docs/manual-usuario.md` §11.1 |
| Etiquetas | `cuentas` |

#### `PROD-22` — Créditos, primera carga real y altas en ShipsGo

Como usuario de Compras, quiero los pedidos vigentes en TrackIn y rastreándose, para empezar a usarlo.

**Criterios de aceptación**

- Dado el paquete de créditos comprado, cuando se registra en **Altas en ShipsGo → Registrar paquete comprado**, entonces `/health` deja de decir `"SIN_PAQUETE"` y `altas_maximas_dia` queda en un valor acorde con la carga inicial (`US-57`)
- Dado el Z-tracking vigente, cuando Compras lo carga, entonces el informe de la carga se revisa con Compras línea por línea rechazada, y lo que haya que corregir en SAP queda anotado
- Dadas las referencias nuevas, cuando se dan de alta, entonces a las pocas horas los pedidos salen de **Sin Tracking** y aparecen en los mapas
- Dado `PROD-12`, cuando termina esta tarea, entonces el token ya no está en los equipos de desarrollo

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Must** |
| Estimación | 3 h |
| Origen | D4, `US-55`, `US-57` (la prueba real que quedó pendiente) |
| Etiquetas | `datos,shipsgo,ruta-critica` |

#### `PROD-23` — Autorizar el dominio en el mapa embebido de ShipsGo

Como usuario, quiero ver el mapa en vivo de ShipsGo en el detalle del pedido, como en desarrollo.

**Criterios de aceptación**

- Dado `https://trackin.gutis.com`, cuando se agrega a «Allowed HTTP Origins» de la cuenta de ShipsGo, entonces el detalle de un pedido con referencia muestra el mapa en vivo
- Dado `VITE_SHIPSGO_EMBED_TOKEN`, cuando se fija en la construcción de la imagen, entonces es el token del mapa, no el de la API

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Should** |
| Estimación | 1 h |
| Origen | D13, `docs/informes/novedades_proximo_informe.md` |
| Etiquetas | `shipsgo,mapas` |

#### `PROD-24` — Dejar la pantalla de planta funcionando

Como persona de planta, quiero el monitor mostrando TrackIn todo el día, sin que nadie lo toque.

**Criterios de aceptación**

- Dado el equipo del monitor, cuando entra con la cuenta de planta, **Recordar sesión** y **Pantalla completa**, entonces el carrusel corre y el monitor no se apaga
- Dado un corte de luz o de red, cuando el equipo vuelve, entonces queda documentado qué hace falta para recuperar la pantalla (idealmente: el navegador abre TrackIn al iniciar)
- Dado un día completo, cuando se revisa al final, entonces la pantalla sigue mostrando datos frescos

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Should** |
| Estimación | 2 h |
| Origen | `US-33`, `docs/manual-usuario.md` §12 |
| Etiquetas | `planta` |

#### `PROD-25` — Inducción de los usuarios con el manual

Como usuario de TrackIn, quiero una inducción corta con el manual, para empezar a usarlo sin depender de Mariano.

**Criterios de aceptación**

- Dado el manual de usuario con sus capturas (`TASK-08`), cuando se entrega, entonces cada rol tiene una sesión corta sobre sus tareas
- Dadas las dudas de la sesión, cuando no están en el manual, entonces se agregan

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Should** |
| Estimación | 3 h |
| Origen | `TASK-08` |
| Etiquetas | `usuarios,documentacion` |

### Fase 3: piloto y traspaso (30/11 al 04/12)

#### `PROD-26` — Piloto de una semana con criterios de salida

Como usuario de Compras, quiero usar TrackIn junto al Excel durante una semana, para confiar en él antes de dejar el proceso anterior.

**Criterios de aceptación**

- Dados los criterios acordados en `PROD-02`, cuando termina la semana, entonces cada uno se evalúa con evidencia. Propuestos: el sistema estuvo disponible en horario laboral; la carga semanal se hizo desde TrackIn; las fechas proyectadas de una muestra de pedidos coinciden con lo que sabe Compras, o la diferencia tiene explicación; ningún error bloqueó una tarea
- Dado cada problema del piloto, cuando aparece, entonces queda anotado con su gravedad para `PROD-27`
- Dados los criterios cumplidos, cuando Compras lo confirma, entonces TrackIn pasa a ser la fuente oficial del seguimiento

| | |
|---|---|
| Tipo | Story |
| MoSCoW | **Must** |
| Estimación | 6 h (seguimiento durante la semana) |
| Origen | D20 |
| Etiquetas | `piloto,usuarios` |

#### `PROD-27` — Correcciones del piloto

Como usuario de TrackIn, quiero corregido lo que bloqueó o confundió en el piloto.

**Criterios de aceptación**

- Dado cada problema grave del piloto, cuando se corrige, entonces sale en una versión nueva (`v1.0.1` o la que corresponda) por el procedimiento de actualización, con respaldo previo
- Dado un problema menor que no entra, cuando termina la extensión, entonces queda en el manual de operación como pendiente conocido

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Must** |
| Estimación | 8 h (reserva) |
| Origen | Cronograma, «Correcciones derivadas de la validación con usuarios» (23/11 al 27/11) |
| Etiquetas | `correcciones` |

#### `PROD-28` — Manual de operación para el Centro de Competencias

Como técnico del Centro de Competencias, quiero un manual de operación del TrackIn que está en producción, para mantenerlo sin el autor.

**Criterios de aceptación**

- Dado el manual, cuando lo leo, entonces dice dónde está todo (servidor, ruta, `.env.produccion`, respaldos, monitoreo), cómo actualizar y volver atrás, cómo restaurar, qué mirar en `/health`, qué hacer ante los problemas de `docs/deployment.md` §9 y las tareas periódicas (carga semanal, créditos, renovación del certificado, revisión de respaldos)
- Dado el manual, cuando lo comparo con `docs/deployment.md`, entonces no la repite: la guía dice cómo instalar en cualquier servidor; el manual, cómo operar **este**
- Dadas las cuentas y los secretos, cuando el manual los menciona, entonces dice dónde están, nunca su valor

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Must** |
| Estimación | 6 h |
| Origen | D21 |
| Etiquetas | `documentacion,traspaso` |

#### `PROD-29` — Sesión de traspaso y acta

Como Centro de Competencias, quiero recibir TrackIn en una sesión con el autor, para asumirlo con todo claro.

**Criterios de aceptación**

- Dada la sesión, cuando termina, entonces el técnico que recibe hizo él mismo, con el manual, una actualización de prueba y una restauración
- Dada el acta, cuando se firma, entonces nombra quién opera el sistema, quién administra el servidor y quién responde por los créditos de ShipsGo

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Must** |
| Estimación | 3 h |
| Origen | Cronograma, «Traspaso técnico al Centro de Competencias» (30/11 al 04/12) |
| Etiquetas | `traspaso` |

#### `PROD-30` — Cerrar el checklist de salida y declarar la salida a producción

Como responsable de TrackIn, quiero el checklist de la guía cerrado, para declarar la salida a producción con evidencia.

**Criterios de aceptación**

- Dado `docs/deployment.md` §11, cuando se revisa, entonces cada casilla está marcada o tiene escrito por qué no aplica
- Dado el piloto aprobado (`PROD-26`) y el acta de traspaso (`PROD-29`), cuando existen, entonces se declara la salida a producción y queda la fecha en este backlog y en el informe

| | |
|---|---|
| Tipo | Task |
| MoSCoW | **Must** |
| Estimación | 1 h |
| Origen | `docs/deployment.md` §11 |
| Etiquetas | `cierre` |
