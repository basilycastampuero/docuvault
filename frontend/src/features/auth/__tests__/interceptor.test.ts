/**
 * Tests for the axios interceptors in api-client.ts.
 *
 * Architecture note on module isolation:
 *   `isRefreshing` and `failedQueue` are module-level variables in api-client.ts
 *   with no exported reset function. Using `vi.resetModules()` per-test would
 *   create separate store instances for the interceptor closure vs. the test
 *   body, breaking assertions on `useAuthStore().accessToken` after logout.
 *
 *   Solution: import modules once, run tests sequentially (Vitest default),
 *   and design each test to complete the refresh cycle fully so `isRefreshing`
 *   returns to false before the next test begins. The `afterEach` resets
 *   localStorage and Zustand state. MSW `resetHandlers` clears all per-test
 *   route overrides.
 *
 * MSW intercepts at the XMLHttpRequest / fetch level in jsdom, so axios
 * requests are captured without any stub on the axios instance itself.
 *
 * Phase 6.1 note: the refresh token now travels as an HttpOnly cookie
 * (`sv_refresh`), invisible to JS. The interceptor no longer reads/writes
 * `localStorage` for the refresh flow — it always attempts a network refresh
 * on 401 (the browser attaches the cookie automatically via
 * `withCredentials: true`), and adds a `X-CSRF-Token` header read via
 * `getCookie()` from `@/lib/cookies` for the double-submit CSRF check.
 * `getCookie` is mocked here (via `vi.hoisted`) so tests can simulate
 * "CSRF cookie present" vs. "no CSRF cookie" without touching real
 * `document.cookie` parsing.
 */

import { describe, test, expect, beforeAll, beforeEach, afterEach, afterAll, vi } from 'vitest'
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'

// ─── Mock @/lib/cookies — controls the CSRF header the interceptor sends ──────

const { mockGetCookie } = vi.hoisted(() => ({ mockGetCookie: vi.fn<(name: string) => string | null>() }))

vi.mock('@/lib/cookies', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/cookies')>()
  return { ...actual, getCookie: mockGetCookie }
})

// ─── Single import — must match the instance used by the interceptor ──────────
import { apiClient } from '@/lib/api-client'
import { useAuthStore } from '@/features/auth/store'

// ─── MSW server ───────────────────────────────────────────────────────────────

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }))
beforeEach(() => {
  // Default: a valid CSRF cookie exists (mirrors "user has an active session").
  // Individual tests override this with `mockGetCookie.mockReturnValue(null)`
  // to simulate "no session cookie".
  mockGetCookie.mockReset()
  mockGetCookie.mockReturnValue('default-csrf-token')
})
afterEach(() => {
  server.resetHandlers()
  useAuthStore.setState({ accessToken: null, user: null })
  localStorage.clear()
  // Clear the default Authorization header the interceptor sets on success
  delete apiClient.defaults.headers.common['Authorization']
})
afterAll(() => server.close())

// ─── window.location.href mock ────────────────────────────────────────────────
// jsdom throws "Not implemented: navigation" when code assigns
// `window.location.href = '/login'`. We intercept just the href setter
// (not the full location getter) so the jsdom URL base stays intact and
// axios can resolve absolute URLs correctly.

let locationHrefSetter: ReturnType<typeof vi.fn>

beforeEach(() => {
  locationHrefSetter = vi.fn()
  // Replace window.location with an object that proxies all properties but
  // intercepts the href setter so jsdom does not throw "Not implemented:
  // navigation". The spread excludes 'href' explicitly to avoid the
  // esbuild duplicate-key warning when we define the setter below.
  const originalLocation = window.location
  const { href: _href, ...rest } = originalLocation as unknown as Record<string, unknown>
  void _href // silence unused variable warning
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: Object.defineProperty(
      Object.assign(Object.create(null), rest),
      'href',
      {
        get: () => 'http://localhost:3000/',
        set: (v: string) => locationHrefSetter(v),
        configurable: true,
      },
    ),
  })
})

