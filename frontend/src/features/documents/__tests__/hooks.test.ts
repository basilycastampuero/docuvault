/**
 * Tests for useDocument — specifically the refetchInterval polling logic.
 *
 * Strategy: mock `./api` so documentsApi.getById resolves with a document
 * whose ocr_status/thumbnail_status we control. Render the hook inside a
 * QueryClientProvider and wait for data to load. Then inspect the TanStack
 * Query observer options to confirm the refetchInterval function returns the
 * correct value.
 *
 * TanStack Query v5 passes a `Query` object to the refetchInterval callback.
 * `query.state.data` holds the last resolved value. By seeding the cache with
 * a known document we can call the callback in isolation without timer faking.
 *
 * All tests use a fresh QueryClient (retry:0, gcTime:0) so queries don't bleed
 * between test cases.
 *
 * Also covers useRegenerateThumbnail — the mutation used by the "Regenerar
 * miniatura" button on DocumentDetailPage.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import type { Document, OcrStatus, ThumbnailStatus } from '@/shared/types'
import { useDocument, useRegenerateThumbnail, documentKeys } from '../hooks'

// ─── Mock the documents API ───────────────────────────────────────────────────
// We need to control what getById returns without a real network request.

const mockGetById = vi.fn()
const mockRegenerateThumbnail = vi.fn()

vi.mock('../api', () => ({
  documentsApi: {
    getById: (...args: unknown[]) => mockGetById(...args),
    // Stub all other methods so the module loads without errors
    list: vi.fn(),
    upload: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    getDownloadUrl: vi.fn(),
    getVersions: vi.fn(),
    uploadVersion: vi.fn(),
    reprocessOcr: vi.fn(),
    requestAiAnalysis: vi.fn(),
    regenerateThumbnail: (...args: unknown[]) => mockRegenerateThumbnail(...args),
  },
}))

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeDocument(
  ocr_status: OcrStatus,
  thumbnail_status: ThumbnailStatus = 'ready',
): Document {
  return {
    id: 'doc-test-id',
    name: 'test.pdf',
    description: '',
    mime_type: 'application/pdf',
    file_size: 1024,
    checksum: 'abc123',
    status: 'draft',
    version: 1,
    ocr_status,
    ocr_content: '',
    thumbnail_status,
    thumbnail_url: thumbnail_status === 'ready' ? 'https://minio.local/thumb.jpg' : null,
    tags: [],
    metadata: {},
    folder: null,
    folder_name: null,
    created_by_email: 'test@test.com',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  }
}

function makeWrapper(queryClient: QueryClient) {
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children)
}

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        // Disable garbage collection delay so queries are fully isolated
        gcTime: 0,
        // Disable stale-while-revalidate so we can inspect state precisely
        staleTime: 0,
      },
    },
  })
}

// ─── Setup / teardown ─────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.restoreAllMocks()
})

// ─── refetchInterval logic ────────────────────────────────────────────────────
//
// Rather than re-implementing the polling rule inline (which can silently
// drift from the real hook), these tests pull the ACTUAL refetchInterval
// function off the live query's options and invoke it with a fake query
// state. This exercises the real production logic, including the OCR/
// thumbnail combination and the 40-update polling cap.

type RefetchIntervalFn = (query: {
  state: { data?: Document; dataUpdateCount?: number }
}) => number | false

function getRefetchIntervalFn(qc: QueryClient, id: string): RefetchIntervalFn {
  const query = qc.getQueryCache().find({ queryKey: documentKeys.detail(id) })
  if (!query) throw new Error('Query not found in cache — did the hook mount?')
  // `refetchInterval` is an observer-only option (QueryObserverOptions) that
  // is not part of the base `Query.options` type (QueryOptions), even though
  // it is present on the runtime object built by useQuery. Cast is required.
  const options = query.options as unknown as { refetchInterval?: unknown }
  const fn = options.refetchInterval
  if (typeof fn !== 'function') {
    throw new Error('refetchInterval is not a function on this query')
  }
  return fn as RefetchIntervalFn
}

describe('useDocument — refetchInterval polling logic (OCR)', () => {
  it('returns 3000ms interval when ocr_status is pending', async () => {
    /**Should poll every 3s while OCR is waiting to start */
    const qc = makeQueryClient()
    mockGetById.mockResolvedValue(makeDocument('pending', 'ready'))

    renderHook(() => useDocument('doc-test-id'), { wrapper: makeWrapper(qc) })
    await waitFor(() => expect(mockGetById).toHaveBeenCalled())

    const refetchInterval = getRefetchIntervalFn(qc, 'doc-test-id')
    const doc = makeDocument('pending', 'ready')
    expect(refetchInterval({ state: { data: doc, dataUpdateCount: 1 } })).toBe(3000)
  })

  it('returns 3000ms interval when ocr_status is processing', async () => {
    /**Should continue polling every 3s while OCR is actively running */
    const qc = makeQueryClient()
    mockGetById.mockResolvedValue(makeDocument('processing', 'ready'))

    renderHook(() => useDocument('doc-test-id'), { wrapper: makeWrapper(qc) })
    await waitFor(() => expect(mockGetById).toHaveBeenCalled())

    const refetchInterval = getRefetchIntervalFn(qc, 'doc-test-id')
    const doc = makeDocument('processing', 'ready')
    expect(refetchInterval({ state: { data: doc, dataUpdateCount: 1 } })).toBe(3000)
  })

  it('returns false (no polling) when both ocr_status and thumbnail_status are terminal', async () => {
    /**Should stop polling once both background jobs finished (successfully or not) */
    const qc = makeQueryClient()
    mockGetById.mockResolvedValue(makeDocument('completed', 'ready'))

    renderHook(() => useDocument('doc-test-id'), { wrapper: makeWrapper(qc) })
    await waitFor(() => expect(mockGetById).toHaveBeenCalled())

    const refetchInterval = getRefetchIntervalFn(qc, 'doc-test-id')
    const doc = makeDocument('completed', 'ready')
    expect(refetchInterval({ state: { data: doc, dataUpdateCount: 1 } })).toBe(false)
  })

  it('returns false (no polling) when ocr_status is failed and thumbnail is ready', async () => {
    /**Should not poll after a failed OCR run — no automatic retry from the client */
    const qc = makeQueryClient()
    mockGetById.mockResolvedValue(makeDocument('failed', 'ready'))

    renderHook(() => useDocument('doc-test-id'), { wrapper: makeWrapper(qc) })
    await waitFor(() => expect(mockGetById).toHaveBeenCalled())

    const refetchInterval = getRefetchIntervalFn(qc, 'doc-test-id')
    const doc = makeDocument('failed', 'ready')
    expect(refetchInterval({ state: { data: doc, dataUpdateCount: 1 } })).toBe(false)
  })

  it('returns false (no polling) when ocr_status is skipped and thumbnail is skipped', async () => {
    /**Should not poll for office documents where OCR and thumbnails were both bypassed */
    const qc = makeQueryClient()
    mockGetById.mockResolvedValue(makeDocument('skipped', 'skipped'))

    renderHook(() => useDocument('doc-test-id'), { wrapper: makeWrapper(qc) })
    await waitFor(() => expect(mockGetById).toHaveBeenCalled())

    const refetchInterval = getRefetchIntervalFn(qc, 'doc-test-id')
    const doc = makeDocument('skipped', 'skipped')
    expect(refetchInterval({ state: { data: doc, dataUpdateCount: 1 } })).toBe(false)
  })

  it('returns false when data is undefined (query not yet loaded)', async () => {
    /**Should not schedule a refetch when there is no data yet in the cache */
    const qc = makeQueryClient()
    mockGetById.mockResolvedValue(makeDocument('pending', 'ready'))

    renderHook(() => useDocument('doc-test-id'), { wrapper: makeWrapper(qc) })
    await waitFor(() => expect(mockGetById).toHaveBeenCalled())

    const refetchInterval = getRefetchIntervalFn(qc, 'doc-test-id')
    expect(refetchInterval({ state: { data: undefined, dataUpdateCount: 0 } })).toBe(false)
  })
})

