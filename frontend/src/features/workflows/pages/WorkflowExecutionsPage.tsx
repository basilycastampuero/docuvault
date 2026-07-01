import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, ChevronRight } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
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
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useAuthStore } from '@/features/auth/store'
import { useWorkflowExecutions, useStartWorkflowExecution, useWorkflowTemplates } from '../hooks'
import { useDocuments } from '@/features/documents/hooks'
import { ExecutionStatusBadge } from '../components/ExecutionStatusBadge'
import { START_ROLES, type StartRole } from '@/shared/lib/roles'

function canStart(role: string | undefined): role is StartRole {
  return START_ROLES.includes(role as StartRole)
}

const startSchema = z.object({
  document_id: z.string().min(1, 'Selecciona un documento'),
  template_id: z.string().uuid('Selecciona una plantilla'),
})
type StartFormValues = z.infer<typeof startSchema>

export function WorkflowExecutionsPage() {
  const [startOpen, setStartOpen] = useState(false)
  const role = useAuthStore((s) => s.user?.role)
  const userCanStart = canStart(role)

  const { data, isLoading } = useWorkflowExecutions()
  const { data: templatesData } = useWorkflowTemplates()
  const { data: documentsData, isLoading: documentsLoading } = useDocuments()
  const startExecution = useStartWorkflowExecution()

  const form = useForm<StartFormValues>({
    resolver: zodResolver(startSchema),
    defaultValues: { document_id: '', template_id: '' },
  })

  const handleStart = (values: StartFormValues) => {
    startExecution.mutate(values, {
      onSuccess: () => {
        setStartOpen(false)
        form.reset()
      },
    })
  }

  const activeTemplates = templatesData?.items.filter((t) => t.is_active) ?? []
  const documents = documentsData?.items ?? []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Ejecuciones de Workflow</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Seguimiento de los procesos de aprobación en curso.
          </p>
        </div>
        {userCanStart && (
          <Button onClick={() => setStartOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Iniciar workflow
          </Button>
        )}
      </div>

      <div className="text-sm">
        <Link
          to="/workflows"
          className="text-primary underline-offset-4 hover:underline"
        >
          Ver plantillas
        </Link>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((n) => (
            <Skeleton key={n} className="h-24 w-full" />
          ))}
        </div>
      ) : !data || data.items.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center text-muted-foreground">
            <p className="text-base font-medium">No hay ejecuciones</p>
            {userCanStart && (
              <p className="text-sm mt-1">Inicia un workflow para un documento.</p>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {data.items.map((execution) => (
            <Card key={execution.id} className="hover:border-primary/50 transition-colors">
              <CardContent className="py-4 px-5">
                <div className="flex items-center gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium truncate">{execution.document_name}</h3>
                      <ExecutionStatusBadge status={execution.status} />
                    </div>
                    <p className="text-sm text-muted-foreground mt-0.5">
                      Plantilla: {execution.template_name}
                    </p>
                    <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                      {execution.current_step && (
                        <span>Paso actual: {execution.current_step.name}</span>
                      )}
                      <span>
                        Iniciado{' '}
                        {execution.started_at
                          ? format(new Date(execution.started_at), 'dd MMM yyyy', { locale: es })
                          : '—'}
                      </span>
                    </div>
                  </div>

                  <Button variant="ghost" size="sm" asChild>
                    <Link to={`/workflows/executions/${execution.id}`}>
                      Ver detalle
                      <ChevronRight className="ml-1 h-4 w-4" />
                    </Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog
        open={startOpen}
        onOpenChange={(v) => {
          if (!v) form.reset()
          setStartOpen(v)
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Iniciar workflow</DialogTitle>
          </DialogHeader>

          <Form {...form}>
            <form onSubmit={form.handleSubmit(handleStart)} className="space-y-4">
              <FormField
                control={form.control}
                name="document_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Documento</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value}
                      disabled={documentsLoading}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue
                            placeholder={
                              documentsLoading ? 'Cargando documentos...' : 'Seleccionar documento'
                            }
                          />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {documents.length === 0 ? (
                          <SelectItem value="_none" disabled>
                            No hay documentos disponibles
                          </SelectItem>
                        ) : (
                          documents.map((doc) => (
                            <SelectItem key={doc.id} value={doc.id}>
                              {doc.name} — {doc.status}
                            </SelectItem>
                          ))
                        )}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="template_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Plantilla</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Seleccionar plantilla" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {activeTemplates.length === 0 ? (
                          <SelectItem value="_none" disabled>
                            No hay plantillas activas
                          </SelectItem>
                        ) : (
                          activeTemplates.map((t) => (
                            <SelectItem key={t.id} value={t.id}>
                              {t.name}
                            </SelectItem>
                          ))
                        )}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setStartOpen(false)
                    form.reset()
                  }}
                >
                  Cancelar
                </Button>
                <Button type="submit" disabled={startExecution.isPending}>
                  {startExecution.isPending ? 'Iniciando...' : 'Iniciar'}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
