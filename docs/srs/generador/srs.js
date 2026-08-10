const H = require("./build.js");
const {
  fs, Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  TableOfContents, PageBreak, Footer, PageNumber, LevelFormat,
  CONTENT_W, AZUL, GRIS_ENC, MARCADORES,
  t, p, h1, h2, h3, bullet, marcador, celda, tabla, fichaTabla,
  espacio, RF, CU, RN,
} = H;

const FECHA = "10 de agosto de 2026";
const M = MARCADORES;

// ============================================================== PORTADA
const centrado = (text, o = {}) =>
  new Paragraph({
    children: [t(text, o)],
    alignment: AlignmentType.CENTER,
    spacing: { after: o.after || 100 },
  });

const portada = [
  ...espacio(2),
  centrado("INSTITUTO TECNOLÓGICO DE COSTA RICA", { bold: true, size: 26, color: AZUL }),
  centrado("ESCUELA DE INGENIERÍA EN COMPUTACIÓN", { bold: true, size: 24, color: AZUL }),
  centrado("BACHILLERATO EN INGENIERÍA EN COMPUTACIÓN", { size: 22, color: AZUL, after: 600 }),
  ...espacio(2),
  centrado("ESPECIFICACIÓN DE REQUERIMIENTOS DE SOFTWARE (SRS)", { bold: true, size: 32 }),
  ...espacio(1),
  centrado("TrackIn — Automatización del seguimiento logístico de compras internacionales de insumos farmacéuticos mediante rastreo marítimo y aéreo en tiempo real para Laboratorios Gutis", { size: 24, italics: true, after: 400 }),
  ...espacio(2),
  centrado("Documento elaborado conforme al estándar IEEE 830-1998, adaptado", { size: 20, italics: true, after: 500 }),
  ...espacio(3),
  new Table({
    columnWidths: [3200, 6160],
    width: { size: CONTENT_W, type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE },
      left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE },
      insideHorizontal: { style: BorderStyle.NONE }, insideVertical: { style: BorderStyle.NONE },
    },
    rows: [
      ["Autor", "Mariano de Jesús Mayorga Halabi"],
      ["Carné", "2022075454"],
      ["Correo", "mamayorga@estudiantec.cr"],
      ["Empresa", "Laboratorios Gutis Ltda."],
      ["Supervisor de empresa", "Greivin Mora Ferreto — Gerente Centro de Competencias"],
      ["Profesor asesor", "Luis Montoya Poitevien"],
      ["Entregable", "Sprint 1 — Práctica de Especialidad"],
      ["Versión", "v0.1"],
      ["Fecha", FECHA],
    ].map(([k, v]) => new TableRow({
      children: [celda(k, 3200, { bold: true }), celda(v, 6160)],
    })),
  }),
];

// =================================================== HISTORIAL DE REVISIONES
const historial = [
  new Paragraph({ children: [t("Historial de revisiones", { bold: true, size: 28, color: AZUL })], pageBreakBefore: true, spacing: { after: 200 } }),
  tabla(
    ["Versión", "Fecha", "Autor", "Descripción del cambio"],
    [["v0.1", FECHA, "Mariano Mayorga", "Versión inicial. Estructura completa del documento y prellenado a partir del anteproyecto y del documento técnico-funcional."]],
    [1200, 1600, 2200, 4360]
  ),
  ...espacio(1),
  p("Este documento se mantiene bajo control de versiones en el repositorio del proyecto. Toda modificación posterior a la aprobación de la versión v1.0 debe registrarse en esta tabla e ir acompañada de la aprobación del supervisor de empresa."),
];

// ==================================================== TABLA DE CONTENIDOS
const toc = [
  new Paragraph({ children: [t("Tabla de contenidos", { bold: true, size: 28, color: AZUL })], pageBreakBefore: true, spacing: { after: 200 } }),
  new Paragraph({ children: [t("Al abrir el documento en Word, coloque el cursor sobre la tabla y presione F9 para actualizar los números de página.", { italics: true, size: 18 })], spacing: { after: 200 } }),
  new TableOfContents("Contenido", { hyperlink: true, headingStyleRange: "1-3" }),
];

// ========================================================= 1. INTRODUCCIÓN
const seccion1 = [
  h1("1. Introducción"),

  h2("1.1 Propósito del documento"),
  p("Este documento especifica los requerimientos funcionales y no funcionales del sistema TrackIn, una aplicación web empresarial para el seguimiento logístico de compras internacionales de insumos farmacéuticos de Laboratorios Gutis Ltda."),
  p("El documento persigue tres fines. Primero, servir de base contractual entre el estudiante practicante, Laboratorios Gutis y la Escuela de Ingeniería en Computación del Instituto Tecnológico de Costa Rica, delimitando de forma inequívoca qué se construirá durante la Práctica de Especialidad. Segundo, guiar las etapas de diseño, construcción y prueba del sistema, sirviendo de referencia para el diseño del modelo de datos y de la arquitectura. Tercero, establecer los criterios objetivos contra los cuales se verificará la aceptación de cada entregable."),
  p("La audiencia prevista comprende al supervisor de empresa, al profesor asesor, a los usuarios clave de las áreas de Compras, Logística y Planificación de Producción, y al personal técnico del Centro de Competencias que asumirá el mantenimiento y el eventual despliegue productivo del sistema."),
  p("Este documento corresponde al primero de los productos esperados del Objetivo Específico 1 del anteproyecto: el documento de especificación de requerimientos funcionales y no funcionales."),

  h2("1.2 Alcance del sistema"),
  p("TrackIn es una aplicación web que centraliza la telemetría logística de las compras internacionales de Laboratorios Gutis, cruzando datos geoespaciales satelitales en tiempo real con la información maestra de pedidos de compra. El sistema calcula la fecha proyectada de disponibilidad de cada pedido combinando la ETA obtenida de las APIs de rastreo con el lead time maestro del destino, y genera indicadores de riesgo cuando existe posibilidad de incumplimiento respecto a la fecha de entrega comprometida."),
  p("El producto de esta práctica es un sistema funcional en entorno de desarrollo, acompañado de la documentación técnica necesaria para su posterior despliegue productivo por parte del Centro de Competencias."),

  h3("1.2.1 Dentro del alcance"),
  bullet("Análisis de requerimientos funcionales y no funcionales, con base en el documento técnico-funcional proporcionado por la empresa."),
  bullet("Diseño del modelo de datos relacional con soporte geoespacial mediante PostGIS."),
  bullet("Diseño de la arquitectura del sistema: backend, frontend, base de datos e integraciones."),
  bullet("Diseño de wireframes y prototipos de interfaz del dashboard."),
  bullet("Desarrollo del backend en FastAPI, con consumo de APIs de rastreo marítimo (AIS) y aéreo (ADS-B)."),
  bullet("Implementación del servicio de cálculo automático de estados logísticos."),
  bullet("Desarrollo del frontend en React, con dashboard, grilla, mapas Leaflet y KPIs."),
  bullet("Implementación de la base de datos PostgreSQL con historial de tracking."),
  bullet("Carga de pedidos desde archivos Excel como fuente inicial de datos."),
  bullet("Ejecución del sistema en entorno de desarrollo local."),
  bullet("Pruebas funcionales, de integración y demostración con usuarios clave."),
  bullet("Documentación técnica: manual de instalación local, manual de usuario y guía de despliegue para producción."),

  h3("1.2.2 Fuera del alcance"),
  p("Las siguientes capacidades quedan explícitamente excluidas y se contemplan como implementación futura del Centro de Competencias:"),
  bullet("Despliegue a producción en la infraestructura corporativa de Laboratorios Gutis."),
  bullet("Configuración de servidor web productivo, balanceo de carga y terminación SSL."),
  bullet("Integración con el sistema de autenticación corporativo (Active Directory / SSO)."),
  bullet("Configuración de sistema de colas distribuido en modo productivo."),
  bullet("Monitoreo, logging centralizado y alertas de producción."),
  bullet("Integración automática directa con SAP S/4HANA."),
  bullet("Trazabilidad automática por contenedor, BL o booking sin dato de nave asociado."),
  bullet("Gestión documental de facturas, BL, AWB, DUAs u otros documentos."),
  bullet("Predicción avanzada de retrasos por congestión portuaria o condiciones climáticas."),
  bullet("Aplicación móvil nativa."),
  bullet("Contratación de licencias de APIs comerciales de rastreo."),

  h2("1.3 Definiciones, acrónimos y abreviaciones"),
  p("La siguiente tabla recoge la terminología empleada a lo largo del documento. El Anexo A amplía este glosario con términos del dominio logístico y farmacéutico."),
  tabla(
    ["Término", "Definición"],
    [
      ["ADS-B", "Automatic Dependent Surveillance–Broadcast. Tecnología por la cual una aeronave difunde periódicamente su posición derivada de navegación satelital. Es la fuente de los datos de rastreo aéreo del sistema."],
      ["AIS", "Automatic Identification System. Sistema de identificación automática que las embarcaciones transmiten por radio con su identidad, posición, rumbo y velocidad. Es la fuente de los datos de rastreo marítimo."],
      ["API (informática)", "Application Programming Interface. Interfaz que permite la comunicación entre sistemas de software."],
      ["API (farmacéutico)", "Active Pharmaceutical Ingredient, o principio activo farmacéutico. Materia prima crítica cuya importación monitorea el sistema. En este documento el sentido se indica siempre que exista riesgo de ambigüedad."],
      ["ATA", "Actual Time of Arrival. Fecha y hora real de llegada reportada por la fuente externa."],
      ["AWB", "Air Waybill, o guía aérea. Documento de transporte emitido para un embarque aéreo."],
      ["BL", "Bill of Lading, o conocimiento de embarque. Documento de transporte marítimo que acredita el contrato de flete y la recepción de la mercancía."],
      ["DUA", "Declaración Única Aduanera. Documento de declaración ante la autoridad aduanera costarricense."],
      ["ERP", "Enterprise Resource Planning. Sistema corporativo de planificación de recursos; en Gutis, SAP S/4HANA."],
      ["ETA", "Estimated Time of Arrival. Fecha y hora estimada de llegada al destino, obtenida de la API de rastreo."],
      ["IMO", "International Maritime Organization number. Identificador único y permanente asignado al casco de un buque."],
      ["KPI", "Key Performance Indicator. Indicador clave de desempeño mostrado en la cinta superior del dashboard."],
      ["Lead time", "Tiempo, en días, que transcurre entre el arribo de la carga al destino y su disponibilidad efectiva en planta, incluyendo desembarque, nacionalización y tratamiento."],
      ["MMSI", "Maritime Mobile Service Identity. Identificador de nueve dígitos de la estación de radio de una embarcación."],
      ["MVP", "Minimum Viable Product. Producto mínimo viable."],
      ["OC", "Orden de Compra. Documento que formaliza un pedido a un proveedor."],
      ["PostGIS", "Extensión geoespacial de PostgreSQL que habilita tipos geométricos y consultas espaciales."],
      ["REST", "Representational State Transfer. Estilo arquitectónico de los servicios web del backend."],
      ["SLA", "Service Level Agreement. Acuerdo de nivel de servicio."],
      ["SRS", "Software Requirements Specification. Este documento."],
      ["SSO", "Single Sign-On. Autenticación única corporativa."],
      ["TrackIn", "Nombre del sistema especificado en este documento."],
    ],
    [2000, 7360]
  ),

  h2("1.4 Referencias"),
  tabla(
    ["Ref.", "Documento o recurso"],
    [
      ["[1]", "Mayorga Halabi, M. (2026). Formulario de presentación de anteproyecto de Práctica de Especialidad — TrackIn. Instituto Tecnológico de Costa Rica, Escuela de Ingeniería en Computación."],
      ["[2]", "Centro de Competencias, Laboratorios Gutis (2026). Documento Técnico-Funcional: Dashboard de Tracking Logístico para Compras en Tránsito, versión 1.0, 18 de junio de 2026."],
      ["[3]", "IEEE (1998). IEEE Std 830-1998 — Recommended Practice for Software Requirements Specifications. Institute of Electrical and Electronics Engineers."],
      ["[4]", "AISStream. Documentación de la API. https://aisstream.io/documentation"],
      ["[5]", "OpenSky Network. Documentación de la API. https://openskynetwork.github.io/opensky-api/"],
      ["[6]", "MarineTraffic. AIS API Documentation. https://servicedocs.marinetraffic.com/"],
      ["[7]", "FlightAware. AeroAPI. https://www.flightaware.com/commercial/aeroapi/"],
      ["[8]", "VesselFinder. AIS API Documentation. https://api.vesselfinder.com/docs/"],
    ],
    [900, 8460]
  ),

  h2("1.5 Visión general del documento"),
  p("El documento se organiza en once secciones y tres anexos. La sección 2 describe el sistema en términos generales: su perspectiva dentro del ecosistema de aplicaciones de Gutis, sus funcionalidades de alto nivel, las características de sus usuarios y las restricciones y suposiciones que condicionan el diseño. La sección 3 identifica los actores, tanto humanos como sistemas externos."),
  p("Las secciones 4 y 5 constituyen el núcleo normativo: la primera enumera los requerimientos funcionales agrupados por categoría, y la segunda los requerimientos no funcionales organizados por atributo de calidad. La sección 6 desarrolla los casos de uso principales con sus flujos detallados, y la sección 7 consolida las reglas de negocio que gobiernan el cálculo de estados."),
  p("La sección 8 presenta el modelo de datos preliminar, que se formalizará en el Sprint 2. Las secciones 9 y 10 recogen las restricciones del proyecto y los criterios de aceptación generales. Los anexos amplían el glosario, especifican el formato del archivo de carga y detallan las referencias técnicas de las APIs."),
  marcador(M.ASESOR, "Confirmar si la Escuela exige alguna sección adicional o un orden distinto de secciones para este entregable."),
];

