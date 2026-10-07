import { useSesion } from '@/auth/useSesion'
import { EstadoShipsGo } from '@/components/EstadoShipsGo'
import { CintaKpis } from '@/components/CintaKpis'
import { MapaBase } from '@/components/MapaBase'
import { PanelPedidos } from '@/components/PanelPedidos'
import { ProximosArribos } from '@/components/ProximosArribos'
import { cerrarSesion } from '@/services/auth'

/**
 * Encuadres del Figma: el Caribe y Centroamérica, con Costa Rica abajo a la
 * izquierda. El aéreo mira un poco más al norte, por donde entran las rutas
 * desde Estados Unidos.
 */
const MARITIMO: [number, number] = [16, -77]
const AEREO: [number, number] = [17, -78]

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
              <button
                type="button"
                onClick={() => void cerrarSesion()}
                className="text-marca-300 underline hover:text-marca-200"
              >
                Cerrar sesión
              </button>
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
          <CintaKpis />
          <ProximosArribos />
          <PanelPedidos />
        </div>
        <div className="order-3 xl:order-none">
          <MapaBase titulo="Mapa Aéreo" centro={AEREO} zoom={4} />
        </div>
      </main>
    </div>
  )
}
