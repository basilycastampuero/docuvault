/**
 * Tests for LoginForm error display logic.
 *
 * Focuses on the type-safe narrowing of mutation errors:
 *   - ApiError with 401 → "Email o contraseña incorrectos"
 *   - ApiError with other status → shows raw message
 *   - generic Error → shows message
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClientProvider, QueryClient } from '@tanstack/react-query'
import { createElement } from 'react'
import { ApiError } from '@/shared/types'
import { LoginForm } from '../components/LoginForm'

// ─── Mock hooks module ────────────────────────────────────────────────────────
// We mock the entire hooks module so we can control what useLogin returns.
// useLogout and useMe are stubbed because they're imported by hooks.ts itself.

const mockUseLogin = vi.fn()

vi.mock('@/features/auth/hooks', () => ({
  useLogin: () => mockUseLogin(),
  useLogout: () => ({ mutate: vi.fn(), isPending: false }),
  useMe: () => ({ data: null, isLoading: false }),
}))

// ─── Helpers ─────────────────────────────────────────────────────────────────

function buildLoginMutation(error: Error | null) {
  return {
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
    isError: error !== null,
    error,
    reset: vi.fn(),
  }
}

function renderLoginForm(mutation: ReturnType<typeof buildLoginMutation>) {
  mockUseLogin.mockReturnValue(mutation)

  const testQueryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })

  return render(
    createElement(
      QueryClientProvider,
      { client: testQueryClient },
      createElement(MemoryRouter, null, createElement(LoginForm)),
    ),
  )
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('LoginForm error display', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('muestra mensaje amigable para error 401 ApiError', () => {
    const error = new ApiError('Unauthorized', 'INVALID_CREDENTIALS', 401)
    renderLoginForm(buildLoginMutation(error))

    expect(screen.getByRole('alert')).toHaveTextContent('Email o contraseña incorrectos')
  })

  it('muestra mensaje amigable para ApiError con code INVALID_CREDENTIALS', () => {
    const error = new ApiError('Invalid credentials', 'INVALID_CREDENTIALS', 400)
    renderLoginForm(buildLoginMutation(error))

    expect(screen.getByRole('alert')).toHaveTextContent('Email o contraseña incorrectos')
  })

  it('muestra el mensaje del servidor para ApiError con otro código', () => {
    const error = new ApiError('Cuenta suspendida', 'ACCOUNT_SUSPENDED', 403)
    renderLoginForm(buildLoginMutation(error))

    expect(screen.getByRole('alert')).toHaveTextContent('Cuenta suspendida')
  })

  it('muestra el mensaje para un Error genérico no-ApiError', () => {
    const error = new Error('Network error')
    renderLoginForm(buildLoginMutation(error))

    expect(screen.getByRole('alert')).toHaveTextContent('Network error')
  })

  it('no muestra alerta de error cuando no hay error', () => {
    renderLoginForm(buildLoginMutation(null))

    expect(screen.queryByRole('alert')).toBeNull()
  })
})
