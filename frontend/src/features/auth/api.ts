import { apiClient, unwrap } from '@/lib/api-client'
import type { Envelope } from '@/shared/types'
import type { UserProfile } from '@/shared/types'
import type { LoginCredentials, TokenPair, RefreshResponse } from './types'

// POST /auth/login/ → { access, refresh }
export async function login(credentials: LoginCredentials): Promise<TokenPair> {
  const response = await apiClient.post<TokenPair>('/auth/login/', credentials)
  return response.data
}

// POST /auth/logout/ → {} (requiere refresh token en body para blacklistear)
export async function logout(refreshToken: string): Promise<void> {
  await apiClient.post('/auth/logout/', { refresh: refreshToken })
}

// POST /auth/refresh/ → { access }
export async function refreshToken(refresh: string): Promise<RefreshResponse> {
  const response = await apiClient.post<RefreshResponse>('/auth/refresh/', { refresh })
  return response.data
}

// GET /auth/me/ → { data: UserProfile, meta: {} }
export async function getMe(): Promise<UserProfile> {
  const response = await apiClient.get<Envelope<UserProfile>>('/auth/me/')
  return unwrap(response)
}
