/**
 * Tests for ProtectedRoute — session restoration on page reload.
 *
 * Uses MSW to intercept HTTP calls. The component calls:
 *   - POST /auth/refresh/   → { access }
 *   - GET  /auth/me/        → { data: UserProfile, meta: {} }
 *
 * Uses MemoryRouter so Navigate renders without a real browser. The Outlet
 * sentinel and a fake Login route allow us to assert what the router rendered.
 *
 * Isolation: useAuthStore is reset before each test via setState so tests
 * don't bleed state into each other.
 */

import { describe, test, expect, beforeAll, afterEach, afterAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'
import { useAuthStore } from '@/features/auth/store'
import { ProtectedRoute } from '../ProtectedRoute'
import type { UserProfile } from '@/shared/types'

// ─── MSW server ───────────────────────────────────────────────────────────────

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }))
afterEach(() => {
  server.resetHandlers()
  useAuthStore.setState({ accessToken: null, user: null })
  localStorage.clear()
})
afterAll(() => server.close())

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

const REFRESH_RESPONSE = { access: 'new-access-token' }

const ME_RESPONSE = { data: MOCK_USER, meta: {} }

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
  // 1. No refreshToken en localStorage → redirige a /login
  test('sin refreshToken en localStorage → redirige a /login', async () => {
    // localStorage está limpio (beforeEach)
    renderProtectedRoute()

    await waitFor(() => {
      expect(screen.getByTestId('login-page')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('protected-content')).toBeNull()
  })

  // 2. Refresh válido → restaura token Y perfil, renderiza Outlet
  test('refresh válido → restaura token y perfil, muestra contenido protegido', async () => {
    localStorage.setItem('refreshToken', 'valid-refresh')

    server.use(
      http.post('http://localhost:8000/api/v1/auth/refresh/', () =>
        HttpResponse.json(REFRESH_RESPONSE),
      ),
      http.get('http://localhost:8000/api/v1/auth/me/', () =>
        HttpResponse.json(ME_RESPONSE),
      ),
    )

    renderProtectedRoute()

    await waitFor(() => {
      expect(screen.getByTestId('protected-content')).toBeInTheDocument()
    })

    // Store debe estar hidratado con token y perfil
    const state = useAuthStore.getState()
    expect(state.accessToken).toBe('new-access-token')
    expect(state.user?.email).toBe('test@test.com')
  })

  // 3. Refresh válido pero /auth/me/ falla → logout y redirige a /login
  test('refresh válido pero getMe falla → logout y redirige a /login', async () => {
    localStorage.setItem('refreshToken', 'valid-refresh')

    server.use(
      http.post('http://localhost:8000/api/v1/auth/refresh/', () =>
        HttpResponse.json(REFRESH_RESPONSE),
      ),
      http.get('http://localhost:8000/api/v1/auth/me/', () =>
        new HttpResponse(null, { status: 500 }),
      ),
    )

    renderProtectedRoute()

    await waitFor(() => {
      expect(screen.getByTestId('login-page')).toBeInTheDocument()
    })

    // Store debe haber quedado limpio por logout
    const state = useAuthStore.getState()
    expect(state.accessToken).toBeNull()
    expect(state.user).toBeNull()
  })

  // 4. Refresh inválido (401) → logout y redirige a /login
  test('refresh inválido (401) → logout y redirige a /login', async () => {
    localStorage.setItem('refreshToken', 'expired-refresh')

    server.use(
      http.post('http://localhost:8000/api/v1/auth/refresh/', () =>
        new HttpResponse(null, { status: 401 }),
      ),
    )

    renderProtectedRoute()

    await waitFor(() => {
      expect(screen.getByTestId('login-page')).toBeInTheDocument()
    })

    const state = useAuthStore.getState()
    expect(state.accessToken).toBeNull()
    expect(state.user).toBeNull()
  })

  // 5. Token + user ya en memoria → no hace requests de red, renderiza Outlet
  test('token y perfil ya en memoria → renderiza Outlet sin requests de red', async () => {
    // Pre-setar el store con sesión válida
    useAuthStore.setState({ accessToken: 'existing-token', user: MOCK_USER })

    let refreshCalled = false
    let meCalled = false

    server.use(
      http.post('http://localhost:8000/api/v1/auth/refresh/', () => {
        refreshCalled = true
        return HttpResponse.json(REFRESH_RESPONSE)
      }),
      http.get('http://localhost:8000/api/v1/auth/me/', () => {
        meCalled = true
        return HttpResponse.json(ME_RESPONSE)
      }),
    )

    renderProtectedRoute()

    // Debe renderizar contenido protegido inmediatamente (sin esperar red)
    await waitFor(() => {
      expect(screen.getByTestId('protected-content')).toBeInTheDocument()
    })

    // No debe haber llamado a la red
    expect(refreshCalled).toBe(false)
    expect(meCalled).toBe(false)
  })
})
