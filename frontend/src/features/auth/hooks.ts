import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from './store'
import { login as loginApi, logout as logoutApi, getMe } from './api'
import type { LoginCredentials } from './types'
import type { ApiError } from '@/shared/types'

// ─── useLogin ─────────────────────────────────────────────────────────────────

export function useLogin() {
  const navigate = useNavigate()
  const setAccessToken = useAuthStore((s) => s.setAccessToken)
  const setUser = useAuthStore((s) => s.setUser)

  return useMutation<void, ApiError, LoginCredentials>({
    meta: { suppressGlobalToast: true },
    mutationFn: async (credentials: LoginCredentials) => {
      const tokens = await loginApi(credentials)
      // 1. Guardar access token en memoria (Zustand)
      setAccessToken(tokens.access)
      // El refresh token ya no llega al JS — viaja como cookie HttpOnly
      // sv_refresh seteada por el backend en la misma respuesta (Fase 6.1).
      // 2. Obtener perfil del usuario y guardarlo en el store
      const user = await getMe()
      setUser(user)
    },
    onSuccess: () => {
      navigate('/')
    },
  })
}

// ─── useLogout ────────────────────────────────────────────────────────────────

export function useLogout() {
  const navigate = useNavigate()
  const logout = useAuthStore((s) => s.logout)

  return useMutation<void, ApiError, void>({
    mutationFn: async () => {
      // El refresh token viaja en la cookie HttpOnly sv_refresh — el backend
      // la lee solo. Best-effort: no bloquear logout si el backend falla.
      try {
        await logoutApi()
      } catch {
        // Ignorar errores del logout remoto — la sesión local siempre se limpia
      }
    },
    onSettled: () => {
      logout()
      navigate('/login')
    },
  })
}

// ─── useMe ────────────────────────────────────────────────────────────────────

export function useMe() {
  const accessToken = useAuthStore((s) => s.accessToken)

  return useQuery({
    queryKey: ['auth', 'me'],
    queryFn: getMe,
    enabled: !!accessToken,
    staleTime: 1000 * 60 * 10, // 10 minutos — el perfil cambia poco
  })
}