// ============================================ 2. DESCRIPCIÓN GENERAL
const seccion2 = [
  h1("2. Descripción general del sistema"),

  h2("2.1 Perspectiva del producto"),
  p("TrackIn es un sistema nuevo y autocontenido. No sustituye ni extiende una aplicación existente: actualmente Laboratorios Gutis no dispone de herramienta alguna de tracking logístico, y el monitoreo se realiza mediante consultas manuales a proveedores, navieras y agentes aduanales, complementadas con la consulta de sitios web públicos de rastreo."),
  p("El sistema se sitúa como una capa de consulta y proyección que se alimenta de dos fuentes. Por un lado, la información maestra de pedidos de compra, que en esta fase se carga desde archivos Excel exportados del ERP corporativo. Por otro, los datos de posición y estado de viaje que proveen las APIs externas de rastreo satelital. TrackIn no escribe en el ERP ni pretende sustituirlo; su función es cruzar ambas fuentes y derivar información de decisión que hoy no existe de forma consolidada."),
  p("En una fase posterior, fuera del alcance de esta práctica, se prevé sustituir la carga por Excel por una integración directa con SAP S/4HANA, y las APIs gratuitas por servicios comerciales con acuerdo de nivel de servicio."),

  h2("2.2 Funcionalidades del producto"),
  p("A alto nivel, el sistema ofrece las siguientes capacidades. La sección 4 las desarrolla como requerimientos verificables."),
  bullet("Carga de pedidos de compra en tránsito desde archivos Excel, con validación del formato y reporte de errores."),
  bullet("Asociación de cada pedido a un identificador de rastreo externo: MMSI, IMO o nombre de buque para vía marítima; número de vuelo para vía aérea."),
  bullet("Consulta periódica y automática de las APIs de rastreo, con obtención de posición, rumbo, velocidad, ETA y estado de viaje."),
  bullet("Cálculo de la fecha proyectada de disponibilidad como suma de la ETA o ATA del destino más el lead time maestro parametrizado."),
  bullet("Determinación automática del estado logístico de cada pedido bajo un esquema de semáforo."),
  bullet("Confirmación manual de desembarco, para los casos en que la fuente automática no reporta la llegada."),
  bullet("Dashboard web con cinta de KPIs, grilla central de pedidos y dos mapas interactivos diferenciados por vía de transporte."),
  bullet("Filtrado transversal por orden de compra, proveedor, material, vía, estado y destino."),
  bullet("Registro histórico de posiciones con almacenamiento del payload completo de la API, para auditoría y reconstrucción de trayecto."),
  bullet("Administración del maestro de destinos y sus lead times asociados."),

  h2("2.3 Características de los usuarios"),
  p("Los usuarios del sistema pertenecen a cuatro áreas funcionales de Laboratorios Gutis. Todos poseen familiaridad con herramientas ofimáticas y con el ERP corporativo, pero no se asume conocimiento técnico en sistemas de información geográfica ni en logística satelital. Esta consideración condiciona los requerimientos de usabilidad de la sección 5.3."),
  tabla(
    ["Perfil", "Área", "Frecuencia de uso", "Competencia técnica"],
    [
      ["Usuario de Compras", "Compras", "Diaria", "Media. Domina el ERP y Excel. Sin conocimiento de cartografía ni de sistemas de rastreo."],
      ["Usuario de Logística", "Logística y comercio exterior", "Diaria", "Media-alta en el dominio logístico. Conoce documentación de embarque, identificadores de nave y trámites aduanales."],
      ["Usuario de Planificación", "Planificación de Producción", "Semanal o ante alerta", "Media. Consume la fecha proyectada como insumo del cálculo de necesidades de materiales."],
      ["Gerencia de Operaciones", "Dirección de operaciones", "Semanal, consulta agregada", "Baja-media. Consume principalmente KPIs y tendencias, no el detalle operativo."],
      ["Administrador del sistema", "Centro de Competencias", "Ocasional", "Alta. Perfil técnico responsable de la parametrización y el mantenimiento."],
    ],
    [1900, 2100, 1900, 3460]
  ),
  marcador(M.ENTREVISTAS, "Confirmar el número de usuarios por perfil, su disponibilidad horaria y si existe algún perfil adicional no contemplado, por ejemplo del área de Aseguramiento de la Calidad."),

  h2("2.4 Restricciones generales"),
  bullet("El sistema se ejecutará exclusivamente en entorno de desarrollo durante la Práctica de Especialidad. No habrá despliegue productivo dentro del alcance."),
  bullet("El stack tecnológico está definido por el documento técnico-funcional y no es objeto de decisión: Python 3.12 o superior con FastAPI, PostgreSQL 16 con PostGIS, React 18 con TypeScript y Leaflet."),
  bullet("Las APIs de rastreo empleadas son gratuitas y carecen de acuerdo de nivel de servicio. La cobertura de AIS satelital y de ADS-B es incompleta por naturaleza, particularmente en alta mar y sobre regiones sin receptores terrestres."),
  bullet("El sistema no puede rastrear mercancía: las APIs AIS rastrean naves. Un pedido sin identificador de nave o vuelo asociado no es rastreable automáticamente, y permanecerá en estado Sin tracking."),
  bullet("La fuente de pedidos es un archivo Excel de exportación manual. La frescura de los datos de pedido depende de la periodicidad con que el usuario ejecute esa exportación."),
  bullet("No se implementará autenticación corporativa. El control de acceso en esta fase será el mínimo necesario para distinguir roles y auditar confirmaciones manuales."),

  h2("2.5 Suposiciones y dependencias"),
  p("La validez de esta especificación descansa sobre las siguientes suposiciones. Su incumplimiento obligaría a revisar el alcance."),
  bullet("Se asume que Laboratorios Gutis puede proveer, para una fracción significativa de sus pedidos en tránsito, el identificador de nave o de vuelo. Sin este dato el rastreo automático no es posible."),
  bullet("Se asume que el equipo de Logística puede definir y mantener los lead times por destino con precisión suficiente para que la fecha proyectada sea accionable."),
  bullet("Se asume que las APIs gratuitas de AISStream y OpenSky Network mantendrán su disponibilidad y sus condiciones de uso durante el período de la práctica."),
  bullet("Se asume que los usuarios clave estarán disponibles para las sesiones de levantamiento de requerimientos, validación de prototipos y pruebas de aceptación."),
  bullet("Se asume que la empresa proveerá una muestra real, anonimizada si procede, del archivo Excel de pedidos, para determinar su estructura exacta."),
  marcador(M.DATOS, "La estructura definitiva del archivo de carga y el volumen típico de pedidos en tránsito dependen de recibir la muestra real. El Anexo B queda pendiente de esta información."),

  h2("2.6 Documentos aplicables"),
  p("Los documentos que rigen el desarrollo del proyecto, en orden de precedencia, son el anteproyecto aprobado [1], que delimita el alcance contractual; el documento técnico-funcional [2], que define la arquitectura objetivo y las reglas de negocio; y el presente SRS, que traduce ambos en requerimientos verificables. Ante discrepancia entre el anteproyecto y este documento, prevalece el anteproyecto por su carácter contractual con la Escuela."),
];

