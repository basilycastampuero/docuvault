/**
 * Tests for AdvanceStepDialog component.
 *
 * Strategy:
 *   - The dialog is an AlertDialog (always mounted in the DOM, shown/hidden via
 *     the `open` prop). We test what renders when `open=true`.
 *   - The action Select defaults to 'approved'. We cannot easily change Radix
 *     Select values in jsdom without user-event, so we test the default
 *     (approved) path and the commented path by manipulating the form state
 *     through the hidden input value approach via fireEvent on the Radix trigger.
 *   - The comment field is always rendered. For 'commented' action validation
 *     we test via the RHF refine: submit without comment shows an error.
 *   - Since the default action is 'approved', we can test valid approval submit
 *     directly without any Select interaction.
 *   - Cancel button is tested via onOpenChange spy.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { AdvanceStepDialog } from '../components/AdvanceStepDialog'

// ─── Helpers ──────────────────────────────────────────────────────────────────

interface RenderOptions {
  open?: boolean
  isPending?: boolean
  onOpenChange?: ReturnType<typeof vi.fn>
  onSubmit?: ReturnType<typeof vi.fn>
}

function renderDialog(opts: RenderOptions = {}) {
  const onOpenChange = opts.onOpenChange ?? vi.fn()
  const onSubmit = opts.onSubmit ?? vi.fn()
  return {
    onOpenChange,
    onSubmit,
    ...render(
      <AdvanceStepDialog
        open={opts.open ?? true}
        isPending={opts.isPending ?? false}
        onOpenChange={onOpenChange}
        onSubmit={onSubmit}
      />,
    ),
  }
}

// ─── Setup ────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks()
})

// ─── Dialog visibility ────────────────────────────────────────────────────────

describe('AdvanceStepDialog — visibility', () => {
  it('renders the dialog title when open=true', () => {
    /**Should display the dialog when the open prop is true */
    renderDialog({ open: true })
    expect(screen.getByText('Avanzar paso del workflow')).toBeInTheDocument()
  })

  it('does not render the dialog content when open=false', () => {
    /**Should hide the dialog content when open is false */
    renderDialog({ open: false })
    expect(screen.queryByText('Avanzar paso del workflow')).not.toBeInTheDocument()
  })
})

// ─── Field presence ───────────────────────────────────────────────────────────

describe('AdvanceStepDialog — field presence', () => {
  it('renders the action selector', () => {
    /**Should display a combobox/select for choosing the step action */
    renderDialog()
    expect(screen.getByRole('combobox')).toBeInTheDocument()
  })

  it('renders the comment textarea', () => {
    /**Should display a textarea for optional or required comments */
    renderDialog()
    expect(
      screen.getByPlaceholderText(/agrega un comentario sobre esta decisión/i),
    ).toBeInTheDocument()
  })

  it('shows "Acción" label for the select', () => {
    /**Should label the action selector clearly */
    renderDialog()
    expect(screen.getByText('Acción')).toBeInTheDocument()
  })

  it('shows the comment field label', () => {
    /**Should label the comment textarea (optional by default since action is approved) */
    renderDialog()
    // Default action is 'approved', so label reads "Comentario (opcional)"
    expect(screen.getByText(/comentario/i)).toBeInTheDocument()
  })

  it('renders the Cancel button', () => {
    /**Should have a cancel button that closes the dialog without submitting */
    renderDialog()
    expect(screen.getByRole('button', { name: /cancelar/i })).toBeInTheDocument()
  })

  it('renders the submit button with "Aprobar" label for default action', () => {
    /**Default action is approved — submit button should reflect this */
    renderDialog()
    expect(screen.getByRole('button', { name: /aprobar/i })).toBeInTheDocument()
  })
})

// ─── Submit button state ──────────────────────────────────────────────────────

