import { useEffect, useState } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '@/features/auth/store'
import { refreshToken } from '@/features/auth/api'
import { Skeleton } from '@/components/ui/skeleton'

// ─── ProtectedRoute ───────────────────────────────────────────────────────────
// Guarda las rutas autenticadas.
// Al montar: si no hay accessToken en memoria pero sí hay refreshToken en
// localStorage, intenta un refresh silencioso para restaurar la sesión
// (p.ej. tras recargar la página).

export function ProtectedRoute() {
  const accessToken = useAuthStore((s) => s.accessToken)
  const setAccessToken = useAuthStore((s) => s.setAccessToken)
  const logout = useAuthStore((s) => s.logout)

  const [isRestoring, setIsRestoring] = useState(false)
  const [restorationAttempted, setRestorationAttempted] = useState(false)

  useEffect(() => {
    // Solo intentar restauración si no hay token en memoria
    if (accessToken) {
      setRestorationAttempted(true)
      return
    }

    const storedRefresh = localStorage.getItem('refreshToken')
    if (!storedRefresh) {
      setRestorationAttempted(true)
      return
    }

    // Hay refresh token guardado — intentar recuperar la sesión
    setIsRestoring(true)
    refreshToken(storedRefresh)
      .then(({ access }) => {
        setAccessToken(access)
      })
      .catch(() => {
        // Refresh inválido o expirado — limpiar estado
        logout()
      })
      .finally(() => {
        setIsRestoring(false)
        setRestorationAttempted(true)
      })
  }, []) // Solo al montar

  // Mientras se intenta restaurar la sesión, mostrar pantalla de carga
  if (isRestoring || !restorationAttempted) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="space-y-3 w-64">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      </div>
    )
  }

  // Sin token tras intentar restaurar → redirigir al login
  if (!accessToken) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
