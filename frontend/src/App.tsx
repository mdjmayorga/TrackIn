import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { type ReactNode, Suspense, lazy } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthProvider } from '@/auth/AuthContext'
import { RutaProtegida } from '@/auth/RutaProtegida'
import Login from '@/pages/Login'

// Cada pantalla protegida se descarga cuando se abre, no con el login: Leaflet
// y las tres pantallas juntas pasaban de los 500 kB que Vite marca como límite
// (15/10). El login, que es la primera que se ve, va en el paquete inicial.
const Dashboard = lazy(() => import('@/pages/Dashboard'))
const Cargas = lazy(() => import('@/pages/Cargas'))
const DetallePedido = lazy(() => import('@/pages/DetallePedido'))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Los datos de tracking cambian seguido; 30 s es un punto de partida
      // razonable que se ajustará por recurso en sprints posteriores.
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
})

function Protegida({ children }: { children: ReactNode }) {
  return (
    <RutaProtegida>
      <Suspense
        fallback={<p className="min-h-screen bg-panel-fondo p-8 text-slate-400">Cargando…</p>}
      >
        {children}
      </Suspense>
    </RutaProtegida>
  )
}

/** Las rutas, separadas del router para poder probarlas con uno en memoria. */
export function Rutas() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <Protegida>
            <Dashboard />
          </Protegida>
        }
      />
      <Route
        path="/cargas"
        element={
          <Protegida>
            <Cargas />
          </Protegida>
        }
      />
      <Route
        path="/pedidos/:id"
        element={
          <Protegida>
            <DetallePedido />
          </Protegida>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Rutas />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
