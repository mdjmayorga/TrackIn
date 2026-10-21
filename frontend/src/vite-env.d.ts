/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** URL base de la API de TrackIn. Ver `.env.example`. */
  readonly VITE_API_URL?: string
  /** Token del ShipsGo Embed (no el de la API): el mapa en vivo del detalle. */
  readonly VITE_SHIPSGO_EMBED_TOKEN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
