import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthProvider } from '@/auth/AuthContext'
import { RutaProtegida } from '@/auth/RutaProtegida'
import Cargas from '@/pages/Cargas'
import Dashboard from '@/pages/Dashboard'
import Login from '@/pages/Login'

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

/** Las rutas, separadas del router para poder probarlas con uno en memoria. */
export function Rutas() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <RutaProtegida>
            <Dashboard />
          </RutaProtegida>
        }
      />
      <Route
        path="/cargas"
        element={
          <RutaProtegida>
            <Cargas />
          </RutaProtegida>
        }
      />
      {/* Sprint 6 y 7: /pedidos/:id */}
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