// ==================================================== 3. ACTORES
const seccion3 = [
  h1("3. Actores del sistema"),
  p("Se identifican cinco actores humanos y dos sistemas externos. Los actores humanos corresponden a los roles definidos en el documento técnico-funcional, ajustados a la estructura organizativa descrita en el anteproyecto."),
  tabla(
    ["Actor", "Descripción", "Responsabilidades principales"],
    [
      ["Usuario de Compras", "Personal del área de Compras responsable de la gestión de órdenes de compra internacionales.", "Consultar el estado de sus pedidos. Detectar atrasos y anticipar su impacto. Filtrar por orden de compra, proveedor, material, estado y destino. Gestionar la comunicación con el proveedor ante desvíos."],
      ["Usuario de Logística", "Personal de logística y comercio exterior encargado del seguimiento de embarques y trámites aduanales.", "Asociar cada pedido a su identificador de rastreo externo. Mantener el maestro de destinos y sus lead times. Confirmar manualmente el desembarco. Registrar observaciones logísticas."],
      ["Usuario de Planificación de Producción", "Personal responsable del cálculo de necesidades de materiales y de la programación de planta.", "Consultar la fecha proyectada de disponibilidad como insumo de la planificación. Reaccionar ante pedidos en riesgo o retrasados reprogramando producción."],
      ["Gerencia de Operaciones", "Dirección responsable del desempeño global de la cadena de suministro.", "Consultar indicadores agregados de desempeño logístico. Evaluar tendencias de cumplimiento por proveedor, destino y vía de transporte."],
      ["Administrador del sistema", "Perfil técnico del Centro de Competencias.", "Parametrizar credenciales y umbrales de las APIs. Administrar cuentas de usuario. Mantener las reglas de cálculo y los parámetros de configuración."],
      ["AISStream (sistema externo)", "Servicio WebSocket gratuito de recepción de datos AIS de embarcaciones.", "Proveer reportes de posición de buques por área geográfica. Requiere clave de API. Es la fuente del rastreo marítimo del prototipo."],
      ["OpenSky Network (sistema externo)", "API abierta de rastreo de vuelos con datos ADS-B.", "Proveer estado y posición de aeronaves. No entrega itinerarios comerciales ni datos de retraso no derivados de ADS-B. Es la fuente del rastreo aéreo del prototipo."],
    ],
    [1900, 3200, 4260]
  ),
  marcador(M.ENTREVISTAS, "Validar que los roles del documento técnico-funcional (Visualizador, Compras, Logística, Administrador) se corresponden con los actores aquí definidos, y determinar si se requiere un perfil de solo lectura para pantalla permanente en planta."),
];

