import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, GitBranch } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { useWorkflowTemplate } from '../hooks'

const ROLE_LABELS: Record<string, string> = {
  super_admin: 'Super admin',
  org_admin: 'Admin de organización',
  supervisor: 'Supervisor',
  editor: 'Editor',
  viewer: 'Visualizador',
  auditor: 'Auditor',
}

export function WorkflowTemplateDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const { data: template, isLoading, error } = useWorkflowTemplate(id ?? '')

  if (!id) {
    navigate('/workflows')
    return null
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-9 w-48" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (error || !template) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <p className="text-lg font-medium text-muted-foreground">Plantilla no encontrada</p>
        <Button variant="outline" onClick={() => navigate('/workflows')}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Volver a plantillas
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors mb-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Volver
          </button>
          <h1 className="text-2xl font-bold tracking-tight">{template.name}</h1>
          <div className="flex items-center gap-2">
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
            <span className="text-xs text-muted-foreground">
              {template.steps.length} pasos
            </span>
          </div>
        </div>

        <Button asChild>
          <Link to={`/workflows/executions`}>
            <GitBranch className="mr-2 h-4 w-4" />
            Ver ejecuciones
          </Link>
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Pasos del workflow</CardTitle>
            </CardHeader>
            <CardContent className="space-y-0 divide-y divide-border">
              {template.steps.map((step, index) => (
                <div key={step.id} className="flex items-center gap-4 py-3">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                    {index + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium">{step.name}</p>
                    <p className="text-xs text-muted-foreground">
                      Rol: {ROLE_LABELS[step.required_role] ?? step.required_role}
                    </p>
                  </div>
                  {step.is_final && (
                    <Badge variant="outline" className="text-xs shrink-0">
                      Paso final
                    </Badge>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Información</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Estado</span>
                <span className="font-medium">
                  {template.is_active ? 'Activa' : 'Inactiva'}
                </span>
              </div>
              <Separator />
              <div className="flex justify-between">
                <span className="text-muted-foreground">Pasos</span>
                <span className="font-medium">{template.steps.length}</span>
              </div>
              <Separator />
              <div className="flex justify-between">
                <span className="text-muted-foreground">Creada</span>
                <span className="font-medium">
                  {format(new Date(template.created_at), 'dd MMM yyyy', { locale: es })}
                </span>
              </div>
              <Separator />
              <div className="flex justify-between">
                <span className="text-muted-foreground">Actualizada</span>
                <span className="font-medium">
                  {format(new Date(template.updated_at), 'dd MMM yyyy', { locale: es })}
                </span>
              </div>
            </CardContent>
          </Card>

          {template.description && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Descripción</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{template.description}</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
