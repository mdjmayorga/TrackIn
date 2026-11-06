---
status: accepted
---

# Solo producción da de alta en ShipsGo

Gutis tiene **una sola cuenta de ShipsGo** y un solo paquete de créditos, y desarrollo y producción usarían el mismo token. Desde la salida a producción, **el token de la API vive solo en el servidor** y su worker es el único que hace altas; los equipos de desarrollo trabajan con los payloads grabados de las pruebas, o con el worker apagado. Si no, una carga de prueba en un equipo de desarrollo gasta créditos reales y da de alta referencias que producción después cree propias, y el saldo que lleva TrackIn (`US-57`) deja de coincidir con el de la cuenta. Aceptada el 06/11/2026 (`docs/backlog/backlog_produccion.md`, D12 y `PROD-12`).

## Considered Options

- **Una segunda cuenta de ShipsGo para desarrollo.** Rechazada por ahora: duplica el costo y la administración para un uso marginal.
- **Que desarrollo use el token con cuidado y no dé de alta.** Insuficiente: basta un clic en «Dar de alta» en un equipo de desarrollo para gastar uno; la regla tiene que ser que el token no esté.
