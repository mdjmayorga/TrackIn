/**
 * Avión o barco, en trazo, como en las tarjetas del Figma. El texto de la vía
 * va en el `title` para quien no distinga el dibujo.
 */

import type { Via } from '@/types/api'

const TEXTO: Record<Via, string> = { AEREO: 'Aéreo', MARITIMO: 'Marítimo', TERRESTRE: 'Terrestre' }

export function IconoVia({ via, className = '' }: { via: Via; className?: string }) {
  return (
    <svg
      role="img"
      aria-label={TEXTO[via]}
      viewBox="0 0 24 18"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <title>{TEXTO[via]}</title>
      {via === 'AEREO' ? (
        <>
          {/* Avión despegando, con estelas detrás. */}
          <path d="M5 11.5 20 6.5c1.6-.5 2.6.6 1.6 1.6L9.5 13.6 6.5 14 4 11.8Z" />
          <path d="M11 9.5 8.5 4.5l1.8-.4 4.6 4.1" />
          <path d="M10.6 12.8 12 16l1.6-.6-.2-3.9" />
          <path d="M1 13.5h3M2 16h4" />
        </>
      ) : (
        <>
          {/* Buque portacontenedores. */}
          <path d="M1.5 11h21l-2.5 4.5H4Z" />
          <path d="M4 11V8h4v3M8 11V7h4v4M12 11V8h4v3" />
          <path d="M17 11V6.5h2.5V11M18 6.5V4.5" />
          <path d="M1 17.3c1.5 0 1.5-.8 3-.8s1.5.8 3 .8 1.5-.8 3-.8 1.5.8 3 .8" />
        </>
      )}
    </svg>
  )
}
