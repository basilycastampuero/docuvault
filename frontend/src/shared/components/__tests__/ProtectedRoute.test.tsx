/**
 * Tests for ProtectedRoute — session restoration on page reload.
 *
 * Phase 6.1 note: the refresh token now travels as an HttpOnly cookie
 * (`sv_refresh`), invisible to JS. There is no longer a client-readable
 * signal (e.g. a localStorage flag) to decide *whether* to attempt a
 * restoration — the component always calls `refreshToken()` on mount when
 * there is no accessToken/user in memory, and lets the backend reject the
 * call when there is no valid session cookie.
 *
 * The component calls:
 *   - refreshToken() (from @/features/auth/api) → { access }
 *   - getMe()        (from @/features/auth/api) → UserProfile
 *
 * Both are mocked directly at the module level (not via MSW/HTTP) so each
 * test can simulate "valid cookie" vs. "no/invalid cookie" deterministically,
 * without relying on incidental network-error behavior for unmocked routes.
 *
 * Uses MemoryRouter so Navigate renders without a real browser. The Outlet
 * sentinel and a fake Login route allow us to assert what the router rendered.
 *
 * Isolation: useAuthStore is reset before each test via setState so tests
 * don't bleed state into each other.
 */

import { describe, test, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { useAuthStore } from '@/features/auth/store'
import { ProtectedRoute } from '../ProtectedRoute'
import * as authApi from '@/features/auth/api'
import type { UserProfile } from '@/shared/types'

// ─── Mock @/features/auth/api — controls the restoration flow deterministically ─

vi.mock('@/features/auth/api', () => ({
  refreshToken: vi.fn(),
  getMe: vi.fn(),
}))

afterEach(() => {
  useAuthStore.setState({ accessToken: null, user: null })
  localStorage.clear()
  vi.clearAllMocks()
})

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const MOCK_USER: UserProfile = {
  id: 'u1',
  email: 'test@test.com',
  first_name: 'Test',
  last_name: 'User',
  role: 'editor',
  organization_id: 'org1',
  organization_name: 'Test Org',
  is_active: true,
}

// ─── Test harness ─────────────────────────────────────────────────────────────
// Renders ProtectedRoute inside a MemoryRouter with:
//   - /         → ProtectedRoute > sentinel div (testid="protected-content")
//   - /login    → login placeholder (testid="login-page")

function renderProtectedRoute(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<ProtectedRoute />}>
          <Route
            path="/"
            element={<div data-testid="protected-content">Protected content</div>}
          />
        </Route>
        <Route
          path="/login"
          element={<div data-testid="login-page">Login page</div>}
        />
      </Routes>
    </MemoryRouter>,
  )
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('ProtectedRoute — session restoration', () => {
  beforeEach(() => {
    // Sensible defaults — most tests override one or both per scenario.
    vi.mocked(authApi.refreshToken).mockResolvedValue({ access: 'new-access-token' })
    vi.mocked(authApi.getMe).mockResolvedValue(MOCK_USER)
  })

  // 1. Sin sesión en memoria → siempre intenta refreshToken() al montar,
  //    y si resuelve, restaura token + perfil, renderiza Outlet.
  test('sin accessToken en memoria → siempre intenta refreshToken() al montar; si resuelve, restaura token y perfil', async () => {
    renderProtectedRoute()

    await waitFor(() => {
      expect(screen.getByTestId('protected-content')).toBeInTheDocument()
    })

    // La cookie es invisible a JS — no hay forma de saber de antemano si hay
    // sesión, así que el refresh SIEMPRE se intenta al montar.
    expect(authApi.refreshToken).toHaveBeenCalledTimes(1)
    expect(authApi.getMe).toHaveBeenCalledTimes(1)

    const state = useAuthStore.getState()
    expect(state.accessToken).toBe('new-access-token')
    expect(state.user?.email).toBe('test@test.com')
  })

  // 2. Refresh válido pero getMe falla → logout y redirige a /login
  test('refresh válido pero getMe falla → logout y redirige a /login', async () => {
    vi.mocked(authApi.getMe).mockRejectedValue(new Error('500 Internal Server Error'))

    renderProtectedRoute()

    await waitFor(() => {
      expect(screen.getByTestId('login-page')).toBeInTheDocument()
    })

    const state = useAuthStore.getState()
    expect(state.accessToken).toBeNull()
    expect(state.user).toBeNull()
  })

  // 3. refreshToken() rechaza (sin cookie o cookie inválida) → logout y redirige a /login
  test('refreshToken() rechaza (sin cookie válida) → logout y redirige a /login, sin llamar a getMe', async () => {
    vi.mocked(authApi.refreshToken).mockRejectedValue(new Error('401 Unauthorized'))

    renderProtectedRoute()

    await waitFor(() => {
      expect(screen.getByTestId('login-page')).toBeInTheDocument()
    })

    // El intento SIEMPRE ocurre — no hay gate client-side para saltarlo.
    expect(authApi.refreshToken).toHaveBeenCalledTimes(1)
    expect(authApi.getMe).not.toHaveBeenCalled()

    const state = useAuthStore.getState()
    expect(state.accessToken).toBeNull()
    expect(state.user).toBeNull()
  })

  // 4. Token + user ya en memoria → no hace requests, renderiza Outlet
  test('token y perfil ya en memoria → renderiza Outlet sin llamar a refreshToken() ni getMe()', async () => {
    // Pre-setar el store con sesión válida
    useAuthStore.setState({ accessToken: 'existing-token', user: MOCK_USER })

    renderProtectedRoute()

    // Debe renderizar contenido protegido inmediatamente (sin esperar red)
    await waitFor(() => {
      expect(screen.getByTestId('protected-content')).toBeInTheDocument()
    })

    expect(authApi.refreshToken).not.toHaveBeenCalled()
    expect(authApi.getMe).not.toHaveBeenCalled()
  })

  // 5. Skeleton durante la restauración: ni contenido protegido ni login se
  //    muestran hasta que el ciclo refresh+getMe termina; restorationAttempted
  //    se marca true al final tanto en éxito como en fallo (cubierto por los
  //    waitFor de los tests 1 y 3, que dependen de este flag para resolver).
  test('muestra un estado de carga (ni contenido protegido ni login) mientras la restauración está en curso', async () => {
    let resolveRefresh: (value: { access: string }) => void = () => {}
    const pendingRefresh = new Promise<{ access: string }>((resolve) => {
      resolveRefresh = resolve
    })
    vi.mocked(authApi.refreshToken).mockReturnValue(pendingRefresh)

    renderProtectedRoute()

    // Mientras la promesa de refresh no resuelve, no debe verse ni el
    // contenido protegido ni la página de login — solo el skeleton.
    expect(screen.queryByTestId('protected-content')).toBeNull()
    expect(screen.queryByTestId('login-page')).toBeNull()

    resolveRefresh({ access: 'new-access-token' })

    await waitFor(() => {
      expect(screen.getByTestId('protected-content')).toBeInTheDocument()
    })
  })
})
