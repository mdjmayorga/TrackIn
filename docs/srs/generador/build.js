/* Generador del SRS de TrackIn — Sprint 1, Práctica de Especialidad TEC 2026-II */
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  TableOfContents, PageBreak, Footer, Header, PageNumber, LevelFormat,
  convertInchesToTwip,
} = require("docx");

// ---------------------------------------------------------------- constantes
const CONTENT_W = 9360;            // 12240 (Letter) - 1440*2 de márgenes
const AZUL = "1F3864";
const GRIS_ENC = "D9E2F3";
const GRIS_ETQ = "F2F2F2";
const AMBAR = "FFF2CC";

const MARCADORES = {
  ENTREVISTAS: "[COMPLETAR CON ENTREVISTAS]",
  GREIVIN: "[VALIDAR CON GREIVIN]",
  ASESOR: "[VALIDAR CON ASESOR TEC]",
  DATOS: "[PENDIENTE MUESTRA DE DATOS]",
};

// ------------------------------------------------------------------ helpers
const t = (text, o = {}) => new TextRun({ text, ...o });

const p = (text, o = {}) =>
  new Paragraph({
    children: typeof text === "string" ? [t(text)] : text,
    spacing: { after: 120, line: 276 },
    alignment: o.align || AlignmentType.JUSTIFIED,
    ...o,
  });

const h1 = (text) =>
  new Paragraph({
    text,
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 180 },
    pageBreakBefore: true,
  });

const h2 = (text) =>
  new Paragraph({ text, heading: HeadingLevel.HEADING_2, spacing: { before: 280, after: 140 } });

const h3 = (text) =>
  new Paragraph({ text, heading: HeadingLevel.HEADING_3, spacing: { before: 220, after: 120 } });

const bullet = (text) =>
  new Paragraph({
    children: typeof text === "string" ? [t(text)] : text,
    numbering: { reference: "vinetas", level: 0 },
    spacing: { after: 80 },
    alignment: AlignmentType.JUSTIFIED,
  });

// Marcador resaltado, para que salte a la vista en la revisión.
const marcador = (tipo, detalle) =>
  new Paragraph({
    children: [
      t(tipo + " ", { bold: true, color: "9C5700" }),
      t(detalle, { italics: true, color: "9C5700" }),
    ],
    shading: { type: ShadingType.CLEAR, fill: AMBAR },
    spacing: { before: 100, after: 140 },
    alignment: AlignmentType.LEFT,
  });

const celda = (contenido, w, o = {}) =>
  new TableCell({
    width: { size: w, type: WidthType.DXA },
    shading: o.fill ? { type: ShadingType.CLEAR, fill: o.fill } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: (Array.isArray(contenido) ? contenido : [contenido]).map((c) =>
      typeof c === "string"
        ? new Paragraph({
            children: [t(c, { bold: o.bold, color: o.color, size: 20 })],
            spacing: { after: 0 },
            alignment: o.align || AlignmentType.LEFT,
          })
        : c
    ),
  });

// Tabla de datos con encabezado.
const tabla = (encabezados, filas, anchos) =>
  new Table({
    columnWidths: anchos,
    width: { size: CONTENT_W, type: WidthType.DXA },
    rows: [
      new TableRow({
        tableHeader: true,
        children: encabezados.map((e, i) => celda(e, anchos[i], { bold: true, fill: GRIS_ENC })),
      }),
      ...filas.map(
        (f) => new TableRow({ children: f.map((c, i) => celda(c, anchos[i])) })
      ),
    ],
  });

// Tabla etiqueta/valor, usada por RF, CU y RN.
const fichaTabla = (pares) =>
  new Table({
    columnWidths: [2400, 6960],
    width: { size: CONTENT_W, type: WidthType.DXA },
    rows: pares.map(
      ([k, v]) =>
        new TableRow({
          children: [
            celda(k, 2400, { bold: true, fill: GRIS_ETQ }),
            celda(v, 6960),
          ],
        })
    ),
  });

const tituloFicha = (codigo, titulo) =>
  new Paragraph({
    children: [t(codigo + ": " + titulo, { bold: true, size: 22, color: AZUL })],
    spacing: { before: 260, after: 100 },
    keepNext: true,
  });

const espacio = (n = 1) =>
  Array.from({ length: n }, () => new Paragraph({ children: [t("")], spacing: { after: 0 } }));

// Bloque de requerimiento funcional.
const RF = ({ id, titulo, descripcion, actor, pre, post, prioridad, oe }) => [
  tituloFicha(id, titulo),
  fichaTabla([
    ["Descripción", descripcion],
    ["Actor principal", actor],
    ["Precondiciones", pre],
    ["Postcondiciones", post],
    ["Prioridad", prioridad],
    ["Objetivo específico", oe],
  ]),
];

// Bloque de caso de uso. `flujo` y `alternos` son arreglos de strings ya numerados.
const CU = ({ id, titulo, actor, pre, flujo, alternos, post }) => {
  const lineas = (arr) =>
    arr.map(
      (s) =>
        new Paragraph({
          children: [t(s, { size: 20 })],
          spacing: { after: 40 },
          alignment: AlignmentType.LEFT,
        })
    );
  return [
    tituloFicha(id, titulo),
    new Table({
      columnWidths: [2400, 6960],
      width: { size: CONTENT_W, type: WidthType.DXA },
      rows: [
        new TableRow({ children: [celda("Actor principal", 2400, { bold: true, fill: GRIS_ETQ }), celda(actor, 6960)] }),
        new TableRow({ children: [celda("Precondiciones", 2400, { bold: true, fill: GRIS_ETQ }), celda(pre, 6960)] }),
        new TableRow({ children: [celda("Flujo principal", 2400, { bold: true, fill: GRIS_ETQ }), new TableCell({ width: { size: 6960, type: WidthType.DXA }, margins: { top: 60, bottom: 60, left: 100, right: 100 }, children: lineas(flujo) })] }),
        new TableRow({ children: [celda("Flujos alternativos", 2400, { bold: true, fill: GRIS_ETQ }), new TableCell({ width: { size: 6960, type: WidthType.DXA }, margins: { top: 60, bottom: 60, left: 100, right: 100 }, children: lineas(alternos) })] }),
        new TableRow({ children: [celda("Postcondiciones", 2400, { bold: true, fill: GRIS_ETQ }), celda(post, 6960)] }),
      ],
    }),
  ];
};

const RN = ({ id, titulo, descripcion, origen }) => [
  tituloFicha(id, titulo),
  fichaTabla([["Descripción", descripcion], ["Origen", origen]]),
];

module.exports = {
  fs, Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table,
  TableRow, TableCell, WidthType, ShadingType, BorderStyle, TableOfContents,
  PageBreak, Footer, Header, PageNumber, LevelFormat, convertInchesToTwip,
  CONTENT_W, AZUL, GRIS_ENC, GRIS_ETQ, AMBAR, MARCADORES,
  t, p, h1, h2, h3, bullet, marcador, celda, tabla, fichaTabla, tituloFicha,
  espacio, RF, CU, RN,
};
