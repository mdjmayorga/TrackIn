<#
.SYNOPSIS
    Instala TrackIn en un equipo Windows de una sola vez, sin administrador.

.DESCRIPTION
    Hace en orden lo que docs/manual-instalacion.md describe a mano:
      1. Python 3.12   (si falta: instalador oficial, solo para el usuario)
      2. Node.js 24    (si falta: ZIP oficial en %LOCALAPPDATA%\Programs\nodejs)
      3. PostgreSQL 16 + PostGIS (binarios portables en -RutaPostgres)
      4. Cluster, bases trackin_dev y trackin_test
      5. backend\.env con contraseña y SECRET_KEY aleatorias
      6. Entorno de Python, dependencias y migraciones
      7. Primer Administrador
      8. frontend\.env y dependencias del panel

    Es idempotente: si se corta, se vuelve a correr y salta lo que ya está.
    Se lanza con instalar.cmd, en la raíz del repositorio.

.EXAMPLE
    instalar.cmd
    instalar.cmd -ShipsGoToken abc123
    instalar.cmd -RutaPostgres D:\pgsql -PuertoBD 5433
#>
[CmdletBinding()]
param(
    [string]$RutaPostgres = (Join-Path $HOME "pgsql"),
    [int]$PuertoBD = 5432,
    [string]$ShipsGoToken = "",
    [string]$AdminUsuario = "",
    [string]$AdminNombre = "",
    [switch]$SinAdmin,
    # No pregunta nada: token vacío y Administrador solo si viene -AdminUsuario.
    [switch]$SinPreguntas
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Raiz = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Raiz "backend"
$Frontend = Join-Path $Raiz "frontend"
# Ruta larga: con perfiles de nombre raro, %TEMP% llega en formato 8.3
# (C:\Users\M4A71~1.MAY\...) y Move-Item no lo resuelve.
$Descargas = Join-Path (Get-Item -LiteralPath $env:TEMP).FullName "trackin-instalacion"
New-Item -ItemType Directory -Force $Descargas | Out-Null

$URL_PYTHON = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
$URL_NODE = "https://nodejs.org/dist/latest-v24.x"
$URL_POSTGRES = "https://get.enterprisedb.com/postgresql/postgresql-16.14-1-windows-x64-binaries.zip"
# De archive/: OSGeo saca de la carpeta principal la versión anterior apenas
# publica una nueva (23/11/2026: 3.7.0), y el enlace directo da 404.
$URL_POSTGIS = "https://download.osgeo.org/postgis/windows/pg16/archive/postgis-bundle-pg16-3.6.2x64.zip"

function Paso([string]$texto) { Write-Host ""; Write-Host "==> $texto" -ForegroundColor Cyan }
function Ok([string]$texto) { Write-Host "    OK  $texto" -ForegroundColor Green }
function Info([string]$texto) { Write-Host "    $texto" }
function Falla([string]$texto) { throw $texto }

function Ejecutar([string]$exe, [string[]]$argumentos, [string]$queHace) {
    & $exe @argumentos
    if ($LASTEXITCODE -ne 0) { Falla "$queHace terminó con error (código $LASTEXITCODE)." }
}

function Descargar([string]$url, [string]$destino) {
    if (Test-Path $destino) { Info "Ya descargado: $(Split-Path -Leaf $destino)"; return }
    Info "Descargando $(Split-Path -Leaf $destino)..."
    $parcial = "$destino.parcial"
    & curl.exe -L --fail --silent --show-error -o $parcial $url
    if ($LASTEXITCODE -ne 0) {
        Info "curl falló; reintento con Invoke-WebRequest."
        Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $parcial
    }
    [IO.File]::Move($parcial, $destino)
}

function Extraer([string]$zip, [string]$destino) {
    New-Item -ItemType Directory -Force $destino | Out-Null
    # tar (incluido en Windows 10+) es mucho más rápido que Expand-Archive.
    & tar.exe -xf $zip -C $destino 2>$null
    if ($LASTEXITCODE -ne 0) { Expand-Archive -Force -Path $zip -DestinationPath $destino }
}

function Agregar-AlPath([string]$carpeta) {
    $usuario = [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not $usuario) { $usuario = "" }
    if (($usuario -split ";") -notcontains $carpeta) {
        [Environment]::SetEnvironmentVariable("Path", ($usuario.TrimEnd(";") + ";" + $carpeta).TrimStart(";"), "User")
    }
    if (($env:Path -split ";") -notcontains $carpeta) { $env:Path = "$carpeta;$env:Path" }
}

function Leer-Env([string]$archivo) {
    $valores = @{}
    if (Test-Path $archivo) {
        foreach ($linea in Get-Content $archivo) {
            if ($linea -match '^\s*([A-Z0-9_]+)\s*=\s*(.*)$') { $valores[$Matches[1]] = $Matches[2].Trim() }
        }
    }
    return $valores
}

function Escribir-SinBOM([string]$archivo, [string]$contenido) {
    [IO.File]::WriteAllText($archivo, $contenido, (New-Object Text.UTF8Encoding($false)))
}

# ---------------------------------------------------------------------------
Paso "0. Comprobaciones"
if (-not (Test-Path (Join-Path $Backend "requirements-dev.txt"))) {
    Falla "No encuentro backend\requirements-dev.txt. Corra instalar.cmd desde la raíz del repositorio."
}
if ($Raiz.Length -gt 80) {
    Write-Host "    AVISO: la ruta del repositorio es larga ($($Raiz.Length) caracteres)." -ForegroundColor Yellow
    Write-Host "    Sin rutas largas de Windows, pip puede fallar. Mejor: C:\Users\<usuario>\Documents\GitHub\TrackIn" -ForegroundColor Yellow
}
Ok "Repositorio en $Raiz"

# ---------------------------------------------------------------------------
Paso "1. Python 3.12"
function Buscar-Python {
    $candidatos = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
        "C:\Program Files\Python312\python.exe"
    )
    foreach ($c in $candidatos) { if (Test-Path $c) { return $c } }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        $ruta = & $py.Source -3.12 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $ruta) { return $ruta.Trim() }
    }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    # El python.exe de WindowsApps es un atajo a la Microsoft Store, no un Python.
    if ($python -and $python.Source -notlike "*WindowsApps*") {
        $version = & $python.Source --version 2>&1
        if ("$version" -like "Python 3.12*") { return $python.Source }
    }
    return $null
}
$Python = Buscar-Python
if (-not $Python) {
    $instalador = Join-Path $Descargas "python-3.12.10-amd64.exe"
    Descargar $URL_PYTHON $instalador
    Info "Instalando Python 3.12 para este usuario (un par de minutos)..."
    $p = Start-Process -FilePath $instalador -Wait -PassThru -ArgumentList @(
        "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_test=0", "Include_launcher=0"
    )
    if ($p.ExitCode -ne 0) { Falla "El instalador de Python terminó con código $($p.ExitCode)." }
    $Python = Buscar-Python
    if (-not $Python) { Falla "Python se instaló pero no lo encuentro. Abra una consola nueva y vuelva a correr instalar.cmd." }
}
Ok "$(& $Python --version) en $Python"

