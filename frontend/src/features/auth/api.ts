import { apiClient, unwrap } from '@/lib/api-client'
import type { Envelope } from '@/shared/types'
import type { UserProfile } from '@/shared/types'
import type { LoginCredentials, TokenPair, RefreshResponse } from './types'

// POST /auth/login/ → { data: { access, refresh, user }, meta: {} }
export async function login(credentials: LoginCredentials): Promise<TokenPair> {
  const response = await apiClient.post<Envelope<TokenPair>>('/auth/login/', credentials)
  return unwrap(response)
}

// POST /auth/logout/ → 204 (el refresh viaja en la cookie HttpOnly sv_refresh;
// el header X-CSRF-Token lo adjunta automáticamente el interceptor de apiClient)
export async function logout(): Promise<void> {
  await apiClient.post('/auth/logout/', {})
}

// POST /auth/refresh/ → { data: { access }, meta: {} } (refresh vía cookie)
export async function refreshToken(): Promise<RefreshResponse> {
  const response = await apiClient.post<Envelope<RefreshResponse>>('/auth/refresh/', {})
  return unwrap(response)
}

// GET /auth/me/ → { data: UserProfile, meta: {} }
export async function getMe(): Promise<UserProfile> {
  const response = await apiClient.get<Envelope<UserProfile>>('/auth/me/')
  return unwrap(response)
}