// ======================================= 4. REQUERIMIENTOS FUNCIONALES
const seccion4 = [
  h1("4. Requerimientos funcionales"),
  p("Los requerimientos se agrupan en siete categorías funcionales. Cada requerimiento se identifica con el prefijo RF y un número correlativo, y se asocia a uno de los cuatro objetivos específicos del anteproyecto, según la siguiente correspondencia:"),
  tabla(
    ["Código", "Objetivo específico"],
    [
      ["OE1", "Analizar los requerimientos funcionales y no funcionales, diseñando el modelo de datos, la arquitectura y los prototipos de interfaz."],
      ["OE2", "Desarrollar el módulo de backend con consumo de APIs de rastreo marítimo y aéreo, cálculo de estados logísticos y servicios REST."],
      ["OE3", "Desarrollar el frontend del dashboard web con grilla, mapas interactivos, indicadores KPI y sistema de filtros."],
      ["OE4", "Implementar la capa de persistencia en PostgreSQL con PostGIS y entregar la documentación técnica."],
    ],
    [900, 8460]
  ),
  p("La prioridad se expresa en tres niveles. Alta corresponde a un requerimiento sin el cual el sistema no cumple su propósito y que debe estar presente en la demostración funcional. Media corresponde a un requerimiento que aporta valor sustantivo pero cuya ausencia no invalida el prototipo. Baja corresponde a un requerimiento deseable, candidato a posponerse si el cronograma se comprime."),

  h2("4.1 Gestión de pedidos en tránsito"),
  ...RF({
    id: "RF-01", titulo: "Carga de pedidos desde archivo Excel",
    descripcion: "El sistema debe permitir la carga masiva de pedidos de compra en tránsito a partir de un archivo Excel exportado del ERP corporativo. Por cada pedido se registrarán, como mínimo, el número de orden de compra, la posición de la orden, el material, el proveedor, la fecha de entrega comprometida, la vía de transporte y el destino.",
    actor: "Usuario de Compras, Usuario de Logística",
    pre: "El usuario dispone de un archivo Excel con la estructura esperada. " + M.DATOS,
    post: "Los pedidos quedan persistidos en la tabla de pedidos en tránsito. Los pedidos ya existentes se actualizan; los nuevos se insertan. El sistema informa el número de registros procesados, actualizados y rechazados.",
    prioridad: "Alta", oe: "OE2",
  }),
  ...RF({
    id: "RF-02", titulo: "Validación del archivo de carga",
    descripcion: "El sistema debe validar la estructura y el contenido del archivo antes de persistir dato alguno, verificando la presencia de las columnas obligatorias, el tipo de dato de cada campo y la coherencia de los valores de dominio, como la vía de transporte. Los registros inválidos deben rechazarse individualmente sin abortar la carga completa.",
    actor: "Usuario de Compras, Usuario de Logística",
    pre: "El usuario ha iniciado una carga de archivo (RF-01).",
    post: "El sistema presenta un informe de validación que identifica cada registro rechazado con su fila de origen y el motivo del rechazo. Los registros válidos se persisten.",
    prioridad: "Alta", oe: "OE2",
  }),
  ...RF({
    id: "RF-03", titulo: "Asociación de identificador de rastreo externo",
    descripcion: "El sistema debe permitir asociar a cada pedido un identificador de rastreo externo, indicando su tipo (MMSI, IMO, nombre de buque, número de vuelo, AWB, contenedor o booking) y su valor. Un pedido sin identificador asociado permanece en estado Sin tracking.",
    actor: "Usuario de Logística",
    pre: "El pedido existe en el sistema.",
    post: "El pedido queda habilitado para el rastreo automático si el tipo de identificador es soportado por alguna de las APIs integradas.",
    prioridad: "Alta", oe: "OE2",
  }),
  ...RF({
    id: "RF-04", titulo: "Listado de pedidos en tránsito",
    descripcion: "El sistema debe presentar el conjunto de pedidos en tránsito en una grilla con ordenamiento por columna y paginación, mostrando orden de compra, material, proveedor, vía, destino, ETA, fecha proyectada de disponibilidad, fecha de entrega comprometida y estado calculado.",
    actor: "Todos los actores humanos",
    pre: "Existe al menos un pedido cargado en el sistema.",
    post: "El usuario visualiza el conjunto de pedidos conforme a los filtros activos.",
    prioridad: "Alta", oe: "OE3",
  }),
  ...RF({
    id: "RF-05", titulo: "Consulta de detalle de un pedido",
    descripcion: "El sistema debe permitir acceder al detalle completo de un pedido, incluyendo todos sus datos maestros, su identificador de rastreo, la última posición conocida, la fecha y hora de la última consulta exitosa a la API, y el desglose del cálculo que produjo la fecha proyectada de disponibilidad.",
    actor: "Todos los actores humanos",
    pre: "El pedido existe en el sistema.",
    post: "El usuario visualiza el detalle del pedido y puede navegar a su historial de tracking.",
    prioridad: "Alta", oe: "OE3",
  }),

  h2("4.2 Integración con APIs externas"),
  ...RF({
    id: "RF-06", titulo: "Consumo de la API marítima AIS",
    descripcion: "El sistema debe establecer y mantener una conexión WebSocket con el servicio AISStream para recibir reportes de posición de embarcaciones, filtrando por las naves asociadas a pedidos activos o por área geográfica de interés. De cada reporte debe extraer MMSI, latitud, longitud, velocidad sobre tierra y rumbo.",
    actor: "Sistema (proceso automático), AISStream",
    pre: "Existe una clave de API válida configurada. Existe al menos un pedido marítimo con identificador de nave asociado.",
    post: "La posición actual del pedido queda actualizada y se agrega un registro al historial de tracking.",
    prioridad: "Alta", oe: "OE2",
  }),
  ...RF({
    id: "RF-07", titulo: "Consumo de la API aérea ADS-B",
    descripcion: "El sistema debe consultar la API REST de OpenSky Network para obtener el estado y la posición de las aeronaves asociadas a pedidos con vía de transporte aérea, extrayendo latitud, longitud, altitud, velocidad y rumbo.",
    actor: "Sistema (proceso automático), OpenSky Network",
    pre: "Existen credenciales configuradas. Existe al menos un pedido aéreo con identificador de vuelo asociado.",
    post: "La posición actual del pedido queda actualizada y se agrega un registro al historial de tracking.",
    prioridad: "Alta", oe: "OE2",
  }),
  ...RF({
    id: "RF-08", titulo: "Programación de consultas periódicas",
    descripcion: "El sistema debe ejecutar las consultas a las APIs externas de forma periódica y desatendida, con frecuencias diferenciadas por vía de transporte. El documento técnico-funcional sugiere entre 30 y 60 minutos para el rastreo marítimo, y entre 5 y 10 minutos para el aéreo. Las frecuencias deben ser parametrizables sin modificar el código fuente.",
    actor: "Sistema (proceso automático)",
    pre: "El servicio de tareas programadas está activo.",
    post: "Las posiciones de los pedidos activos se refrescan conforme a la periodicidad configurada.",
    prioridad: "Alta", oe: "OE2",
  }),
  ...RF({
    id: "RF-09", titulo: "Gestión de errores y reintentos",
    descripcion: "El sistema debe tolerar la indisponibilidad temporal de las APIs externas sin degradar la consulta del dashboard. Ante un fallo debe aplicar una política de reintentos con espera creciente, registrar el error y conservar el último dato válido conocido, señalando su antigüedad al usuario.",
    actor: "Sistema (proceso automático)",
    pre: "Se ha intentado una consulta a una API externa.",
    post: "El fallo queda registrado. El pedido conserva su última posición válida, marcada con la fecha y hora de esa lectura. El dashboard permanece operativo.",
    prioridad: "Alta", oe: "OE2",
  }),

  h2("4.3 Cálculo automático de estados logísticos"),
  ...RF({
    id: "RF-10", titulo: "Cálculo de la fecha proyectada de disponibilidad",
    descripcion: "El sistema debe calcular, para cada pedido, la fecha proyectada de disponibilidad aplicando la fórmula definida en la regla de negocio RN-01: ETA o ATA del destino, más el lead time maestro del destino, más un ajuste manual opcional.",
    actor: "Sistema (proceso automático)",
    pre: "El pedido cuenta con ETA o ATA, y su destino existe en el maestro de destinos con lead time definido.",
    post: "El pedido almacena su fecha proyectada de disponibilidad, disponible para el cálculo de estado y para la planificación de producción.",
    prioridad: "Alta", oe: "OE2",
  }),
  ...RF({
    id: "RF-11", titulo: "Determinación del estado logístico",
    descripcion: "El sistema debe determinar automáticamente el estado logístico de cada pedido conforme al esquema de semáforo definido en las reglas RN-02 a RN-10, comparando la fecha proyectada de disponibilidad contra la fecha de entrega comprometida y considerando la etapa del viaje reportada por la fuente externa.",
    actor: "Sistema (proceso automático)",
    pre: "El pedido cuenta con fecha proyectada de disponibilidad, o bien carece de tracking asociado.",
    post: "El pedido almacena su estado calculado, que gobierna el color de su fila en la grilla y de su marcador en el mapa.",
    prioridad: "Alta", oe: "OE2",
  }),
  ...RF({
    id: "RF-12", titulo: "Recálculo ante cambios",
    descripcion: "El sistema debe recalcular la fecha proyectada y el estado de un pedido cada vez que cambie alguno de sus insumos: nueva lectura de ETA o ATA desde la API, modificación del lead time del destino, registro de una confirmación manual de desembarco o aplicación de un ajuste manual.",
    actor: "Sistema (proceso automático)",
    pre: "Se ha producido un cambio en alguno de los insumos del cálculo.",
    post: "La fecha proyectada y el estado del pedido reflejan los valores vigentes.",
    prioridad: "Alta", oe: "OE2",
  }),

  h2("4.4 Confirmación manual de desembarco"),
  ...RF({
    id: "RF-13", titulo: "Confirmación manual de desembarco",
    descripcion: "El sistema debe permitir al usuario de Logística registrar manualmente la llegada efectiva de una carga a su destino, indicando la fecha y hora reales. Esta confirmación tiene precedencia sobre la ETA reportada por la API y pasa a alimentar el cálculo de la fecha proyectada de disponibilidad.",
    actor: "Usuario de Logística",
    pre: "El pedido existe y no se encuentra en un estado terminal.",
    post: "El pedido registra su ATA confirmada. La fecha proyectada y el estado se recalculan (RF-12). La acción queda auditada (RF-14).",
    prioridad: "Alta", oe: "OE2",
  }),
  ...RF({
    id: "RF-14", titulo: "Auditoría de confirmaciones y ajustes manuales",
    descripcion: "El sistema debe registrar, por cada intervención manual sobre un pedido, el usuario que la ejecutó, la fecha y hora, el valor anterior, el valor nuevo y el motivo declarado. Este registro responde al riesgo de trazabilidad identificado en el documento técnico-funcional.",
    actor: "Sistema, Usuario de Logística",
    pre: "Un usuario ha ejecutado una confirmación manual o un ajuste sobre un pedido.",
    post: "La intervención queda registrada de forma inalterable y consultable.",
    prioridad: "Alta", oe: "OE4",
  }),

  h2("4.5 Visualización en el dashboard"),
  ...RF({
    id: "RF-15", titulo: "Cinta de indicadores KPI",
    descripcion: "El sistema debe presentar una cinta superior de indicadores con el número de pedidos activos, el porcentaje de pedidos a tiempo, en riesgo y retrasados, y el lead time promedio. Los indicadores deben responder a los filtros activos.",
    actor: "Todos los actores humanos",
    pre: "Existe al menos un pedido cargado.",
    post: "El usuario visualiza el estado agregado de la cartera de pedidos.",
    prioridad: "Alta", oe: "OE3",
  }),
  ...RF({
    id: "RF-16", titulo: "Mapa interactivo marítimo",
    descripcion: "El sistema debe presentar un mapa interactivo con la posición actual de las embarcaciones asociadas a los pedidos marítimos resultantes del filtro, empleando marcadores coloreados según el estado del pedido.",
    actor: "Todos los actores humanos",
    pre: "Existe al menos un pedido marítimo con posición conocida.",
    post: "El usuario visualiza geográficamente la distribución de sus cargas marítimas.",
    prioridad: "Alta", oe: "OE3",
  }),
  ...RF({
    id: "RF-17", titulo: "Mapa interactivo aéreo",
    descripcion: "El sistema debe presentar un mapa interactivo, separado del marítimo, con la posición de las aeronaves asociadas a los pedidos aéreos resultantes del filtro, empleando el mismo esquema de color por estado.",
    actor: "Todos los actores humanos",
    pre: "Existe al menos un pedido aéreo con posición conocida.",
    post: "El usuario visualiza geográficamente la distribución de sus cargas aéreas.",
    prioridad: "Alta", oe: "OE3",
  }),
  ...RF({
    id: "RF-18", titulo: "Información emergente en marcadores",
    descripcion: "Cada marcador de los mapas debe exponer, al posarse el cursor sobre él o al seleccionarlo, la orden de compra, el material, el proveedor, la ETA, la fecha proyectada de disponibilidad y el estado del pedido asociado.",
    actor: "Todos los actores humanos",
    pre: "El mapa muestra al menos un marcador.",
    post: "El usuario obtiene el contexto del pedido sin abandonar la vista cartográfica.",
    prioridad: "Media", oe: "OE3",
  }),
  ...RF({
    id: "RF-19", titulo: "Sistema de filtros transversales",
    descripcion: "El sistema debe ofrecer filtros por orden de compra, proveedor, material, vía de transporte, estado y destino. Los filtros deben aplicarse simultáneamente a la cinta de KPIs, a la grilla y a ambos mapas, manteniendo la coherencia de la vista.",
    actor: "Todos los actores humanos",
    pre: "Existe al menos un pedido cargado.",
    post: "Todos los componentes del dashboard reflejan el subconjunto de pedidos seleccionado.",
    prioridad: "Alta", oe: "OE3",
  }),
  ...RF({
    id: "RF-20", titulo: "Indicación de frescura de los datos",
    descripcion: "El encabezado del dashboard debe mostrar la fecha y hora de la última actualización y el estado de sincronización con las fuentes externas, de modo que el usuario pueda juzgar la vigencia de la información que consulta.",
    actor: "Todos los actores humanos",
    pre: "El sistema ha ejecutado al menos un ciclo de consulta.",
    post: "El usuario conoce la antigüedad de los datos presentados.",
    prioridad: "Media", oe: "OE3",
  }),

  h2("4.6 Historial de tracking"),
  ...RF({
    id: "RF-21", titulo: "Registro del historial de posiciones",
    descripcion: "El sistema debe almacenar, por cada lectura exitosa de una API externa, un registro histórico con la fecha de captura, latitud, longitud, velocidad, rumbo, estado crudo reportado por la fuente y el payload completo de la respuesta, para auditoría posterior.",
    actor: "Sistema (proceso automático)",
    pre: "Se ha obtenido una lectura válida de una API externa.",
    post: "El historial del pedido incorpora un nuevo registro inmutable.",
    prioridad: "Alta", oe: "OE4",
  }),
  ...RF({
    id: "RF-22", titulo: "Consulta del historial y del trayecto",
    descripcion: "El sistema debe permitir consultar la secuencia histórica de posiciones de un pedido y representar su trayecto sobre el mapa correspondiente.",
    actor: "Usuario de Logística, Usuario de Compras",
    pre: "El pedido cuenta con al menos dos registros en su historial.",
    post: "El usuario visualiza la evolución de la carga a lo largo del tiempo.",
    prioridad: "Media", oe: "OE3",
  }),

  h2("4.7 Administración de datos maestros"),
  ...RF({
    id: "RF-23", titulo: "Mantenimiento del maestro de destinos",
    descripcion: "El sistema debe permitir crear, consultar, modificar y desactivar destinos (puertos y aeropuertos), registrando su vía de transporte asociada, su lead time estándar en días, su lead time crítico y observaciones logísticas.",
    actor: "Usuario de Logística, Administrador del sistema",
    pre: "El usuario cuenta con permisos de mantenimiento de maestros.",
    post: "El maestro de destinos refleja los valores vigentes. Los pedidos afectados se recalculan (RF-12).",
    prioridad: "Alta", oe: "OE2",
  }),
  ...RF({
    id: "RF-24", titulo: "Parametrización de umbrales y credenciales",
    descripcion: "El sistema debe mantener fuera del código fuente los parámetros de configuración: credenciales de las APIs, frecuencias de consulta y umbrales de los estados logísticos, conforme al requerimiento de mantenibilidad del documento técnico-funcional.",
    actor: "Administrador del sistema",
    pre: "El usuario cuenta con perfil de administración.",
    post: "Los parámetros quedan vigentes sin requerir un nuevo despliegue del código.",
    prioridad: "Media", oe: "OE2",
  }),
  marcador(M.ENTREVISTAS, "Verificar con los usuarios de Compras y Logística si existen requerimientos funcionales no contemplados: notificaciones por correo ante cambio de estado, exportación de la grilla a Excel, o vistas específicas por proveedor."),
  marcador(M.GREIVIN, "Confirmar la priorización asignada, en particular si RF-22 (trayecto histórico) y RF-18 (tooltips) deben elevarse a prioridad Alta para la demostración funcional."),
];

// ================================ 5. REQUERIMIENTOS NO FUNCIONALES
const rnf = (id, texto) =>
  new Paragraph({
    children: [t(id + ". ", { bold: true, color: AZUL }), t(texto)],
    spacing: { after: 120, line: 276 },
    alignment: AlignmentType.JUSTIFIED,
  });

