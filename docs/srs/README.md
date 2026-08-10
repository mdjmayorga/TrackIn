# SRS de TrackIn — estado del documento

Especificación de Requerimientos de Software del proyecto TrackIn, entregable del
**Sprint 1** de la Práctica de Especialidad (cierre: 21 de agosto de 2026).

| | |
|---|---|
| Archivo | [`SRS_TrackIn_v0.1.docx`](SRS_TrackIn_v0.1.docx) |
| Versión | v0.1 — 10 de agosto de 2026 |
| Estándar | IEEE 830-1998, adaptado |
| Extensión | 41 páginas, ~10.800 palabras, 63 tablas |
| Fuentes | Anteproyecto aprobado + Documento Técnico-Funcional v1.0 (18/06/2026) |

Contenido normativo: **24** requerimientos funcionales, **23** no funcionales,
**9** casos de uso y **14** reglas de negocio, numerados sin huecos.

> La tabla de contenidos ya trae los números de página resueltos. Si editás el
> documento y cambia la paginación, seleccionala y presioná **F9** para actualizarla.

---

## Estado por sección

Leyenda: **Completa** = no requiere más información externa · **Parcial** = redactada
pero con supuestos que hay que confirmar · **Pendiente** = depende de información que
todavía no existe.

| Sección | Estado | Qué falta |
|---|---|---|
| Portada, historial de revisiones, TOC | Completa | — |
| 1.1 Propósito | Completa | — |
| 1.2 Alcance | Completa | Tomado literal del anteproyecto aprobado |
| 1.3 Definiciones y acrónimos | Completa | Ampliable si aparece terminología nueva |
| 1.4 Referencias | Completa | — |
| 1.5 Visión general | Parcial | Confirmar con el asesor si la Escuela exige otro orden de secciones |
| 2.1 Perspectiva del producto | Completa | — |
| 2.2 Funcionalidades | Completa | — |
| 2.3 Características de usuarios | **Parcial** | Número de usuarios por perfil y disponibilidad; posible perfil de Calidad |
| 2.4 Restricciones generales | Completa | — |
| 2.5 Suposiciones y dependencias | **Parcial** | Depende de recibir la muestra del Excel |
| 2.6 Documentos aplicables | Completa | — |
| 3. Actores | **Parcial** | Validar contra los roles del técnico-funcional; definir si hay perfil de solo lectura |
| 4. Requerimientos funcionales | **Parcial** | Priorización a confirmar; posibles RF no contemplados (notificaciones, exportación) |
| 5.1 Rendimiento | **Parcial** | Faltan umbrales numéricos y volumen máximo de pedidos |
| 5.2 Seguridad | Completa | — |
| 5.3 Usabilidad | **Parcial** | Validar wireframes; resolución de la pantalla de planta |
| 5.4–5.5 Confiabilidad y mantenibilidad | Completa | — |
| 5.6 Portabilidad | **Parcial** | Confirmar la desviación de Docker (ver nota abajo) |
| 5.7–5.8 Escalabilidad y stack | Completa | — |
| 6. Casos de uso | **Parcial** | Validar CU-01 y CU-05 contra el proceso real |
| 7. Reglas de negocio | **Parcial** | **Umbrales concretos sin definir** — es el bloqueante más importante |
| 8. Modelo de datos | **Parcial** | Se formaliza en Sprint 2; falta definir cardinalidad pedido↔nave |
| 9. Restricciones y supuestos | **Parcial** | Falta designación nominal de usuarios clave |
| 10. Criterios de aceptación | **Parcial** | Confirmar si la Escuela exige criterios académicos adicionales |
| Anexo A. Glosario extendido | Completa | — |
| Anexo B. Formato del Excel | **Pendiente** | Bloqueado: no existe hasta recibir la muestra real |
| Anexo C. Referencias de APIs | **Parcial** | Falta cuantificar el % de pedidos con identificador de nave |

---

## Checklist de información por conseguir

### De Greivin Mora (supervisor) — 7 puntos

- [ ] **Umbrales de los estados logísticos.** Cuántas horas o días definen "En riesgo"
      frente a "A tiempo". El técnico-funcional propone 48 h como referencia, sin
      confirmar. → Secciones 7.3 (RN-11) y 4.3. **Bloquea el Sprint 3.**
- [ ] **Condición de aplicación del lead time crítico** frente al estándar, y quién
      toma esa decisión. → RN-12
