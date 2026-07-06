/**
 * Tests for DocumentThumbnail component.
 *
 * DocumentThumbnail is a reusable tile used both in DocumentCard (grid, cover
 * fit) and DocumentDetailPage (preview card, contain fit). It has three
 * mutually exclusive render branches:
 *   1. status === 'ready' && url && !imgFailed → <img>
 *   2. status === 'processing'                 → spinner (Loader2)
 *   3. anything else (pending/failed/skipped/undefined, or an image load
 *      error) → generic FileText fallback icon
 *
 * These tests lock in that branching so a future refactor cannot silently
 * swap which branch renders for a given status, and guard the `onError`
 * degrade-to-fallback behavior explicitly (a real risk: broken presigned
 * URLs / expired MinIO links must not show a broken-image icon to the user).
 */

import { describe, it, expect } from 'vitest'
import { render, fireEvent } from '@testing-library/react'
import { DocumentThumbnail } from '../components/DocumentThumbnail'
import type { ThumbnailStatus } from '@/shared/types'

const MIME_TYPE = 'image/jpeg'
const URL = 'https://minio.local/bucket/thumb-doc-1.jpg'

describe('DocumentThumbnail — ready status with url', () => {
  it('renders an <img> with the correct src when status is ready and url is present', () => {
    /**Should show the actual thumbnail image once generation succeeded */
    const { container } = render(
      <DocumentThumbnail status="ready" url={URL} mimeType={MIME_TYPE} />,
    )

    const img = container.querySelector('img')
    expect(img).not.toBeNull()
    expect(img).toHaveAttribute('src', URL)
  })

  it('sets loading="lazy" on the rendered image', () => {
    /**Should defer offscreen thumbnail loading — important on list pages with many cards */
    const { container } = render(
      <DocumentThumbnail status="ready" url={URL} mimeType={MIME_TYPE} />,
    )

    const img = container.querySelector('img')
    expect(img).toHaveAttribute('loading', 'lazy')
  })

  it('does not render the spinner or the fallback icon when the image renders', () => {
    /**Should render exactly one visual element — no overlap between branches */
    const { container } = render(
      <DocumentThumbnail status="ready" url={URL} mimeType={MIME_TYPE} />,
    )

    expect(container.querySelector('.animate-spin')).toBeNull()
    expect(container.querySelectorAll('svg')).toHaveLength(0)
  })
})

describe('DocumentThumbnail — processing status', () => {
  it('renders a spinner instead of an image', () => {
    /**Should indicate that thumbnail generation is actively running */
    const { container } = render(
      <DocumentThumbnail status="processing" url={null} mimeType={MIME_TYPE} />,
    )

    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('.animate-spin')).not.toBeNull()
  })

  it('renders the spinner even if a stale url happens to be present', () => {
    /**Processing must win over a leftover url from a previous thumbnail generation */
    const { container } = render(
      <DocumentThumbnail status="processing" url={URL} mimeType={MIME_TYPE} />,
    )

    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('.animate-spin')).not.toBeNull()
  })
})

describe('DocumentThumbnail — fallback statuses', () => {
  const fallbackStatuses: ThumbnailStatus[] = ['pending', 'failed', 'skipped']

  it.each(fallbackStatuses)(
    'renders the generic fallback icon (no image, no spinner) for status "%s"',
    (status) => {
      /**Should degrade gracefully to a generic file icon for any non-ready, non-processing state */
      const { container } = render(
        <DocumentThumbnail status={status} url={null} mimeType={MIME_TYPE} />,
      )

      expect(container.querySelector('img')).toBeNull()
      expect(container.querySelector('.animate-spin')).toBeNull()
      expect(container.querySelectorAll('svg')).toHaveLength(1)
    },
  )

  it('renders the fallback icon when status is ready but url is null', () => {
    /**Should not attempt to render an <img> without a url even if status says ready */
    const { container } = render(
      <DocumentThumbnail status="ready" url={null} mimeType={MIME_TYPE} />,
    )

    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelectorAll('svg')).toHaveLength(1)
  })

  it('renders the fallback icon without crashing when status is undefined', () => {
    /**Should handle the SearchResult-cast-to-Document case, where thumbnail
     * fields are stripped from the type and may be undefined at runtime */
    const { container } = render(
      <DocumentThumbnail status={undefined} url={undefined} mimeType={MIME_TYPE} />,
    )

    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('.animate-spin')).toBeNull()
    expect(container.querySelectorAll('svg')).toHaveLength(1)
  })
})

describe('DocumentThumbnail — image load failure degrades to fallback', () => {
  it('falls back to the generic icon after the <img> fires an error event', () => {
    /**Should not leave a broken-image placeholder visible — a stale/expired
     * presigned URL must degrade to the same fallback used for pending/failed */
    const { container } = render(
      <DocumentThumbnail status="ready" url={URL} mimeType={MIME_TYPE} />,
    )

    const img = container.querySelector('img')
    expect(img).not.toBeNull()

    fireEvent.error(img as HTMLImageElement)

    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelectorAll('svg')).toHaveLength(1)
  })
})

describe('DocumentThumbnail — fit and className', () => {
  it('defaults to object-cover when fit is not specified', () => {
    /**Should default to cover fit for grid tiles (DocumentCard usage) */
    const { container } = render(
      <DocumentThumbnail status="ready" url={URL} mimeType={MIME_TYPE} />,
    )

    const img = container.querySelector('img')
    expect(img).toHaveClass('object-cover')
  })

  it('applies object-contain when fit="contain" is passed', () => {
    /**Should support the preview-card usage (DocumentDetailPage) without cropping */
    const { container } = render(
      <DocumentThumbnail status="ready" url={URL} mimeType={MIME_TYPE} fit="contain" />,
    )

    const img = container.querySelector('img')
    expect(img).toHaveClass('object-contain')
    expect(img).not.toHaveClass('object-cover')
  })

  it('applies a custom className to the outer wrapper', () => {
    /**Should let callers control sizing (e.g. h-10 w-10 in the card grid) */
    const { container } = render(
      <DocumentThumbnail
        status="pending"
        url={null}
        mimeType={MIME_TYPE}
        className="custom-size-class"
      />,
    )

    expect(container.querySelector('.custom-size-class')).not.toBeNull()
  })
})
