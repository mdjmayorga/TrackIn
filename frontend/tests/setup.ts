/** Setup global de vitest: agrega los matchers de jest-dom (`toBeInTheDocument`, …). */
import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

// Vitest lee el `.env` del frontend igual que Vite: sin esto, las pruebas verían
// el token del ShipsGo Embed en una máquina que lo tiene y no en CI, y darían
// resultados distintos. Las que prueban el mapa en vivo lo activan ellas.
vi.stubEnv('VITE_SHIPSGO_EMBED_TOKEN', '')
