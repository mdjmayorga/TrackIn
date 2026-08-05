/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** URL base de la API de TrackIn. Ver `.env.example`. */
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
