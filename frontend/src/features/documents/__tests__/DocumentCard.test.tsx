/**
 * Tests for DocumentCard — focused on the new DocumentThumbnail integration
 * (Fase 6.2). Previously the card always rendered a fixed FileText icon;
 * now it delegates to <DocumentThumbnail> using document.thumbnail_status
 * and document.thumbnail_url.
 *
 * Also covers a real production scenario: SearchPage renders DocumentCard
 * with a SearchResult cast to Document via `as unknown as Document`.
 * SearchResult omits thumbnail_status/thumbnail_url entirely, so at runtime
 * those fields are `undefined` even though the Document type claims they are
 * required. The card must not crash in that case.
 *
 * DocumentCard requires a Router context (useNavigate) and a QueryClient
 * (useDownloadDocument uses useMutation), so both are provided in the
 * render helper, mirroring the pattern used in DocumentDetailPage.test.tsx.
 */

import { describe, it, expect, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAuthStore } from '@/features/auth/store'
import type { Document, UserProfile } from '@/shared/types'
import { DocumentCard } from '../components/DocumentCard'

// ─── Fixtures ─────────────────────────────────────────────────────────────────

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

const MOCK_DOCUMENT: Document = {
  id: 'doc-uuid-123',
  name: 'contrato.pdf',
  description: '',
  mime_type: 'application/pdf',
  file_size: 204800,
  checksum: 'abc123',
  status: 'draft',
  ocr_status: 'completed',
  version: 1,
  tags: ['legal'],
  metadata: {},
  ocr_content: 'texto',
  thumbnail_status: 'ready',
  thumbnail_url: 'https://minio.local/bucket/thumb-doc-uuid-123.jpg',
  folder: null,
  folder_name: null,
  created_by_email: 'editor@acme.com',
  created_at: '2026-06-30T17:49:49.454403Z',
  updated_at: '2026-06-30T17:49:49.556866Z',
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

afterEach(() => {
  useAuthStore.setState({ accessToken: null, user: null })
})

function renderCard(document: Document) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DocumentCard document={document} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

// ─── Thumbnail rendering ──────────────────────────────────────────────────────

describe('DocumentCard — thumbnail rendering', () => {
  it('renders the document thumbnail image when thumbnail_status is ready and url is present', () => {
    /**Should show the real thumbnail instead of the old fixed FileText icon */
    useAuthStore.setState({ accessToken: 'test-token', user: VIEWER_USER })

    const { container } = renderCard(MOCK_DOCUMENT)

    const img = container.querySelector('img')
    expect(img).not.toBeNull()
    expect(img).toHaveAttribute('src', MOCK_DOCUMENT.thumbnail_url as string)
  })

  it('renders the fallback icon when thumbnail_status is pending', () => {
    /**Should not attempt to render an image before the backend has generated one */
    useAuthStore.setState({ accessToken: 'test-token', user: VIEWER_USER })

    const { container } = renderCard({
      ...MOCK_DOCUMENT,
      thumbnail_status: 'pending',
      thumbnail_url: null,
    })

    expect(container.querySelector('img')).toBeNull()
  })

  it('does not crash when thumbnail_status/thumbnail_url are undefined (SearchResult cast)', () => {
    /**
     * Regression guard: SearchPage renders DocumentCard with a SearchResult
     * cast `as unknown as Document`. SearchResult's type explicitly omits
     * thumbnail_status/thumbnail_url, so real API responses from /search/ do
     * not include those keys — they are undefined at runtime despite the
     * Document type claiming they exist.
     */
    useAuthStore.setState({ accessToken: 'test-token', user: VIEWER_USER })

    const searchResultShaped = { ...MOCK_DOCUMENT, rank: 0.5 } as Partial<Document> & {
      rank: number
    }
    delete searchResultShaped.thumbnail_status
    delete searchResultShaped.thumbnail_url

    expect(() =>
      renderCard(searchResultShaped as unknown as Document),
    ).not.toThrow()
    expect(screen.getByText('contrato.pdf')).toBeInTheDocument()
  })
})

// ─── General card content ─────────────────────────────────────────────────────

describe('DocumentCard — general content', () => {
  it('renders the document name, file type badge and OCR status badge', () => {
    /**Should surface the key metadata a user scans a card grid for */
    useAuthStore.setState({ accessToken: 'test-token', user: VIEWER_USER })

    renderCard(MOCK_DOCUMENT)

    expect(screen.getByText('contrato.pdf')).toBeInTheDocument()
    expect(screen.getByText('PDF')).toBeInTheDocument()
    expect(screen.getByText('OCR Completado')).toBeInTheDocument()
  })
})
