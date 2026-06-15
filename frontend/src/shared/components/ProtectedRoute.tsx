import { useEffect, useState } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '@/features/auth/store'
import { refreshToken, getMe } from '@/features/auth/api'
import { Skeleton } from '@/components/ui/skeleton'

// ─── ProtectedRoute ───────────────────────────────────────────────────────────
// Guarda las rutas autenticadas.
// Al montar: si no hay accessToken + perfil en memoria pero sí hay
// refreshToken en localStorage, ejecuta bootstrap secuencial:
//   1) refresh token → obtiene nuevo access token
//   2) getMe() → rehidrata el perfil de usuario
// Esto evita que el estado quede con token pero sin perfil tras recargar.

export function ProtectedRoute() {
  const accessToken = useAuthStore((s) => s.accessToken)
  const setAccessToken = useAuthStore((s) => s.setAccessToken)
  const setUser = useAuthStore((s) => s.setUser)
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  const [isRestoring, setIsRestoring] = useState(false)
  const [restorationAttempted, setRestorationAttempted] = useState(false)

  useEffect(() => {
    // Si ya hay token Y perfil en memoria, no hay nada que restaurar.
    if (accessToken && user) {
      setRestorationAttempted(true)
      return
    }

    const storedRefresh = localStorage.getItem('refreshToken')
    if (!storedRefresh) {
      setRestorationAttempted(true)
      return
    }

    // Bootstrap secuencial: 1) refrescar token, 2) rehidratar perfil.
    setIsRestoring(true)
    refreshToken(storedRefresh)
      .then(async ({ access }) => {
        setAccessToken(access)
        // El interceptor de request lee el token del store en getMe().
        const profile = await getMe()
        setUser(profile)
      })
      .catch(() => {
        // Token inválido o perfil inaccesible — sesión inconsistente: logout.
        logout()
      })
      .finally(() => {
        setIsRestoring(false)
        setRestorationAttempted(true)
      })
    // Solo ejecutar al montar — las dependencias del store no deben re-disparar el efecto.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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

  if (!accessToken) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