const seccion5 = [
  h1("5. Requerimientos no funcionales"),
  p("Los requerimientos de esta sección se derivan de la sección 13 del documento técnico-funcional y de las restricciones tecnológicas del anteproyecto. Se identifican con el prefijo RNF."),

  h2("5.1 Rendimiento"),
  rnf("RNF-01", "El dashboard debe renderizar la vista inicial completa, incluyendo cinta de KPIs, grilla y ambos mapas, en un tiempo que no resulte disruptivo para una consulta operativa habitual."),
  rnf("RNF-02", "La aplicación de un filtro debe reflejarse en todos los componentes de la vista sin recarga completa de la página."),
  rnf("RNF-03", "Las consultas a las APIs externas deben ejecutarse de forma asíncrona y desacoplada de las peticiones del usuario, de modo que la latencia de una fuente externa no bloquee la consulta del dashboard."),
  marcador(M.GREIVIN, "Definir umbrales numéricos concretos de tiempo de respuesta y el volumen máximo esperado de pedidos simultáneos en tránsito, para poder verificar objetivamente RNF-01 y RNF-02."),

  h2("5.2 Seguridad"),
  rnf("RNF-04", "El acceso al sistema debe requerir autenticación. En el alcance de esta práctica se implementará un mecanismo propio; la integración con Active Directory o SSO corporativo queda fuera del alcance."),
  rnf("RNF-05", "El sistema debe distinguir perfiles de usuario con permisos diferenciados, de modo que las operaciones de mantenimiento de maestros y de confirmación manual queden restringidas a los perfiles autorizados."),
  rnf("RNF-06", "Toda intervención manual sobre un pedido debe quedar registrada con usuario, fecha, valor anterior, valor nuevo y motivo, conforme a RF-14."),
  rnf("RNF-07", "Las credenciales de las APIs externas y de la base de datos no deben residir en el código fuente ni en el repositorio de control de versiones."),

  h2("5.3 Usabilidad"),
  rnf("RNF-08", "El estado de cada pedido debe ser reconocible por color conforme al esquema de semáforo, de forma consistente entre la grilla y los mapas."),
  rnf("RNF-09", "La interfaz debe estar íntegramente en español, empleando la terminología logística habitual de los usuarios."),
  rnf("RNF-10", "El sistema debe ser operable por usuarios sin formación técnica en sistemas de información geográfica, sin requerir capacitación previa más allá del manual de usuario."),
  rnf("RNF-11", "El dashboard debe ser legible en una pantalla de gran formato en modo de visualización permanente, contemplando el escenario de pantalla tipo aeropuerto descrito en el documento técnico-funcional."),
  marcador(M.ENTREVISTAS, "Validar los wireframes con los usuarios clave y confirmar la resolución y el tamaño de la pantalla de visualización permanente, si finalmente se instala."),

  h2("5.4 Confiabilidad"),
  rnf("RNF-12", "La indisponibilidad de una API externa no debe impedir la consulta del dashboard. El sistema debe degradar mostrando el último dato válido conocido junto con su antigüedad."),
  rnf("RNF-13", "El sistema debe conservar íntegramente el historial de posiciones y el payload original de cada respuesta de API, de modo que cualquier estado calculado sea reconstruible a posteriori."),
  rnf("RNF-14", "Un fallo en el procesamiento de un pedido no debe interrumpir el procesamiento de los restantes."),

  h2("5.5 Mantenibilidad"),
  rnf("RNF-15", "Los parámetros de configuración —credenciales de API, destinos, lead times, umbrales y frecuencias— deben residir fuera del código fuente, conforme a la sección 13 del documento técnico-funcional."),
  rnf("RNF-16", "El código fuente debe alojarse en un repositorio Git organizado, con historial de cambios legible."),
  rnf("RNF-17", "El backend debe exponer su documentación de API de forma automática mediante OpenAPI y Swagger UI."),
  rnf("RNF-18", "El sistema debe contar con pruebas automatizadas de sus reglas de negocio de cálculo de estado, por ser el núcleo funcional del producto."),

  h2("5.6 Portabilidad"),
  rnf("RNF-19", "El sistema debe ejecutarse en entorno de desarrollo local sobre Windows, mediante un procedimiento documentado y reproducible."),
  rnf("RNF-20", "La capa de persistencia debe depender únicamente de PostgreSQL 16 con la extensión PostGIS, sin recurrir a características propietarias de un proveedor de nube."),
  marcador(M.GREIVIN, "El anteproyecto contempla la ejecución mediante contenedores Docker. En el equipo asignado al practicante no es posible ejecutar Docker por restricciones de permisos administrativos, por lo que el entorno de desarrollo se levanta de forma nativa. Los archivos de contenedor se mantienen como artefacto de despliegue para el servidor. Confirmar que esta desviación es aceptable."),

  h2("5.7 Escalabilidad"),
  rnf("RNF-21", "La arquitectura debe permitir incorporar nuevas fuentes de rastreo sin alterar la lógica de cálculo de estados, aislando cada integración tras una interfaz común."),
  rnf("RNF-22", "El modelo de datos debe soportar el crecimiento del historial de posiciones sin degradar la consulta de los pedidos activos."),
  rnf("RNF-23", "La arquitectura debe quedar preparada para la incorporación posterior de comunicación por WebSockets hacia el frontend, conforme a la evolución prevista en el documento técnico-funcional."),

  h2("5.8 Restricciones tecnológicas"),
  p("El stack está definido por el anteproyecto y no admite sustitución dentro del alcance de la práctica:"),
  tabla(
    ["Capa", "Tecnología", "Versión"],
    [
      ["Lenguaje de backend", "Python", "3.12 o superior"],
      ["Framework de backend", "FastAPI", "0.115.x"],
      ["ORM y migraciones", "SQLAlchemy 2.0 con Alembic", "2.0.x / 1.14.x"],
      ["Base de datos", "PostgreSQL con extensión PostGIS", "16.x / 3.x"],
      ["Framework de frontend", "React con TypeScript", "18.x"],
      ["Herramienta de construcción", "Vite", "Última estable"],
      ["Cartografía", "Leaflet", "Última estable"],
      ["Estilos", "TailwindCSS", "Última estable"],
      ["Pruebas", "pytest (backend), Vitest (frontend)", "8.x / última estable"],
      ["Control de versiones", "Git y GitHub", "No aplica"],
    ],
    [2600, 4400, 2360]
  ),
];

