import { useEffect, useRef } from 'react'
import { useForm, useFieldArray } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus } from 'lucide-react'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { WorkflowStepEditor } from './WorkflowStepEditor'

const USER_ROLES = [
  'super_admin',
  'org_admin',
  'supervisor',
  'editor',
  'viewer',
  'auditor',
] as const

const stepSchema = z.object({
  name: z.string().min(1, 'El nombre del paso es obligatorio'),
  required_role: z.enum(USER_ROLES),
  is_final: z.boolean(),
})

const templateSchema = z.object({
  name: z.string().min(1, 'El nombre es obligatorio').max(255),
  description: z.string().max(1000).optional(),
  steps: z
    .array(stepSchema)
    .min(1, 'Se necesita al menos un paso')
    .refine((steps) => steps.filter((s) => s.is_final).length === 1, {
      message: 'Exactamente un paso debe ser el paso final',
    }),
})

export type TemplateFormValues = z.infer<typeof templateSchema>

interface WorkflowTemplateFormProps {
  defaultValues?: Partial<TemplateFormValues>
  onSubmit: (values: TemplateFormValues) => void
  isPending: boolean
  submitLabel?: string
}

const DEFAULT_STEP: TemplateFormValues['steps'][number] = {
  name: '',
  required_role: 'editor',
  is_final: false,
}

export function WorkflowTemplateForm({
  defaultValues,
  onSubmit,
  isPending,
  submitLabel = 'Crear plantilla',
}: WorkflowTemplateFormProps) {
  const form = useForm<TemplateFormValues>({
    resolver: zodResolver(templateSchema),
    defaultValues: {
      name: '',
      description: '',
      steps: [{ ...DEFAULT_STEP }],
      ...defaultValues,
    },
  })

  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: 'steps',
  })

  // Capture defaultValues on first render so the effect does not re-fire when a
  // parent passes an inline object literal (new reference every render).
  const defaultValuesRef = useRef(defaultValues)
  useEffect(() => {
    if (defaultValuesRef.current) {
      form.reset({
        name: '',
        description: '',
        steps: [{ ...DEFAULT_STEP }],
        ...defaultValuesRef.current,
      })
    }
  // form is stable across renders (returned by useForm); run once on mount only.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form])

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Nombre de la plantilla</FormLabel>
              <FormControl>
                <Input placeholder="Ej: Aprobación de contratos" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Descripción (opcional)</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Describe el propósito de este workflow..."
                  rows={3}
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <FormLabel className="text-sm font-medium">Pasos del workflow</FormLabel>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => append({ ...DEFAULT_STEP })}
            >
              <Plus className="mr-1 h-3.5 w-3.5" />
              Agregar paso
            </Button>
          </div>

          {fields.map((field, index) => (
            <WorkflowStepEditor
              key={field.id}
              index={index}
              control={form.control}
              onRemove={() => remove(index)}
              canRemove={fields.length > 1}
            />
          ))}

          {form.formState.errors.steps?.root && (
            <p className="text-sm text-destructive">
              {form.formState.errors.steps.root.message}
            </p>
          )}
          {typeof form.formState.errors.steps?.message === 'string' && (
            <p className="text-sm text-destructive">
              {form.formState.errors.steps.message}
            </p>
          )}
        </div>

        <div className="flex justify-end gap-2">
          <Button type="submit" disabled={isPending}>
            {isPending ? 'Guardando...' : submitLabel}
          </Button>
        </div>
      </form>
    </Form>
  )
}
