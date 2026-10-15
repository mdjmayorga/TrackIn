/**
 * «Filtros de consulta» del Figma (`US-21`): tres campos de texto —Orden de
 * compra, Posición, Material— y tres listas —Vía, Etapa, Cumplimiento—.
 *
 * Los campos de texto esperan a que se deje de escribir (`ESPERA_MS`) antes de
 * avisar: sin eso, «4500016171» serían diez consultas, y la última podría
 * llegar antes que una anterior. Las listas avisan al instante.
 *
 * Para limpiar, quien la usa cambia su `key`: los campos vuelven a nacer vacíos.
 */

import { useEffect, useRef, useState } from 'react'

import { ETAPAS, type EtapaVisible } from '@/components/estados'
import type { Via } from '@/types/api'
import { type CumplimientoFiltro, type FiltrosPanel, soloDigitos } from '@/utils/filtros'

/** Con 300 ms la vista responde bien dentro del segundo de RNF-02. */
export const ESPERA_MS = 300

/**
 * Solo las dos vías del alcance. `TERRESTRE` existe en el modelo para reconocer
 * el valor del Z-tracking, pero no se rastrea ni llega a la base (14/10).
 */
const VIAS: Array<[Via, string]> = [
  ['MARITIMO', 'Marítimo'],
  ['AEREO', 'Aéreo'],
]

const ORDEN_ETAPAS: EtapaVisible[] = [
  'SIN_TRACKING',
  'EN_ORIGEN',
  'EN_TRANSITO',
  'EN_DESTINO',
  'EN_PROCESO_ADUANAL',
  'RECIBIDO_EN_PLANTA',
  'CERRADO',
  'CANCELADO',
]

const CUMPLIMIENTOS: Array<[CumplimientoFiltro, string]> = [
  ['A_TIEMPO', 'A Tiempo'],
  ['EN_RIESGO', 'En Riesgo'],
  ['RETRASADO', 'Retrasado'],
  ['SIN_PROYECCION', 'Sin proyección (–)'],
]

interface CampoTextoProps {
  id: string
  etiqueta: string
  placeholder: string
  valorInicial: string
  onCambio: (valor: string) => void
  limpiar?: (valor: string) => string
  numerico?: boolean
}

function CampoTexto({
  id,
  etiqueta,
  placeholder,
  valorInicial,
  onCambio,
  limpiar = (v) => v,
  numerico = false,
}: CampoTextoProps) {
  const [valor, setValor] = useState(valorInicial)
  // El último valor avisado: evita avisar al montar y al repetir lo mismo.
  const avisado = useRef(valorInicial)
  const aviso = useRef(onCambio)

  useEffect(() => {
    aviso.current = onCambio
  }, [onCambio])

  useEffect(() => {
    if (valor === avisado.current) return
    const espera = setTimeout(() => {
      avisado.current = valor
      aviso.current(valor)
    }, ESPERA_MS)
    return () => clearTimeout(espera)
  }, [valor])

  return (
    <label
      htmlFor={id}
      className="flex min-w-0 flex-col rounded-lg bg-panel-cabecera px-2 py-1 text-[11px] text-slate-200"
    >
      {etiqueta}:
      <input
        id={id}
        value={valor}
        placeholder={placeholder}
        inputMode={numerico ? 'numeric' : undefined}
        autoComplete="off"
        onChange={(e) => setValor(limpiar(e.target.value))}
        className="mt-0.5 w-full bg-transparent text-xs text-white placeholder:text-slate-400 focus:outline-none"
      />
    </label>
  )
}

interface ListaProps<T extends string> {
  etiqueta: string
  valor: T | ''
  opciones: Array<[T, string]>
  onCambio: (valor: T | '') => void
}

function Lista<T extends string>({ etiqueta, valor, opciones, onCambio }: ListaProps<T>) {
  return (
    <select
      aria-label={etiqueta}
      value={valor}
      onChange={(e) => onCambio(e.target.value as T | '')}
      className={`h-6 rounded bg-panel-cabecera px-1.5 text-xs focus:outline-none focus-visible:ring-1 focus-visible:ring-marca-400 ${
        valor ? 'text-white' : 'text-slate-300'
      }`}
    >
      {/* Sin selección, la lista se rotula con su nombre, como en el Figma. */}
      <option value="">{etiqueta}</option>
      {opciones.map(([clave, texto]) => (
        <option key={clave} value={clave}>
          {texto}
        </option>
      ))}
    </select>
  )
}

export interface BarraFiltrosProps {
  filtros: FiltrosPanel
  onCambio: (cambios: Partial<FiltrosPanel>) => void
}

export function BarraFiltros({ filtros, onCambio }: BarraFiltrosProps) {
  return (
    <div className="grid grid-cols-2 gap-1.5 sm:flex sm:flex-wrap sm:items-start">
      <div className="sm:w-28">
        <CampoTexto
          id="filtro-oc"
          etiqueta="Orden de compra"
          placeholder="4500"
          valorInicial={filtros.oc}
          numerico
          limpiar={(v) => soloDigitos(v, 10)}
          onCambio={(oc) => onCambio({ oc })}
        />
      </div>
      <div className="sm:w-20">
        <CampoTexto
          id="filtro-posicion"
          etiqueta="Posición"
          placeholder="Todos"
          valorInicial={filtros.posicion}
          numerico
          limpiar={(v) => soloDigitos(v, 6)}
          onCambio={(posicion) => onCambio({ posicion })}
        />
      </div>
      <div className="col-span-2 sm:w-32">
        <CampoTexto
          id="filtro-material"
          etiqueta="Material"
          placeholder="Buscar Material"
          valorInicial={filtros.material}
          limpiar={(v) => v.slice(0, 60)}
          onCambio={(material) => onCambio({ material })}
        />
      </div>
      <Lista
        etiqueta="Vía"
        valor={filtros.via}
        opciones={VIAS}
        onCambio={(via) => onCambio({ via })}
      />
      <Lista
        etiqueta="Etapa"
        valor={filtros.etapa}
        opciones={ORDEN_ETAPAS.map((e) => [e, ETAPAS[e].texto])}
        onCambio={(etapa) => onCambio({ etapa })}
      />
      <Lista
        etiqueta="Cumplimiento"
        valor={filtros.cumplimiento}
        opciones={CUMPLIMIENTOS}
        onCambio={(cumplimiento) => onCambio({ cumplimiento })}
      />
    </div>
  )
}