describe('useDocument — refetchInterval polling logic (thumbnail)', () => {
  it('keeps polling when thumbnail_status is pending even though ocr_status is terminal', async () => {
    /**Should not stop polling early just because OCR finished — the thumbnail
     * job is independent and may still be running */
    const qc = makeQueryClient()
    mockGetById.mockResolvedValue(makeDocument('completed', 'pending'))

    renderHook(() => useDocument('doc-test-id'), { wrapper: makeWrapper(qc) })
    await waitFor(() => expect(mockGetById).toHaveBeenCalled())

    const refetchInterval = getRefetchIntervalFn(qc, 'doc-test-id')
    const doc = makeDocument('completed', 'pending')
    expect(refetchInterval({ state: { data: doc, dataUpdateCount: 1 } })).toBe(3000)
  })

  it('keeps polling when thumbnail_status is processing even though ocr_status is terminal', async () => {
    /**Mirrors the pending case for the processing state */
    const qc = makeQueryClient()
    mockGetById.mockResolvedValue(makeDocument('skipped', 'processing'))

    renderHook(() => useDocument('doc-test-id'), { wrapper: makeWrapper(qc) })
    await waitFor(() => expect(mockGetById).toHaveBeenCalled())

    const refetchInterval = getRefetchIntervalFn(qc, 'doc-test-id')
    const doc = makeDocument('skipped', 'processing')
    expect(refetchInterval({ state: { data: doc, dataUpdateCount: 1 } })).toBe(3000)
  })

  it('stops polling when thumbnail_status is failed and ocr_status is terminal', async () => {
    /**A failed thumbnail is a terminal state — no automatic retry from the client */
    const qc = makeQueryClient()
    mockGetById.mockResolvedValue(makeDocument('completed', 'failed'))

    renderHook(() => useDocument('doc-test-id'), { wrapper: makeWrapper(qc) })
    await waitFor(() => expect(mockGetById).toHaveBeenCalled())

    const refetchInterval = getRefetchIntervalFn(qc, 'doc-test-id')
    const doc = makeDocument('completed', 'failed')
    expect(refetchInterval({ state: { data: doc, dataUpdateCount: 1 } })).toBe(false)
  })

  it('keeps polling when both ocr_status and thumbnail_status are still active', async () => {
    /**Both jobs racing concurrently must keep the interval alive until the last one finishes */
    const qc = makeQueryClient()
    mockGetById.mockResolvedValue(makeDocument('processing', 'processing'))

    renderHook(() => useDocument('doc-test-id'), { wrapper: makeWrapper(qc) })
    await waitFor(() => expect(mockGetById).toHaveBeenCalled())

    const refetchInterval = getRefetchIntervalFn(qc, 'doc-test-id')
    const doc = makeDocument('processing', 'processing')
    expect(refetchInterval({ state: { data: doc, dataUpdateCount: 1 } })).toBe(3000)
  })
})

