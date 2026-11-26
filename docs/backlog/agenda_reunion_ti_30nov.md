# Reunión con los jefes de TI: arranque de la puesta en producción

**Fecha:** lunes 30/11/2026, 1:00 p. m. **Participantes:** Mariano Mayorga, jefes de TI
(`[nombres por anotar]`). **Tarea:** `PROD-01` de [backlog_produccion.md](backlog_produccion.md).

**Objetivo:** salir de la reunión con el servidor, los accesos y los responsables definidos
para instalar TrackIn el mismo 30/11 o el 01/12. Si el servidor no está esa semana, el
piloto con Compras no entra antes del 04/12.

**Lo que ya se sabe:** TI no quiere servidores Linux; el servidor es **Windows Server 2025**.
TrackIn se instala **nativo, sin Docker**, con la API y el worker como servicios de Windows
e **IIS** delante (D2, 26/11).

---

## Para abrir (dos minutos)

- TrackIn sigue las compras internacionales (barcos, contenedores y guías aéreas) para
  Compras, Logística y Planificación. Está terminado y se presentó a la universidad el 27/11.
- Piloto con Compras hasta el 04/12, con Itza Fallas como responsable funcional (D27).
  Después lo recibe el Centro de Competencias.
- **Lo hago yo:** instalar TrackIn, configurarlo, los respaldos programados, la
  documentación y el traspaso. **Les pido a ustedes:** el servidor, la red, el certificado
  y quién lo administra.

---

**Agenda de la reunión:**

1. **El servidor.**
   - Tamaño: 2 vCPU, 8 GB de RAM y 60 GB de disco.
   - Quién lo crea y **cuándo está listo**. Lo ideal es el mismo 30/11.
   - Nombre de la máquina, y en qué disco y carpeta va TrackIn (por ejemplo, `D:\TrackIn`).
   - Acceso por Escritorio remoto desde la red interna, con qué usuario.
2. **Permisos e instalación del software.**
   - ¿Me dan administrador local, o lo instalan ellos? Lista: PostgreSQL 16 con PostGIS 3.6,
     Python 3.12, Node.js 20 o superior (solo para construir el panel), Git y un envoltorio
     de servicios (WinSW o NSSM).
   - IIS con los módulos **URL Rewrite** y **Application Request Routing**.
   - ¿Hay alguna política contra instalar ese software? ¿Usan una cuenta de servicio para
     los servicios de Windows?
3. **Nombre, HTTPS y firewall.**
   - El nombre en el DNS interno: `trackin.gutis.com` u otro.
   - El certificado: público o de la autoridad interna, que los equipos acepten sin
     advertencia. Quién lo instala en IIS, cuándo vence y quién lo renueva.
   - Puerto 443 abierto desde la red interna (y el 80 redirigido a 443). Desde afuera, solo
     por la VPN.
   - Recordar por qué el HTTPS es obligatorio: la pantalla de planta necesita HTTPS para
     mantener el monitor encendido.
4. **Salida a internet.**
   - Desde el servidor: `api.shipsgo.com`, `ticaconsultas.hacienda.go.cr`, `github.com`,
     `pypi.org`, `files.pythonhosted.org` y `registry.npmjs.org`.
   - Desde los navegadores, también en la red de planta: `tile.openstreetmap.org` y
     `embed.shipsgo.com`.
   - ¿Hay un proxy de salida? Si lo hay, necesito su dirección para configurar Python, pip,
     npm y Git.
5. **Antivirus y actualizaciones.**
   - Exclusión de la carpeta de datos de PostgreSQL en el antivirus.
   - Ventana de Windows Update y reinicios: los servicios de TrackIn arrancan solos, pero
     hay que saber cuándo se reinicia.
6. **Respaldos.**
   - A qué carpeta de red copio el respaldo diario y con qué cuenta. Retención propuesta: 14 días.
   - ¿Respaldan también la máquina virtual completa?
7. **Secretos.** Dónde guardan en custodia el archivo de configuración con las contraseñas
   (`backend\.env`).
