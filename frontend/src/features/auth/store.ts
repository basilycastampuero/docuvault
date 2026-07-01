import { create } from 'zustand'
import type { UserProfile } from '@/shared/types'

interface AuthState {
  accessToken: string | null
  user: UserProfile | null
}

interface AuthActions {
  setAccessToken: (token: string) => void
  setUser: (user: UserProfile) => void
  logout: () => void
}

export type AuthStore = AuthState & AuthActions

export const useAuthStore = create<AuthStore>()((set) => ({
  // ─── State ──────────────────────────────────────────────────────────────────
  accessToken: null,
  user: null,

  // ─── Actions ────────────────────────────────────────────────────────────────
  setAccessToken: (token: string) => set({ accessToken: token }),
  setUser: (user: UserProfile) => set({ user }),
  logout: () => {
    set({ accessToken: null, user: null })
    localStorage.removeItem('refreshToken')
  },
}))