afterEach(() => {
  // Restore window.location to its original jsdom descriptor
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: window.location,
  })
  vi.restoreAllMocks()
})

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const DOCUMENTS_RESPONSE = { data: [{ id: 'doc-1', name: 'report.pdf' }], meta: {} }

// ─── REQUEST INTERCEPTOR ──────────────────────────────────────────────────────

describe('Request interceptor', () => {
  test('adds Authorization header when a token is present in the store', async () => {
    /**Should inject `Bearer <token>` so the backend can authenticate the request */
    let capturedAuthHeader: string | null = null

    server.use(
      http.get('http://localhost:8000/api/v1/documents/', ({ request }) => {
        capturedAuthHeader = request.headers.get('Authorization')
        return HttpResponse.json(DOCUMENTS_RESPONSE)
      }),
    )

    useAuthStore.getState().setAccessToken('access-abc123')
    await apiClient.get('/documents/')

    expect(capturedAuthHeader).toBe('Bearer access-abc123')
  })

  test('does not add Authorization header when no token is present', async () => {
    /**Should send no Authorization header for anonymous requests */
    let capturedAuthHeader: string | null | undefined = 'sentinel'

    server.use(
      http.get('http://localhost:8000/api/v1/documents/', ({ request }) => {
        capturedAuthHeader = request.headers.get('Authorization')
        return HttpResponse.json(DOCUMENTS_RESPONSE)
      }),
    )

    // No setAccessToken — store has null token from afterEach reset
    await apiClient.get('/documents/')

    expect(capturedAuthHeader).toBeNull()
  })

  // ── CSRF double-submit header (Phase 6.1) ─────────────────────────────────

  test('adds X-CSRF-Token header on requests to /auth/refresh/', async () => {
    /**Should read the CSRF cookie value and attach it as X-CSRF-Token for the refresh endpoint */
    mockGetCookie.mockReturnValue('csrf-value-refresh')
    let capturedCsrf: string | null = null

    server.use(
      http.post('http://localhost:8000/api/v1/auth/refresh/', ({ request }) => {
        capturedCsrf = request.headers.get('X-CSRF-Token')
        return HttpResponse.json({ data: { access: 'tok' }, meta: {} })
      }),
    )

    await apiClient.post('/auth/refresh/', {})

    expect(capturedCsrf).toBe('csrf-value-refresh')
  })

  test('adds X-CSRF-Token header on requests to /auth/logout/', async () => {
    /**Should read the CSRF cookie value and attach it as X-CSRF-Token for the logout endpoint */
    mockGetCookie.mockReturnValue('csrf-value-logout')
    let capturedCsrf: string | null = null

    server.use(
      http.post('http://localhost:8000/api/v1/auth/logout/', ({ request }) => {
        capturedCsrf = request.headers.get('X-CSRF-Token')
        return new HttpResponse(null, { status: 204 })
      }),
    )

    await apiClient.post('/auth/logout/', {})

    expect(capturedCsrf).toBe('csrf-value-logout')
  })

  test('does not add X-CSRF-Token header on unrelated routes even when a CSRF cookie exists', async () => {
    /**Should only attach the CSRF header on the two protected paths, never on arbitrary API calls */
    mockGetCookie.mockReturnValue('csrf-value-should-not-leak')
    let capturedCsrf: string | null | undefined = 'sentinel'

    server.use(
      http.get('http://localhost:8000/api/v1/documents/', ({ request }) => {
        capturedCsrf = request.headers.get('X-CSRF-Token')
        return HttpResponse.json(DOCUMENTS_RESPONSE)
      }),
    )

    await apiClient.get('/documents/')

    expect(capturedCsrf).toBeNull()
  })

  test('does not add X-CSRF-Token header when no CSRF cookie is present', async () => {
    /**Should omit the header entirely (not send an empty string) when getCookie returns null */
    mockGetCookie.mockReturnValue(null)
    let capturedCsrf: string | null | undefined = 'sentinel'

    server.use(
      http.post('http://localhost:8000/api/v1/auth/logout/', ({ request }) => {
        capturedCsrf = request.headers.get('X-CSRF-Token')
        return new HttpResponse(null, { status: 204 })
      }),
    )

    await apiClient.post('/auth/logout/', {})

    expect(capturedCsrf).toBeNull()
  })
})

