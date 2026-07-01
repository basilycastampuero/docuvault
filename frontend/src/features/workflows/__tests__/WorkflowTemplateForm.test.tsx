/**
 * Tests for WorkflowTemplateForm component.
 *
 * Rendering context:
 *   react-hook-form (v7) registers fields by dispatching native events on
 *   hidden <input> elements it creates in jsdom. jsdom processes these events
 *   synchronously, which triggers React's error recovery path in a context
 *   where the FormFieldContext has not been re-established. This causes
 *   shadcn's `FormLabel` (which calls `useFormField()`) to throw.
 *
 *   Fix: mock `@/components/ui/form` with safe wrappers that (a) still wire
 *   react-hook-form's FormProvider / Controller correctly so validation and
 *   useFieldArray work, and (b) replace FormLabel/FormControl/FormMessage with
 *   plain elements that don't depend on the FormFieldContext chain.
 *
 *   Also mock WorkflowStepEditor with a plain-HTML implementation so Radix
 *   Select portals don't add additional DOM noise.
 *
 *   These mocks let us test the form's own logic:
 *     - Field array manipulation (add/remove steps)
 *     - zod validation error display for the template name field
 *     - onSubmit shape
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import React from 'react'
import {
  Controller,
  FormProvider,
  useFormContext,
  type ControllerProps,
  type FieldPath,
  type FieldValues,
} from 'react-hook-form'

// ─── Mock @/components/ui/form ────────────────────────────────────────────────
// We keep FormProvider/Controller wiring intact but replace the context-
// dependent display components with safe HTML equivalents.

vi.mock('@/components/ui/form', () => {
  const FormFieldContext = React.createContext<{ name: string } | null>(null)
  const FormItemContext = React.createContext<{ id: string } | null>(null)

  const Form = FormProvider

  const FormField = <
    TFieldValues extends FieldValues = FieldValues,
    TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>
  >(
    props: ControllerProps<TFieldValues, TName>,
  ) => (
    <FormFieldContext.Provider value={{ name: props.name }}>
      <Controller {...props} />
    </FormFieldContext.Provider>
  )

  const FormItem = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
    ({ children, ...props }, ref) => {
      const id = React.useId()
      return (
        <FormItemContext.Provider value={{ id }}>
          <div ref={ref} {...props}>
            {children}
          </div>
        </FormItemContext.Provider>
      )
    },
  )
  FormItem.displayName = 'FormItem'

  // Safe FormLabel: renders a plain <label> without useFormField
  const FormLabel = React.forwardRef<HTMLLabelElement, React.LabelHTMLAttributes<HTMLLabelElement>>(
    ({ children, ...props }, ref) => (
      <label ref={ref} {...props}>
        {children}
      </label>
    ),
  )
  FormLabel.displayName = 'FormLabel'

  // Safe FormControl: renders a plain wrapper without aria-invalid magic
  const FormControl = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
    ({ children, ...props }, ref) => (
      <div ref={ref} {...props}>
        {children}
      </div>
    ),
  )
  FormControl.displayName = 'FormControl'

  // Safe FormMessage: reads error from RHF context for the current field
  const FormMessage = React.forwardRef<
    HTMLParagraphElement,
    React.HTMLAttributes<HTMLParagraphElement>
  >(({ children, ...props }, ref) => {
    const fieldCtx = React.useContext(FormFieldContext)
    const { formState } = useFormContext()

    let errorMsg: string | undefined
    if (fieldCtx) {
      const parts = fieldCtx.name.split('.')
      // Traverse the error object by path parts
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let node: any = formState.errors
      for (const part of parts) {
        node = node?.[part]
        if (!node) break
      }
      errorMsg = node?.message as string | undefined
    }

    const body = errorMsg ?? children
    if (!body) return null
    return (
      <p ref={ref} role="alert" {...props}>
        {body}
      </p>
    )
  })
  FormMessage.displayName = 'FormMessage'

  const FormDescription = React.forwardRef<
    HTMLParagraphElement,
    React.HTMLAttributes<HTMLParagraphElement>
  >(({ children, ...props }, ref) => (
    <p ref={ref} {...props}>
      {children}
    </p>
  ))
  FormDescription.displayName = 'FormDescription'

  return {
    Form,
    FormField,
    FormItem,
    FormLabel,
    FormControl,
    FormMessage,
    FormDescription,
    useFormField: () => ({ id: 'mock-id', name: 'mock', formItemId: 'mock-form-item' }),
  }
})

// ─── Mock WorkflowStepEditor ──────────────────────────────────────────────────
// Removes Radix Select portal from the tree — we test step list management
// via the add/remove buttons, which are part of WorkflowTemplateForm itself.

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
      <input placeholder="Ej: Revisión legal" aria-label={`Nombre del paso ${index}`} />
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

// Import component AFTER mocks are in place
import { WorkflowTemplateForm } from '../components/WorkflowTemplateForm'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function renderForm(opts?: {
  onSubmit?: ReturnType<typeof vi.fn>
  isPending?: boolean
  submitLabel?: string
}) {
  const onSubmit = opts?.onSubmit ?? vi.fn()
  return {
    onSubmit,
    ...render(
      <WorkflowTemplateForm
        onSubmit={onSubmit}
        isPending={opts?.isPending ?? false}
        submitLabel={opts?.submitLabel}
      />,
    ),
  }
}

// ─── Setup ────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks()
})

// ─── Initial render ───────────────────────────────────────────────────────────

describe('WorkflowTemplateForm — initial render', () => {
  it('renders the template name input', () => {
    /**Should display a text input for the workflow template name */
    renderForm()
    expect(screen.getByPlaceholderText(/aprobación de contratos/i)).toBeInTheDocument()
  })

  it('renders the description textarea', () => {
    /**Should display an optional textarea for the workflow description */
    renderForm()
    expect(screen.getByPlaceholderText(/describe el propósito/i)).toBeInTheDocument()
  })

  it('renders the "Agregar paso" button', () => {
    /**Should have a button to add more steps to the workflow */
    renderForm()
    expect(screen.getByRole('button', { name: /agregar paso/i })).toBeInTheDocument()
  })

  it('renders with exactly one step editor by default', () => {
    /**Should start with one step editor visible */
    renderForm()
    expect(screen.getByTestId('step-editor-0')).toBeInTheDocument()
    expect(screen.queryByTestId('step-editor-1')).not.toBeInTheDocument()
  })

  it('renders the submit button with default label "Crear plantilla"', () => {
    /**Should show the default submit label when submitLabel prop is not provided */
    renderForm()
    expect(screen.getByRole('button', { name: /crear plantilla/i })).toBeInTheDocument()
  })

  it('renders a custom submitLabel when provided', () => {
    /**Should use the provided submitLabel instead of the default */
    renderForm({ submitLabel: 'Guardar cambios' })
    expect(screen.getByRole('button', { name: /guardar cambios/i })).toBeInTheDocument()
  })

  it('renders the submit button as disabled when isPending is true', () => {
    /**Should prevent double-submit by disabling the button while pending */
    renderForm({ isPending: true })
    const button = screen.getByRole('button', { name: /guardando/i })
    expect(button).toBeDisabled()
  })

  it('shows "Guardando..." text on submit button when isPending', () => {
    /**Should give visual feedback that a save is in progress */
    renderForm({ isPending: true })
    expect(screen.getByText(/guardando/i)).toBeInTheDocument()
  })
})

