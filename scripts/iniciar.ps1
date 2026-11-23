<#
.SYNOPSIS
    Arranca TrackIn: PostgreSQL, la API, el worker de rastreo y el panel.

.DESCRIPTION
    PostgreSQL corre oculto (sobrevive a cerrar ventanas). La API, el worker y el
    panel abren cada uno su ventana: cerrarla detiene ese proceso. Al final abre
    el panel en el navegador. Se lanza con iniciar.cmd, en la raíz del repositorio.
#>
[CmdletBinding()]
param(
    [string]$RutaPostgres = (Join-Path $HOME "pgsql")
)

$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Raiz "backend"
$Frontend = Join-Path $Raiz "frontend"

$puerto = 5432
$envBackend = Join-Path $Backend ".env"
if (-not (Test-Path $envBackend)) { throw "Falta backend\.env: corra primero instalar.cmd." }
foreach ($linea in Get-Content $envBackend) {
    if ($linea -match '^\s*POSTGRES_PORT\s*=\s*(\d+)') { $puerto = [int]$Matches[1] }
}

$PgBin = Join-Path $RutaPostgres "bin"
$PgData = Join-Path $RutaPostgres "data"
& (Join-Path $PgBin "pg_ctl.exe") status -D $PgData *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Arrancando PostgreSQL..."
    Start-Process -WindowStyle Hidden -FilePath (Join-Path $PgBin "pg_ctl.exe") -ArgumentList @(
        "-D", "`"$PgData`"", "-l", "`"$(Join-Path $PgData 'server.log')`"", "start"
    )
}
$listo = $false
for ($i = 0; $i -lt 90; $i++) {
    & (Join-Path $PgBin "pg_isready.exe") -h localhost -p $puerto *> $null
    if ($LASTEXITCODE -eq 0) { $listo = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $listo) { throw "PostgreSQL no respondió en el puerto $puerto. Revise $PgData\server.log" }
Write-Host "PostgreSQL arriba en el puerto $puerto."

$ocupados = Get-NetTCPConnection -State Listen -LocalPort 8000, 5173 -ErrorAction SilentlyContinue
if ($ocupados) {
    Write-Host "TrackIn ya parece estar corriendo (puertos 8000/5173 ocupados): abro el panel." -ForegroundColor Yellow
    Write-Host "Si no responde, cierre las ventanas de TrackIn y vuelva a correr iniciar.cmd."
    Start-Process "http://localhost:5173"
    exit 0
}

function Ventana([string]$titulo, [string]$carpeta, [string]$comando) {
    Start-Process -FilePath "cmd.exe" -WorkingDirectory $carpeta -ArgumentList "/k", "title $titulo && $comando"
}
Ventana "TrackIn - API" $Backend ".venv\Scripts\python -m uvicorn app.main:app --port 8000"
Ventana "TrackIn - Worker de rastreo" $Backend ".venv\Scripts\python -m app.workers"
Ventana "TrackIn - Panel" $Frontend "npm.cmd run dev"

Write-Host "Esperando a la API..."
# El primer arranque tarda más: el antivirus revisa las dependencias recién instaladas.
for ($i = 0; $i -lt 120; $i++) {
    try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 http://localhost:8000/health | Out-Null; break }
    catch { Start-Sleep -Seconds 1 }
}
Start-Process "http://localhost:5173"
Write-Host "Listo. Para detener: cerrar las tres ventanas. La base sigue corriendo; se detiene con"
Write-Host "  `"$PgBin\pg_ctl.exe`" -D `"$PgData`" stop"
