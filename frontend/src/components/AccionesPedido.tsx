/**
 * La barra de acciones del detalle (`US-60`, Figma «US-37», wireframes §4.8).
 *
 * Muestra solo lo que el rol puede hacer. Lo que no aplica a la etapa actual
 * se ve deshabilitado y dice por qué: un botón que desaparece no explica nada.
 * Ninguna acción es de un clic: todas abren su formulario con el motivo
 * obligatorio de RF-14.
 *
 * «Actualizar nave por transbordo» no está: es `US-30`, en el Sprint 7.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, type ReactNode, useState } from 'react'

import { type Accion, puedeIntervenir } from '@/auth/permisos'
import { useSesion } from '@/auth/useSesion'
import { esTerminal } from '@/components/estados'
import { refrescarTrasIntervenir } from '@/hooks/refrescar'
import {
  ajustarDias,
  cerrarForzado,
  comoConflictoDesembarco,
  comoRecepcionCorta,
  confirmarDesembarco,
  liberarCalidad,
  pasarAAduana,
  registrarRecepcion,
} from '@/services/acciones'
import { mensajeDeError } from '@/services/api'
import type { PedidoDetalle } from '@/types/api'
import { formatearCantidad } from '@/utils/detalle'
import {
  ahoraParaCampo,
  campoAInstante,
  diasEntre,
  formatearFecha,
  formatearFechaHora,
  sumarDias,
} from '@/utils/fechas'

/** El mínimo del backend (`auditoria.LONGITUD_MINIMA_MOTIVO`). */
const MOTIVO_MINIMO = 5

interface Definicion {
  accion: Accion
  titulo: string
  /** Nulo si aplica a la etapa; si no, por qué no. */
  bloqueo: (p: PedidoDetalle) => string | null
}

const ACCIONES: Definicion[] = [
  {
    accion: 'desembarco',
    titulo: 'Confirmar desembarco',
    bloqueo: (p) =>
      p.etapa_viaje === 'RECIBIDO_EN_PLANTA' ? 'El pedido ya se recibió en planta.' : null,
  },
  {
    accion: 'aduana',
    titulo: 'Pasar a proceso aduanal',
    bloqueo: (p) =>
      p.etapa_viaje === 'EN_DESTINO' ? null : 'Solo desde «En destino»: confirme antes la llegada.',
  },
  {
    accion: 'recepcion',
    titulo: 'Registrar recepción en planta',
    bloqueo: (p) =>
      p.etapa_viaje === 'EN_PROCESO_ADUANAL' ? null : 'Exige que el pedido haya pasado aduana.',
  },
  {
    accion: 'liberacion',
    titulo: 'Registrar liberación de Calidad',
    bloqueo: (p) =>
      p.etapa_viaje === 'RECIBIDO_EN_PLANTA' ? null : 'Exige la recepción en planta.',
  },
  {
    accion: 'ajuste',
    titulo: 'Ajustar días',
    // Se elige la nueva fecha en un calendario: sin fecha calculada no hay qué mover.
    bloqueo: (p) =>
      p.calculo.fecha_proyectada ? null : 'Sin fecha proyectada: no hay fecha que ajustar.',
  },
]

export function AccionesPedido({ pedido }: { pedido: PedidoDetalle }) {
  const sesion = useSesion()
  const [abierta, setAbierta] = useState<Accion | null>(null)
  const disponibles = ACCIONES.filter((a) => puedeIntervenir(a.accion, sesion?.usuario.rol))
  if (disponibles.length === 0) return null

  const cerrado = esTerminal(pedido)
  const activa = ACCIONES.find((a) => a.accion === abierta)

  return (
    <section aria-label="Acciones del pedido" className="mt-10">
      <div className="flex flex-wrap gap-3">
        {disponibles.map((a) => {
          const porque = cerrado
            ? 'El pedido está cerrado: no admite cambios (RN-13).'
            : a.bloqueo(pedido)
          return (
            <button
              key={a.accion}
              type="button"
              disabled={porque !== null}
              title={porque ?? undefined}
              aria-pressed={abierta === a.accion}
              onClick={() => setAbierta(abierta === a.accion ? null : a.accion)}
              className={`rounded px-4 py-2 text-base ${
                abierta === a.accion ? 'bg-slate-500' : 'bg-panel-cabecera'
              } text-slate-100 hover:bg-slate-600 disabled:cursor-not-allowed disabled:text-slate-500 disabled:hover:bg-panel-cabecera`}
            >
              {a.titulo}
            </button>
          )
        })}
      </div>

      {activa && (
        <div className="mt-4 max-w-xl rounded border border-panel-borde bg-panel-superficie p-4">
          <h2 className="mb-3 text-lg font-semibold">{activa.titulo}</h2>
          <Formulario
            key={activa.accion}
            accion={activa.accion}
            pedido={pedido}
            onListo={() => setAbierta(null)}
          />
        </div>
      )}
    </section>
  )
}

