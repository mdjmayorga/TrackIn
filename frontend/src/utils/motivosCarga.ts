/** Los motivos de rechazo de una carga (`US-32`), dichos para quien corrige SAP. */

const MOTIVOS: Record<string, string> = {
  sin_via_transporte: 'Sin vía de transporte',
  sin_destino_resoluble: 'Sin destino reconocible',
  sin_clave_natural: 'Sin OC o posición',
  sin_datos_minimos: 'Sin los datos mínimos',
  sin_fecha_de_entrega: 'Sin fecha de entrega',
  referencia_invalida: 'Referencia de embarque inválida',
  no_la_sigue_shipsgo: 'Referencia que ShipsGo no sigue',
  aerolinea_sin_cobertura: 'Aerolínea sin cobertura en ShipsGo',
}

/** Qué hacer en SAP para cada motivo frecuente. */
export const QUE_HACER: Record<string, string> = {
  sin_via_transporte: 'Complete la vía (Aéreo, Marítimo o Terrestre) en SAP y vuelva a cargar.',
  sin_destino_resoluble: 'Indique el puerto o aeropuerto de llegada en el incoterm o el destino.',
}

export function nombreMotivo(motivo: string): string {
  return MOTIVOS[motivo] ?? motivo.replaceAll('_', ' ')
}