// ============================================ 6. CASOS DE USO
const seccion6 = [
  h1("6. Casos de uso principales"),
  p("Se documentan nueve casos de uso que cubren las interacciones principales del sistema. Cada uno se describe mediante su actor principal, sus precondiciones, el flujo principal numerado, los flujos alternativos y las postcondiciones. Los diagramas de secuencia y de componentes correspondientes se entregarán con el documento de arquitectura del Sprint 2."),

  ...CU({
    id: "CU-01", titulo: "Cargar pedidos desde archivo Excel",
    actor: "Usuario de Compras",
    pre: "El usuario ha iniciado sesión y dispone de un archivo Excel exportado del ERP con la estructura esperada.",
    flujo: [
      "1. El usuario accede a la función de carga de pedidos.",
      "2. El sistema presenta el formulario de carga e indica el formato esperado.",
      "3. El usuario selecciona el archivo Excel y confirma la carga.",
      "4. El sistema valida la estructura del archivo y el contenido de cada fila.",
      "5. El sistema inserta los pedidos nuevos y actualiza los existentes, identificándolos por orden de compra y posición.",
      "6. El sistema presenta un informe con el número de registros insertados, actualizados y rechazados.",
      "7. El usuario revisa el informe y confirma la operación.",
    ],
    alternos: [
      "4a. El archivo carece de una columna obligatoria: el sistema aborta la carga sin persistir nada e informa qué columnas faltan.",
      "4b. Una fila contiene datos inválidos: el sistema la rechaza individualmente, continúa con las restantes y la incluye en el informe con su número de fila y el motivo.",
      "5a. Un pedido ya existente presenta cambios en su fecha de entrega comprometida: el sistema lo actualiza y marca el pedido para recálculo de estado.",
      "3a. El archivo excede el tamaño máximo admitido: el sistema rechaza la carga e informa el límite.",
    ],
    post: "Los pedidos válidos quedan persistidos y disponibles en el dashboard. Los pedidos sin identificador de rastreo quedan en estado Sin tracking.",
  }),

  ...CU({
    id: "CU-02", titulo: "Consultar el dashboard de pedidos en tránsito",
    actor: "Todos los actores humanos",
    pre: "El usuario ha iniciado sesión y existe al menos un pedido cargado.",
    flujo: [
      "1. El usuario accede a la pantalla principal del sistema.",
      "2. El sistema recupera los pedidos activos con su estado calculado vigente.",
      "3. El sistema presenta el encabezado con la fecha y hora de la última actualización y el estado de sincronización.",
      "4. El sistema presenta la cinta de KPIs: pedidos activos, porcentaje a tiempo, en riesgo y retrasados, y lead time promedio.",
      "5. El sistema presenta la grilla central con los pedidos y su estado, coloreados según el semáforo.",
      "6. El sistema presenta los mapas marítimo y aéreo con los marcadores correspondientes.",
    ],
    alternos: [
      "2a. No existen pedidos cargados: el sistema presenta la pantalla con un mensaje que orienta al usuario hacia la función de carga.",
      "3a. La última sincronización con una API externa falló: el sistema señala la incidencia y muestra la antigüedad del último dato válido.",
      "6a. Ningún pedido cuenta con posición conocida: el sistema presenta los mapas en su vista general sin marcadores.",
    ],
    post: "El usuario dispone de la visión consolidada del estado de la cartera de pedidos en tránsito.",
  }),

  ...CU({
    id: "CU-03", titulo: "Ver el detalle de un pedido específico",
    actor: "Todos los actores humanos",
    pre: "El usuario visualiza la grilla de pedidos o un marcador en el mapa.",
    flujo: [
      "1. El usuario selecciona un pedido en la grilla o su marcador en el mapa.",
      "2. El sistema recupera el detalle completo del pedido.",
      "3. El sistema presenta los datos maestros: orden de compra, posición, material, proveedor, fecha de entrega comprometida, vía y destino.",
      "4. El sistema presenta los datos de rastreo: tipo y valor del identificador externo, última posición conocida, ETA, ATA si existe y fecha de la última consulta exitosa.",
      "5. El sistema presenta el desglose del cálculo de la fecha proyectada de disponibilidad y el estado resultante.",
      "6. El usuario puede navegar desde aquí al historial de tracking del pedido.",
    ],
    alternos: [
      "2a. El pedido carece de identificador de rastreo: el sistema presenta los datos maestros e indica que el pedido no es rastreable automáticamente, ofreciendo la acción de asociar un identificador.",
      "4a. Nunca se obtuvo una lectura exitosa: el sistema indica que no hay posición disponible.",
    ],
    post: "El usuario conoce el detalle del pedido y el fundamento de su estado calculado.",
  }),

  ...CU({
    id: "CU-04", titulo: "Filtrar pedidos por vía, estado y destino",
    actor: "Todos los actores humanos",
    pre: "El usuario visualiza el dashboard con al menos un pedido cargado.",
    flujo: [
      "1. El usuario despliega la barra de filtros superior.",
      "2. El usuario selecciona uno o varios criterios: orden de compra, proveedor, material, vía de transporte, estado o destino.",
      "3. El sistema aplica los criterios de forma conjunta sobre el conjunto de pedidos.",
      "4. El sistema actualiza simultáneamente la cinta de KPIs, la grilla y ambos mapas.",
      "5. El sistema indica el número de pedidos que satisfacen el filtro.",
    ],
    alternos: [
      "3a. Ningún pedido satisface la combinación de criterios: el sistema presenta la vista vacía con un mensaje explicativo y la opción de limpiar los filtros.",
      "2a. El usuario limpia los filtros: el sistema restablece la vista completa.",
    ],
    post: "Todos los componentes del dashboard reflejan de forma coherente el subconjunto seleccionado.",
  }),

  ...CU({
    id: "CU-05", titulo: "Confirmar el desembarco de un pedido",
    actor: "Usuario de Logística",
    pre: "El usuario cuenta con perfil de Logística. El pedido existe y no está en estado terminal.",
    flujo: [
      "1. El usuario accede al detalle del pedido cuyo desembarco desea confirmar.",
      "2. El usuario selecciona la acción de confirmar desembarco.",
      "3. El sistema solicita la fecha y hora reales de llegada y un motivo u observación.",
      "4. El usuario introduce los datos y confirma.",
      "5. El sistema registra la ATA confirmada, que pasa a tener precedencia sobre la ETA de la API.",
      "6. El sistema recalcula la fecha proyectada de disponibilidad y el estado del pedido.",
      "7. El sistema registra la intervención en la bitácora de auditoría con usuario, fecha, valores anterior y nuevo, y motivo.",
      "8. El sistema actualiza la grilla y los mapas.",
    ],
    alternos: [
      "4a. La fecha introducida es futura: el sistema la rechaza e informa que la confirmación de desembarco requiere una fecha no posterior al momento actual.",
      "4b. El usuario cancela: el sistema descarta la operación sin alterar el pedido.",
      "5a. El pedido ya contaba con una ATA confirmada: el sistema advierte de la sobrescritura y exige confirmación explícita.",
    ],
    post: "El pedido refleja su llegada real. El estado se recalcula y la intervención queda auditada.",
  }),

  ...CU({
    id: "CU-06", titulo: "Actualizar el maestro de destinos y lead times",
    actor: "Usuario de Logística, Administrador del sistema",
    pre: "El usuario cuenta con permisos de mantenimiento de maestros.",
    flujo: [
      "1. El usuario accede a la administración del maestro de destinos.",
      "2. El sistema presenta los destinos registrados con su vía, lead time estándar, lead time crítico y estado de activación.",
      "3. El usuario crea un destino nuevo o selecciona uno existente para modificarlo.",
      "4. El usuario introduce o ajusta el nombre del destino, la vía de transporte, el lead time estándar en días, el lead time crítico y las observaciones.",
      "5. El sistema valida los datos y persiste el cambio.",
      "6. El sistema identifica los pedidos activos asociados a ese destino y los marca para recálculo.",
      "7. El sistema recalcula la fecha proyectada y el estado de los pedidos afectados.",
    ],
    alternos: [
      "5a. El lead time introducido es negativo o no numérico: el sistema rechaza el valor e informa el formato esperado.",
      "5b. Ya existe un destino con el mismo nombre y vía: el sistema impide la duplicación.",
      "3a. El usuario desactiva un destino con pedidos activos asociados: el sistema advierte del impacto y solicita confirmación.",
    ],
    post: "El maestro refleja los valores vigentes y los pedidos afectados presentan su estado recalculado.",
  }),

  ...CU({
    id: "CU-07", titulo: "Ver el mapa marítimo con posiciones actuales",
    actor: "Todos los actores humanos",
    pre: "Existe al menos un pedido marítimo con identificador de nave y posición conocida.",
    flujo: [
      "1. El usuario dirige su atención al mapa marítimo del dashboard.",
      "2. El sistema recupera la última posición conocida de cada nave asociada a los pedidos marítimos del filtro activo.",
      "3. El sistema representa cada nave como un marcador coloreado según el estado del pedido.",
      "4. El usuario posa el cursor sobre un marcador o lo selecciona.",
      "5. El sistema presenta la información emergente: orden de compra, material, proveedor, ETA, fecha proyectada y estado.",
      "6. El usuario puede desplazar y acercar el mapa libremente.",
    ],
    alternos: [
      "2a. Una nave carece de lectura reciente: el sistema representa su última posición conocida diferenciándola visualmente e indicando su antigüedad.",
      "3a. Varias naves coinciden en una zona reducida: el sistema agrupa los marcadores y los despliega al acercar la vista.",
      "4a. El usuario selecciona el marcador: el sistema ofrece navegar al detalle del pedido.",
    ],
    post: "El usuario conoce la ubicación geográfica de sus cargas marítimas y su estado.",
  }),

  ...CU({
    id: "CU-08", titulo: "Ver el mapa aéreo con vuelos activos",
    actor: "Todos los actores humanos",
    pre: "Existe al menos un pedido aéreo con identificador de vuelo y posición conocida.",
    flujo: [
      "1. El usuario dirige su atención al mapa aéreo del dashboard.",
      "2. El sistema recupera la posición de las aeronaves asociadas a los pedidos aéreos del filtro activo.",
      "3. El sistema representa cada aeronave como un marcador coloreado según el estado del pedido.",
      "4. El usuario posa el cursor sobre un marcador o lo selecciona.",
      "5. El sistema presenta la información emergente del pedido asociado.",
    ],
    alternos: [
      "2a. El vuelo ha finalizado y ya no emite ADS-B: el sistema representa la última posición registrada e indica que el vuelo concluyó.",
      "2b. La cobertura ADS-B no alcanza la posición actual de la aeronave: el sistema conserva la última posición válida y señala la antigüedad del dato.",
    ],
    post: "El usuario conoce la ubicación de sus cargas aéreas y su estado.",
  }),

  ...CU({
    id: "CU-09", titulo: "Consultar el historial de tracking de un pedido",
    actor: "Usuario de Logística, Usuario de Compras",
    pre: "El pedido cuenta con al menos un registro en su historial de posiciones.",
    flujo: [
      "1. El usuario accede al detalle del pedido.",
      "2. El usuario selecciona la opción de consultar el historial de tracking.",
      "3. El sistema recupera la secuencia cronológica de posiciones registradas.",
      "4. El sistema presenta la secuencia en forma de tabla, con fecha de captura, coordenadas, velocidad, rumbo y estado reportado por la fuente.",
      "5. El sistema representa el trayecto recorrido sobre el mapa correspondiente a la vía del pedido.",
    ],
    alternos: [
      "3a. El pedido cuenta con un solo registro: el sistema presenta el punto sin trazar trayecto.",
      "4a. El usuario solicita el detalle técnico de un registro: el sistema presenta el payload original de la respuesta de la API.",
    ],
    post: "El usuario conoce la evolución de la carga a lo largo del tiempo y dispone de la evidencia para auditoría.",
  }),
  marcador(M.ENTREVISTAS, "Validar los flujos con los usuarios clave, en particular CU-01 y CU-05, que son los que implican intervención manual y donde el proceso real puede diferir de lo aquí supuesto."),
];

// ======================================= 7. REGLAS DE NEGOCIO
const seccion7 = [
  h1("7. Reglas de negocio"),
  p("Las reglas de esta sección gobiernan el cálculo de la fecha proyectada de disponibilidad y la determinación del estado logístico. Proceden de la sección 6 del documento técnico-funcional y constituyen el núcleo de valor del sistema."),

  h2("7.1 Regla de cálculo fundamental"),
  ...RN({
    id: "RN-01", titulo: "Fórmula de la fecha proyectada de disponibilidad",
    descripcion: "La fecha proyectada de disponibilidad de un pedido se calcula como la suma de la ETA o ATA del destino, más el lead time maestro del destino expresado en días, más un ajuste manual opcional. Cuando existe ATA confirmada, ésta tiene precedencia sobre la ETA estimada por la API.",
    origen: "Documento técnico-funcional [2], sección 6: fórmula clave.",
  }),

  h2("7.2 Estados del ciclo de vida del pedido"),
  p("El estado de un pedido se determina en cada recálculo evaluando las reglas siguientes. Las reglas relativas a la etapa del viaje (RN-02 a RN-05) describen dónde se encuentra la carga; las relativas al cumplimiento (RN-07 a RN-09) describen si llegará a tiempo."),
  ...RN({ id: "RN-02", titulo: "Estado Sin tracking", descripcion: "Un pedido activo que carece de identificador de nave, vuelo o contenedor asociado se clasifica como Sin tracking y se representa en color gris. No es rastreable automáticamente.", origen: "Documento técnico-funcional [2], sección 6." }),
  ...RN({ id: "RN-03", titulo: "Estado En origen", descripcion: "Un pedido con identificador de rastreo asociado que aún no registra salida real se clasifica como En origen y se representa en azul claro.", origen: "Documento técnico-funcional [2], sección 6." }),
  ...RN({ id: "RN-04", titulo: "Estado En tránsito", descripcion: "Un pedido con salida real registrada y posición actual activa se clasifica como En tránsito y se representa en azul.", origen: "Documento técnico-funcional [2], sección 6." }),
  ...RN({ id: "RN-05", titulo: "Estado En destino", descripcion: "Un pedido cuya fuente externa reporta la llegada al puerto o aeropuerto de destino se clasifica como En destino y se representa en morado.", origen: "Documento técnico-funcional [2], sección 6." }),
  ...RN({ id: "RN-06", titulo: "Estado En proceso aduanal", descripcion: "Un pedido cuya carga ha llegado al destino pero para el cual aún corre el lead time de tratamiento se clasifica como En proceso aduanal y se representa en amarillo.", origen: "Documento técnico-funcional [2], sección 6." }),
  ...RN({ id: "RN-07", titulo: "Estado A tiempo", descripcion: "Un pedido cuya fecha proyectada de disponibilidad es anterior o igual a la fecha de entrega comprometida se clasifica como A tiempo y se representa en verde.", origen: "Documento técnico-funcional [2], sección 6." }),
  ...RN({ id: "RN-08", titulo: "Estado En riesgo", descripcion: "Un pedido cuya fecha proyectada de disponibilidad se sitúa dentro del umbral crítico definido respecto a la fecha de entrega comprometida se clasifica como En riesgo y se representa en naranja. El documento técnico-funcional propone 48 horas como valor de referencia.", origen: "Documento técnico-funcional [2], sección 6." }),
  ...RN({ id: "RN-09", titulo: "Estado Retrasado", descripcion: "Un pedido cuya fecha proyectada de disponibilidad es posterior a la fecha de entrega comprometida se clasifica como Retrasado y se representa en rojo.", origen: "Documento técnico-funcional [2], sección 6." }),
  ...RN({ id: "RN-10", titulo: "Estado Cerrado", descripcion: "Un pedido cuya mercancía ha sido recibida en planta o almacén se clasifica como Cerrado. Es un estado terminal: el pedido deja de consultarse contra las APIs externas y se archiva.", origen: "Documento técnico-funcional [2], sección 6." }),

  h2("7.3 Reglas complementarias"),
  ...RN({
    id: "RN-11", titulo: "Umbral crítico del estado En riesgo",
    descripcion: "El umbral que separa el estado A tiempo del estado En riesgo debe ser un parámetro configurable, no un valor fijo en el código. El documento técnico-funcional propone 48 horas como referencia inicial.",
    origen: "Documento técnico-funcional [2], secciones 6 y 13. " + M.GREIVIN,
  }),
  ...RN({
    id: "RN-12", titulo: "Lead time estándar frente a lead time crítico",
    descripcion: "El maestro de destinos contempla dos lead times por destino: el estándar, aplicable en condiciones normales, y el crítico, aplicable ante congestión o revisión especial. Debe definirse bajo qué condición se aplica cada uno y quién toma esa decisión.",
    origen: "Documento técnico-funcional [2], sección 7.2. " + M.ENTREVISTAS,
  }),
  ...RN({
    id: "RN-13", titulo: "Estados terminales",
    descripcion: "Se consideran terminales los estados en los que el pedido deja de ser objeto de seguimiento activo. El estado Cerrado es terminal por definición. Debe determinarse si existen otros supuestos terminales, como la cancelación de una orden de compra o el rechazo de la mercancía por control de calidad.",
    origen: "Derivado del documento técnico-funcional [2]. " + M.ENTREVISTAS,
  }),
  ...RN({
    id: "RN-14", titulo: "Precedencia del dato manual sobre el automático",
    descripcion: "Cuando existe una confirmación manual de desembarco registrada por el usuario de Logística, ésta prevalece sobre el dato reportado por la API externa para el cálculo de la fecha proyectada.",
    origen: "Derivado de la sección 12 del documento técnico-funcional [2], riesgo de cambios manuales sin auditoría.",
  }),
  marcador(M.GREIVIN, "Los umbrales concretos en días u horas para los estados En riesgo y Retrasado, así como la condición de aplicación del lead time crítico, requieren validación con el supervisor y los usuarios de Logística antes de su implementación en el Sprint 3."),
];

