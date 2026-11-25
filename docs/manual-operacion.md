# Manual de operación de TrackIn

Cómo se mantiene funcionando **el TrackIn que está en producción en Gutis**, después de
que termina su desarrollo (`PROD-28`).

| Parte | Para quién | Qué trae |
|---|---|---|
| [Parte A: uso diario](#parte-a-uso-diario) | **Itza Fallas**, Compras: la dueña del sistema | Las tareas de cada semana, las cuentas y qué hacer cuando algo se ve mal. Sin comandos |
| [Parte B: el servidor](#parte-b-el-servidor) | **Centro de Competencias y TI** | Dónde está todo, qué mirar, cómo respaldar, restaurar y actualizar |

Este manual dice cómo operar **este** TrackIn. Cómo se usa cada pantalla está en el
[manual de usuario](manual-usuario.md); cómo instalarlo en cualquier servidor, en la
[guía de despliegue](deployment.md). Aquí se enlazan en vez de repetirse.

> Lo marcado **`[pendiente de TI]`** se completa con la respuesta de TI al pedido del
> servidor (`PROD-01`), o el día de la instalación. **Ninguna contraseña ni token se
> escribe en este documento:** solo dónde están.

## Contactos

| Para | Quién | Cómo |
|---|---|---|
| Dudas de uso, cuentas, la carga semanal, créditos de ShipsGo | Itza Fallas (Compras) | `[extensión o correo]` |
| El servidor: no abre, está lento, falta espacio, reinicios | `[pendiente de TI]` | `[pendiente de TI]` |
| Cambios al sistema o errores del programa | Centro de Competencias | `[pendiente]` |
| La cuenta de ShipsGo (pagos, paquetes) | Compras | — |

---

# Parte A: uso diario

*Para Itza Fallas. Todo se hace desde el panel, con una cuenta de Administrador o de
Compras.*

## A.1 Qué hacer cada semana

| Cuándo | Qué | Dónde está explicado |
|---|---|---|
| **Lunes o martes** | Subir el Z-tracking de la semana. La burbuja de **Ajustes Z-tracking** se pone naranja cuando toca y roja si pasó el martes | [Manual de usuario §9](manual-usuario.md#9-la-carga-semanal-del-z-tracking) |
| Justo después de la carga | Leer el informe: las líneas rechazadas dicen qué corregir en SAP | Manual de usuario §9, «Leer el informe» |
| Justo después de la carga | Dar de alta en ShipsGo las referencias nuevas (**Altas en ShipsGo**). Cada alta gasta un crédito | [Manual de usuario §10](manual-usuario.md#10-altas-y-créditos-de-shipsgo) |
| Durante la semana | Mirar la insignia de ShipsGo del panel. Verde: todo bien | Manual de usuario §3, «Insignia de ShipsGo» |

**Qué hace la carga con los pedidos**, para no sorprenderse:

- Los pedidos **sin BL ni guía** entran igual, en **Sin Tracking**, y empiezan a
  rastrearse en la carga en que llegue el documento.
- Los pedidos que **ya no vienen** en el Z-tracking se dan por cerrados en SAP: TrackIn
  los **cierra** y salen del panel. No se borran: están en el filtro de cerrados, con el
  motivo «Ya no vino en el Z-tracking». Si vuelven a venir en otra carga, se reabren solos.

## A.2 Créditos de ShipsGo

Cada referencia nueva que se rastrea cuesta un crédito de la cuenta de ShipsGo de Gutis.

- **Cuándo comprar:** el panel muestra un aviso bajo el título (solo a Compras y al
  Administrador) cuando se consumió el 80 % del paquete, se agotó, vence en menos de 60
  días o no hay paquete registrado. Con ese aviso, Compras compra el siguiente paquete en
  ShipsGo.
- **Después de comprar:** registrarlo en TrackIn en **Altas en ShipsGo → Registrar paquete
  comprado**. Si no se registra, TrackIn no sabe cuántos créditos quedan.
- **Sin créditos** TrackIn sigue funcionando, pero las referencias nuevas se quedan en Sin
  Tracking.

## A.3 Cuentas

*Solo con una cuenta de Administrador.* **Configuración → Usuarios**
([manual de usuario §11.1](manual-usuario.md#111-usuarios)).

Las cuentas que se crearon en la salida (`PROD-21`):

| Cuenta | Para | Rol |
|---|---|---|
| `compras` | Compras: carga, altas, ETA | Compras |
| `[usuario de Logística]` | Desembarco, aduanas y recepción en planta | Logística |
| `planificacion` | Consulta | Planificación |
| `[usuario de planta]` | La pantalla permanente | Planta |
| `[Administrador de Itza]` | Administración después del 04/12 | Administrador |
| `[Administrador de respaldo]` | TI, por si hace falta entrar | Administrador |

**Las contraseñas no se anotan aquí.** Al crear una cuenta, la contraseña inicial se le
entrega a la persona en mano o por un medio seguro, y ella la cambia al entrar.

| Situación | Qué hacer |
|---|---|
| Alguien nuevo necesita entrar | **Nueva cuenta**, o darle la contraseña de la cuenta compartida de su equipo |
| Alguien olvidó la contraseña | **Reiniciar contraseña** en su fila |
| Alguien se va del equipo y usaba una cuenta compartida | **Reiniciar contraseña** de esa cuenta y darles la nueva a los que siguen |
| Una cuenta ya no se usa | **Desactivar**. Las cuentas no se borran: la línea de tiempo de los pedidos guarda quién hizo cada cosa |
| La cuenta quedó bloqueada | Tras 5 intentos fallidos se bloquea 15 minutos. Esperar, o reiniciar la contraseña |

## A.4 Cuando algo se ve mal

Primero, el [manual de usuario, «Problemas frecuentes»](manual-usuario.md#problemas-frecuentes):
resuelve casi todo lo del día a día (un pedido que no aparece, un botón deshabilitado, la
sesión que se cerró).

| Lo que se ve | Qué es | Qué hacer |
|---|---|---|
| El panel no abre en ningún equipo, o dice «Sin conexión con TrackIn» | El servidor no responde | Esperar 5 minutos y recargar. Si sigue, **avisar a TI** (contactos, arriba) |
| La insignia dice «ShipsGo con fallas» o «sin lectura reciente» por más de una hora | El rastreo no está leyendo | **Avisar a TI**: probablemente hay que revisar el servidor ([B.4](#b4-qué-hacer-ante-cada-problema)) |
| Las altas en ShipsGo fallan | Casi siempre, sin créditos | Revisar el saldo en **Altas en ShipsGo** ([A.2](#a2-créditos-de-shipsgo)) |
| El navegador muestra una advertencia de seguridad al entrar | El certificado venció | **Avisar a TI**. No continuar a pesar de la advertencia |
| La pantalla de planta se apagó o se quedó en el inicio de sesión | Corte de luz o de red | Volver a entrar con la cuenta de planta, **Recordar sesión** y **Pantalla completa** ([manual de usuario §12](manual-usuario.md#12-la-pantalla-de-planta)) |
| Un error del programa: algo que antes funcionaba y ahora no | — | Anotar qué se hizo, en qué pedido y la hora, y avisar al Centro de Competencias |

---

# Parte B: el servidor

*Para el Centro de Competencias y TI. Supone la instalación con Docker de la
[guía de despliegue](deployment.md) §7.*

## B.1 Dónde está todo

| Qué | Dónde |
|---|---|
| Dirección del panel | `https://[pendiente de TI]` (el nombre interno, D7) |
| Servidor | `[pendiente de TI]`: nombre o IP, sistema operativo, quién lo administra |
| Cómo se entra | `[pendiente de TI]`: SSH con el usuario `[...]`, del grupo `docker` |
| Carpeta de TrackIn | `[pendiente: por ejemplo /opt/trackin]`: el repositorio clonado. **Todos los comandos se corren desde aquí** |
| Versión instalada | `curl http://localhost:8080/health` (campo `version`), o el pie del menú **Configuración** |
| Configuración y secretos | `.env.produccion`, en la carpeta de TrackIn. **No está en GitHub.** Copia en custodia: `[pendiente de TI]` |
| La base de datos | El volumen de Docker `trackin_postgres_data`. **`docker compose down -v` lo borra** |
| Respaldos | `respaldos/` en la carpeta de TrackIn, 14 días. Copia fuera del servidor: `[pendiente de TI]` |
| Monitoreo | `[pendiente de TI]`: su herramienta, o `scripts/vigilar_salud.sh` cada 5 minutos con aviso a `[correo]` |
| HTTPS y certificado | `[pendiente de TI]`: en el proxy corporativo o en el nginx de TrackIn; vence el `[fecha]` |
| Tareas programadas | `crontab -l` del usuario que administra Docker: el respaldo diario (02:00) y, si aplica, la vigilancia |
| Código fuente | `https://github.com/mdjmayorga/TrackIn`. El servidor corre siempre una etiqueta `vX.Y.Z` |

En todos los comandos de abajo, `DC` es una abreviatura de:

```bash
docker compose --env-file .env.produccion
```

## B.2 Tareas periódicas

| Cada | Qué | Cómo |
|---|---|---|
| Día | Respaldo de la base | Automático (cron, 02:00). Se revisa el log: `tail respaldos/respaldar.log` |
| Semana | Que el respaldo de anoche exista y tenga tamaño razonable | `ls -lh respaldos/ \| tail -3`. Unos 100 KB a pocos MB |
| Mes | Espacio en disco | `df -h` y `docker system df`. Los logs de Docker ya tienen tope (5 × 10 MB por servicio) |
| Mes | Parches del sistema operativo | Según la ventana de mantenimiento de TI. Después de reiniciar, comprobar [B.3](#b3-comprobar-que-todo-está-bien) |
| Trimestre | **Restaurar un respaldo** en una prueba, para saber que sirven | [Guía §8](deployment.md#8-respaldos-y-restauración), «Restaurar» |
| Antes de que venza | **Renovar el certificado** | `[pendiente de TI]`. Un certificado vencido deja a todos fuera con una advertencia del navegador |

Las tareas de Compras (la carga semanal y los créditos) están en la [parte A](#a1-qué-hacer-cada-semana).

## B.3 Comprobar que todo está bien

```bash
DC ps                                  # los cuatro contenedores "running"
curl -s http://localhost:8080/health   # el estado completo
```

| Campo de `/health` | Bien | Si no |
|---|---|---|
| `status` | `"ok"` | `"degraded"`: la base no responde ([B.4](#b4-qué-hacer-ante-cada-problema)) |
| `database` | `"up"` | Igual que arriba |
| `fuentes[]` → `degradada` | `false` en `shipsgo` y `tica` | ShipsGo o TICA no responden ([B.4](#b4-qué-hacer-ante-cada-problema)) |
| `creditos_shipsgo.nivel` | `"OK"` | Le toca a Compras ([A.2](#a2-créditos-de-shipsgo)) |
| `version` | La etiqueta instalada | — |

`/health` **no nota si el worker se detuvo**: las fuentes solo dejan de actualizarse. Por
eso hay que mirar también `DC ps`.

## B.4 Qué hacer ante cada problema

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| El panel no abre | Docker o los contenedores detenidos (por ejemplo, tras reiniciar el servidor) | `DC ps`. Si no están: `DC up -d`. Si Docker no arrancó solo: `sudo systemctl enable --now docker` |
| `database: "down"` | El contenedor `postgres` detenido o sin disco | `DC ps`, `df -h`, `DC logs --tail 100 postgres`. Liberar espacio y `DC up -d` |
| ShipsGo `degradada: true` con error de red | El servidor perdió la salida a `api.shipsgo.com` | El worker reintenta solo cada 5 minutos. Si sigue más de una hora, revisar el firewall con TI |
| ShipsGo `degradada: true` con 401 | El token de ShipsGo dejó de valer | Pedir a Compras el token nuevo, ponerlo en `SHIPSGO_API_TOKEN` de `.env.produccion` y `DC up -d worker`. **Con 401 no reintenta solo** |
| TICA `degradada: true` | `ticaconsultas.hacienda.go.cr` caído o bloqueado | Suele ser del lado de Hacienda y se arregla solo. Si dura un día, revisar la salida a internet |
| El worker no aparece en `DC ps` | Se cayó | `DC logs --tail 200 worker` para ver por qué, y `DC up -d worker` |
| Advertencia de certificado en el navegador | Venció | Renovarlo (`[pendiente de TI]`) |
| Disco lleno | Respaldos con nombre acumulados o imágenes viejas | Borrar a mano los `respaldos/trackin-antes-de-*` que ya no hagan falta, y `docker image prune` |
| La carga del Z-tracking dice que el archivo pesa demasiado | El límite es 20 MB, y el Z-tracking normal pesa mucho menos | Revisar con Compras que sea el archivo correcto, exportado de SAP |

Para ver qué pasó: `DC logs --tail 200 backend worker`. Los logs dicen la causa en
castellano.

## B.5 Respaldar, restaurar, actualizar y volver atrás

Todo está en la guía de despliegue, con los comandos exactos:

| Para | Dónde |
|---|---|
| Respaldar a mano (por ejemplo, antes de algo riesgoso) | [Guía §8](deployment.md#8-respaldos-y-restauración): `bash scripts/respaldar.sh antes-de-algo` |
| Restaurar un respaldo | Guía §8, «Restaurar». **Reemplaza la base entera** y pide confirmación |
| Instalar una versión nueva | [Guía §9](deployment.md#9-operación), «Actualizar a una versión nueva». Siempre con respaldo antes |
| Volver a la versión anterior | Guía §9, «Volver a la versión anterior». Si la versión nueva traía una migración, hay que restaurar el respaldo |

Dos reglas para este servidor:

1. **Actualizar fuera del horario de Compras**, para poder volver atrás sin perder lo que
   registren entre tanto.
2. **Avisar a Itza antes y después.**

## B.6 Pendientes conocidos

Lo que se sabe al traspasar y no se resolvió en el desarrollo (`PROD-27`):

- `[se completa al final del piloto, 04/12]`
- La pantalla permanente de planta: el equipo y el lugar los define Compras (`PROD-24`).
