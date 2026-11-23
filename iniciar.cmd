@echo off
rem Arranca TrackIn: base, API, worker de rastreo y panel. Ver docs\manual-instalacion.md.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\iniciar.ps1" %*
if errorlevel 1 pause
