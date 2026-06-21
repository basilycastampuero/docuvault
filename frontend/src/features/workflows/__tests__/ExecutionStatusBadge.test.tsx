/**
 * Tests for ExecutionStatusBadge component.
 *
 * Verifies that each WorkflowStatus maps to the correct label text and CSS
 * classes. The `in_progress` status is the only one that carries the
 * `animate-pulse` class — tests lock in this invariant so a future refactor
 * cannot silently break the visual feedback for active executions.
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ExecutionStatusBadge } from '../components/ExecutionStatusBadge'
import type { WorkflowStatus } from '@/shared/types'

// ─── Helper ───────────────────────────────────────────────────────────────────

function renderBadge(status: WorkflowStatus) {
  return render(<ExecutionStatusBadge status={status} />)
}

// ─── Label text ───────────────────────────────────────────────────────────────

describe('ExecutionStatusBadge — label text', () => {
  it('renders "Pendiente" for status pending', () => {
    /**Should show a waiting indicator when the execution has not started yet */
    renderBadge('pending')
    expect(screen.getByText('Pendiente')).toBeInTheDocument()
  })

  it('renders "En progreso" for status in_progress', () => {
    /**Should show an active indicator while the workflow is being executed */
    renderBadge('in_progress')
    expect(screen.getByText('En progreso')).toBeInTheDocument()
  })

  it('renders "Completado" for status completed', () => {
    /**Should confirm to the user that the workflow finished successfully */
    renderBadge('completed')
    expect(screen.getByText('Completado')).toBeInTheDocument()
  })

  it('renders "Rechazado" for status rejected', () => {
    /**Should clearly signal that the workflow was rejected at some step */
    renderBadge('rejected')
    expect(screen.getByText('Rechazado')).toBeInTheDocument()
  })

  it('renders "Cancelado" for status cancelled', () => {
    /**Should indicate that the workflow was explicitly cancelled */
    renderBadge('cancelled')
    expect(screen.getByText('Cancelado')).toBeInTheDocument()
  })
})

// ─── CSS classes / visual state ───────────────────────────────────────────────

describe('ExecutionStatusBadge — visual state', () => {
  it('in_progress badge has animate-pulse class for animation', () => {
    /**Should visually indicate ongoing work via CSS animation */
    renderBadge('in_progress')
    const badge = screen.getByText('En progreso')
    expect(badge).toHaveClass('animate-pulse')
  })

  it('pending badge does NOT have animate-pulse class', () => {
    /**Pending state is waiting, not actively running — no animation needed */
    renderBadge('pending')
    const badge = screen.getByText('Pendiente')
    expect(badge).not.toHaveClass('animate-pulse')
  })

  it('completed badge does NOT have animate-pulse class', () => {
    /**Completed state is static — animating it would be misleading */
    renderBadge('completed')
    const badge = screen.getByText('Completado')
    expect(badge).not.toHaveClass('animate-pulse')
  })

  it('rejected badge does NOT have animate-pulse class', () => {
    /**Rejected state is terminal — no active work is happening */
    renderBadge('rejected')
    const badge = screen.getByText('Rechazado')
    expect(badge).not.toHaveClass('animate-pulse')
  })

  it('cancelled badge does NOT have animate-pulse class', () => {
    /**Cancelled state is terminal — no active work is happening */
    renderBadge('cancelled')
    const badge = screen.getByText('Cancelado')
    expect(badge).not.toHaveClass('animate-pulse')
  })

  it('in_progress badge has blue color classes', () => {
    /**Should use blue styling to indicate an active in-progress state */
    renderBadge('in_progress')
    const badge = screen.getByText('En progreso')
    expect(badge).toHaveClass('text-blue-700')
  })

  it('completed badge has green color classes', () => {
    /**Should use green styling to confirm successful completion */
    renderBadge('completed')
    const badge = screen.getByText('Completado')
    expect(badge).toHaveClass('text-green-700')
  })

  it('rejected badge has red color classes', () => {
    /**Should use red styling to draw attention to the failure/rejection */
    renderBadge('rejected')
    const badge = screen.getByText('Rechazado')
    expect(badge).toHaveClass('text-red-700')
  })

  it('pending badge has gray color classes', () => {
    /**Should use neutral gray to indicate a queued/waiting state */
    renderBadge('pending')
    const badge = screen.getByText('Pendiente')
    expect(badge).toHaveClass('text-gray-600')
  })

  it('cancelled badge has gray color classes', () => {
    /**Should use muted gray to indicate an intentionally cancelled state */
    renderBadge('cancelled')
    const badge = screen.getByText('Cancelado')
    expect(badge).toHaveClass('text-gray-500')
  })
})

// ─── Rendering completeness ───────────────────────────────────────────────────

describe('ExecutionStatusBadge — rendering completeness', () => {
  it('renders without throwing for every valid WorkflowStatus value', () => {
    /**Should not crash for any status — exhaustive render check */
    const statuses: WorkflowStatus[] = [
      'pending',
      'in_progress',
      'completed',
      'rejected',
      'cancelled',
    ]

    statuses.forEach((status) => {
      expect(() => {
        const { unmount } = render(<ExecutionStatusBadge status={status} />)
        unmount()
      }).not.toThrow()
    })
  })

  it('each status renders exactly one text label in the DOM', () => {
    /**Should render a single label per status — no duplicate or ghost nodes */
    const expected: Record<WorkflowStatus, string> = {
      pending: 'Pendiente',
      in_progress: 'En progreso',
      completed: 'Completado',
      rejected: 'Rechazado',
      cancelled: 'Cancelado',
    }

    const statuses: WorkflowStatus[] = [
      'pending',
      'in_progress',
      'completed',
      'rejected',
      'cancelled',
    ]

    statuses.forEach((status) => {
      const { unmount } = render(<ExecutionStatusBadge status={status} />)
      const matches = screen.getAllByText(expected[status])
      expect(matches).toHaveLength(1)
      unmount()
    })
  })
})
