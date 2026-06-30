import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import {
  useWorkflowExecution,
  useWorkflowExecutionLogs,
  useAdvanceWorkflowStep,
} from '../hooks'
import { ExecutionStatusBadge } from '../components/ExecutionStatusBadge'
import { AdvanceStepDialog } from '../components/AdvanceStepDialog'
import { WorkflowStepLogTimeline } from '../components/WorkflowStepLogTimeline'
import type { AdvanceStepData } from '../api'

const ROLE_LABELS: Record<string, string> = {
  super_admin: 'Super admin',
  org_admin: 'Admin de organización',
  supervisor: 'Supervisor',
  editor: 'Editor',
  viewer: 'Visualizador',
  auditor: 'Auditor',
}

export function WorkflowExecutionDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [advanceOpen, setAdvanceOpen] = useState(false)

  const { data: execution, isLoading, error } = useWorkflowExecution(id ?? '')
  const { data: logsData } = useWorkflowExecutionLogs(id ?? '')
  const advanceStep = useAdvanceWorkflowStep()

  if (!id) {
    navigate('/workflows/executions')
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

  if (error || !execution) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <p className="text-lg font-medium text-muted-foreground">Ejecución no encontrada</p>
        <Button variant="outline" onClick={() => navigate('/workflows/executions')}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Volver a ejecuciones
        </Button>
      </div>
    )
  }

  const handleAdvance = (data: AdvanceStepData) => {
    advanceStep.mutate(
      { id: execution.id, data },
      { onSuccess: () => setAdvanceOpen(false) },
    )
  }

  const isActive = execution.status === 'pending' || execution.status === 'in_progress'

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
          <h1 className="text-2xl font-bold tracking-tight">{execution.document_name}</h1>
          <div className="flex items-center gap-2">
            <ExecutionStatusBadge status={execution.status} />
            <span className="text-sm text-muted-foreground">
              Plantilla: {execution.template_name}
            </span>
          </div>
        </div>

        {isActive && (
          <Button onClick={() => setAdvanceOpen(true)}>
            Avanzar paso
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          {execution.current_step && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Paso actual</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">
                    {execution.current_step.order}
                  </div>
                  <div>
                    <p className="font-medium">{execution.current_step.name}</p>
                    <p className="text-xs text-muted-foreground">
                      Rol requerido:{' '}
                      {ROLE_LABELS[execution.current_step.required_role] ??
                        execution.current_step.required_role}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Historial de actividad</CardTitle>
            </CardHeader>
            <CardContent className="pt-2">
              <WorkflowStepLogTimeline logs={logsData?.items ?? []} />
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
                <span className="text-muted-foreground">Documento</span>
                <Link
                  to={`/documents/${execution.document}`}
                  className="font-medium text-primary hover:underline truncate max-w-32"
                >
                  {execution.document_name}
                </Link>
              </div>
              <Separator />
              <div className="flex justify-between">
                <span className="text-muted-foreground">Iniciado por</span>
                <span className="font-medium truncate max-w-32" title={execution.started_by_email}>
                  {execution.started_by_email}
                </span>
              </div>
              <Separator />
              {execution.started_at && (
                <>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Inicio</span>
                    <span className="font-medium">
                      {format(new Date(execution.started_at), 'dd MMM yyyy', { locale: es })}
                    </span>
                  </div>
                  <Separator />
                </>
              )}
              {execution.completed_at && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Completado</span>
                  <span className="font-medium">
                    {format(new Date(execution.completed_at), 'dd MMM yyyy', { locale: es })}
                  </span>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <AdvanceStepDialog
        open={advanceOpen}
        isPending={advanceStep.isPending}
        onOpenChange={setAdvanceOpen}
        onSubmit={handleAdvance}
      />
    </div>
  )
}