# ---------------------------------------------------------------------------
Paso "2. Node.js"
function Buscar-Node {
    $local = Join-Path $env:LOCALAPPDATA "Programs\nodejs\node.exe"
    if (Test-Path $local) { return $local }
    $node = Get-Command node.exe -ErrorAction SilentlyContinue
    if ($node) {
        $mayor = [int]((& $node.Source --version).TrimStart("v").Split(".")[0])
        if ($mayor -ge 20) { return $node.Source }
    }
    return $null
}
$Node = Buscar-Node
if (-not $Node) {
    # El MSI de Node pide administrador; el ZIP no.
    $sumas = (Invoke-WebRequest -UseBasicParsing "$URL_NODE/SHASUMS256.txt").Content
    $linea = ($sumas -split "`n") | Where-Object { $_ -match "node-v[\d.]+-win-x64\.zip" } | Select-Object -First 1
    $hash, $nombre = ($linea.Trim() -split "\s+")
    $zip = Join-Path $Descargas $nombre
    Descargar "$URL_NODE/$nombre" $zip
    if ((Get-FileHash -Algorithm SHA256 $zip).Hash -ne $hash.ToUpper()) {
        Remove-Item $zip; Falla "La descarga de Node no coincide con su suma SHA256. Vuelva a correr instalar.cmd."
    }
    $programas = Join-Path $env:LOCALAPPDATA "Programs"
    $tmp = Join-Path $Descargas "node-extraido"
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    Extraer $zip $tmp
    $carpeta = Get-ChildItem $tmp -Directory | Select-Object -First 1
    New-Item -ItemType Directory -Force $programas | Out-Null
    Move-Item $carpeta.FullName (Join-Path $programas "nodejs")
    $Node = Buscar-Node
}
$NodeDir = Split-Path -Parent $Node
Agregar-AlPath $NodeDir
$Npm = Join-Path $NodeDir "npm.cmd"
Ok "Node $(& $Node --version) en $NodeDir"

