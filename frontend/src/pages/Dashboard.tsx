import { useState } from 'react'
import { Link } from 'react-router-dom'

import { esPantallaPlanta, puedeVerBandeja } from '@/auth/permisos'
import { useSesion } from '@/auth/useSesion'
import { EstadoShipsGo } from '@/components/EstadoShipsGo'
import { CintaKpis } from '@/components/CintaKpis'
import { MapaBase } from '@/components/MapaBase'
import { MenuConfiguracion } from '@/components/MenuConfiguracion'
import { PanelPedidos } from '@/components/PanelPedidos'
import { ProximosArribos } from '@/components/ProximosArribos'
import { useBandejaArribos } from '@/hooks/usePedidos'
import { FILTROS_VACIOS, type FiltrosPanel } from '@/utils/filtros'

/**
 * Encuadres del Figma: el Caribe y Centroamérica, con Costa Rica abajo a la
 * izquierda. El aéreo mira un poco más al norte, por donde entran las rutas
 * desde Estados Unidos.
 */
const MARITIMO: [number, number] = [16, -77]
const AEREO: [number, number] = [17, -78]

/**
 * El botón de la bandeja (`US-48`), con el diseño de `figma/Arribos_Pendientes.png`:
 * el pin con el ancla y el texto, con el color del botón «Configuración».
 *
 * El diseño no trae número, y el criterio de `US-48` pide un contador visible:
 * va en una burbuja sobre la esquina, **solo cuando hay pendientes**. En cero
 * el botón queda tal cual el diseño. El número va también en el nombre
 * accesible, porque la burbuja sola no se lee.
 */
function AvisoBandeja() {
  const { data } = useBandejaArribos()
  const pendientes = data?.total ?? 0
  const lectura = !data
    ? ''
    : pendientes === 0
      ? ' (ninguno)'
      : ` (${pendientes} ${pendientes === 1 ? 'pendiente' : 'pendientes'})`
  return (
    <Link
      to="/bandeja"
      aria-label={`Arribos pendientes${lectura}`}
      className="group relative inline-flex items-center gap-2 rounded-lg bg-panel-cabecera py-1.5 pl-2.5 pr-3.5 text-sm text-slate-50 hover:bg-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-marca-400"
    >
      <IconoPinAncla />
      Arribos pendientes
      {pendientes > 0 && (
        <span
          aria-hidden="true"
          className="absolute -right-2 -top-2 min-w-[1.375rem] rounded-full bg-estado-destino px-1.5 text-center text-xs font-semibold leading-[1.375rem] text-white ring-2 ring-panel-fondo"
        >
          {pendientes}
        </span>
      )}
    </Link>
  )
}

/** El pin de ubicación con un ancla del diseño: llegada a puerto. */
function IconoPinAncla() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 32" className="h-6 w-[1.125rem] shrink-0">
      <path
        d="M12 1C6 1 1.5 5.6 1.5 11.3c0 4 2.2 8.3 4.6 12.1L12 31l5.9-7.6c2.4-3.8 4.6-8.1 4.6-12.1C22.5 5.6 18 1 12 1z"
        fill="currentColor"
      />
      <circle cx="12" cy="11" r="7.2" className="fill-panel-cabecera group-hover:fill-slate-600" />
      <g
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="12" cy="6.6" r="1.3" />
        <path d="M12 7.9v7.6M9.6 9.8h4.8M7.8 12.2c.5 2.2 2.1 3.4 4.2 3.4s3.7-1.2 4.2-3.4" />
        <path d="M7.1 13.3l.7-1.1 1.1.7M16.9 13.3l-.7-1.1-1.1.7" />
      </g>
    </svg>
  )
}

/**
 * Panel de control (Figma «Dashboard Principal», aprobado el 06/10): mapa
 * marítimo a la izquierda, aéreo a la derecha y, al centro, KPIs, próximos
 * arribos y la grilla. En pantallas angostas las tres columnas se apilan con
 * la grilla primero, que es lo que se consulta a diario.
 *
 * Llega por partes: la grilla (`US-19`) ya está; los KPIs (`US-22`), los
 * próximos arribos (`US-28`), los filtros (`US-21`) y la frescura (`US-23`) se
 * suman en el Sprint 6, y los mapas en el Sprint 7.
 */
export default function Dashboard() {
  const sesion = useSesion()
  // Un solo juego de filtros para los tres bloques (`US-21`): KPIs, arribos y
  // grilla muestran siempre el mismo subconjunto. Los mapas lo usarán en el
  // Sprint 7.
  const [filtros, setFiltros] = useState<FiltrosPanel>(FILTROS_VACIOS)
  const [versionFiltros, setVersionFiltros] = useState(0)
  // La pantalla de planta (`US-43`): el mismo panel con la grilla simple y sin
  // enlaces de gestión, porque queda desatendida y su rol solo lee.
  const planta = esPantallaPlanta(sesion?.usuario.rol)

  function cambiarFiltros(cambios: Partial<FiltrosPanel>) {
    setFiltros((actuales) => ({ ...actuales, ...cambios }))
  }

  function limpiarFiltros() {
    setFiltros(FILTROS_VACIOS)
    setVersionFiltros((v) => v + 1)
  }

  return (
    <div className="min-h-screen bg-panel-fondo text-slate-100">
      <header className="grid grid-cols-1 items-start gap-3 px-4 pb-4 pt-3 lg:grid-cols-[1fr_auto_1fr]">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-slate-300">
          {sesion && (
            <>
              <MenuConfiguracion sesion={sesion} />
              {/* Fuera del menú: es un aviso, y escondido dejaría de avisar (`US-48`). */}
              {puedeVerBandeja(sesion.usuario.rol) && <AvisoBandeja />}
            </>
          )}
        </div>

        <div className="text-center">
          <h1 className="text-2xl font-bold sm:text-3xl">
            Panel de Control Logístico - Compras en Tránsito
          </h1>
          <p className="mt-1 text-lg text-slate-300">Tracking aéreo-marítimo</p>
        </div>

        <div className="flex lg:justify-end">
          <EstadoShipsGo />
        </div>
      </header>

      <main className="grid grid-cols-1 gap-6 px-4 pb-12 xl:grid-cols-[1fr_minmax(0,1fr)_1fr]">
        <div className="order-2 xl:order-none">
          <MapaBase titulo="Mapa Marítimo" centro={MARITIMO} zoom={4} />
        </div>
        <div className="order-1 flex min-w-0 flex-col gap-5 xl:order-none">
          <CintaKpis filtros={filtros} />
          <ProximosArribos filtros={filtros} />
          <PanelPedidos
            filtros={filtros}
            onCambioFiltros={cambiarFiltros}
            onLimpiarFiltros={limpiarFiltros}
            versionFiltros={versionFiltros}
            vista={planta ? 'simple' : 'completa'}
          />
        </div>
        <div className="order-3 xl:order-none">
          <MapaBase titulo="Mapa Aéreo" centro={AEREO} zoom={4} />
        </div>
      </main>
    </div>
  )
}
