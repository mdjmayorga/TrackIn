# Correo a TI: infraestructura para la puesta en producción de TrackIn

**Para:** TI de Gutis (destinatario por confirmar). **Copia:** Greivin. **Tarea:** `PROD-01` de
[backlog_produccion.md](backlog_produccion.md). **Objetivo:** respuesta de TI el **13/11** y
la máquina virtual lista el **viernes 20/11**, para empezar la instalación el lunes 23/11 con
margen.

> Borrador del 06/11/2026, ajustado con las decisiones D1 a D25 confirmadas ese día.
> Lo marcado con `[ ]` se completa al enviarlo.

---

**Asunto:** TrackIn: servidor y red para la puesta en producción (máquina virtual para el 20/11)

Buenos días:

Les escribo por TrackIn, el sistema de seguimiento de las compras internacionales que
desarrollé en la práctica con Compras y Logística. El desarrollo está terminado y, como se
acordó al inicio de la práctica, vamos a ponerlo en producción en la **red interna de
Gutis** durante la extensión del proyecto, del 23/11 al 04/12.

Para eso necesito de ustedes la infraestructura que detallo abajo. **Lo urgente es la
máquina virtual: si está lista el viernes 20/11, llegamos al 04/12 con una semana de
piloto.**
Todo lo de TrackIn (instalación, configuración, respaldos y documentación) lo hago yo, y al
final se lo traspaso al Centro de Competencias.

## Lo que necesito

**1. Una máquina virtual Linux con Docker.**

| | |
|---|---|
| Sistema operativo | Linux (Ubuntu Server 24.04 LTS o la distribución que ustedes usen) |
| Tamaño | 2 vCPU, 4 GB de RAM, 40 GB de disco |
| Software | Docker Engine 24 o superior, con el plugin `compose` 2.24 o superior, y Git |
| Acceso | Un usuario para mí con permiso para usar Docker (grupo `docker`) y acceso por SSH desde la red interna |
| Reloj | Sincronizado por NTP, zona horaria de Costa Rica |

Si no tienen Linux disponible, **avísenme**: TrackIn también corre en un servidor Windows
sin Docker, pero cambia el plan de instalación.

**2. Un nombre en el DNS interno.**
Propongo **`trackin.gutis.com`** (o el que ustedes prefieran), apuntando a la máquina
virtual o al proxy, según el punto 3. Importa que sea un subdominio de un dominio real de
Gutis: el certificado del punto 3 no se puede emitir para nombres `.local` ni para una IP.

**3. HTTPS con un certificado de confianza para los equipos de Gutis.**
TrackIn tiene que ir por HTTPS aunque sea solo interno: la pantalla de planta usa una
función del navegador que mantiene el monitor encendido y que **solo existe con HTTPS**.

- **¿Tienen un proxy corporativo** (o balanceador) donde se pueda terminar el HTTPS? Si sí,
  el proxy reenvía a la máquina virtual por HTTP al puerto **8080**, que es el único que
  publica TrackIn.
- Si no lo tienen, me entregan el certificado y su llave y TrackIn atiende HTTPS por su
  cuenta en el puerto 443.
- El certificado puede ser público (validado por DNS) o de la autoridad certificadora
  interna de Gutis, siempre que los navegadores de los equipos confíen en ella sin
  mostrar advertencias.

**4. Salida a internet.**

| Destino (HTTPS, puerto 443) | Desde dónde | Para qué |
|---|---|---|
| `api.shipsgo.com` | La máquina virtual | El rastreo de barcos, contenedores y guías aéreas (servicio contratado por Compras) |
| `ticaconsultas.hacienda.go.cr` | La máquina virtual | El rastreo de las guías aéreas en la aduana de Costa Rica |
| `tile.openstreetmap.org` | Los **navegadores** de los usuarios | El fondo de los mapas |
| `embed.shipsgo.com` | Los **navegadores** de los usuarios | El mapa en vivo del detalle de un pedido |
| `github.com` | La máquina virtual | Descargar el código de TrackIn para instalarlo y actualizarlo |
| Docker Hub (`registry-1.docker.io` y relacionados) | La máquina virtual | Descargar las imágenes base (PostgreSQL, Python, Node, nginx) |

Los dos destinos de los navegadores también tienen que pasar en la **red de planta**,
donde va a estar la pantalla permanente.

**5. Acceso desde afuera.**
Los usuarios son internos. Quien trabaje fuera de la oficina entraría por la **VPN
corporativa**; no hace falta exponer TrackIn a internet. ¿Lo confirman?

**6. Respaldos.**
TrackIn deja un respaldo diario de su base de datos (un solo archivo, pequeño) en la
máquina virtual. Necesito saber **a dónde copiarlo fuera de la máquina virtual** (una
carpeta de red o el sistema de respaldos que usen) y cuántos días lo retienen ustedes. Yo
propongo 14 días.

**7. Secretos.**
TrackIn tiene un archivo de configuración con contraseñas (`.env.produccion`). ¿Dónde
guardan ustedes los secretos de los servidores, para dejarles una copia en custodia?

**8. Monitoreo.**
TrackIn publica su estado en `https://trackin.gutis.com/health`. ¿Tienen una herramienta de
monitoreo donde agregarlo, con aviso por correo si deja de responder? Si no, lo resuelvo
desde la propia máquina virtual.

**9. Quién administra.**
¿Quién de TI es el responsable de la máquina virtual (parches del sistema operativo,
reinicios, espacio en disco) y cuál es la ventana de mantenimiento?

## Lo que entrego yo

- La instalación de TrackIn en la máquina virtual, con la [guía de despliegue](../deployment.md)
  y un asistente que la automatiza.
- Los respaldos programados, con una restauración probada antes de la salida.
- Un manual de operación y una sesión de traspaso con el Centro de Competencias al final.
- TrackIn guarda pedidos de compra, referencias de embarque y las cuentas de sus
  usuarios (nombre, correo y rol); las contraseñas, solo como hash, nunca en claro.

## Fechas

| Fecha | Qué |
|---|---|
| **13/11** | Respuesta a los puntos 1, 3, 5, 6, 7, 8 y 9 (sobre todo: si hay Linux y si hay proxy) |
| **20/11** | Máquina virtual lista (punto 1) |
| 23/11 al 26/11 | Instalación de TrackIn; nombre, certificado y salida a internet (puntos 2, 3 y 4) |
| 27/11 al 30/11 | Salida a producción con datos reales |
| 30/11 al 04/12 | Piloto con Compras y traspaso al Centro de Competencias |

Muchas gracias.

Saludos,

Mariano Mayorga
`[ ] teléfono o extensión`

---

## Después de enviarlo

- [ ] Enviado el `[ ]` a `[ ]`
- [ ] Respuesta de TI anotada en `PROD-01`, con la fecha comprometida de la máquina virtual
- [ ] Si TI no tiene Linux: reabrir D2 y el [ADR 0002](../adr/0002-produccion-en-maquina-virtual-linux-de-la-red-interna.md)
- [ ] Si hay proxy corporativo: cancelar `PROD-10`
