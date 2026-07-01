import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import type { AdvanceStepData } from '../api'

const advanceSchema = z
  .object({
    action: z.enum(['approved', 'rejected', 'commented']),
    comment: z.string().optional(),
  })
  .refine(
    (data) => data.action !== 'commented' || (data.comment && data.comment.length > 0),
    {
      message: 'El comentario es obligatorio para esta acción',
      path: ['comment'],
    },
  )

type AdvanceFormValues = z.infer<typeof advanceSchema>

interface AdvanceStepDialogProps {
  open: boolean
  isPending: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: AdvanceStepData) => void
}

const ACTION_LABELS: Record<string, string> = {
  approved: 'Aprobar',
  rejected: 'Rechazar',
  commented: 'Comentar',
}

export function AdvanceStepDialog({
  open,
  isPending,
  onOpenChange,
  onSubmit,
}: AdvanceStepDialogProps) {
  const form = useForm<AdvanceFormValues>({
    resolver: zodResolver(advanceSchema),
    defaultValues: {
      action: 'approved',
      comment: '',
    },
  })

  const action = form.watch('action')

  const handleSubmit = (values: AdvanceFormValues) => {
    onSubmit({
      action: values.action,
      comment: values.comment || undefined,
    })
    form.reset()
  }

  const handleOpenChange = (value: boolean) => {
    if (!value) form.reset()
    onOpenChange(value)
  }

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent className="sm:max-w-md">
        <AlertDialogHeader>
          <AlertDialogTitle>Avanzar paso del workflow</AlertDialogTitle>
        </AlertDialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="action"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Acción</FormLabel>
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Seleccionar acción" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {Object.entries(ACTION_LABELS).map(([value, label]) => (
                        <SelectItem key={value} value={value}>
                          {label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="comment"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    Comentario{action === 'commented' ? ' (obligatorio)' : ' (opcional)'}
                  </FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Agrega un comentario sobre esta decisión..."
                      rows={4}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <AlertDialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => handleOpenChange(false)}
                disabled={isPending}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={isPending}>
                {isPending ? 'Procesando...' : ACTION_LABELS[action] ?? 'Confirmar'}
              </Button>
            </AlertDialogFooter>
          </form>
        </Form>
      </AlertDialogContent>
    </AlertDialog>
  )
}