// ─── Adding steps ─────────────────────────────────────────────────────────────

describe('WorkflowTemplateForm — adding steps', () => {
  it('clicking "Agregar paso" adds a second step editor', async () => {
    /**Should render a new step editor each time the add button is clicked */
    renderForm()
    fireEvent.click(screen.getByRole('button', { name: /agregar paso/i }))
    await waitFor(() => {
      expect(screen.getByTestId('step-editor-1')).toBeInTheDocument()
    })
  })

  it('clicking "Agregar paso" twice produces three step editors', async () => {
    /**Should allow arbitrary step counts — each click adds exactly one editor */
    renderForm()
    const addButton = screen.getByRole('button', { name: /agregar paso/i })
    fireEvent.click(addButton)
    fireEvent.click(addButton)
    await waitFor(() => {
      expect(screen.getByTestId('step-editor-2')).toBeInTheDocument()
    })
  })

  it('the delete button is disabled when there is only one step', () => {
    /**Should prevent removing the last step — the form requires at least one */
    renderForm()
    const removeBtn = screen.getByRole('button', { name: /eliminar paso 0/i })
    expect(removeBtn).toBeDisabled()
  })

  it('the delete button is enabled when there are two steps', async () => {
    /**Should allow removing a step when there are multiple steps */
    renderForm()
    fireEvent.click(screen.getByRole('button', { name: /agregar paso/i }))
    await waitFor(() => {
      const removeBtn = screen.getByRole('button', { name: /eliminar paso 0/i })
      expect(removeBtn).not.toBeDisabled()
    })
  })

  it('clicking remove on the second step removes that step editor', async () => {
    /**Should decrease the step count when a remove button is clicked */
    renderForm()
    fireEvent.click(screen.getByRole('button', { name: /agregar paso/i }))
    await waitFor(() => {
      expect(screen.getByTestId('step-editor-1')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: /eliminar paso 1/i }))
    await waitFor(() => {
      expect(screen.queryByTestId('step-editor-1')).not.toBeInTheDocument()
    })
  })
})

// ─── Template name validation ─────────────────────────────────────────────────

describe('WorkflowTemplateForm — template name validation', () => {
  it('shows "El nombre es obligatorio" when submitting without a template name', async () => {
    /**Should reject submission when the template name field is empty */
    renderForm()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /crear plantilla/i }))
    })
    await waitFor(() => {
      expect(screen.getByText(/el nombre es obligatorio/i)).toBeInTheDocument()
    })
  })

  it('does NOT call onSubmit when template name is empty', async () => {
    /**onSubmit must never be called when required fields fail validation */
    const { onSubmit } = renderForm()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /crear plantilla/i }))
    })
    await waitFor(() => {
      expect(screen.getByText(/el nombre es obligatorio/i)).toBeInTheDocument()
    })
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('clears the name error after filling in the template name', async () => {
    /**Filling in the name after a failed submit should suppress the error */
    renderForm()
    // Trigger validation
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /crear plantilla/i }))
    })
    await waitFor(() => {
      expect(screen.getByText(/el nombre es obligatorio/i)).toBeInTheDocument()
    })
    // Fill the name — error should clear
    fireEvent.change(
      screen.getByPlaceholderText(/aprobación de contratos/i),
      { target: { value: 'Workflow de contratos' } },
    )
    await waitFor(() => {
      expect(screen.queryByText(/el nombre es obligatorio/i)).not.toBeInTheDocument()
    })
  })
})
