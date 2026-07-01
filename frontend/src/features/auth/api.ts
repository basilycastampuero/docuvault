import { apiClient, unwrap } from '@/lib/api-client'
import type { Envelope } from '@/shared/types'
import type { UserProfile } from '@/shared/types'
import type { LoginCredentials, TokenPair, RefreshResponse } from './types'

// POST /auth/login/ → { data: { access, refresh, user }, meta: {} }
export async function login(credentials: LoginCredentials): Promise<TokenPair> {
  const response = await apiClient.post<Envelope<TokenPair>>('/auth/login/', credentials)
  return unwrap(response)
}

// POST /auth/logout/ → {} (requiere refresh token en body para blacklistear)
export async function logout(refreshToken: string): Promise<void> {
  await apiClient.post('/auth/logout/', { refresh: refreshToken })
}

// POST /auth/refresh/ → { data: { access, refresh }, meta: {} }
export async function refreshToken(refresh: string): Promise<RefreshResponse> {
  const response = await apiClient.post<Envelope<RefreshResponse>>('/auth/refresh/', { refresh })
  return unwrap(response)
}

// GET /auth/me/ → { data: UserProfile, meta: {} }
export async function getMe(): Promise<UserProfile> {
  const response = await apiClient.get<Envelope<UserProfile>>('/auth/me/')
  return unwrap(response)
}