// ================================= 8. MODELO DE DATOS PRELIMINAR
const seccion8 = [
  h1("8. Modelo de datos preliminar"),
  p("Esta sección presenta el modelo de datos tentativo derivado de la sección 7 del documento técnico-funcional. El modelo definitivo, con su diagrama entidad-relación y su diccionario de datos completo, constituye un entregable independiente del Sprint 2 y se documentará en el archivo correspondiente del repositorio."),
  p("Se identifican seis entidades. Las tres primeras proceden directamente del documento técnico-funcional; las tres restantes se incorporan para normalizar datos hoy embebidos como texto libre y para dar soporte a la auditoría de intervenciones manuales."),

  h2("8.1 Entidades identificadas"),
  tabla(
    ["Entidad", "Propósito", "Origen"],
    [
      ["pedidos_transito", "Registro central de cada línea de orden de compra en tránsito, con sus datos maestros, su identificador de rastreo, su última posición conocida y su estado calculado.", "Documento técnico-funcional, sección 7.1"],
      ["maestro_destinos", "Catálogo de puertos y aeropuertos con sus lead times estándar y crítico, que alimentan el cálculo de la fecha proyectada.", "Documento técnico-funcional, sección 7.2"],
      ["historial_tracking", "Secuencia inmutable de posiciones registradas por pedido, con el payload completo de la respuesta de la API para auditoría.", "Documento técnico-funcional, sección 7.3"],
      ["proveedores", "Normalización del proveedor, hoy almacenado como texto libre en el pedido. Habilita el análisis de desempeño por proveedor.", "Derivado del anteproyecto, sección 4"],
      ["materiales", "Normalización del material, hoy almacenado como código y descripción concatenados. Habilita el filtrado y la agregación por material.", "Derivado del documento técnico-funcional"],
      ["usuarios", "Soporte de la autenticación y, sobre todo, de la auditoría de confirmaciones manuales y ajustes exigida por RF-14.", "Derivado del riesgo de trazabilidad, sección 12 del documento técnico-funcional"],
    ],
    [2100, 4600, 2660]
  ),

  h2("8.2 Campos preliminares de pedidos_transito"),
  tabla(
    ["Campo", "Tipo sugerido", "Descripción"],
    [
      ["oc_numero", "VARCHAR", "Número de orden de compra."],
      ["posicion_oc", "INTEGER", "Línea o posición dentro de la orden."],
      ["material", "VARCHAR", "Código y descripción del material."],
      ["proveedor", "VARCHAR", "Proveedor asociado al pedido."],
      ["fecha_entrega_pedido", "DATE", "Fecha comprometida según el pedido."],
      ["via_transporte", "VARCHAR", "Aéreo o marítimo."],
      ["tracking_interno", "VARCHAR", "Código único interno de seguimiento."],
      ["tipo_tracking_externo", "VARCHAR", "MMSI, IMO, BL, AWB, contenedor, vuelo o booking."],
      ["tracking_externo", "VARCHAR", "Valor del identificador externo."],
      ["destino", "VARCHAR", "Puerto o aeropuerto de destino."],
      ["eta_api", "TIMESTAMP", "Fecha estimada de llegada reportada por la API."],
      ["ata_api", "TIMESTAMP", "Fecha real de llegada, si existe."],
      ["lead_time_destino_dias", "INTEGER", "Días de tratamiento del destino."],
      ["fecha_proyectada_disponible", "DATE", "Fecha empleada para evaluar el cumplimiento."],
      ["estado_calculado", "VARCHAR", "Estado funcional calculado conforme a la sección 7."],
      ["ultima_actualizacion_api", "TIMESTAMP", "Fecha y hora de la última consulta exitosa."],
    ],
    [2600, 1800, 4960]
  ),

  h2("8.3 Campos preliminares de maestro_destinos"),
  tabla(
    ["Campo", "Tipo sugerido", "Descripción"],
    [
      ["destino", "VARCHAR", "Puerto o aeropuerto."],
      ["via_transporte", "VARCHAR", "Aéreo o marítimo."],
      ["lead_time_estandar_dias", "INTEGER", "Días normales de desembarque, nacionalización y tratamiento."],
      ["lead_time_critico_dias", "INTEGER", "Días alternativos ante congestión o revisión especial."],
      ["activo", "BOOLEAN", "Indica si el destino se emplea para los cálculos."],
      ["observacion", "TEXT", "Comentarios logísticos."],
    ],
    [2600, 1800, 4960]
  ),

  h2("8.4 Campos preliminares de historial_tracking"),
  tabla(
    ["Campo", "Tipo sugerido", "Descripción"],
    [
      ["id", "BIGSERIAL", "Identificador del registro histórico."],
      ["tracking_interno", "VARCHAR", "Relación con el pedido."],
      ["fecha_registro", "TIMESTAMP", "Momento de la captura."],
      ["latitud", "NUMERIC", "Latitud reportada."],
      ["longitud", "NUMERIC", "Longitud reportada."],
      ["velocidad", "NUMERIC", "Velocidad sobre tierra, si aplica."],
      ["rumbo", "NUMERIC", "Curso o rumbo."],
      ["estado_api", "VARCHAR", "Estado crudo de la fuente externa."],
      ["payload_api", "JSONB", "Respuesta completa de la API, para auditoría."],
    ],
    [2600, 1800, 4960]
  ),

  h2("8.5 Consideraciones geoespaciales"),
  p("El almacenamiento de latitud y longitud como valores numéricos independientes, tal como propone el documento técnico-funcional, resulta insuficiente para las consultas espaciales que exige el Objetivo Específico 4. Se propone incorporar una columna de tipo geometría de PostGIS, con sistema de referencia WGS 84, que permita calcular distancias, reconstruir trayectos y determinar la proximidad a un destino mediante operadores espaciales nativos."),
  marcador(M.GREIVIN, "Confirmar si el modelo debe contemplar la relación de varias líneas de orden de compra viajando en una misma nave, lo que afectaría la cardinalidad entre pedido y elemento rastreado."),
];

// ===================== 9. RESTRICCIONES Y SUPUESTOS DEL PROYECTO
const seccion9 = [
  h1("9. Restricciones y supuestos del proyecto"),

  h2("9.1 Restricciones de alcance"),
  p("El alcance queda delimitado por el anteproyecto aprobado. La sección 1.2.2 de este documento enumera las exclusiones explícitas. La restricción de mayor impacto sobre el diseño es que el sistema no se desplegará en producción dentro de la práctica, lo que traslada al Centro de Competencias la responsabilidad del despliegue posterior y eleva la importancia de la documentación técnica como entregable."),

  h2("9.2 Restricciones de tiempo"),
  p("El proyecto dispone de dieciséis semanas, del 3 de agosto al 21 de noviembre de 2026, con posibilidad de extensión de dos semanas adicionales hasta el 5 de diciembre de 2026. La distribución comprende una semana de inducción, siete sprints de dos semanas bajo metodología Scrum y una semana de cierre. Este documento corresponde al entregable del Sprint 1, cuyo cierre está previsto para el 21 de agosto de 2026."),
  p("La restricción temporal condiciona la priorización de los requerimientos: aquellos marcados con prioridad Baja son los primeros candidatos a posponerse si el cronograma se comprime."),

  h2("9.3 Restricciones tecnológicas"),
  p("El stack tecnológico está fijado por el anteproyecto y se detalla en la sección 5.8. No es objeto de decisión durante la práctica. Existe una desviación conocida respecto de lo previsto: el anteproyecto contempla la ejecución del entorno de desarrollo mediante contenedores Docker, lo cual no es posible en el equipo asignado al practicante por carecer de permisos administrativos para habilitar la virtualización requerida. El entorno se levanta de forma nativa y los archivos de contenedor se conservan como artefacto para el despliegue en servidor."),

  h2("9.4 Supuestos sobre datos, accesos y usuarios"),
  bullet("Se supone que la empresa proveerá una muestra representativa del archivo Excel de pedidos en tránsito antes del inicio del Sprint 2."),
  bullet("Se supone que existe, para una fracción operativamente significativa de los pedidos, el identificador de nave o vuelo necesario para el rastreo automático."),
  bullet("Se supone que los usuarios clave de Compras y Logística estarán disponibles para las sesiones de levantamiento, validación de prototipos y pruebas de aceptación."),
  bullet("Se supone que se dispondrá de credenciales válidas para AISStream y OpenSky Network durante todo el período de desarrollo."),
  bullet("Se supone que la conectividad de red del entorno de desarrollo permitirá alcanzar los servicios externos de rastreo."),
  marcador(M.GREIVIN, "Confirmar la designación nominal de los usuarios clave de Compras y de Logística, que el anteproyecto deja como Por definir, y acordar la cadencia de las sesiones de validación."),
];

