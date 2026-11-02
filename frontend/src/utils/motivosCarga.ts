/** Los motivos de rechazo de una carga (`US-32`), dichos para quien corrige SAP. */

const MOTIVOS: Record<string, string> = {
  sin_via_transporte: 'Sin vía de transporte',
  sin_destino_resoluble: 'Sin destino reconocible',
  // 21/10: antes salían como «sin destino», que no explicaba la causa.
  via_fuera_de_alcance: 'Vía fuera del alcance',
  sin_clave_natural: 'Sin OC o posición',
  sin_datos_minimos: 'Sin los datos mínimos',
  sin_fecha_de_entrega: 'Sin fecha de entrega',
  // `US-59`: el detalle dice el campo, el valor que traía y lo esperado.
  formato_invalido: 'Formato inválido',
  dato_descartado: 'Dato descartado',
  referencia_invalida: 'Referencia de embarque inválida',
  no_la_sigue_shipsgo: 'Referencia que ShipsGo no sigue',
  aerolinea_sin_cobertura: 'Aerolínea sin cobertura en ShipsGo',
}

/** Qué hacer en SAP para cada motivo frecuente. */
export const QUE_HACER: Record<string, string> = {
  sin_via_transporte: 'Complete la vía (Aéreo o Marítimo) en SAP y vuelva a cargar.',
  sin_destino_resoluble:
    'Agregue el BL o la guía madre, o indique el puerto de llegada en el incoterm (CIF LIMON). Con EXW, FCA o FOB el incoterm nombra el origen, no el destino.',
  via_fuera_de_alcance:
    'No hay nada que corregir: TrackIn sigue solo envíos aéreos y marítimos. Las compras terrestres no entran.',
  formato_invalido:
    'Corrija la celda que dice el detalle, con el formato que pide, y vuelva a cargar.',
  dato_descartado:
    'La línea entró sin ese dato. Corríjalo en SAP para que la próxima carga lo tome.',
}

export function nombreMotivo(motivo: string): string {
  return MOTIVOS[motivo] ?? motivo.replaceAll('_', ' ')
}
