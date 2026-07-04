import { useEffect, useState } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '@/features/auth/store'
import { refreshToken, getMe } from '@/features/auth/api'
import { Skeleton } from '@/components/ui/skeleton'

// ─── ProtectedRoute ───────────────────────────────────────────────────────────
// Guarda las rutas autenticadas.
// Al montar: si no hay accessToken + perfil en memoria, ejecuta bootstrap
// secuencial:
//   1) refresh token (vía cookie HttpOnly sv_refresh, invisible a JS) → nuevo access token
//   2) getMe() → rehidrata el perfil de usuario
// Como la cookie no es legible desde JS (Fase 6.1), ya no hay forma de saber
// de antemano si existe una sesión — se intenta el refresh siempre; si no hay
// cookie válida, el backend responde 401 y el catch hace logout().
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
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setRestorationAttempted(true)
      return
    }

    // No hay forma de inspeccionar la cookie sv_refresh desde JS (HttpOnly) —
    // se intenta el refresh siempre. Si no hay cookie válida, el backend
    // responde 401 y el catch de abajo limpia la sesión.
    // Bootstrap secuencial: 1) refrescar token, 2) rehidratar perfil.
    setIsRestoring(true)
    refreshToken()
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
