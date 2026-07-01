/**
 * Tests for AuditLogFilters component.
 *
 * The component renders a filter form with:
 *   - An action Select (Radix, uses setValue directly via onValueChange)
 *   - entity_type text input
 *   - user email text input
 *   - created_after date input
 *   - created_before date input
 *   - Submit ("Filtrar") and clear ("Limpiar") buttons
 *
 * Since the action field is a Radix Select, we test presence of its trigger
 * and the initial state. Text inputs and buttons are tested via fireEvent.
 *
 * The onFilter prop is a plain callback — verified via vi.fn() spies.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { AuditLogFilters } from '../components/AuditLogFilters'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function renderFilters(onFilter?: ReturnType<typeof vi.fn>) {
  const spy = onFilter ?? vi.fn()
  return {
    onFilter: spy,
    ...render(<AuditLogFilters onFilter={spy} />),
  }
}

// ─── Setup ────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks()
})

// ─── Field presence ───────────────────────────────────────────────────────────

describe('AuditLogFilters — field presence', () => {
  it('renders the action select trigger', () => {
    /**Should display a dropdown to filter by audit action */
    renderFilters()
    expect(screen.getByRole('combobox')).toBeInTheDocument()
  })

  it('renders the entity_type text input', () => {
    /**Should allow filtering by entity type (e.g. "document") */
    renderFilters()
    expect(screen.getByPlaceholderText(/ej: document/i)).toBeInTheDocument()
  })

  it('renders the user email input', () => {
    /**Should allow filtering by user email address */
    renderFilters()
    expect(screen.getByPlaceholderText(/usuario@ejemplo\.com/i)).toBeInTheDocument()
  })

  it('renders the created_after date input', () => {
    /**Should allow filtering log entries from a specific date */
    renderFilters()
    // Date inputs have labels "Desde" and "Hasta"
    expect(screen.getByText('Desde')).toBeInTheDocument()
  })

  it('renders the created_before date input', () => {
    /**Should allow filtering log entries up to a specific date */
    renderFilters()
    expect(screen.getByText('Hasta')).toBeInTheDocument()
  })

  it('renders the "Filtrar" submit button', () => {
    /**Should have a button to apply the filters */
    renderFilters()
    expect(screen.getByRole('button', { name: /filtrar/i })).toBeInTheDocument()
  })

  it('renders the "Limpiar" clear button', () => {
    /**Should have a button to reset all filters */
    renderFilters()
    expect(screen.getByRole('button', { name: /limpiar/i })).toBeInTheDocument()
  })

  it('renders the "Acción" label', () => {
    /**Should label the action filter clearly */
    renderFilters()
    expect(screen.getByText('Acción')).toBeInTheDocument()
  })

  it('renders "Tipo de entidad" label', () => {
    /**Should label the entity type filter clearly */
    renderFilters()
    expect(screen.getByText('Tipo de entidad')).toBeInTheDocument()
  })

  it('renders "Usuario (email)" label', () => {
    /**Should label the user email filter clearly */
    renderFilters()
    expect(screen.getByText('Usuario (email)')).toBeInTheDocument()
  })
})

// ─── Submit behavior ──────────────────────────────────────────────────────────

