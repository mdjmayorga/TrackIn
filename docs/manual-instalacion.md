# Manual de instalación local

Cómo levantar TrackIn en un equipo Windows **desde cero, sin permisos de
administrador y sin Docker**, hasta tener el panel abierto con un usuario.
Es la ejecución nativa que fija el SRS §9.3: en los equipos de Gutis no se
pueden habilitar WSL2 ni Hyper-V, y sin ellos no corre ningún contenedor.

Para un servidor, con o sin Docker, ver [deployment.md](deployment.md).

**Tiempo estimado:** 45 a 60 minutos, casi todo descargas.

> **Probado el 03/11/2026** en una instalación limpia: clúster nuevo, clon nuevo
> del repositorio, entorno de Python nuevo. Migraciones, primer Administrador,
> inicio de sesión, `/health`, un ciclo del worker y el build del panel, todo
> siguiendo este manual paso a paso.

**Convenciones**

- Los comandos son para **PowerShell**, salvo que se indique otra cosa.
- `$HOME` es la carpeta del usuario (`C:\Users\<usuario>`). Las rutas de este
  manual la usan; si se instala en otro lugar, hay que cambiarlas en todos los
  pasos.
- Al final de cada paso hay una **verificación**. Si falla, no conviene seguir:
  la sección [Problemas conocidos](#problemas-conocidos) cubre los que ya
  aparecieron.

---

## 0. Qué se instala

| Componente | Versión | Dónde queda | Para qué |
|---|---|---|---|
| Python | 3.12 | `%LOCALAPPDATA%\Programs\Python\Python312` | API y worker de rastreo |
| Node.js | 20 o superior (probado con 24 LTS) | `%LOCALAPPDATA%\Programs\nodejs` | Panel web |
| PostgreSQL + PostGIS | 16.14 + 3.6.2 | `$HOME\pgsql` | Base de datos |
| Git | 2.40 o superior | — | Obtener el código |

TrackIn corre como **cuatro procesos**, cada uno en su consola:

| Proceso | Puerto | Qué hace |
|---|---|---|
| PostgreSQL | 5432 | La base |
| API (`uvicorn`) | 8000 | Lo que consulta el panel |
| Worker de rastreo (`app.workers`) | — | Lee ShipsGo y TICA y recalcula los pedidos |
| Panel (`npm run dev`) | 5173 | La interfaz |

---

## 1. Python 3.12

Descargar el instalador de Windows (64 bits) de
<https://www.python.org/downloads/release/python-31210/>. En el instalador:

1. Marcar **«Add python.exe to PATH»**.
2. Elegir **«Install Now»**: instala solo para el usuario y no pide
   administrador. Si pide elevación, ir a «Customize installation» y desmarcar
   «Install for all users».

Con `winget` disponible, es lo mismo en una línea:

```powershell
winget install --id Python.Python.3.12 --scope user
```

**Verificación** (en una consola **nueva**: las abiertas no ven el PATH nuevo):

```powershell
python --version    # Python 3.12.x
```

## 2. Node.js

El instalador MSI de Node **pide administrador**. Se usa el ZIP:

1. Descargar `node-v24.x.x-win-x64.zip` de <https://nodejs.org/en/download>
   (opción «Windows Binary (.zip)»).
2. Extraerlo y renombrar la carpeta a `nodejs`, dentro de
   `%LOCALAPPDATA%\Programs` (queda `%LOCALAPPDATA%\Programs\nodejs\node.exe`).
3. Agregarla al PATH del usuario:

```powershell
$nodo = "$env:LOCALAPPDATA\Programs\nodejs"
$actual = [Environment]::GetEnvironmentVariable("Path", "User")
[Environment]::SetEnvironmentVariable("Path", "$actual;$nodo", "User")
```

**Verificación** (consola nueva):

```powershell
node --version      # v24.x
npm.cmd --version   # 11.x
```

> Se escribe `npm.cmd` y no `npm`: en los equipos de Gutis PowerShell no
> ejecuta scripts, y `npm` sin extensión resuelve a `npm.ps1`. Desde **cmd**,
> `npm` funciona tal cual.

## 3. PostgreSQL 16 + PostGIS

Binarios portables, sin instalador y sin servicio de Windows.

1. Descargar los dos ZIP:
   - PostgreSQL:
     <https://get.enterprisedb.com/postgresql/postgresql-16.14-1-windows-x64-binaries.zip>
   - PostGIS:
     <https://download.osgeo.org/postgis/windows/pg16/postgis-bundle-pg16-3.6.2x64.zip>
2. Extraer el de PostgreSQL. Trae una carpeta `pgsql`: moverla a `$HOME`, de
   modo que exista `$HOME\pgsql\bin\pg_ctl.exe`.
3. Extraer el de PostGIS y copiar **su contenido encima** de `$HOME\pgsql`
   (sus carpetas `bin`, `lib` y `share` se mezclan con las de PostgreSQL;
   aceptar reemplazar).

> Si Windows dice que no puede renombrar o mover una carpeta recién extraída,
> es el antivirus revisándola: reintentar a los pocos segundos.

### 3.1 Crear el clúster

Una sola vez. Pide la contraseña del usuario `trackin` de la base dos veces:
**anotarla**, va en el `.env` del paso 5.

```powershell
& "$HOME\pgsql\bin\initdb.exe" -D "$HOME\pgsql\data" -U trackin -W -E UTF8 --locale=C -A scram-sha-256
```

`-E UTF8 --locale=C` son los mismos parámetros que usa el contenedor de
`docker-compose.yml`: el ordenamiento de los índices queda idéntico al del
servidor.

### 3.2 Arrancar la base

**En cada sesión de trabajo** —la base no arranca sola al encender el equipo,
porque registrarla como servicio exige administrador—:

```powershell
& "$HOME\pgsql\bin\pg_ctl.exe" -D "$HOME\pgsql\data" -l "$HOME\pgsql\data\server.log" start
```

Para detenerla:

```powershell
& "$HOME\pgsql\bin\pg_ctl.exe" -D "$HOME\pgsql\data" stop
```

> Arrancarla **desde PowerShell**, no desde Git Bash: en Git Bash `pg_ctl` se
> queda con la consola y al cerrarla se cae la base.

### 3.3 Crear las bases

Una sola vez: `trackin_dev` para trabajar y `trackin_test` para las pruebas
automáticas. Piden la contraseña de `trackin`.

```powershell
& "$HOME\pgsql\bin\createdb.exe" -h localhost -U trackin -O trackin -E UTF8 --locale=C -T template0 trackin_dev
& "$HOME\pgsql\bin\createdb.exe" -h localhost -U trackin -O trackin -E UTF8 --locale=C -T template0 trackin_test
```

PostGIS no se activa a mano: lo hace la primera migración (paso 6).

**Verificación:**

```powershell
& "$HOME\pgsql\bin\psql.exe" -h localhost -U trackin -d trackin_dev -c "SELECT version();"
```

## 4. Obtener el código

```powershell
cd $HOME\Documents\GitHub
git clone https://github.com/mdjmayorga/TrackIn.git
cd TrackIn
```

> **Una ruta corta.** Sin administrador no se pueden habilitar las rutas largas
> de Windows (más de 260 caracteres), y algunas dependencias de Python tienen
> archivos muy anidados: en una carpeta muy profunda, el paso 6 falla con
> `OSError: [Errno 2] No such file or directory` y una sugerencia sobre «Long
> Path support». `C:\Users\<usuario>\Documents\GitHub\TrackIn` funciona.

**Verificación:** existen `backend\`, `frontend\` y `.env.example`.

## 5. Configurar el backend

La configuración vive en **`backend\.env`**. Crear ese archivo con este
contenido mínimo, cambiando lo que está entre `«»`:

```ini
POSTGRES_USER=trackin
POSTGRES_PASSWORD=«la contraseña del paso 3.1»
POSTGRES_DB=trackin_dev
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

ENVIRONMENT=development
DEBUG=true
BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
SECRET_KEY=«una clave aleatoria, ver abajo»

# Rastreo. Sin token, el sistema funciona pero no rastrea: el worker arranca y lo dice.
SHIPSGO_API_TOKEN=«el token de la API de ShipsGo»
```

- **`SECRET_KEY`**: firma las sesiones. Generarla con
  `python -c "import secrets; print(secrets.token_urlsafe(48))"` y pegar el
  resultado.
- **`SHIPSGO_API_TOKEN`**: en la cuenta de ShipsGo de Gutis, *Settings → API*.
  Es el token de la **API**, no el del mapa embebido. TICA (las guías hijas)
  no necesita credenciales.

> **Ningún valor puede quedar como en la plantilla** (`<placeholder>`,
> `<generar-...>`): el backend no arranca y lista cuáles faltan. Por eso se
> parte de este contenido mínimo y no de copiar `.env.example` entero, que trae
> claves de servicios que ya no se usan (AISStream, OpenSky, TrackingMore).
>
> **No crear un `.env` en la raíz del repositorio.** Lo leía docker-compose y
> tiene precedencia sobre `backend\.env`: taparía esta configuración sin avisar.

## 6. Instalar el backend

Desde `backend\`:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\alembic upgrade head
```

La instalación tarda unos minutos y **tiene que terminar sin ninguna línea
`ERROR`**: si falla a medias, lo que sigue da errores que no parecen de la
instalación (`No module named 'sqlalchemy'`, `No module named alembic.__main__`).

> Todo se llama con el Python del entorno (`.venv\Scripts\python -m ...`) en
> vez de activarlo: `Activate.ps1` es un script, y PowerShell no los ejecuta en
> estos equipos. Desde **cmd**, `.venv\Scripts\activate` sí funciona.

`alembic upgrade head` crea las tablas, activa PostGIS y siembra los maestros:
países, los cuatro destinos (Moín, Limón, Caldera y el Juan Santamaría) y los
parámetros del sistema.

**Verificación:** la última línea de `alembic upgrade head` dice
`Running upgrade ... -> 00xx_...` sin errores, y

```powershell
.venv\Scripts\alembic current     # la última migración, con (head)
```

### 6.1 El primer Administrador

Las cuentas se crean desde el panel, pero solo un Administrador puede hacerlo.
El primero se crea desde la consola; pide la contraseña sin mostrarla
(mínimo 10 caracteres):

```powershell
.venv\Scripts\python scripts\crear_usuario.py admin "Nombre Apellido" ADMINISTRADOR
```

## 7. Configurar e instalar el panel

Desde `frontend\`:

```powershell
cd ..\frontend
Copy-Item .env.example .env
npm.cmd ci
```

`frontend\.env` ya trae `VITE_API_URL=http://localhost:8000`. El
`VITE_SHIPSGO_EMBED_TOKEN` (el mapa en vivo de ShipsGo en el detalle del
pedido) es **opcional**: vacío, el detalle usa el mapa propio. Si se completa,
el origen `http://localhost:5173` tiene que estar en «Allowed HTTP Origins» de
la cuenta de ShipsGo.

> `frontend\.env` va en el navegador: **nunca** poner ahí el token de la API.

## 8. Arrancar

Cuatro consolas de PowerShell, en este orden:

| # | Desde | Comando |
|---|---|---|
| 1 | cualquier carpeta | `& "$HOME\pgsql\bin\pg_ctl.exe" -D "$HOME\pgsql\data" -l "$HOME\pgsql\data\server.log" start` (si no está corriendo) |
| 2 | `backend\` | `.venv\Scripts\python -m uvicorn app.main:app --reload` |
| 3 | `backend\` | `.venv\Scripts\python -m app.workers` |
| 4 | `frontend\` | `npm.cmd run dev` |

**Verificación:**

1. <http://localhost:8000/health> responde `"status":"ok"`, `"database":"up"` y
   la versión de PostGIS. Si hay token de ShipsGo, unos minutos después de
   arrancar el worker la fuente `shipsgo` aparece en `"fuentes"` con
   `"degradada":false`.
2. <http://localhost:5173> muestra el inicio de sesión. Entrar con el
   Administrador del paso 6.1.
3. El panel abre vacío: todavía no hay pedidos.

## 9. Primeros pasos en el panel

1. **Usuarios** (menú del Administrador): crear las cuentas de Compras,
   Logística y Planificación.
2. **Cargas**: descargar la **plantilla del Z-tracking**, completarla (o usar
   el Excel semanal de Compras con las mismas columnas) y subirla. El informe
   de la carga dice qué entró y qué no, y por qué.
3. Si hay token de ShipsGo, el worker empieza a leer los embarques en su
   siguiente ciclo (unos minutos). Un BL o una guía que ShipsGo todavía no
   sigue se da de alta desde **Altas en ShipsGo** —cada alta consume un
   crédito, por eso la decide una persona—.
4. En **Altas en ShipsGo → Registrar paquete comprado**, cargar los créditos
   de la cuenta. Sin eso, `/health` dice `"SIN_PAQUETE"` y TrackIn no puede
   avisar antes de que se agoten.

## 10. Pruebas (opcional)

Desde `backend\`, con la base arrancada:

```powershell
.venv\Scripts\python -m pytest
```

Corren contra `trackin_test`, nunca contra `trackin_dev`. Desde `frontend\`:

```powershell
npm.cmd test
```

---

## Actualizar a una versión nueva

Con los procesos 2, 3 y 4 detenidos:

```powershell
git pull
cd backend
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m alembic upgrade head
cd ..\frontend
npm.cmd ci
```

y volver a arrancar como en el paso 8. **El worker hay que reiniciarlo siempre**:
el `--reload` solo recarga la API, y un worker viejo sigue aplicando las reglas
anteriores (el 02/11/2026 volvió a dar por llegado a Costa Rica un pedido que
seguía en París).

---

## Problemas conocidos

| Síntoma | Causa | Solución |
|---|---|---|
| `python`, `node` o `npm` «no se reconoce como un comando» | La consola se abrió antes de instalarlos | Abrir una consola nueva |
| «La ejecución de scripts está deshabilitada en este sistema» | PowerShell no ejecuta `.ps1` (`Activate.ps1`, `npm.ps1`) | Usar `.venv\Scripts\python -m ...` y `npm.cmd`, o trabajar desde cmd |
| El backend no arranca: «Configuración incompleta; TrackIn no arranca hasta corregir» | Falta una variable o quedó un valor de la plantilla | Corregir lo que lista el mensaje en `backend\.env` |
| `connection refused` al puerto 5432 | La base no está arrancada | Paso 3.2 |
| La base se cae al cerrar una consola | Se arrancó desde Git Bash | Arrancarla desde PowerShell |
| `ModuleNotFoundError` al correr un script | Se usó el Python global, o la instalación del paso 6 no terminó | Usar `.venv\Scripts\python` desde `backend\`; si sigue, repetir el `pip install` y revisar que no dé `ERROR` |
| `No module named alembic.__main__` | La instalación del paso 6 no terminó, y `python -m alembic` encontró la carpeta de migraciones del proyecto, que también se llama `alembic` | Repetir el `pip install`; usar `.venv\Scripts\alembic` |
| `pip install` falla con `OSError ... Long Path support` | La carpeta del repositorio está demasiado profunda | Clonar en una ruta más corta (paso 4) |
| El panel dice «No se pudo contactar la API» | La API no está corriendo, o devolvió un error 500 (el navegador lo ve sin cabeceras CORS) | Revisar la consola de la API: el error real está ahí |
| `/health` muestra ShipsGo degradada | Errores de red al arrancar, o el token es inválido | Con errores de red, el worker reintenta cada 5 minutos solo. Con token inválido (401) no reintenta: corregir el token y reiniciar el worker |
| Un pedido no cambia después de actualizar el código | El worker sigue con el código anterior | Reiniciar el worker |
| Un BL no se rastrea | ShipsGo no lo sigue todavía, o el número está mal escrito | Altas en ShipsGo; corregir la referencia en el detalle del pedido |
| `psql` muestra caracteres raros en tildes | La consola no está en UTF-8 | `$env:PGCLIENTENCODING = "UTF8"` antes de `psql` |