8. **Monitoreo.** ¿Tienen una herramienta donde agregar `https://trackin.gutis.com/health`?
   Si no, ¿qué servidor de correo (SMTP o relé interno) puedo usar para los avisos, y a qué
   correos se avisa?
9. **Quién administra y el traspaso.**
   - Responsable del servidor en TI y contacto de soporte (riesgo R7: sin ese nombre no se
     declara la salida).
   - Una cuenta de Administrador de TrackIn de respaldo para TI (D16).
   - Fecha de la sesión de traspaso con el Centro de Competencias, antes del 04/12.
10. **Pantalla de planta.** Qué equipo, en qué red, con qué navegador (Edge o Chrome), y
    quién la deja configurada.
11. **Calendario.** Confirmar las fechas de la tabla de abajo.

---

## Calendario a confirmar

| Fecha | Qué |
|---|---|
| 30/11 | Servidor listo, accesos y software base |
| 30/11 y 01/12 | Instalación de TrackIn, IIS, certificado, salida a internet y respaldo programado |
| 01/12 | Ensayo general en el servidor y reinicio de la base |
| 02/12 | Salida: cuentas reales, primera carga del Z-tracking y altas en ShipsGo |
| 02/12 al 04/12 | Piloto con Compras y sesión de traspaso |

**Si el servidor no está el 30/11:** cada día de atraso le quita un día al piloto. Si llega
después del 01/12, hay que decidir con Greivin y Compras si el piloto se corre más allá del
04/12 o si la salida queda sin piloto.

---

## Qué llevar

- Esta agenda y el [correo enviado a TI](correo_ti_produccion.md).
- La lista del software con versiones y enlaces de descarga, por si lo instalan ellos
  ([manual de instalación](../manual-instalacion.md) §0).
- El esquema de cómo queda en el servidor: IIS (HTTPS) reenvía `/api/` y `/health` a la API
  en `127.0.0.1:8000`; la API y el worker contra PostgreSQL local.
- La parte B del [manual de operación](../manual-operacion.md), para mostrar qué reciben al final.

---

## Acuerdos (completar en la reunión)

| Acuerdos | Responsable | Fecha límite |
|---|---|---|
| Servidor Windows Server 2025 creado, con acceso por Escritorio remoto | TI | 30/11/2026 |
| Permisos de administrador o software base instalado (PostgreSQL+PostGIS, Python, Node, Git, IIS con URL Rewrite y ARR) | TI | 30/11/2026 |
| Nombre en el DNS interno y certificado instalado en IIS | TI | 01/12/2026 |
| Puerto 443 abierto en la red interna y salida a internet según la lista | TI | 01/12/2026 |
| Exclusión del antivirus para los datos de PostgreSQL | TI | 01/12/2026 |
| Carpeta de red para los respaldos y lugar de custodia de los secretos | TI | 01/12/2026 |
| Monitoreo de `/health` o servidor de correo para los avisos | TI | 01/12/2026 |
| Responsable del servidor en TI nombrado | TI | 30/11/2026 |
| Instalación de TrackIn y ensayo general en el servidor | Mariano Mayorga | 01/12/2026 |
| Salida a producción con datos reales | Mariano Mayorga | 02/12/2026 |
| Sesión de traspaso con el Centro de Competencias | Mariano Mayorga y TI | 04/12/2026 |

## Después de la reunión

- [ ] Anotar las respuestas en `PROD-01`, con la fecha comprometida del servidor
- [ ] Actualizar D9 (el HTTPS termina en IIS), D18 (monitoreo), D22 (contacto en TI) y R7
- [ ] Escribir el ADR que reemplaza al [ADR 0002](../adr/0002-produccion-en-maquina-virtual-linux-de-la-red-interna.md)
- [ ] Completar las marcas `[pendiente de TI]` del manual de operación
- [ ] Si el calendario cambia, ajustar D20 y las fases 1 a 3 del backlog
