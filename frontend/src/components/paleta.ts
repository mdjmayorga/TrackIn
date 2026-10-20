/**
 * Los colores del semáforo (RNF-08, wireframes §1.6), con los tonos del Figma
 * aprobado el 06/10. **El único lugar donde se escriben** (`US-24`):
 *
 * - `tailwind.config.js` los importa para generar `bg-estado-*`, que usan la
 *   grilla, los distintivos y las tarjetas;
 * - `estados.ts` los expone en hexadecimal para lo que no usa clases, como los
 *   marcadores de Leaflet de los mapas.
 *
 * Así un estado no puede verse de un color en la grilla y de otro en el mapa.
 *
 * Sin dependencias ni sintaxis de TypeScript más allá de los tipos: lo lee
 * también la configuración de Tailwind, fuera de Vite.
 */

export const PALETA_ESTADOS = {
  'sin-tracking': '#9ca3af',
  origen: '#0ea589',
  transito: '#0b4dff',
  destino: '#6b3a7f',
  aduanal: '#8c8c26',
  // Sin color en el SRS ni en el Figma: el café quedó definitivo el 14/10.
  recibido: '#92400e',
  'a-tiempo': '#24955f',
  riesgo: '#ea580c',
  retrasado: '#d0141b',
  cancelado: '#000000',
} as const

export type ColorEstado = keyof typeof PALETA_ESTADOS

export const BLANCO = '#ffffff'
export const NEGRO = '#000000'