describe('useDocument — refetchInterval polling cap (40 updates)', () => {
  it('keeps polling at exactly 40 updates while a status is still active', async () => {
    /**The cap check is `updateCount > 40`, so 40 itself must still poll */
    const qc = makeQueryClient()
    mockGetById.mockResolvedValue(makeDocument('processing', 'ready'))

    renderHook(() => useDocument('doc-test-id'), { wrapper: makeWrapper(qc) })
    await waitFor(() => expect(mockGetById).toHaveBeenCalled())

    const refetchInterval = getRefetchIntervalFn(qc, 'doc-test-id')
    const doc = makeDocument('processing', 'ready')
    expect(refetchInterval({ state: { data: doc, dataUpdateCount: 40 } })).toBe(3000)
  })

  it('stops polling once dataUpdateCount exceeds 40 even if a status is still active', async () => {
    /**Should give up polling after ~2 minutes (40 × 3s) to avoid hammering the
     * backend forever if a Celery worker is stuck */
    const qc = makeQueryClient()
    mockGetById.mockResolvedValue(makeDocument('processing', 'pending'))

    renderHook(() => useDocument('doc-test-id'), { wrapper: makeWrapper(qc) })
    await waitFor(() => expect(mockGetById).toHaveBeenCalled())

    const refetchInterval = getRefetchIntervalFn(qc, 'doc-test-id')
    const doc = makeDocument('processing', 'pending')
    expect(refetchInterval({ state: { data: doc, dataUpdateCount: 41 } })).toBe(false)
  })

  it('does not apply the cap once both statuses are already terminal', async () => {
    /**The cap only matters while actively polling — a terminal doc must return
     * false regardless of how many updates have accumulated */
    const qc = makeQueryClient()
    mockGetById.mockResolvedValue(makeDocument('completed', 'ready'))

    renderHook(() => useDocument('doc-test-id'), { wrapper: makeWrapper(qc) })
    await waitFor(() => expect(mockGetById).toHaveBeenCalled())

    const refetchInterval = getRefetchIntervalFn(qc, 'doc-test-id')
    const doc = makeDocument('completed', 'ready')
    expect(refetchInterval({ state: { data: doc, dataUpdateCount: 100 } })).toBe(false)
  })
})

