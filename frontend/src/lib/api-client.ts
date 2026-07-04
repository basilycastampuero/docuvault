import axios from 'axios'
import type { AxiosInstance } from 'axios'
import type {
  Envelope,
  PaginatedEnvelope,
  PaginatedMeta,
  ApiErrorBody,
} from '@/shared/types'
import { ApiError } from '@/shared/types'
import { getCookie, CSRF_COOKIE_NAME, CSRF_HEADER_NAME } from '@/lib/cookies'

// No hay circular dependency real: auth/store no importa api-client.
// Se puede importar directamente. El import era innecesariamente lazy.
import { useAuthStore } from '@/features/auth/store'

// ─── Axios instance ────────────────────────────────────────────────────────────

const baseURL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  'http://localhost:8000/api/v1'

// withCredentials: true — necesario para que el navegador mande (y reciba)
// las cookies sv_refresh (HttpOnly) y sv_csrf en cada request (Fase 6.1).
export const apiClient: AxiosInstance = axios.create({ baseURL, withCredentials: true })

// Rutas que requieren el header CSRF double-submit (leen/mutan la cookie
// sv_refresh en el backend). Ver phase-plan §6.1, decisión 2.
const CSRF_PROTECTED_PATHS = ['/auth/refresh/', '/auth/logout/']

// ─── REQUEST INTERCEPTOR ───────────────────────────────────────────────────────
// Lee el access token del store de Zustand (memoria) en cada request, y
// adjunta el header CSRF double-submit en las rutas que lo requieren.

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  if (config.url && CSRF_PROTECTED_PATHS.some((path) => config.url!.includes(path))) {
    const csrfToken = getCookie(CSRF_COOKIE_NAME)
    if (csrfToken) {
      config.headers[CSRF_HEADER_NAME] = csrfToken
    }
  }
  return config
})

// ─── RESPONSE INTERCEPTOR — cola de refresh ───────────────────────────────────
// Si N requests reciben 401 a la vez, solo se dispara UN refresh.
// Las demás quedan en cola y se resuelven cuando el refresh termina.

let isRefreshing = false
let failedQueue: Array<{
  resolve: (token: string) => void
  reject: (err: unknown) => void
}> = []

function processQueue(error: unknown, token: string | null): void {
  failedQueue.forEach((p) => (error ? p.reject(error) : p.resolve(token!)))
  failedQueue = []
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (!axios.isAxiosError(error)) {
      return Promise.reject(parseApiError(error))
    }

    const originalRequest = error.config as typeof error.config & {
      _retry?: boolean
    }

    // Solo interceptar 401 que NO sea ya un retry
    if (error.response?.status !== 401 || originalRequest?._retry) {
      return Promise.reject(parseApiError(error))
    }

    // Si ya hay un refresh en vuelo, encolar esta request
    if (isRefreshing) {
      return new Promise<string>((resolve, reject) => {
        failedQueue.push({ resolve, reject })
      }).then((token) => {
        if (originalRequest) {
          originalRequest.headers = originalRequest.headers ?? {}
          originalRequest.headers['Authorization'] = `Bearer ${token}`
        }
        return apiClient(originalRequest!)
      })
    }

    // Iniciar el refresh
    if (originalRequest) {
      originalRequest._retry = true
    }
    isRefreshing = true

    try {
      // Llamada directa con axios base (no apiClient) para no entrar en loop
      // de interceptors. El refresh token viaja solo por la cookie HttpOnly
      // sv_refresh — el navegador la adjunta solo porque withCredentials es
      // true; el JS nunca la lee. El header CSRF sí se arma a mano acá.
      const { data: envelope } = await axios.post<{ data: { access: string } }>(
        `${baseURL}/auth/refresh/`,
        {},
        {
          withCredentials: true,
          headers: { [CSRF_HEADER_NAME]: getCookie(CSRF_COOKIE_NAME) ?? '' },
        },
      )

      const newAccess = envelope.data.access
      useAuthStore.getState().setAccessToken(newAccess)
      apiClient.defaults.headers.common['Authorization'] = `Bearer ${newAccess}`

      processQueue(null, newAccess)

      if (originalRequest) {
        originalRequest.headers = originalRequest.headers ?? {}
        originalRequest.headers['Authorization'] = `Bearer ${newAccess}`
        return apiClient(originalRequest)
      }

      // Refresh succeeded pero no hay request original que reintentar.
      // El contrato del interceptor es rechazar; nunca resolver con undefined.
      return Promise.reject(parseApiError(error))
    } catch (refreshError) {
      processQueue(refreshError, null)
      useAuthStore.getState().logout()
      window.location.href = '/login'
      return Promise.reject(refreshError)
    } finally {
      isRefreshing = false
    }
  },
)

// ─── Helpers de unwrap ─────────────────────────────────────────────────────────

export function unwrap<T>(response: { data: Envelope<T> }): T {
  return response.data.data
}

export function unwrapPaginated<T>(response: {
  data: PaginatedEnvelope<T>
}): { items: T[]; meta: PaginatedMeta } {
  return { items: response.data.data, meta: response.data.meta }
}

// ─── Parseo de errores del backend ────────────────────────────────────────────

export function parseApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status ?? 0
    const body = error.response?.data as ApiErrorBody | undefined

    if (body?.error) {
      return new ApiError(
        body.error.message,
        body.error.code,
        status,
        body.error.details ?? {},
      )
    }

    return new ApiError(
      error.message || 'Unexpected server error',
      'NETWORK_ERROR',
      status,
    )
  }

  if (error instanceof Error) {
    return new ApiError(error.message, 'CLIENT_ERROR', 0)
  }

  return new ApiError('Unknown error', 'UNKNOWN', 0)
}
