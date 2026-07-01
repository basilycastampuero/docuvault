/**
 * Regression test: Bug fix — <FormLabel> outside <FormField> crash on mount.
 *
 * Root cause: the "Pasos del workflow" section header used <FormLabel>, which
 * calls useFormField(). useFormField() throws "useFormField should be used
 * within <FormField>" when rendered outside a FormFieldContext provider —
 * i.e., outside a <FormField> wrapper.
 *
 * Fix (WorkflowTemplateForm.tsx): replaced <FormLabel> with a plain <label>
 * element for the "Pasos del workflow" heading. All other <FormLabel> elements
 * remain inside their respective <FormField> contexts where useFormField() is safe.
 *
 * This file intentionally does NOT mock @/components/ui/form so the real shadcn
 * useFormField() runs during render. If <FormLabel> is placed back outside
 * <FormField>, the real useFormField() throws synchronously on mount and this
 * test fails — catching the regression.
 *
 * WorkflowStepEditor is mocked to avoid Radix Select portal noise in jsdom,
 * matching the approach in WorkflowTemplateForm.test.tsx.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { WorkflowTemplateForm } from '../components/WorkflowTemplateForm'

// ─── Mock WorkflowStepEditor ──────────────────────────────────────────────────
// Replaces the Radix Select-heavy editor with a plain HTML stub. The step-list
// management logic under test lives in WorkflowTemplateForm itself, not here.

vi.mock('../components/WorkflowStepEditor', () => ({
  WorkflowStepEditor: ({
    index,
    onRemove,
    canRemove,
  }: {
    index: number
    control: unknown
    onRemove: () => void
    canRemove: boolean
  }) => (
    <div data-testid={`step-editor-${index}`}>
      <button
        type="button"
        aria-label={`Eliminar paso ${index}`}
        onClick={onRemove}
        disabled={!canRemove}
      >
        Eliminar
      </button>
    </div>
  ),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

// ─── Regression guard ─────────────────────────────────────────────────────────

describe('WorkflowTemplateForm — regression: FormLabel outside FormField crash', () => {
  it('mounts without crash and renders the "Pasos del workflow" section label', () => {
    /**
     * Should render the "Pasos del workflow" label as a plain <label> that does
     * not call useFormField(). Regression guard: if <FormLabel> is placed outside
     * <FormField> the real shadcn useFormField() throws on mount and this test
     * fails with "useFormField should be used within <FormField>".
     */
    render(
      <WorkflowTemplateForm
        onSubmit={vi.fn()}
        isPending={false}
      />,
    )
    expect(screen.getByText('Pasos del workflow')).toBeInTheDocument()
  })
})