# ---------------------------------------------------------------------------
Paso "3. PostgreSQL 16 + PostGIS en $RutaPostgres"
$PgBin = Join-Path $RutaPostgres "bin"
$PgCtl = Join-Path $PgBin "pg_ctl.exe"
if (-not (Test-Path $PgCtl)) {
    $zipPg = Join-Path $Descargas "postgresql-16.14-1-windows-x64-binaries.zip"
    Descargar $URL_POSTGRES $zipPg
    $tmp = Join-Path $Descargas "pg-extraido"
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    Info "Extrayendo PostgreSQL..."
    Extraer $zipPg $tmp
    New-Item -ItemType Directory -Force (Split-Path -Parent $RutaPostgres) | Out-Null
    # El antivirus a veces retiene la carpeta recién extraída: se reintenta.
    for ($i = 1; $i -le 5; $i++) {
        try { Move-Item (Join-Path $tmp "pgsql") $RutaPostgres; break }
        catch { if ($i -eq 5) { throw }; Start-Sleep -Seconds 3 }
    }
}
if (-not (Test-Path (Join-Path $RutaPostgres "share\extension\postgis.control"))) {
    $zipGis = Join-Path $Descargas "postgis-bundle-pg16-3.6.2x64.zip"
    Descargar $URL_POSTGIS $zipGis
    $tmp = Join-Path $Descargas "postgis-extraido"
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    Info "Extrayendo PostGIS..."
    Extraer $zipGis $tmp
    $origen = if (Test-Path (Join-Path $tmp "bin")) { $tmp } else { (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName }
    # Un postgres corriendo desde esta carpeta (de un intento anterior) retiene
    # sus DLL y la copia falla («sección asignada a usuario abierta», 24/11/2026).
    $corriendo = Get-Process postgres -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -like "$RutaPostgres\*" }
    if ($corriendo) {
        Info "Detengo el PostgreSQL de un intento anterior para poder copiar PostGIS..."
        $corriendo | Stop-Process -Force
        Start-Sleep -Seconds 2
    }
    & robocopy.exe $origen $RutaPostgres /E /R:3 /W:3 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) {
        # Si el antivirus sigue reteniendo alguna DLL que PostgreSQL ya trae
        # (libcrypto, libssl...), se deja la suya: son la misma versión mayor.
        Write-Host "    Algunos archivos están en uso; copio solo los que faltan." -ForegroundColor Yellow
        & robocopy.exe $origen $RutaPostgres /E /XC /XN /XO /R:3 /W:3 /NFL /NDL /NJH /NJS /NP | Out-Null
        if ($LASTEXITCODE -ge 8) { Falla "No pude copiar PostGIS en $RutaPostgres (robocopy $LASTEXITCODE)." }
    }
}
Ok "Binarios en $RutaPostgres"

