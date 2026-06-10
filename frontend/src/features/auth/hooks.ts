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
    mutationFn: async (credentials: LoginCredentials) => {
      const tokens = await loginApi(credentials)
      // 1. Guardar access token en memoria (Zustand)
      setAccessToken(tokens.access)
      // 2. Guardar refresh token en localStorage (persistencia entre recargas)
      localStorage.setItem('refreshToken', tokens.refresh)
      // 3. Obtener perfil del usuario y guardarlo en el store
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
      const refreshToken = localStorage.getItem('refreshToken')
      if (refreshToken) {
        // Best-effort: no bloquear logout si el backend falla
        try {
          await logoutApi(refreshToken)
        } catch {
          // Ignorar errores del logout remoto — la sesión local siempre se limpia
        }
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
