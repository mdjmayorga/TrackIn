import { useState } from 'react'
import { Link } from 'react-router-dom'

import { puedeCargar, puedeVerBandeja } from '@/auth/permisos'
import { useSesion } from '@/auth/useSesion'
import { EstadoShipsGo } from '@/components/EstadoShipsGo'
import { CintaKpis } from '@/components/CintaKpis'
import { MapaBase } from '@/components/MapaBase'
import { PanelPedidos } from '@/components/PanelPedidos'
import { ProximosArribos } from '@/components/ProximosArribos'
import { useBandejaArribos } from '@/hooks/usePedidos'
import { cerrarSesion } from '@/services/auth'
import { FILTROS_VACIOS, type FiltrosPanel } from '@/utils/filtros'

/**
 * Encuadres del Figma: el Caribe y Centroamérica, con Costa Rica abajo a la
 * izquierda. El aéreo mira un poco más al norte, por donde entran las rutas
 * desde Estados Unidos.
 */
const MARITIMO: [number, number] = [16, -77]
const AEREO: [number, number] = [17, -78]

/**
 * El contador de la bandeja (`US-48`): cuántos pedidos llegaron y esperan el
 * paso a aduana. Resalta solo cuando hay pendientes; en cero queda el enlace,
 * sin llamar la atención.
 */
function AvisoBandeja() {
  const { data } = useBandejaArribos()
  const pendientes = data?.total ?? 0
  return (
    <p className="mt-1">
      <Link
        to="/bandeja"
        className="inline-flex items-center gap-2 text-marca-300 underline hover:text-marca-200"
      >
        Arribos pendientes{' '}
        <span
          className={`rounded-full px-2 text-xs font-semibold no-underline ${
            pendientes > 0 ? 'bg-estado-destino text-white' : 'bg-panel-cabecera text-slate-400'
          }`}
        >
          {data ? pendientes : '…'}
        </span>
      </Link>
    </p>
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
        <div className="text-sm text-slate-300">
          {sesion && (
            <>
              <p>
                {sesion.usuario.nombre_completo}{' '}
                <span className="text-slate-500">{sesion.usuario.rol}</span>
              </p>
              <p className="flex gap-3">
                <button
                  type="button"
                  onClick={() => void cerrarSesion()}
                  className="text-marca-300 underline hover:text-marca-200"
                >
                  Cerrar sesión
                </button>
                <Link to="/cargas" className="text-marca-300 underline hover:text-marca-200">
                  {puedeCargar(sesion.usuario.rol) ? 'Cargar Z-tracking' : 'Cargas del Z-tracking'}
                </Link>
              </p>
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
          />
        </div>
        <div className="order-3 xl:order-none">
          <MapaBase titulo="Mapa Aéreo" centro={AEREO} zoom={4} />
        </div>
      </main>
    </div>
  )
}