// --- Formularios ------------------------------------------------------------------

interface FormularioProps {
  accion: Accion
  pedido: PedidoDetalle
  onListo: () => void
}

function Formulario({ accion, pedido, onListo }: FormularioProps) {
  const queryClient = useQueryClient()
  const restante =
    Number(pedido.cierre.cantidad_recibida ?? 0) - Number(pedido.cierre.cantidad_liberada ?? 0)

  const [fecha, setFecha] = useState(ahoraParaCampo())
  const [cantidad, setCantidad] = useState(
    accion === 'liberacion' ? String(restante) : String(Number(pedido.cantidad_pedida)),
  )
  // El ajuste se elige como fecha (pedido del 15/10) y se guarda como días: la
  // fecha calculada sin ajuste es la proyectada menos el ajuste vigente.
  const ajusteActual = pedido.calculo.ajuste_manual_dias
  const proyectada = pedido.calculo.fecha_proyectada
  const calculada = proyectada ? sumarDias(proyectada, -ajusteActual) : null
  const [nuevaFecha, setNuevaFecha] = useState(proyectada ?? '')
  const dias = calculada && nuevaFecha ? diasEntre(calculada, nuevaFecha) : ajusteActual
  const [motivo, setMotivo] = useState('')

  const ejecutar = useMutation({
    mutationFn: async (variante: 'normal' | 'reemplazar' | 'parcial') => {
      const instante = campoAInstante(fecha)
      const base = { motivo }
      switch (accion) {
        case 'desembarco':
          return confirmarDesembarco(pedido.id, {
            ...base,
            ata: instante,
            confirmar: variante === 'reemplazar',
          })
        case 'aduana':
          return pasarAAduana(pedido.id, base)
        case 'recepcion':
          return (variante === 'parcial' ? cerrarForzado : registrarRecepcion)(pedido.id, {
            ...base,
            fecha: instante,
            cantidad,
          })
        case 'liberacion':
          return liberarCalidad(pedido.id, { ...base, fecha: instante, cantidad })
        case 'ajuste':
          return ajustarDias(pedido.id, { ...base, dias })
      }
    },
    onSuccess: (detalle) => {
      refrescarTrasIntervenir(queryClient, detalle)
      onListo()
    },
  })

  const llegadaPrevia = comoConflictoDesembarco(ejecutar.error)
  const recepcionCorta = comoRecepcionCorta(ejecutar.error)
  const sinCambio = accion === 'ajuste' && dias === ajusteActual
  const listo = motivo.trim().length >= MOTIVO_MINIMO && !ejecutar.isPending && !sinCambio

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    ejecutar.mutate('normal')
  }

  const conFecha = accion !== 'aduana' && accion !== 'ajuste'
  const etiquetaFecha = {
    desembarco: 'Fecha y hora de llegada',
    recepcion: 'Fecha y hora de recepción',
    liberacion: 'Fecha y hora de liberación',
  }[accion as 'desembarco' | 'recepcion' | 'liberacion']

  return (
    <form onSubmit={enviar} aria-label={`Formulario: ${accion}`} className="space-y-3">
      {conFecha && (
        <Campo etiqueta={etiquetaFecha}>
          <input
            type="datetime-local"
            value={fecha}
            max={ahoraParaCampo()}
            required
            onChange={(e) => setFecha(e.target.value)}
            className={ESTILO_CAMPO}
          />
        </Campo>
      )}

      {(accion === 'recepcion' || accion === 'liberacion') && (
        <Campo
          etiqueta={`Cantidad ${accion === 'recepcion' ? 'recibida' : 'liberada'} (${pedido.unidad_medida.toLowerCase()})`}
          ayuda={
            accion === 'recepcion'
              ? `Pedido: ${formatearCantidad(pedido.cantidad_pedida, pedido.unidad_medida)}`
              : `Pendiente de liberar: ${formatearCantidad(String(restante), pedido.unidad_medida)}`
          }
        >
          <input
            type="number"
            min={0}
            step="any"
            value={cantidad}
            required
            onChange={(e) => setCantidad(e.target.value)}
            className={ESTILO_CAMPO}
          />
        </Campo>
      )}

      {accion === 'ajuste' && calculada && (
        <Campo
          etiqueta="Nueva fecha proyectada"
          ayuda={`Fecha calculada sin ajuste: ${formatearFecha(calculada)}. ${
            dias === 0
              ? 'Con esta fecha no queda ajuste.'
              : `Con esta fecha el ajuste queda en ${dias > 0 ? '+' : '−'}${Math.abs(dias)} ${
                  Math.abs(dias) === 1 ? 'día' : 'días'
                }.`
          }`}
        >
          <input
            type="date"
            value={nuevaFecha}
            // El backend admite ±365 días de ajuste.
            min={sumarDias(calculada, -365)}
            max={sumarDias(calculada, 365)}
            required
            onChange={(e) => setNuevaFecha(e.target.value)}
            className={ESTILO_CAMPO}
          />
        </Campo>
      )}

      <Campo etiqueta="Motivo (obligatorio)" ayuda="Queda en la bitácora del pedido.">
        <textarea
          value={motivo}
          rows={2}
          onChange={(e) => setMotivo(e.target.value.slice(0, 300))}
          className={ESTILO_CAMPO}
        />
      </Campo>

      {llegadaPrevia ? (
        <div role="alert" className="rounded bg-amber-900/50 px-3 py-2 text-sm text-amber-100">
          <p>
            Ya hay una llegada confirmada:{' '}
            <strong>{formatearFechaHora(llegadaPrevia.ata_confirmada_actual)}</strong>. ¿La
            reemplaza por la nueva?
          </p>
          <button
            type="button"
            onClick={() => ejecutar.mutate('reemplazar')}
            className="mt-2 rounded bg-white px-3 py-1 text-sm font-semibold text-slate-900"
          >
            Reemplazar la llegada
          </button>
        </div>
      ) : recepcionCorta ? (
        <div role="alert" className="rounded bg-amber-900/50 px-3 py-2 text-sm text-amber-100">
          <p>
            Lo recibido no llega al mínimo conforme (
            {formatearCantidad(recepcionCorta.minimo_conforme, pedido.unidad_medida)} de{' '}
            {formatearCantidad(recepcionCorta.cantidad_pedida, pedido.unidad_medida)}): el pedido no
            avanza. Si el resto no va a llegar, puede cerrarlo con la recepción parcial.
          </p>
          <button
            type="button"
            onClick={() => ejecutar.mutate('parcial')}
            className="mt-2 rounded bg-white px-3 py-1 text-sm font-semibold text-slate-900"
          >
            Cerrar con recepción parcial
          </button>
        </div>
      ) : (
        ejecutar.isError && (
          <p role="alert" className="rounded bg-red-900/60 px-3 py-2 text-sm text-red-100">
            {mensajeDeError(ejecutar.error)}
          </p>
        )
      )}

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={!listo}
          className="rounded bg-white px-4 py-1.5 text-sm font-semibold text-slate-900 hover:bg-slate-200 disabled:opacity-50"
        >
          {ejecutar.isPending ? 'Guardando…' : 'Confirmar'}
        </button>
        <button type="button" onClick={onListo} className="text-sm text-slate-300 underline">
          Cancelar
        </button>
      </div>
    </form>
  )
}

const ESTILO_CAMPO =
  'mt-0.5 w-full rounded bg-panel-cabecera px-2 py-1 text-sm text-white [color-scheme:dark]'

function Campo({
  etiqueta,
  ayuda,
  children,
}: {
  etiqueta: string
  ayuda?: string
  children: ReactNode
}) {
  return (
    <label className="block text-xs text-slate-300">
      {etiqueta}
      {children}
      {ayuda && <span className="mt-0.5 block text-slate-500">{ayuda}</span>}
    </label>
  )
}
