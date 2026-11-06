---
status: proposed
---

# Producción en una máquina virtual Linux con Docker, solo en la red interna

TrackIn sale a producción en una **máquina virtual Linux con Docker** que provee TI de Gutis, accesible **solo desde la red interna** (y desde afuera por la VPN corporativa), con **HTTPS** por un certificado que emite TI. Se elige porque los artefactos de contenedor ya existen y están al día (`TASK-09`), porque los usuarios y la pantalla de planta están todos dentro de la red de Gutis, y porque no exponer el sistema a internet evita endurecer el login y la API frente a ataques que hoy no son un riesgo. El HTTPS no es opcional aunque la red sea interna: la pantalla de planta mantiene el monitor encendido con una API del navegador que solo funciona en un contexto seguro. Confirmada por Mariano el 06/11/2026; queda propuesta hasta que TI confirme que tiene Linux (`docs/backlog/backlog_produccion.md`, `PROD-01`).

## Considered Options

- **Servidor Windows sin Docker** (`docs/deployment.md` §10). Queda como respaldo si TI no tiene Linux: funciona, pero son cuatro servicios de Windows a mano, sin la misma reproducibilidad.
- **Máquina virtual en la nube.** Rechazada mientras los usuarios estén todos en la red interna: agrega un costo mensual, una cuenta que alguien tiene que administrar y la exposición a internet.
- **Internet público.** Rechazada por ahora; si algún día hace falta, se reabre esta decisión con una revisión de seguridad.

## Consequences

- El panel depende de que los navegadores de la red lleguen a los servicios externos del mapa (mosaicos y `embed.shipsgo.com`), y el servidor, a ShipsGo y TICA: la salida a internet se pide a TI como una lista blanca.
- Las imágenes se construyen en el servidor desde una etiqueta de versión de git: el repositorio es público y no hace falta un registro de imágenes.
