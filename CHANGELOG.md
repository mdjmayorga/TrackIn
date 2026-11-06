# Notas de versión

Cada versión de TrackIn que se despliega tiene una etiqueta de git `vX.Y.Z` y una
entrada aquí. La versión vive en `backend/app/__init__.py` (y se repite en
`backend/pyproject.toml` y `frontend/package.json`; una prueba verifica que
coincidan). La muestran `/health` y el menú **Configuración** del panel. Cómo
desplegar una versión y cómo volver a la anterior: [docs/deployment.md](docs/deployment.md) §9.

Numeración: el tercer número sube con una corrección, el segundo con algo nuevo
que no cambia cómo se usa lo que ya existe, y el primero con un cambio que obliga
a los usuarios o a la operación a hacer algo distinto.

---

## v1.0.0 — 06/11/2026

Primera versión para producción: el sistema construido en la práctica, completo.

**Migración más reciente:** `0034_cierre_sin_referencia`. Una base vacía llega con
`alembic upgrade head`.

### Qué hace

- **Carga semanal del Z-tracking** desde el panel, con plantilla descargable,
  validación de formato campo por campo e informe de lo que no entró y por qué.
  La línea sin referencia de embarque no entra, y una carga completa cierra los
  pedidos activos que siguen sin ella.
- **Rastreo** de BL, contenedores, bookings y guías aéreas madre con ShipsGo, y
  de guías hijas con el manifiesto de TICA. Altas en ShipsGo desde el panel, con
  control del saldo de créditos y aviso antes de que se agoten.
- **Cálculo** de la fecha disponible proyectada y del estado de cumplimiento,
  recalculados ante cualquier cambio, con el desglose a la vista en el detalle.
- **Panel**: indicadores, próximos arribos, grilla filtrable con carrusel, mapas
  marítimo y aéreo con rutas, y una leyenda única.
- **Detalle del pedido**: desglose del cálculo, elemento rastreado, arribos, línea
  de tiempo con intervenciones e hitos del viaje, y mapa del envío.
- **Acciones**: confirmar desembarco, paso a proceso aduanal, recepción en planta,
  liberación de Calidad, ETA manual, ajuste de días y asociación o corrección de
  la referencia. Todo queda en la bitácora.
- **Cuentas y roles** (Compras, Logística, Planificación, Administrador y Planta),
  administrados desde el panel. Pantalla permanente de planta.
- **Receptor de la API de SAP**, apagado por omisión.

### Cambios desde el Informe 2 (16/10/2026)

- Mapas marítimo y aéreo del panel, con rutas, agrupación de marcadores, recuadro
  por embarque y leyenda (`US-25`, `US-26`, `US-27`).
- Mapa en vivo de ShipsGo y país de origen en el detalle (`US-44`); hitos del viaje
  y transbordos automáticos en la línea de tiempo (`US-29`, `US-30`).
- Plantilla del Z-tracking y validación por campo (`US-59`); la línea sin
  referencia no entra y la carga cierra los activos sin ella (04/11).
- ETA manual (`US-67`); motivo opcional en todas las intervenciones (02/11).
- Altas en ShipsGo y saldo de créditos (`US-55`, `US-57`); cambio de contraseña y
  administración de cuentas (`US-61`, `US-62`); rol y pantalla de planta (`US-33`,
  `US-43`, `US-63`); bandeja de arribos pendientes (`US-48`); frescura de los datos
  (`US-23`).
- Contrato y receptor de la API de SAP, con interruptor (`US-64` a `US-66`).
- Panel reorganizado a pedido del supervisor (04/11): orden de la grilla, mapas
  arriba, grilla visible al entrar y carrusel para todos los roles.
- Pruebas de punta a punta y cobertura de las reglas de negocio (`TASK-06`);
  manuales de instalación y de usuario y guía de despliegue (`TASK-07` a `TASK-09`).
- Contenedores probados de punta a punta y chequeo de salud del panel corregido
  (`PROD-03`, `PROD-04`); versión única y visible (`PROD-06`).

### Pendiente conocido

- El mapa marítimo del panel (`US-25`) y las altas en ShipsGo (`US-55`) falta
  verlos con embarques reales en viaje: depende de la compra de créditos y de la
  primera carga real (`PROD-22`).
