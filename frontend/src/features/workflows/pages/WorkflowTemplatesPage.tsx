import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, ChevronRight, ToggleLeft, ToggleRight } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useAuthStore } from '@/features/auth/store'
import {
  useWorkflowTemplates,
  useCreateWorkflowTemplate,
  useUpdateWorkflowTemplate,
  useDeleteWorkflowTemplate,
} from '../hooks'
import { WorkflowTemplateForm } from '../components/WorkflowTemplateForm'
import type { TemplateFormValues } from '../components/WorkflowTemplateForm'
import type { WorkflowTemplate } from '@/shared/types'

const ADMIN_ROLES = ['super_admin', 'org_admin'] as const
type AdminRole = (typeof ADMIN_ROLES)[number]

function isAdminRole(role: string | undefined): role is AdminRole {
  return ADMIN_ROLES.includes(role as AdminRole)
}

export function WorkflowTemplatesPage() {
  const [createOpen, setCreateOpen] = useState(false)
  const role = useAuthStore((s) => s.user?.role)
  const canManage = isAdminRole(role)

  const { data, isLoading } = useWorkflowTemplates()
  const createTemplate = useCreateWorkflowTemplate()
  const updateTemplate = useUpdateWorkflowTemplate()
  const deleteTemplate = useDeleteWorkflowTemplate()

  const handleCreate = (values: TemplateFormValues) => {
    const submitData = {
      name: values.name,
      description: values.description,
      steps: values.steps.map((step, i) => ({
        ...step,
        order: i + 1,
        actions: {},
      })),
    }
    createTemplate.mutate(submitData, {
      onSuccess: () => setCreateOpen(false),
    })
  }

  const handleToggleActive = (template: WorkflowTemplate) => {
    updateTemplate.mutate({
      id: template.id,
      data: { is_active: !template.is_active },
    })
  }

  const handleDelete = (id: string) => {
    if (window.confirm('¿Eliminar esta plantilla? Esta acción no se puede deshacer.')) {
      deleteTemplate.mutate(id)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Plantillas de Workflow</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Define los procesos de aprobación para tus documentos.
          </p>
        </div>
        {canManage && (
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Nueva plantilla
          </Button>
        )}
      </div>

      <div className="flex gap-4 text-sm">
        <Link
          to="/workflows/executions"
          className="text-primary underline-offset-4 hover:underline"
        >
          Ver ejecuciones activas
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
            <p className="text-base font-medium">No hay plantillas de workflow</p>
            {canManage && (
              <p className="text-sm mt-1">Crea la primera para empezar.</p>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {data.items.map((template) => (
            <Card key={template.id} className="hover:border-primary/50 transition-colors">
              <CardContent className="py-4 px-5">
                <div className="flex items-center gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium truncate">{template.name}</h3>
                      <Badge
                        variant="secondary"
                        className={
                          template.is_active
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-500'
                        }
                      >
                        {template.is_active ? 'Activa' : 'Inactiva'}
                      </Badge>
                    </div>
                    {template.description && (
                      <p className="text-sm text-muted-foreground mt-0.5 truncate">
                        {template.description}
                      </p>
                    )}
                    <p className="text-xs text-muted-foreground mt-1">
                      {template.steps.length} pasos &bull; Creada{' '}
                      {format(new Date(template.created_at), 'dd MMM yyyy', { locale: es })}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {canManage && (
                      <>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleToggleActive(template)}
                          disabled={updateTemplate.isPending}
                          title={template.is_active ? 'Desactivar' : 'Activar'}
                        >
                          {template.is_active ? (
                            <ToggleRight className="h-4 w-4 text-green-600" />
                          ) : (
                            <ToggleLeft className="h-4 w-4 text-muted-foreground" />
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive hover:text-destructive"
                          onClick={() => handleDelete(template.id)}
                          disabled={deleteTemplate.isPending}
                        >
                          Eliminar
                        </Button>
                      </>
                    )}
                    <Button variant="ghost" size="sm" asChild>
                      <Link to={`/workflows/templates/${template.id}`}>
                        Ver detalle
                        <ChevronRight className="ml-1 h-4 w-4" />
                      </Link>
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Nueva plantilla de workflow</DialogTitle>
          </DialogHeader>
          <WorkflowTemplateForm
            onSubmit={handleCreate}
            isPending={createTemplate.isPending}
          />
        </DialogContent>
      </Dialog>
    </div>
  )
}