// ============================= 10. CRITERIOS DE ACEPTACIÓN
const seccion10 = [
  h1("10. Criterios de aceptación general"),
  p("Los criterios se organizan según los cuatro entregables principales definidos en la sección 9.3 del anteproyecto. Cada entregable se considera aceptado cuando satisface la totalidad de sus criterios y cuenta con la aprobación del supervisor de empresa."),
  tabla(
    ["Entregable", "Criterio de aceptación", "Objetivo"],
    [
      ["1. Análisis y diseño", "Documentos de requerimientos, modelo de datos, arquitectura y prototipos de interfaz revisados y aprobados por el supervisor de empresa y los usuarios clave.", "OE1"],
      ["2. Backend y APIs", "Servicios REST funcionales y documentados en OpenAPI. Datos de tracking obtenidos correctamente de las APIs externas. Estados calculados conforme a las reglas de la sección 7 de este documento.", "OE2"],
      ["3. Frontend y dashboard", "Dashboard funcional accesible en entorno local. Marcadores en mapa coloreados según estado. Filtros operativos sobre KPIs, grilla y mapas de forma coherente.", "OE3"],
      ["4. Base de datos y documentación", "Datos persistidos correctamente. Consultas geoespaciales operativas. Historial auditable. Manual técnico, manual de usuario y guía de despliegue entregados y aprobados.", "OE4"],
    ],
    [2100, 5560, 1700]
  ),
  ...espacio(1),
  p("Adicionalmente, se considerarán criterios transversales de aceptación los siguientes: que el código fuente resida en un repositorio Git organizado y documentado; que las reglas de cálculo de estado cuenten con pruebas automatizadas; y que el sistema sea reproducible en un equipo distinto siguiendo exclusivamente el manual de instalación entregado."),
  marcador(M.ASESOR, "Confirmar si la Escuela exige criterios de aceptación adicionales de carácter académico, como cobertura mínima de pruebas o formato específico de la documentación técnica."),
];

// ================================================ 11. ANEXOS
const anexos = [
  h1("Anexo A. Glosario extendido"),
  p("Este anexo amplía la tabla de la sección 1.3 con terminología del dominio logístico y farmacéutico empleada en el proyecto."),
  tabla(
    ["Término", "Definición"],
    [
      ["Agente aduanal", "Persona física o jurídica autorizada para tramitar la nacionalización de mercancías ante la autoridad aduanera."],
      ["Booking", "Reserva de espacio de carga con una naviera, previa a la emisión del conocimiento de embarque."],
      ["Congestión portuaria", "Saturación de la capacidad operativa de un puerto que produce demoras en el atraque y la descarga. En el contexto de Gutis, un factor de riesgo relevante en el puerto de Moín."],
      ["Excipiente", "Sustancia sin actividad farmacológica que acompaña al principio activo en una formulación farmacéutica."],
      ["Lead time crítico", "Días de tratamiento aplicables a un destino ante condiciones excepcionales de congestión o revisión especial."],
      ["Lead time estándar", "Días de tratamiento aplicables a un destino en condiciones normales de operación."],
      ["Nacionalización", "Conjunto de trámites que permiten el ingreso legal de una mercancía importada al territorio nacional."],
      ["Payload", "Contenido íntegro de la respuesta de una API, conservado sin transformación para fines de auditoría."],
      ["Port call", "Escala de una embarcación en un puerto, con sus eventos de arribo y zarpe."],
      ["Quiebre de stock", "Agotamiento de existencias de un material que impide continuar la producción o atender la demanda."],
      ["Semáforo", "Esquema de codificación por color que comunica el estado logístico de un pedido de un vistazo."],
      ["Trazabilidad", "Capacidad de reconstruir el recorrido y los estados por los que pasó una carga, con evidencia verificable."],
    ],
    [2200, 7160]
  ),

  h1("Anexo B. Formato del archivo Excel de carga inicial"),
  p("Este anexo especificará la estructura exacta del archivo de carga de pedidos: nombre y orden de las columnas, tipos de dato, formatos de fecha, valores admitidos en los campos de dominio y reglas de obligatoriedad. Esta especificación es el insumo directo de RF-01 y RF-02."),
  marcador(M.DATOS, "Este anexo no puede completarse hasta recibir de Laboratorios Gutis una muestra real del archivo de exportación del ERP. Se solicita una muestra anonimizada con un mínimo de veinte pedidos representativos, que incluya casos de vía marítima y aérea, y al menos un caso sin identificador de rastreo asociado."),
  p("Estructura tentativa, sujeta a confirmación con la muestra real:"),
  tabla(
    ["Columna esperada", "Tipo", "Obligatorio", "Observación"],
    [
      ["Número de OC", "Texto", "Sí", "Junto con la posición, identifica unívocamente el pedido."],
      ["Posición", "Entero", "Sí", "Línea dentro de la orden de compra."],
      ["Material", "Texto", "Sí", "Código y descripción."],
      ["Proveedor", "Texto", "Sí", "Nombre o código del proveedor."],
      ["Fecha de entrega", "Fecha", "Sí", "Fecha comprometida. Formato por confirmar."],
      ["Vía de transporte", "Texto", "Sí", "Valores admitidos: Aéreo, Marítimo."],
      ["Destino", "Texto", "Sí", "Debe existir en el maestro de destinos."],
      ["Tipo de tracking", "Texto", "No", "MMSI, IMO, buque, vuelo, AWB, contenedor o booking."],
      ["Tracking externo", "Texto", "No", "Sin este valor el pedido queda en estado Sin tracking."],
    ],
    [2400, 1200, 1400, 4360]
  ),

  h1("Anexo C. Referencias técnicas de las APIs"),
  h2("C.1 Fuentes de rastreo evaluadas"),
  tabla(
    ["Fuente", "Uso previsto", "Observación funcional"],
    [
      ["AISStream", "Rastreo marítimo del prototipo. Gratuito, por WebSocket.", "Recibe datos AIS por área geográfica mediante mensajes PositionReport. Requiere clave de API. Sin acuerdo de nivel de servicio."],
      ["OpenSky Network", "Rastreo aéreo del prototipo. Gratuito, API REST.", "No entrega itinerarios comerciales ni datos de retraso que no se deriven de ADS-B. Cobertura dependiente de la red de receptores."],
      ["MarineTraffic", "Opción marítima para la fase productiva.", "Permite integrar posiciones AIS, eventos, escalas portuarias y datos de buque. Modelo comercial."],
      ["VesselFinder", "Alternativa marítima comercial.", "Ofrece posiciones, datos de viaje, escalas portuarias e información de buque."],
      ["FlightAware AeroAPI", "Opción aérea para la fase productiva.", "Permite estado, ETA, última posición, trayecto y alertas bajo modelo comercial."],
    ],
    [1900, 2800, 4660]
  ),
  ...espacio(1),
  h2("C.2 Consideración crítica sobre el alcance del rastreo"),
  p("Las APIs de AIS rastrean embarcaciones, no mercancía. Si de un pedido sólo se conoce el número de contenedor, el conocimiento de embarque o el booking, no es posible resolver automáticamente qué nave lo transporta. Resolver ese vínculo exige una fuente adicional de container tracking, de carácter comercial, que queda fuera del alcance de esta práctica."),
  p("Esta limitación es la razón de ser del estado Sin tracking definido en RN-02, y su impacto operativo depende directamente de qué proporción de los pedidos de Gutis cuenta con identificador de nave. Determinar esa proporción es una de las prioridades del levantamiento de requerimientos."),
  marcador(M.ENTREVISTAS, "Cuantificar con el área de Logística qué porcentaje de los pedidos en tránsito dispone hoy de MMSI, IMO o nombre de buque, y por qué medio se obtiene ese dato."),
  h2("C.3 Enlaces de documentación"),
  bullet("AISStream: https://aisstream.io/documentation"),
  bullet("OpenSky Network: https://openskynetwork.github.io/opensky-api/"),
  bullet("MarineTraffic: https://servicedocs.marinetraffic.com/"),
  bullet("VesselFinder: https://api.vesselfinder.com/docs/"),
  bullet("FlightAware AeroAPI: https://www.flightaware.com/commercial/aeroapi/"),
];

// ============================================================ DOCUMENTO
const doc = new Document({
  creator: "Mariano Mayorga Halabi",
  title: "SRS — TrackIn",
  description: "Especificación de Requerimientos de Software del sistema TrackIn, Práctica de Especialidad TEC 2026-II",
  styles: {
    default: {
      document: { run: { font: "Calibri", size: 22, color: "000000" }, paragraph: { spacing: { line: 276 } } },
      heading1: { run: { font: "Cambria", size: 32, bold: true, color: AZUL }, paragraph: { spacing: { before: 360, after: 180 } } },
      heading2: { run: { font: "Cambria", size: 26, bold: true, color: AZUL }, paragraph: { spacing: { before: 280, after: 140 } } },
      heading3: { run: { font: "Cambria", size: 23, bold: true, color: "2E5496" }, paragraph: { spacing: { before: 220, after: 120 } } },
    },
  },
  numbering: {
    config: [
      {
        reference: "vinetas",
        levels: [
          { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 460, hanging: 260 } } } },
        ],
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
        },
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                t("SRS TrackIn v0.1 — Sprint 1 — Mariano Mayorga Halabi — Página ", { size: 16, color: "666666" }),
                new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "666666" }),
              ],
            }),
          ],
        }),
      },
      children: [
        ...portada,
        ...historial,
        ...toc,
        ...seccion1,
        ...seccion2,
        ...seccion3,
        ...seccion4,
        ...seccion5,
        ...seccion6,
        ...seccion7,
        ...seccion8,
        ...seccion9,
        ...seccion10,
        ...anexos,
      ],
    },
  ],
});

const salida = process.argv[2] || "SRS_TrackIn_v0.1.docx";
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(salida, buf);
  console.log("Escrito: " + salida + " (" + (buf.length / 1024).toFixed(1) + " KB)");
});