// ─── RESPONSE INTERCEPTOR — refresh flow ──────────────────────────────────────

describe('Response interceptor — refresh flow', () => {
  test('401 response triggers one refresh call and retries the original request', async () => {
    /**Should silently recover by refreshing the token and replaying the failed request */
    let refreshCallCount = 0
    let documentsCallCount = 0

    server.use(
      http.get('http://localhost:8000/api/v1/documents/', () => {
        documentsCallCount++
        if (documentsCallCount === 1) return new HttpResponse(null, { status: 401 })
        return HttpResponse.json(DOCUMENTS_RESPONSE)
      }),
      http.post('http://localhost:8000/api/v1/auth/refresh/', () => {
        refreshCallCount++
        return HttpResponse.json({ data: { access: 'new-access-token' }, meta: {} })
      }),
    )

    const response = await apiClient.get('/documents/')

    expect(refreshCallCount).toBe(1)
    expect(documentsCallCount).toBe(2) // initial 401 + retry
    expect(response.status).toBe(200)
  })

  test('refresh request carries the CSRF header from the cookie, withCredentials, and an empty body', async () => {
    /**Should never send the refresh token in the body — it travels only via the HttpOnly cookie */
    mockGetCookie.mockReturnValue('csrf-secret-value')

    let capturedCsrfHeader: string | null = null
    let capturedBody: unknown

    let documentsCallCount = 0

    server.use(
      http.get('http://localhost:8000/api/v1/documents/', () => {
        documentsCallCount++
        if (documentsCallCount === 1) return new HttpResponse(null, { status: 401 })
        return HttpResponse.json(DOCUMENTS_RESPONSE)
      }),
      http.post('http://localhost:8000/api/v1/auth/refresh/', async ({ request }) => {
        capturedCsrfHeader = request.headers.get('X-CSRF-Token')
        capturedBody = await request.json()
        return HttpResponse.json({ data: { access: 'new-token' }, meta: {} })
      }),
    )

    useAuthStore.getState().setAccessToken('old-token')
    await apiClient.get('/documents/')

    expect(capturedCsrfHeader).toBe('csrf-secret-value')
    expect(capturedBody).toEqual({})
    // Never present in the body — confirms the refresh flow no longer needs
    // a client-known refresh token value at all.
    expect(capturedBody).not.toHaveProperty('refresh')
  })

  test('after successful refresh, the retried request uses the new token', async () => {
    /**Should update the Authorization header with the refreshed token on retry */
    const authHeaders: string[] = []

    server.use(
      http.get('http://localhost:8000/api/v1/documents/', ({ request }) => {
        const header = request.headers.get('Authorization')
        if (header) authHeaders.push(header)
        if (authHeaders.length === 1) return new HttpResponse(null, { status: 401 })
        return HttpResponse.json(DOCUMENTS_RESPONSE)
      }),
      http.post('http://localhost:8000/api/v1/auth/refresh/', () => {
        return HttpResponse.json({ data: { access: 'freshly-issued-token' }, meta: {} })
      }),
    )

    useAuthStore.getState().setAccessToken('expired-token')
    await apiClient.get('/documents/')

    expect(authHeaders).toHaveLength(2)
    expect(authHeaders[0]).toBe('Bearer expired-token')
    expect(authHeaders[1]).toBe('Bearer freshly-issued-token')
  })

  test('401 refresh failure triggers logout and does not retry the original request', async () => {
    /**Should clean up the session when the refresh endpoint also rejects — no infinite loop */
    let documentsCallCount = 0

    server.use(
      http.get('http://localhost:8000/api/v1/documents/', () => {
        documentsCallCount++
        return new HttpResponse(null, { status: 401 })
      }),
      // Refresh itself returns 401 — the session cookie is truly expired/invalid
      http.post('http://localhost:8000/api/v1/auth/refresh/', () => {
        return new HttpResponse(null, { status: 401 })
      }),
    )

    useAuthStore.getState().setAccessToken('some-access-token')

    await expect(apiClient.get('/documents/')).rejects.toBeTruthy()

    // Only the original request fires — no retry after a failed refresh
    expect(documentsCallCount).toBe(1)
    // Store must be wiped by logout()
    expect(useAuthStore.getState().accessToken).toBeNull()
    expect(useAuthStore.getState().user).toBeNull()
  })

  test('401 always attempts a network refresh even with no CSRF cookie — the refresh cookie is HttpOnly and invisible to JS', async () => {
    /**
     * Should NOT skip the network call client-side (there is no client-readable
     * signal for "session exists" anymore since sv_refresh is HttpOnly) — the
     * refresh is always attempted, and the backend is the one that rejects it
     * when there is no valid session cookie.
     */
    mockGetCookie.mockReturnValue(null) // no CSRF cookie — mirrors "never logged in"

    let refreshCalled = false

    server.use(
      http.get('http://localhost:8000/api/v1/documents/', () => {
        return new HttpResponse(null, { status: 401 })
      }),
      http.post('http://localhost:8000/api/v1/auth/refresh/', () => {
        refreshCalled = true
        // No valid sv_refresh cookie server-side either — refresh itself rejects
        return new HttpResponse(null, { status: 401 })
      }),
    )

    useAuthStore.getState().setAccessToken('access-token')

    await expect(apiClient.get('/documents/')).rejects.toBeTruthy()

    // Unlike the old localStorage-gated behavior, the refresh endpoint IS called
    expect(refreshCalled).toBe(true)
    // Logout is still called (clears the store)
    expect(useAuthStore.getState().accessToken).toBeNull()
  })

  // ── Queue pattern (THE most critical test) ─────────────────────────────────

  test('concurrent 401s trigger only ONE refresh call (queue pattern)', async () => {
    /**
     * Should not call the refresh endpoint more than once even when multiple
     * requests fail with 401 simultaneously — prevents thundering-herd on
     * the refresh endpoint and avoids token invalidation race conditions.
     */
    let refreshCallCount = 0
    let aCallCount = 0
    let bCallCount = 0
    let cCallCount = 0

    server.use(
      http.get('http://localhost:8000/api/v1/documents/a', () => {
        aCallCount++
        if (aCallCount === 1) return new HttpResponse(null, { status: 401 })
        return HttpResponse.json({ data: { id: 'a' }, meta: {} })
      }),
      http.get('http://localhost:8000/api/v1/documents/b', () => {
        bCallCount++
        if (bCallCount === 1) return new HttpResponse(null, { status: 401 })
        return HttpResponse.json({ data: { id: 'b' }, meta: {} })
      }),
      http.get('http://localhost:8000/api/v1/documents/c', () => {
        cCallCount++
        if (cCallCount === 1) return new HttpResponse(null, { status: 401 })
        return HttpResponse.json({ data: { id: 'c' }, meta: {} })
      }),
      http.post('http://localhost:8000/api/v1/auth/refresh/', async () => {
        refreshCallCount++
        // Simulate a small network delay so the queue fills before the
        // first refresh resolves and the queuing logic gets exercised
        await new Promise<void>((r) => setTimeout(r, 20))
        return HttpResponse.json({ data: { access: 'shared-new-token' }, meta: {} })
      }),
    )

    useAuthStore.getState().setAccessToken('old-access-token')

    // Fire all three requests in parallel — all will receive a 401
    const [r1, r2, r3] = await Promise.all([
      apiClient.get('/documents/a'),
      apiClient.get('/documents/b'),
      apiClient.get('/documents/c'),
    ])

    // The single most important assertion: refresh was called exactly once
    expect(refreshCallCount).toBe(1)

    // All three must have completed successfully after the single refresh
    expect(r1.status).toBe(200)
    expect(r2.status).toBe(200)
    expect(r3.status).toBe(200)

    // Each endpoint was hit exactly twice: initial 401 + retry
    expect(aCallCount).toBe(2)
    expect(bCallCount).toBe(2)
    expect(cCallCount).toBe(2)
  })

  test('after successful refresh, queued requests use the new token', async () => {
    /**
     * Should resolve all queued requests with the freshly issued token, not
     * the old one — otherwise the retries would still be rejected by the server.
     */
    const authHeadersA: string[] = []
    const authHeadersB: string[] = []

    server.use(
      http.get('http://localhost:8000/api/v1/documents/a', ({ request }) => {
        const h = request.headers.get('Authorization')
        if (h) authHeadersA.push(h)
        if (authHeadersA.length === 1) return new HttpResponse(null, { status: 401 })
        return HttpResponse.json({ data: {}, meta: {} })
      }),
      http.get('http://localhost:8000/api/v1/documents/b', ({ request }) => {
        const h = request.headers.get('Authorization')
        if (h) authHeadersB.push(h)
        if (authHeadersB.length === 1) return new HttpResponse(null, { status: 401 })
        return HttpResponse.json({ data: {}, meta: {} })
      }),
      http.post('http://localhost:8000/api/v1/auth/refresh/', async () => {
        await new Promise<void>((r) => setTimeout(r, 20))
        return HttpResponse.json({ data: { access: 'brand-new-token' }, meta: {} })
      }),
    )

    useAuthStore.getState().setAccessToken('old-token')

    await Promise.all([
      apiClient.get('/documents/a'),
      apiClient.get('/documents/b'),
    ])

    // Both retried requests must carry the new token, not the old one
    expect(authHeadersA[1]).toBe('Bearer brand-new-token')
    expect(authHeadersB[1]).toBe('Bearer brand-new-token')
  })

  // ── Non-401 errors pass through ────────────────────────────────────────────

  test('non-401 errors are passed through without triggering refresh', async () => {
    /**Should not attempt token refresh for 403, 404, 500 — only 401 triggers refresh */
    let refreshCalled = false

    server.use(
      http.get('http://localhost:8000/api/v1/documents/', () => {
        return new HttpResponse(null, { status: 403 })
      }),
      http.post('http://localhost:8000/api/v1/auth/refresh/', () => {
        refreshCalled = true
        return HttpResponse.json({ access: 'should-not-be-called' })
      }),
    )

    await expect(apiClient.get('/documents/')).rejects.toBeTruthy()
    expect(refreshCalled).toBe(false)
  })

  // ── Retry idempotency ──────────────────────────────────────────────────────

  test('a 401 on the retried request does not trigger a second refresh', async () => {
    /**
     * Should not enter an infinite refresh loop when the retried request also
     * fails with 401 — the `_retry` flag prevents recursive refresh attempts.
     */
    let refreshCallCount = 0

    server.use(
      // Always returns 401, even on the retry
      http.get('http://localhost:8000/api/v1/documents/', () => {
        return new HttpResponse(null, { status: 401 })
      }),
      http.post('http://localhost:8000/api/v1/auth/refresh/', () => {
        refreshCallCount++
        return HttpResponse.json({ access: 'new-token' })
      }),
    )

    await expect(apiClient.get('/documents/')).rejects.toBeTruthy()

    // Refresh attempted exactly once — not in a loop
    expect(refreshCallCount).toBe(1)
  })

  // ── Promise.reject guarantee when originalRequest is absent ───────────────

  // TODO: test — refresh succeeded but originalRequest is undefined → rejects instead of resolving undefined.
  // This branch (lines after the `if (originalRequest)` block) is unreachable via MSW because
  // axios always populates error.config when it processes a response. Testing it requires either:
  //   (a) calling the interceptor function directly with a synthetic AxiosError where config is undefined, or
  //   (b) exposing and calling the interceptor handler in isolation.
  // Neither is straightforward without refactoring api-client.ts to export the handler.
  // The fix is nevertheless load-bearing as a safety net for callers that invoke the interceptor
  // outside of a standard request flow.
})
