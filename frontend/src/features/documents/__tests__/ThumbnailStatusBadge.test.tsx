/**
 * Tests for ThumbnailStatusBadge component.
 *
 * Verifies that the correct label text and CSS classes are rendered for each
 * ThumbnailStatus value. The component maps each status to a fixed CONFIG
 * entry — these tests lock in that mapping so a future refactor cannot
 * silently break the UI.
 *
 * Animation class (animate-pulse) is verified for `processing` because it is
 * a visible indicator that a background task is in progress.
 *
 * Mirrors the structure of OcrStatusBadge.test.tsx (analogous component).
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ThumbnailStatusBadge } from '../components/ThumbnailStatusBadge'
import type { ThumbnailStatus } from '@/shared/types'

// ─── Helper ───────────────────────────────────────────────────────────────────

function renderBadge(status: ThumbnailStatus) {
  return render(<ThumbnailStatusBadge status={status} />)
}

// ─── Label text ───────────────────────────────────────────────────────────────

describe('ThumbnailStatusBadge — label text', () => {
  it('renders "Miniatura pendiente" for status pending', () => {
    /**Should show a waiting indicator to the user when thumbnail generation has not started */
    renderBadge('pending')
    expect(screen.getByText('Miniatura pendiente')).toBeInTheDocument()
  })

  it('renders "Generando miniatura..." for status processing', () => {
    /**Should show an in-progress indicator while the thumbnail is being generated */
    renderBadge('processing')
    expect(screen.getByText('Generando miniatura...')).toBeInTheDocument()
  })

  it('renders "Miniatura lista" for status ready', () => {
    /**Should confirm to the user that the thumbnail finished successfully */
    renderBadge('ready')
    expect(screen.getByText('Miniatura lista')).toBeInTheDocument()
  })

  it('renders "Miniatura fallida" for status failed', () => {
    /**Should clearly signal to the user that thumbnail generation encountered an error */
    renderBadge('failed')
    expect(screen.getByText('Miniatura fallida')).toBeInTheDocument()
  })

  it('renders "Sin miniatura" for status skipped', () => {
    /**Should indicate that thumbnail generation was intentionally bypassed */
    renderBadge('skipped')
    expect(screen.getByText('Sin miniatura')).toBeInTheDocument()
  })
})

// ─── CSS classes / visual state ───────────────────────────────────────────────

describe('ThumbnailStatusBadge — visual state', () => {
  it('processing badge has animate-pulse class for animation', () => {
    /**Should visually indicate ongoing work via CSS animation */
    renderBadge('processing')
    const badge = screen.getByText('Generando miniatura...')
    expect(badge).toHaveClass('animate-pulse')
  })

  it('ready badge does NOT have animate-pulse class', () => {
    /**Ready state is static — animation would be misleading */
    renderBadge('ready')
    const badge = screen.getByText('Miniatura lista')
    expect(badge).not.toHaveClass('animate-pulse')
  })

  it('pending badge does NOT have animate-pulse class', () => {
    /**Pending state is waiting, not actively working — no animation needed */
    renderBadge('pending')
    const badge = screen.getByText('Miniatura pendiente')
    expect(badge).not.toHaveClass('animate-pulse')
  })

  it('failed badge has red color classes', () => {
    /**Should use red styling to draw attention to the failure state */
    renderBadge('failed')
    const badge = screen.getByText('Miniatura fallida')
    expect(badge).toHaveClass('text-red-700')
  })

  it('ready badge has green color classes', () => {
    /**Should use green styling to confirm successful processing */
    renderBadge('ready')
    const badge = screen.getByText('Miniatura lista')
    expect(badge).toHaveClass('text-green-700')
  })

  it('processing badge has blue color classes', () => {
    /**Should use blue styling to indicate an active in-progress state */
    renderBadge('processing')
    const badge = screen.getByText('Generando miniatura...')
    expect(badge).toHaveClass('text-blue-700')
  })

  it('pending badge has gray color classes', () => {
    /**Should use neutral gray to indicate a queued/waiting state */
    renderBadge('pending')
    const badge = screen.getByText('Miniatura pendiente')
    expect(badge).toHaveClass('text-gray-600')
  })

  it('skipped badge has gray color classes', () => {
    /**Should use muted gray to indicate an intentionally skipped state */
    renderBadge('skipped')
    const badge = screen.getByText('Sin miniatura')
    expect(badge).toHaveClass('text-gray-500')
  })
})

// ─── Rendering completeness ───────────────────────────────────────────────────

describe('ThumbnailStatusBadge — rendering completeness', () => {
  it('renders without throwing for every valid ThumbnailStatus value', () => {
    /**Should not crash for any status — exhaustive render check for each value */
    const statuses: ThumbnailStatus[] = ['pending', 'processing', 'ready', 'failed', 'skipped']

    statuses.forEach((status) => {
      expect(() => {
        const { unmount } = render(<ThumbnailStatusBadge status={status} />)
        unmount()
      }).not.toThrow()
    })
  })

  it('each status renders exactly one text label in the DOM', () => {
    /**Should render a single label per status — no duplicate or ghost nodes */
    const expected: Record<ThumbnailStatus, string> = {
      pending: 'Miniatura pendiente',
      processing: 'Generando miniatura...',
      ready: 'Miniatura lista',
      failed: 'Miniatura fallida',
      skipped: 'Sin miniatura',
    }

    const statuses: ThumbnailStatus[] = ['pending', 'processing', 'ready', 'failed', 'skipped']

    statuses.forEach((status) => {
      const { unmount } = render(<ThumbnailStatusBadge status={status} />)
      const label = expected[status]
      const matches = screen.getAllByText(label)
      expect(matches).toHaveLength(1)
      unmount()
    })
  })

  it('does not crash and uses the defensive fallback for an unmapped status value', () => {
    /**Should never throw for a status outside the known enum — e.g. a stale
     * value from an API contract change — and must render some text instead
     * of an empty badge. */
    const unknownStatus = 'archived' as unknown as ThumbnailStatus

    expect(() => renderBadge(unknownStatus)).not.toThrow()
    expect(screen.getByText('archived')).toBeInTheDocument()
  })

  it('falls back to "Desconocido" when status is undefined', () => {
    /**Should render a defensive label instead of crashing when status is
     * missing entirely — mirrors the case where SearchResult (which omits
     * thumbnail fields) is cast to Document. */
    const undefinedStatus = undefined as unknown as ThumbnailStatus

    expect(() => renderBadge(undefinedStatus)).not.toThrow()
    expect(screen.getByText('Desconocido')).toBeInTheDocument()
  })
})
