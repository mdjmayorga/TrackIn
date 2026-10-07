import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/services/api'
import { listarPedidos } from '@/services/pedidos'

import { pagina } from './fixtures'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('servicio de pedidos', () => {
  it('pide la página con su orden y su tramo', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: pagina([]) })

    await listarPedidos({ orden: '-oc', limite: 25, desplazamiento: 50 })

    expect(get).toHaveBeenCalledWith('/api/v1/pedidos', {
      params: { orden: '-oc', limite: 25, desplazamiento: 50 },
    })
  })

  it('los filtros de lista van repetidos, como los lee FastAPI', () => {
    const url = api.getUri({ url: '/api/v1/pedidos', params: { via: ['AEREO', 'MARITIMO'] } })

    expect(url).toContain('via=AEREO&via=MARITIMO')
  })
})