# ---------------------------------------------------------------------------
Paso "4. Base de datos"
$EnvBackend = Join-Path $Backend ".env"
$envActual = Leer-Env $EnvBackend
$PgData = Join-Path $RutaPostgres "data"
if (Test-Path (Join-Path $PgData "PG_VERSION")) {
    if (-not $envActual["POSTGRES_PASSWORD"]) {
        Falla "Ya existe un cluster en $PgData pero backend\.env no trae POSTGRES_PASSWORD. Agréguela a mano y vuelva a correr."
    }
    $Contrasena = $envActual["POSTGRES_PASSWORD"]
    if ($envActual["POSTGRES_PORT"]) { $PuertoBD = [int]$envActual["POSTGRES_PORT"] }
    Info "El cluster ya existía; uso la contraseña de backend\.env."
} else {
    $Contrasena = if ($envActual["POSTGRES_PASSWORD"]) { $envActual["POSTGRES_PASSWORD"] } else {
        (& $Python -c "import secrets; print(secrets.token_urlsafe(24))").Trim()
    }
    $archivoClave = Join-Path $Descargas "pwfile.txt"
    Escribir-SinBOM $archivoClave $Contrasena
    try {
        Ejecutar (Join-Path $PgBin "initdb.exe") @(
            "-D", $PgData, "-U", "trackin", "--pwfile=$archivoClave",
            "-E", "UTF8", "--locale=C", "-A", "scram-sha-256"
        ) "initdb"
    } finally { Remove-Item -Force $archivoClave -ErrorAction SilentlyContinue }
    Add-Content -Path (Join-Path $PgData "postgresql.conf") -Value "`nport = $PuertoBD" -Encoding ASCII
    Ok "Cluster creado (usuario trackin, puerto $PuertoBD)"
}

& $PgCtl status -D $PgData *> $null
if ($LASTEXITCODE -ne 0) {
    Info "Arrancando PostgreSQL..."
    # Ventana oculta: así la base no muere si se cierra esta consola.
    Start-Process -WindowStyle Hidden -FilePath $PgCtl -ArgumentList @(
        "-D", "`"$PgData`"", "-l", "`"$(Join-Path $PgData 'server.log')`"", "start"
    )
}
$listo = $false
for ($i = 0; $i -lt 60; $i++) {
    & (Join-Path $PgBin "pg_isready.exe") -h localhost -p $PuertoBD *> $null
    if ($LASTEXITCODE -eq 0) { $listo = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $listo) { Falla "PostgreSQL no respondió en el puerto $PuertoBD. Revise $PgData\server.log" }

$env:PGPASSWORD = $Contrasena
foreach ($base in "trackin_dev", "trackin_test") {
    $existe = & (Join-Path $PgBin "psql.exe") -h localhost -p $PuertoBD -U trackin -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$base'"
    if ($LASTEXITCODE -ne 0) { Falla "No pude conectarme a PostgreSQL con el usuario trackin." }
    if ("$existe".Trim() -ne "1") {
        Ejecutar (Join-Path $PgBin "createdb.exe") @(
            "-h", "localhost", "-p", "$PuertoBD", "-U", "trackin", "-O", "trackin",
            "-E", "UTF8", "--locale=C", "-T", "template0", $base
        ) "createdb $base"
    }
}
Remove-Item Env:\PGPASSWORD
Ok "PostgreSQL arriba en el puerto $PuertoBD con trackin_dev y trackin_test"

# ---------------------------------------------------------------------------
Paso "5. Configuración del backend"
if (Test-Path $EnvBackend) {
    Info "backend\.env ya existe: no lo toco."
} else {
    if (-not $ShipsGoToken -and -not $SinPreguntas) {
        $ShipsGoToken = Read-Host "    Token de la API de ShipsGo (Enter para dejarlo vacío; se agrega después en backend\.env)"
    }
    $clave = (& $Python -c "import secrets; print(secrets.token_urlsafe(48))").Trim()
    $lineas = @(
        "POSTGRES_USER=trackin",
        "POSTGRES_PASSWORD=$Contrasena",
        "POSTGRES_DB=trackin_dev",
        "POSTGRES_HOST=localhost",
        "POSTGRES_PORT=$PuertoBD",
        "",
        "ENVIRONMENT=development",
        "DEBUG=true",
        "BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173",
        "SECRET_KEY=$clave",
        "",
        "# Rastreo. Sin token, el sistema funciona pero no rastrea."
    )
    if ($ShipsGoToken) { $lineas += "SHIPSGO_API_TOKEN=$ShipsGoToken" } else { $lineas += "# SHIPSGO_API_TOKEN=" }
    Escribir-SinBOM $EnvBackend (($lineas -join "`r`n") + "`r`n")
    Ok "backend\.env creado"
}

# ---------------------------------------------------------------------------
Paso "6. Dependencias del backend y migraciones (unos minutos)"
$VenvPy = Join-Path $Backend ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) { Ejecutar $Python @("-m", "venv", (Join-Path $Backend ".venv")) "Crear el entorno de Python" }
Ejecutar $VenvPy @("-m", "pip", "install", "--disable-pip-version-check", "-q", "--upgrade", "pip") "Actualizar pip"
Ejecutar $VenvPy @("-m", "pip", "install", "--disable-pip-version-check", "--retries", "10", "--timeout", "60", "-q", "-r", (Join-Path $Backend "requirements-dev.txt")) "pip install"
Ok "Dependencias de Python instaladas"
Push-Location $Backend
try {
    # Recién extraído, el antivirus revisa cada postgres.exe que se lanza y la
    # base puede rechazar conexiones un rato («CreateProcess() call failed ...
    # error code 5» en server.log; visto en la prueba del 23/11/2026). Se reintenta.
    for ($intento = 1; $intento -le 4; $intento++) {
        & (Join-Path $Backend ".venv\Scripts\alembic.exe") upgrade head
        if ($LASTEXITCODE -eq 0) { break }
        if ($intento -eq 4) { Falla "alembic upgrade head terminó con error (código $LASTEXITCODE)." }
        Write-Host "    La base no respondió a tiempo; reintento en 20 s ($intento de 3)..." -ForegroundColor Yellow
        Start-Sleep -Seconds 20
    }
} finally { Pop-Location }
Ok "Base migrada"

