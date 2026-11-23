@echo off
rem Instala TrackIn de una vez: Python, Node, PostgreSQL + PostGIS, dependencias y base.
rem Ver docs\manual-instalacion.md. Acepta los parametros de scripts\instalar.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\instalar.ps1" %*
if errorlevel 1 (
  echo.
  echo La instalacion se detuvo con un error. Corrija lo que dice arriba y vuelva a correr instalar.cmd:
  echo salta lo que ya quedo hecho.
)
pause
