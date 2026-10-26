/**
 * De cuándo es el rastreo del panel (`US-23`, RF-20, RNF-12), bajo la insignia
 * de ShipsGo del encabezado, como el «Última actualización» del Figma.
 *
 * Es la última consulta buena a ShipsGo, que el worker repite cada minuto. Si la
 * fuente falla, la insignia lo dice y esta línea da la antigüedad del último
 * dato válido. La carga semanal del Z-tracking, el otro origen de los datos,
 * vive desde el 26/10 en «Ajustes Z-tracking» (`MenuZtracking`).
 */

import { useHealth } from '@/hooks/useHealth'
import { formatearFechaHora, haceCuanto } from '@/utils/fechas'

export function FrescuraDatos() {
  const salud = useHealth()
  const contacto = salud.data?.fuentes?.find((f) => f.fuente === 'shipsgo')?.ultimo_contacto_ok

  return (
    <p className="text-right text-xs text-slate-300">
      Última consulta a ShipsGo:{' '}
      {contacto ? (
        <>
          {formatearFechaHora(contacto)}{' '}
          <span className="text-slate-500">({haceCuanto(contacto)})</span>
        </>
      ) : (
        <span className="text-slate-500">todavía no hay</span>
      )}
    </p>
  )
}
