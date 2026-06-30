/**
 * Regression test: Bug fix — TypeError on DocumentVersionList when accessing
 * version.created_by.email (nested) on a response that uses the flat field.
 *
 * Root cause: the "Subido por" table column rendered {version.created_by.email}.
 * The API — and the DocumentVersion type — returns a flat field
 * created_by_email: string, not a nested object. This caused:
 *   TypeError: Cannot read properties of undefined (reading 'email')
 *   on every document detail page that had existing versions.
 *
 * Fix: changed JSX to {version.created_by_email}.
 *
 * These tests use MSW to intercept GET /documents/:id/versions/ and render
 * the component directly (it accepts `document` as a prop). They verify:
 *   1. The component mounts without a TypeError crash.
 *   2. The uploader email from created_by_email appears in the versions table.
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'
import { useAuthStore } from '@/features/auth/store'
import type { Document, DocumentVersion, PaginatedMeta } from '@/shared/types'
import { DocumentVersionList } from '../components/DocumentVersionList'

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
  tags: [],
  metadata: {},
  folder: null,
  folder_name: null,
  created_by_email: 'editor@acme.com',
  created_at: '2026-06-30T17:49:49.454403Z',
  updated_at: '2026-06-30T17:49:49.556866Z',
}

const MOCK_VERSION: DocumentVersion = {
  id: 'ver-uuid-123',
  version_number: 1,
  file_size: 274349,
  mime_type: 'image/jpeg',
  checksum: 'abc123',
  change_description: 'Initial version',
  // Flat field — the fix that this regression test guards.
  created_by_email: 'editor@acme.com',
  created_at: '2026-06-30T17:49:49.558701Z',
}

const VERSIONS_RESPONSE: { data: DocumentVersion[]; meta: PaginatedMeta } = {
  data: [MOCK_VERSION],
  meta: { count: 1, next: null, previous: null, page: 1, page_size: 20 },
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

// The component is pure-prop — no router context needed.
function renderVersionList() {
  const queryClient = makeQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <DocumentVersionList document={MOCK_DOCUMENT} />
    </QueryClientProvider>,
  )
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('DocumentVersionList — regression: created_by_email flat field', () => {
  it('mounts without crashing when versions use the flat created_by_email field', async () => {
    /**
     * Should load version data and render the table without a TypeError. Before
     * the fix, accessing version.created_by.email where created_by is undefined
     * crashed the "Subido por" column on every document with at least one version.
     */
    // No auth role needed — upload button is hidden, viewer access is default.
    server.use(
      http.get('http://localhost:8000/api/v1/documents/doc-uuid-123/versions/', () =>
        HttpResponse.json(VERSIONS_RESPONSE),
      ),
    )

    renderVersionList()

    // Wait for the version number cell — confirms the table rendered without crash.
    await waitFor(() => {
      expect(screen.getByText('v1')).toBeInTheDocument()
    })
  })

  it('renders the uploader email from created_by_email in the "Subido por" column', async () => {
    /**
     * Should display "editor@acme.com" from version.created_by_email in the
     * "Subido por" table column. Before the fix, the template tried to render
     * version.created_by.email which was undefined on the flat-field API shape,
     * crashing the component for any document that had existing version history.
     */
    server.use(
      http.get('http://localhost:8000/api/v1/documents/doc-uuid-123/versions/', () =>
        HttpResponse.json(VERSIONS_RESPONSE),
      ),
    )

    renderVersionList()

    await waitFor(() => {
      expect(screen.getByText('editor@acme.com')).toBeInTheDocument()
    })
  })
})
