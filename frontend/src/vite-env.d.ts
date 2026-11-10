/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** URL base de la API de TrackIn. Ver `.env.example`. */
  readonly VITE_API_URL?: string
  /** Token del ShipsGo Embed (no el de la API): el mapa en vivo del detalle. */
  readonly VITE_SHIPSGO_EMBED_TOKEN?: string
  /** Mosaicos del fondo de los mapas. Vacía: OpenStreetMap (`utils/mosaicos.ts`). */
  readonly VITE_MOSAICOS_URL?: string
  /** Atribución de esos mosaicos, en HTML. Vacía: la de OpenStreetMap. */
  readonly VITE_MOSAICOS_ATRIBUCION?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

/** La versión de TrackIn (la del package.json), fijada por Vite al construir. */
declare const __APP_VERSION__: string
