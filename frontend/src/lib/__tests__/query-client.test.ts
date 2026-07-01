import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useMutation, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { queryClient } from '../query-client'
import { ApiError } from '@/shared/types'

vi.mock('sonner', () => ({ toast: { error: vi.fn() } }))

// Use a dynamic import so the mock above applies before the module is evaluated.
const { toast } = await import('sonner')

describe('queryClient global mutation error handler', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    queryClient.clear()
  })

  it('dispara toast.error cuando una mutación falla', async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      createElement(QueryClientProvider, { client: queryClient }, children)

    const { result } = renderHook(
      () =>
        useMutation({
          mutationFn: async () => {
            throw new ApiError('Server error', 'SERVER_ERROR', 500)
          },
        }),
      { wrapper },
    )

    await act(async () => {
      try {
        await result.current.mutateAsync(undefined)
      } catch {
        // expected — we only care about the toast side-effect
      }
    })

    expect(toast.error).toHaveBeenCalledWith('Server error')
  })

  it('NO dispara toast cuando meta.suppressGlobalToast es true', async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      createElement(QueryClientProvider, { client: queryClient }, children)

    const { result } = renderHook(
      () =>
        useMutation({
          mutationFn: async () => {
            throw new ApiError('Login error', 'INVALID', 401)
          },
          meta: { suppressGlobalToast: true },
        }),
      { wrapper },
    )

    await act(async () => {
      try {
        await result.current.mutateAsync(undefined)
      } catch {
        // expected
      }
    })

    expect(toast.error).not.toHaveBeenCalled()
  })
})