// ─── useDocument — enabled flag ───────────────────────────────────────────────

describe('useDocument — enabled flag', () => {
  it('does not fire an API request when id is empty string', async () => {
    /**Should be a no-op guard — empty id means no document to fetch */
    const qc = makeQueryClient()

    const { result } = renderHook(() => useDocument(''), {
      wrapper: makeWrapper(qc),
    })

    // Query is disabled when id is falsy
    expect(result.current.fetchStatus).toBe('idle')
    expect(mockGetById).not.toHaveBeenCalled()
  })

  it('fires an API request when id is a non-empty string', async () => {
    /**Should enable the query and call the API when a valid id is provided */
    const qc = makeQueryClient()
    mockGetById.mockResolvedValue(makeDocument('completed'))

    const { result } = renderHook(() => useDocument('some-document-id'), {
      wrapper: makeWrapper(qc),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockGetById).toHaveBeenCalledWith('some-document-id')
  })
})

// ─── useRegenerateThumbnail ───────────────────────────────────────────────────

describe('useRegenerateThumbnail', () => {
  it('calls documentsApi.regenerateThumbnail with the given document id', async () => {
    /**Should trigger the backend regeneration endpoint for the correct document */
    const qc = makeQueryClient()
    mockRegenerateThumbnail.mockResolvedValue(undefined)

    const { result } = renderHook(() => useRegenerateThumbnail(), {
      wrapper: makeWrapper(qc),
    })

    result.current.mutate('doc-test-id')

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mockRegenerateThumbnail).toHaveBeenCalledWith('doc-test-id')
  })

  it('invalidates the document detail query on success', async () => {
    /**Should refetch the document so the UI picks up thumbnail_status=processing
     * after the regenerate call succeeds */
    const qc = makeQueryClient()
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
    mockRegenerateThumbnail.mockResolvedValue(undefined)

    const { result } = renderHook(() => useRegenerateThumbnail(), {
      wrapper: makeWrapper(qc),
    })

    result.current.mutate('doc-test-id')

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: documentKeys.detail('doc-test-id') })
  })

  it('does not invalidate any query when the mutation fails', async () => {
    /**Should leave the cache untouched on failure — no false "ready" flash */
    const qc = makeQueryClient()
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
    mockRegenerateThumbnail.mockRejectedValue(new Error('network error'))

    const { result } = renderHook(() => useRegenerateThumbnail(), {
      wrapper: makeWrapper(qc),
    })

    result.current.mutate('doc-test-id')

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(invalidateSpy).not.toHaveBeenCalled()
  })
})