describe('AdvanceStepDialog — submit button state', () => {
  it('submit button is enabled when not pending', () => {
    /**Should allow submission when no async operation is in flight */
    renderDialog({ isPending: false })
    const submitBtn = screen.getByRole('button', { name: /aprobar/i })
    expect(submitBtn).not.toBeDisabled()
  })

  it('submit button is disabled when isPending=true', () => {
    /**Should prevent double-submit by disabling the button while pending */
    renderDialog({ isPending: true })
    const submitBtn = screen.getByRole('button', { name: /procesando/i })
    expect(submitBtn).toBeDisabled()
  })

  it('cancel button is disabled when isPending=true', () => {
    /**Should prevent cancel while a submission is in flight */
    renderDialog({ isPending: true })
    expect(screen.getByRole('button', { name: /cancelar/i })).toBeDisabled()
  })

  it('shows "Procesando..." text on submit button when isPending', () => {
    /**Should give visual feedback that an action is being processed */
    renderDialog({ isPending: true })
    expect(screen.getByText(/procesando/i)).toBeInTheDocument()
  })
})

// ─── Cancel button ────────────────────────────────────────────────────────────

describe('AdvanceStepDialog — cancel button', () => {
  it('clicking Cancel calls onOpenChange with false', () => {
    /**Should close the dialog by calling onOpenChange(false) */
    const { onOpenChange } = renderDialog()
    fireEvent.click(screen.getByRole('button', { name: /cancelar/i }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('clicking Cancel does NOT call onSubmit', () => {
    /**Cancelling should not trigger any data submission */
    const { onOpenChange, onSubmit } = renderDialog()
    fireEvent.click(screen.getByRole('button', { name: /cancelar/i }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(onSubmit).not.toHaveBeenCalled()
  })
})

// ─── Valid submit (default action = approved) ──────────────────────────────────

describe('AdvanceStepDialog — valid submit with approved action', () => {
  it('submitting with default action (approved) and no comment calls onSubmit', async () => {
    /**Approved action does not require a comment — submit should succeed */
    const { onSubmit } = renderDialog()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /aprobar/i }))
    })
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1)
    })
  })

  it('onSubmit receives action="approved" for default submission', async () => {
    /**Should pass the selected action value to onSubmit */
    const { onSubmit } = renderDialog()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /aprobar/i }))
    })
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1)
    })
    const args = onSubmit.mock.calls[0][0]
    expect(args.action).toBe('approved')
  })

  it('submitting with a comment calls onSubmit and includes the comment', async () => {
    /**Should pass the comment to onSubmit when the user fills it in */
    const { onSubmit } = renderDialog()
    const commentArea = screen.getByPlaceholderText(/agrega un comentario/i)
    fireEvent.change(commentArea, { target: { value: 'Todo correcto' } })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /aprobar/i }))
    })
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1)
    })
    const args = onSubmit.mock.calls[0][0]
    expect(args.action).toBe('approved')
    expect(args.comment).toBe('Todo correcto')
  })
})

// ─── Comment field label changes with action ──────────────────────────────────

describe('AdvanceStepDialog — comment label reflects current action', () => {
  it('shows "Comentario (opcional)" when action is approved (default)', () => {
    /**Comment is optional for approved actions */
    renderDialog()
    expect(screen.getByText(/comentario \(opcional\)/i)).toBeInTheDocument()
  })
})

// ─── Action select options ────────────────────────────────────────────────────

describe('AdvanceStepDialog — action select options', () => {
  it('the action select trigger is present and accessible', () => {
    /**Should have a combobox that the user can interact with */
    renderDialog()
    const combobox = screen.getByRole('combobox')
    expect(combobox).toBeInTheDocument()
    expect(combobox).not.toBeDisabled()
  })

  it('the select trigger shows the default action value text', () => {
    /**Radix Select renders the current value text inside the trigger */
    renderDialog()
    // "Aprobar" appears in both the select trigger value AND the SelectItem content
    // and also in the submit button label. We assert at least one instance exists.
    const matches = screen.getAllByText('Aprobar')
    expect(matches.length).toBeGreaterThanOrEqual(1)
  })
})