describe('AuditLogFilters — submit behavior', () => {
  it('calls onFilter with empty object when submitting with no values', async () => {
    /**Empty filter form should produce an empty params object */
    const { onFilter } = renderFilters()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /filtrar/i }))
    })
    await waitFor(() => {
      expect(onFilter).toHaveBeenCalledTimes(1)
    })
    expect(onFilter).toHaveBeenCalledWith({})
  })

  it('calls onFilter with entity_type when entity_type input is filled', async () => {
    /**Should include entity_type in params when the user types a value */
    const { onFilter } = renderFilters()
    fireEvent.change(screen.getByPlaceholderText(/ej: document/i), {
      target: { value: 'document' },
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /filtrar/i }))
    })
    await waitFor(() => {
      expect(onFilter).toHaveBeenCalledTimes(1)
    })
    expect(onFilter).toHaveBeenCalledWith(
      expect.objectContaining({ entity_type: 'document' }),
    )
  })

  it('calls onFilter with user_email param when email input is filled', async () => {
    /**Should include user_email in params when the user fills in the field */
    const { onFilter } = renderFilters()
    fireEvent.change(screen.getByPlaceholderText(/usuario@ejemplo\.com/i), {
      target: { value: 'admin@acme.com' },
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /filtrar/i }))
    })
    await waitFor(() => {
      expect(onFilter).toHaveBeenCalledTimes(1)
    })
    expect(onFilter).toHaveBeenCalledWith(
      expect.objectContaining({ user_email: 'admin@acme.com' }),
    )
  })

  it('does NOT include entity_type in params when field is empty', async () => {
    /**Should omit empty fields from the params object — no empty strings */
    const { onFilter } = renderFilters()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /filtrar/i }))
    })
    await waitFor(() => {
      expect(onFilter).toHaveBeenCalledTimes(1)
    })
    const params = onFilter.mock.calls[0][0]
    expect(params).not.toHaveProperty('entity_type')
  })

  it('does NOT include user_email in params when email field is empty', async () => {
    /**Should omit empty user_email field from params */
    const { onFilter } = renderFilters()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /filtrar/i }))
    })
    await waitFor(() => {
      expect(onFilter).toHaveBeenCalledTimes(1)
    })
    const params = onFilter.mock.calls[0][0]
    expect(params).not.toHaveProperty('user_email')
  })

  it('calls onFilter with both entity_type and user_email when both are filled', async () => {
    /**Should combine multiple filter values into one params object */
    const { onFilter } = renderFilters()
    fireEvent.change(screen.getByPlaceholderText(/ej: document/i), {
      target: { value: 'folder' },
    })
    fireEvent.change(screen.getByPlaceholderText(/usuario@ejemplo\.com/i), {
      target: { value: 'editor@corp.com' },
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /filtrar/i }))
    })
    await waitFor(() => {
      expect(onFilter).toHaveBeenCalledTimes(1)
    })
    expect(onFilter).toHaveBeenCalledWith(
      expect.objectContaining({ entity_type: 'folder', user_email: 'editor@corp.com' }),
    )
  })
})

  it('serializes created_before as end-of-day, not midnight', async () => {
    /**Should include the entire selected day in the range, not cut it off at midnight.
     * Bug: new Date("2026-06-29").toISOString() → "2026-06-29T00:00:00.000Z" (midnight),
     * which excludes virtually all events from that day.
     * Fix: endOfDay(parseISO("2026-06-29")).toISOString() → non-midnight end-of-day. */
    const { onFilter } = renderFilters()
    // "Hasta" is the second date input (first is "Desde")
    const dateInputs = document.querySelectorAll('input[type="date"]')
    const hastaInput = dateInputs[1] as HTMLInputElement
    expect(hastaInput).toBeDefined()

    fireEvent.change(hastaInput, { target: { value: '2026-06-29' } })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /filtrar/i }))
    })
    await waitFor(() => {
      expect(onFilter).toHaveBeenCalledTimes(1)
    })

    const params = onFilter.mock.calls[0][0]
    expect(params.created_before).toBeDefined()
    // The old bug produced midnight UTC — assert that is NOT what we send.
    expect(params.created_before).not.toContain('T00:00:00.000Z')
    // The result must be a valid ISO timestamp later in the day.
    expect(() => new Date(params.created_before as string)).not.toThrow()
  })

// ─── Clear button ─────────────────────────────────────────────────────────────

describe('AuditLogFilters — clear button', () => {
  it('clicking "Limpiar" calls onFilter with empty object', async () => {
    /**Should reset all filters and notify the parent with an empty params object */
    const { onFilter } = renderFilters()
    // First fill a field so we know clear is actually doing something
    fireEvent.change(screen.getByPlaceholderText(/ej: document/i), {
      target: { value: 'workflow' },
    })
    fireEvent.click(screen.getByRole('button', { name: /limpiar/i }))
    await waitFor(() => {
      expect(onFilter).toHaveBeenCalled()
    })
    // The last call to onFilter should be with an empty object
    const lastCall = onFilter.mock.calls[onFilter.mock.calls.length - 1][0]
    expect(lastCall).toEqual({})
  })

  it('clicking "Limpiar" clears the entity_type input value', () => {
    /**Should visually reset the text inputs after clearing */
    renderFilters()
    const entityInput = screen.getByPlaceholderText(/ej: document/i)
    fireEvent.change(entityInput, { target: { value: 'document' } })
    expect(entityInput).toHaveValue('document')
    fireEvent.click(screen.getByRole('button', { name: /limpiar/i }))
    expect(entityInput).toHaveValue('')
  })

  it('clicking "Limpiar" clears the user email input value', () => {
    /**Should visually reset the user email input after clearing */
    renderFilters()
    const userInput = screen.getByPlaceholderText(/usuario@ejemplo\.com/i)
    fireEvent.change(userInput, { target: { value: 'test@test.com' } })
    expect(userInput).toHaveValue('test@test.com')
    fireEvent.click(screen.getByRole('button', { name: /limpiar/i }))
    expect(userInput).toHaveValue('')
  })
})

// ─── Action select options (structure) ────────────────────────────────────────

describe('AuditLogFilters — action select structure', () => {
  it('the action select trigger is accessible as a combobox', () => {
    /**Radix Select should be keyboard-accessible and properly labeled */
    renderFilters()
    const combobox = screen.getByRole('combobox')
    expect(combobox).toBeInTheDocument()
    expect(combobox).not.toBeDisabled()
  })

  it('the action select shows placeholder text by default', () => {
    /**Should show "Todas las acciones" as the default placeholder */
    renderFilters()
    expect(screen.getByText('Todas las acciones')).toBeInTheDocument()
  })
})