# ---------------------------------------------------------------------------
Paso "7. Primer Administrador"
if ($SinAdmin) {
    Info "Omitido (-SinAdmin)."
} else {
    if (-not $AdminUsuario -and -not $SinPreguntas) { $AdminUsuario = Read-Host "    Usuario del Administrador (Enter para omitir)" }
    if ($AdminUsuario) {
        if (-not $AdminNombre) { $AdminNombre = if ($SinPreguntas) { $AdminUsuario } else { Read-Host "    Nombre completo" } }
        Push-Location $Backend
        try {
            & $VenvPy (Join-Path $Backend "scripts\crear_usuario.py") $AdminUsuario $AdminNombre ADMINISTRADOR
            if ($LASTEXITCODE -eq 0) { Ok "Administrador '$AdminUsuario' creado" }
            else { Write-Host "    No se creó (¿ya existía?). Se puede repetir con scripts\crear_usuario.py." -ForegroundColor Yellow }
        } finally { Pop-Location }
    } else {
        Info "Omitido. Después: cd backend; .venv\Scripts\python scripts\crear_usuario.py <usuario> ""<Nombre>"" ADMINISTRADOR"
    }
}

# ---------------------------------------------------------------------------
Paso "8. Panel web (dependencias de Node)"
$EnvFrontend = Join-Path $Frontend ".env"
if (-not (Test-Path $EnvFrontend)) { Copy-Item (Join-Path $Frontend ".env.example") $EnvFrontend }
Push-Location $Frontend
try { Ejecutar $Npm @("ci", "--no-audit", "--no-fund", "--loglevel=error") "npm ci" } finally { Pop-Location }
Ok "Dependencias del panel instaladas"

# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Instalación completa." -ForegroundColor Green
Write-Host "Para arrancar TrackIn: doble clic en iniciar.cmd (o escribir iniciar.cmd en esta carpeta)."
Write-Host "Panel: http://localhost:5173   API: http://localhost:8000/health"
