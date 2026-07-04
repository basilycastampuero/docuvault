import { describe, test, expect, beforeEach, vi } from 'vitest'
import { useAuthStore } from '../store'
import type { UserProfile } from '@/shared/types'

// ─── Fixture ──────────────────────────────────────────────────────────────────

const MOCK_USER: UserProfile = {
  id: 'user-uuid-1',
  email: 'alice@example.com',
  first_name: 'Alice',
  last_name: 'Smith',
  role: 'editor',
  organization_id: 'org-uuid-1',
  organization_name: 'Acme Corp',
  is_active: true,
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('useAuthStore', () => {
  beforeEach(() => {
    // Reset Zustand store state between tests (no side-effects from other tests)
    useAuthStore.setState({ accessToken: null, user: null })
    localStorage.clear()
  })

  // ── Initial state ───────────────────────────────────────────────────────────

  test('initial state: accessToken is null', () => {
    /**Should start with no access token in memory */
    const { accessToken } = useAuthStore.getState()
    expect(accessToken).toBeNull()
  })

  test('initial state: user is null', () => {
    /**Should start with no user profile in memory */
    const { user } = useAuthStore.getState()
    expect(user).toBeNull()
  })

  // ── setAccessToken ──────────────────────────────────────────────────────────

  test('setAccessToken: updates accessToken in memory', () => {
    /**Should store the token in Zustand state (in-memory, not localStorage) */
    const { setAccessToken } = useAuthStore.getState()
    setAccessToken('my-access-token')
    expect(useAuthStore.getState().accessToken).toBe('my-access-token')
  })

  test('setAccessToken: replaces previous token', () => {
    /**Should overwrite the old token with the new one */
    const { setAccessToken } = useAuthStore.getState()
    setAccessToken('token-v1')
    setAccessToken('token-v2')
    expect(useAuthStore.getState().accessToken).toBe('token-v2')
  })

  // ── setUser ─────────────────────────────────────────────────────────────────

  test('setUser: updates user profile in store', () => {
    /**Should persist the user object exactly as provided */
    const { setUser } = useAuthStore.getState()
    setUser(MOCK_USER)
    expect(useAuthStore.getState().user).toEqual(MOCK_USER)
  })

  test('setUser: does not touch accessToken', () => {
    /**Should leave accessToken unchanged when only updating the user */
    const { setAccessToken, setUser } = useAuthStore.getState()
    setAccessToken('existing-token')
    setUser(MOCK_USER)
    expect(useAuthStore.getState().accessToken).toBe('existing-token')
  })

  // ── logout ──────────────────────────────────────────────────────────────────

  test('logout: clears accessToken in memory', () => {
    /**Should nullify the in-memory access token */
    const { setAccessToken, logout } = useAuthStore.getState()
    setAccessToken('some-token')
    logout()
    expect(useAuthStore.getState().accessToken).toBeNull()
  })

  test('logout: clears user in memory', () => {
    /**Should nullify the in-memory user profile */
    const { setUser, logout } = useAuthStore.getState()
    setUser(MOCK_USER)
    logout()
    expect(useAuthStore.getState().user).toBeNull()
  })

  test('logout: does not touch localStorage at all (refresh token lives in an HttpOnly cookie, Phase 6.1)', () => {
    /**Should never read or write localStorage — the backend clears the sv_refresh cookie on /auth/logout/ */
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem')
    const removeItemSpy = vi.spyOn(Storage.prototype, 'removeItem')

    const { setAccessToken, logout } = useAuthStore.getState()
    setAccessToken('some-token')
    logout()

    expect(setItemSpy).not.toHaveBeenCalled()
    expect(removeItemSpy).not.toHaveBeenCalled()

    setItemSpy.mockRestore()
    removeItemSpy.mockRestore()
  })

  test('logout: is idempotent — calling twice does not throw', () => {
    /**Should be safe to call logout even when already logged out */
    const { logout } = useAuthStore.getState()
    expect(() => {
      logout()
      logout()
    }).not.toThrow()
  })

  // ── Security: accessToken isolation from localStorage ───────────────────────

  test('accessToken never goes to localStorage (stays in memory only)', () => {
    /**Critical security invariant: access token must NOT be persisted in localStorage */
    const { setAccessToken } = useAuthStore.getState()
    setAccessToken('secret-access-token')

    // Inspect every key in localStorage — none should contain the token value
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)!
      expect(localStorage.getItem(key)).not.toBe('secret-access-token')
    }
    expect(localStorage.getItem('accessToken')).toBeNull()
  })

  test('accessToken survives store re-read within same session', () => {
    /**Should be available via getState() after being set — not ephemeral */
    const { setAccessToken } = useAuthStore.getState()
    setAccessToken('persistent-within-session')
    // Re-read via getState to simulate another component reading the store
    expect(useAuthStore.getState().accessToken).toBe('persistent-within-session')
  })
})