- [ ] Umbrales de rendimiento: tiempo de respuesta aceptable y volumen máximo
      esperado de pedidos simultáneos en tránsito. → RNF-01, RNF-02
- [ ] Confirmar la priorización Alta/Media/Baja de los 24 RF, en particular si RF-18
      (tooltips) y RF-22 (trayecto histórico) deben subir a Alta para la demo.
- [ ] **Aceptar la desviación de Docker.** El anteproyecto contempla contenedores; el
      equipo asignado no permite ejecutarlos por falta de permisos de administrador.
      El entorno corre nativo y los compose quedan como artefacto de despliegue. → 5.6, 9.3
- [ ] Cardinalidad pedido ↔ nave: ¿varias líneas de OC pueden viajar en un mismo buque?
      → Sección 8.5
- [ ] Designación nominal de los usuarios clave de Compras y Logística (el anteproyecto
      los deja como "Por definir") y cadencia de las sesiones de validación. → 9.4

### De las entrevistas con usuarios clave — 8 puntos

- [ ] Número de usuarios por perfil, disponibilidad horaria y si existe un perfil no
      contemplado (por ejemplo, Aseguramiento de la Calidad). → 2.3
- [ ] Validar que los roles del técnico-funcional (Visualizador, Compras, Logística,
      Administrador) se corresponden con los 5 actores definidos. → Sección 3
- [ ] ¿Se requiere un perfil de solo lectura para pantalla permanente en planta? → Sección 3
- [ ] RF no contemplados: notificaciones por correo ante cambio de estado, exportación
      de la grilla a Excel, vistas por proveedor. → Sección 4
- [ ] Validar los flujos de CU-01 (carga de Excel) y CU-05 (confirmación de desembarco),
      que son los que implican intervención manual. → Sección 6
- [ ] Definir si existen estados terminales además de "Cerrado": cancelación de OC,
      rechazo por control de calidad. → RN-13
- [ ] **Qué porcentaje de los pedidos dispone hoy de MMSI, IMO o nombre de buque**, y
      por qué medio se obtiene. Determina cuántos pedidos serán rastreables. → Anexo C.2
- [ ] Resolución y tamaño de la pantalla de visualización permanente, si se instala. → 5.3

### Del profesor asesor (Luis Montoya) — 2 puntos

- [ ] Confirmar si la Escuela exige secciones adicionales o un orden distinto para
      este entregable. → 1.5
- [ ] Confirmar si hay criterios de aceptación académicos adicionales: cobertura mínima
      de pruebas, formato específico de la documentación. → Sección 10

### Muestra de datos — 3 puntos

- [ ] **Archivo Excel real de pedidos en tránsito**, anonimizado si procede. Se pide un
      mínimo de 20 pedidos representativos, con casos marítimos y aéreos, y al menos uno
      sin identificador de rastreo. → Anexo B. **Bloquea RF-01 y RF-02.**
- [ ] Nombres y orden exactos de las columnas, tipos de dato y formato de fecha. → Anexo B
- [ ] Volumen típico de pedidos simultáneos en tránsito. → 2.5, RNF-01

---

## Ruta crítica

Tres pendientes bloquean trabajo de sprints posteriores y conviene resolverlos primero:

1. **Umbrales de estado** (Greivin) — sin ellos no se puede implementar el motor de
   cálculo, que es el núcleo del Objetivo Específico 2.
2. **Muestra del Excel** (empresa) — sin ella no se puede construir ni probar el módulo
   de carga, primer eslabón de toda la cadena de datos.
3. **Porcentaje de pedidos con identificador de nave** (Logística) — determina si el
   producto resuelve el problema para una fracción útil de la operación o para una
   minoría. Es el supuesto de mayor riesgo de todo el proyecto.

---

## Cómo se regenera

El documento se genera con un script de Node que usa la librería `docx`. Los fuentes
están versionados en [`generador/`](generador/):

```bash
cd docs/srs/generador && npm install && npm run build
```

Regenerar **sobrescribe** el `.docx`, así que usá esa vía solo para cambios de fondo
en la estructura. Para correcciones de redacción conviene editar el `.docx`
directamente y registrar la nueva versión en el historial de revisiones —si no, se
pierden al regenerar.

Después de regenerar, abrí el documento en Word y actualizá la tabla de contenidos
con **F9**: el script la deja como campo sin resolver y los números de página
aparecen en blanco hasta que Word los calcula.
