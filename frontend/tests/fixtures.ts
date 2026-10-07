import type { PaginaPedidos, PedidoResumen } from '@/types/api'

/** Un pedido marítimo en tránsito, a tiempo. Cada prueba cambia lo que le importa. */
export function pedido(cambios: Partial<PedidoResumen> = {}): PedidoResumen {
  return {
    id: 1,
    oc_numero: '4500012847',
    posicion_oc: 10,
    tracking_interno: '450001284710',
    material: { id: 1, codigo: '13002006', descripcion: 'Lactosa monohidrato' },
    proveedor: { id: 1, codigo: 'PROV-0001', nombre: 'Proveedor 0001' },
    via_transporte: 'MARITIMO',
    destino: { id: 2, codigo: 'CRLIO', nombre: 'Puerto Limón' },
    eta_utilizada: '2026-09-01T12:00:00Z',
    fecha_proyectada_disponible: '2026-09-08',
    fecha_entrega_pedido: '2026-09-15',
    etapa_viaje: 'EN_TRANSITO',
    estado_cumplimiento: 'A_TIEMPO',
    estado_calculado: 'A_TIEMPO',
    rastreable: true,
    ultima_actualizacion_fuente: null,
    ausente_desde: null,
    fecha_recepcion_planta: null,
    cantidad_recibida: null,
    ...cambios,
  }
}

export function pagina(
  items: PedidoResumen[],
  { total = items.length, limite = 10, desplazamiento = 0 } = {},
): PaginaPedidos {
  return { total, limite, desplazamiento, items }
}
