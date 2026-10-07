import { describe, expect, it } from 'vitest'

import { formatearFecha } from '@/utils/fechas'

describe('formatearFecha', () => {
  it('una fecha sin hora se reacomoda tal cual, sin correrse de día', () => {
    expect(formatearFecha('2026-09-08')).toBe('08/09/2026')
  })

  it('un instante se muestra en hora de Costa Rica', () => {
    // 02:00 UTC del 9 son las 20:00 del 8 en Costa Rica (UTC-6).
    expect(formatearFecha('2026-09-09T02:00:00Z')).toBe('08/09/2026')
  })

  it('sin valor, o con uno inválido, no hay fecha', () => {
    expect(formatearFecha(null)).toBeNull()
    expect(formatearFecha('')).toBeNull()
    expect(formatearFecha('no es fecha')).toBeNull()
  })
})
