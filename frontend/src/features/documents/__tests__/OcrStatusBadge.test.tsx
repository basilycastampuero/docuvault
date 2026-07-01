/**
 * Tests for OcrStatusBadge component.
 *
 * Verifies that the correct label text and CSS classes are rendered for each
 * OcrStatus value. The component maps each status to a fixed CONFIG entry —
 * these tests lock in that mapping so a future refactor cannot silently break
 * the UI.
 *
 * Animation class (animate-pulse) is verified for `processing` because it is
 * a visible indicator that a background task is in progress.
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { OcrStatusBadge } from '../components/OcrStatusBadge'
import type { OcrStatus } from '@/shared/types'

// ─── Helper ───────────────────────────────────────────────────────────────────

function renderBadge(status: OcrStatus) {
  return render(<OcrStatusBadge status={status} />)
}

// ─── Label text ───────────────────────────────────────────────────────────────

describe('OcrStatusBadge — label text', () => {
  it('renders "Pendiente" for status pending', () => {
    /**Should show a waiting indicator to the user when OCR has not started */
    renderBadge('pending')
    expect(screen.getByText('Pendiente')).toBeInTheDocument()
  })

  it('renders "Procesando..." for status processing', () => {
    /**Should show an in-progress indicator while OCR is running */
    renderBadge('processing')
    expect(screen.getByText('Procesando...')).toBeInTheDocument()
  })

  it('renders "OCR Completado" for status completed', () => {
    /**Should confirm to the user that OCR finished successfully */
    renderBadge('completed')
    expect(screen.getByText('OCR Completado')).toBeInTheDocument()
  })

  it('renders "OCR Fallido" for status failed', () => {
    /**Should clearly signal to the user that OCR encountered an error */
    renderBadge('failed')
    expect(screen.getByText('OCR Fallido')).toBeInTheDocument()
  })

  it('renders "Omitido" for status skipped', () => {
    /**Should indicate that OCR was intentionally bypassed (e.g. Office files) */
    renderBadge('skipped')
    expect(screen.getByText('Omitido')).toBeInTheDocument()
  })
})

// ─── CSS classes / visual state ───────────────────────────────────────────────

describe('OcrStatusBadge — visual state', () => {
  it('processing badge has animate-pulse class for animation', () => {
    /**Should visually indicate ongoing work via CSS animation */
    renderBadge('processing')
    const badge = screen.getByText('Procesando...')
    expect(badge).toHaveClass('animate-pulse')
  })

  it('completed badge does NOT have animate-pulse class', () => {
    /**Completed state is static — animation would be misleading */
    renderBadge('completed')
    const badge = screen.getByText('OCR Completado')
    expect(badge).not.toHaveClass('animate-pulse')
  })

  it('pending badge does NOT have animate-pulse class', () => {
    /**Pending state is waiting, not actively working — no animation needed */
    renderBadge('pending')
    const badge = screen.getByText('Pendiente')
    expect(badge).not.toHaveClass('animate-pulse')
  })

  it('failed badge has red color classes', () => {
    /**Should use red styling to draw attention to the failure state */
    renderBadge('failed')
    const badge = screen.getByText('OCR Fallido')
    expect(badge).toHaveClass('text-red-700')
  })

  it('completed badge has green color classes', () => {
    /**Should use green styling to confirm successful processing */
    renderBadge('completed')
    const badge = screen.getByText('OCR Completado')
    expect(badge).toHaveClass('text-green-700')
  })

  it('processing badge has blue color classes', () => {
    /**Should use blue styling to indicate an active in-progress state */
    renderBadge('processing')
    const badge = screen.getByText('Procesando...')
    expect(badge).toHaveClass('text-blue-700')
  })

  it('pending badge has gray color classes', () => {
    /**Should use neutral gray to indicate a queued/waiting state */
    renderBadge('pending')
    const badge = screen.getByText('Pendiente')
    expect(badge).toHaveClass('text-gray-600')
  })

  it('skipped badge has gray color classes', () => {
    /**Should use muted gray to indicate an intentionally skipped state */
    renderBadge('skipped')
    const badge = screen.getByText('Omitido')
    expect(badge).toHaveClass('text-gray-500')
  })
})

// ─── Rendering completeness ───────────────────────────────────────────────────

describe('OcrStatusBadge — rendering completeness', () => {
  it('renders without throwing for every valid OcrStatus value', () => {
    /**Should not crash for any status — exhaustive render check for each value */
    const statuses: OcrStatus[] = ['pending', 'processing', 'completed', 'failed', 'skipped']

    statuses.forEach((status) => {
      expect(() => {
        const { unmount } = render(<OcrStatusBadge status={status} />)
        unmount()
      }).not.toThrow()
    })
  })

  it('each status renders exactly one text label in the DOM', () => {
    /**Should render a single label per status — no duplicate or ghost nodes */
    const expected: Record<OcrStatus, string> = {
      pending: 'Pendiente',
      processing: 'Procesando...',
      completed: 'OCR Completado',
      failed: 'OCR Fallido',
      skipped: 'Omitido',
    }

    const statuses: OcrStatus[] = ['pending', 'processing', 'completed', 'failed', 'skipped']

    statuses.forEach((status) => {
      const { unmount } = render(<OcrStatusBadge status={status} />)
      const label = expected[status]
      const matches = screen.getAllByText(label)
      expect(matches).toHaveLength(1)
      unmount()
    })
  })
})
