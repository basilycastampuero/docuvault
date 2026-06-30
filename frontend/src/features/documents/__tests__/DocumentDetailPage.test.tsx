/**
 * Regression test: Bug fix — TypeError on DocumentDetailPage when accessing
 * document.created_by.email (nested) on a response that uses the flat field.
 *
 * Root cause: the JSX rendered {document.created_by.email}. The API — and the
 * Document type — returns a flat field created_by_email: string, not a nested
 * object. This caused:
 *   TypeError: Cannot read properties of undefined (reading 'email')
 *
 * Fix: changed JSX to {document.created_by_email}.
 *
 * These tests use MSW to intercept GET /documents/:id/ and render the full page
 * component. They verify:
 *   1. The component mounts without a TypeError crash.
 *   2. The creator email from created_by_email appears in the "Creado por" row
 *      of the metadata information panel.
 *
 * A viewer-role user is used so canWrite=false, which avoids rendering
 * DocumentMetadataForm and the "Re-procesar OCR" button, keeping the test focused.
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'
import { useAuthStore } from '@/features/auth/store'
import type { Document, DocumentVersion, PaginatedMeta, UserProfile } from '@/shared/types'
import { DocumentDetailPage } from '../pages/DocumentDetailPage'

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

const MOCK_DOCUMENT: Document = {
  id: 'doc-uuid-123',
  name: 'CEO.jpg',
  description: 'foto del CEO',
  mime_type: 'image/jpeg',
  file_size: 274349,
  checksum: 'abc123',
  status: 'draft',
  ocr_status: 'pending',
  version: 1,
  tags: ['importante'],
  metadata: {},
  folder: null,
  folder_name: null,
  // Flat field — the fix that this regression test guards.
  created_by_email: 'editor@acme.com',
  created_at: '2026-06-30T17:49:49.454403Z',
  updated_at: '2026-06-30T17:49:49.556866Z',
}

const VIEWER_USER: UserProfile = {
  id: 'viewer-1',
  email: 'viewer@acme.com',
  first_name: 'View',
  last_name: 'Er',
  role: 'viewer',
  organization_id: 'org-1',
  organization_name: 'Test Org',
  is_active: true,
}

// Empty versions response — DocumentVersionList always renders in the default tab.
const EMPTY_VERSIONS_RESPONSE: { data: DocumentVersion[]; meta: PaginatedMeta } = {
  data: [],
  meta: { count: 0, next: null, previous: null, page: 1, page_size: 20 },
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

// Renders DocumentDetailPage with /documents/doc-uuid-123 as the active route.
function renderPage() {
  const queryClient = makeQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/documents/doc-uuid-123']}>
        <Routes>
          <Route path="/documents/:id" element={<DocumentDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('DocumentDetailPage — regression: created_by_email flat field', () => {
  it('mounts without crashing when the document has the flat created_by_email field', async () => {
    /**
     * Should load the document and render without a TypeError. Before the fix,
     * accessing document.created_by.email where created_by is undefined caused
     * the component to crash on every document detail page load.
     */
    useAuthStore.setState({ accessToken: 'test-token', user: VIEWER_USER })

    server.use(
      http.get('http://localhost:8000/api/v1/documents/doc-uuid-123/', () =>
        HttpResponse.json({ data: MOCK_DOCUMENT, meta: {} }),
      ),
      http.get('http://localhost:8000/api/v1/documents/doc-uuid-123/versions/', () =>
        HttpResponse.json(EMPTY_VERSIONS_RESPONSE),
      ),
    )

    renderPage()

    // Wait for the document name — confirms the page loaded successfully.
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'CEO.jpg' })).toBeInTheDocument()
    })
  })

  it('renders the creator email from created_by_email in the information panel', async () => {
    /**
     * Should display "editor@acme.com" from document.created_by_email in the
     * "Creado por" row of the right-hand information card. Before the fix, the
     * template tried to render document.created_by.email — undefined on the
     * actual API shape — causing the crash described above.
     */
    useAuthStore.setState({ accessToken: 'test-token', user: VIEWER_USER })

    server.use(
      http.get('http://localhost:8000/api/v1/documents/doc-uuid-123/', () =>
        HttpResponse.json({ data: MOCK_DOCUMENT, meta: {} }),
      ),
      http.get('http://localhost:8000/api/v1/documents/doc-uuid-123/versions/', () =>
        HttpResponse.json(EMPTY_VERSIONS_RESPONSE),
      ),
    )

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('editor@acme.com')).toBeInTheDocument()
    })
  })
})
