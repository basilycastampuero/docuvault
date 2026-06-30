import { formatDistanceToNow } from 'date-fns'
import { es } from 'date-fns/locale'
import { CheckCircle2, XCircle, MessageSquare, Circle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { WorkflowStepLog, WorkflowStepAction } from '@/shared/types'

interface WorkflowStepLogTimelineProps {
  logs: WorkflowStepLog[]
}

const ACTION_CONFIG: Record<
  WorkflowStepAction,
  { label: string; className: string; Icon: React.ComponentType<{ className?: string }> }
> = {
  approved: {
    label: 'Aprobado',
    className: 'text-green-600 bg-green-50 border-green-200',
    Icon: CheckCircle2,
  },
  rejected: {
    label: 'Rechazado',
    className: 'text-red-600 bg-red-50 border-red-200',
    Icon: XCircle,
  },
  commented: {
    label: 'Comentario',
    className: 'text-gray-600 bg-gray-50 border-gray-200',
    Icon: MessageSquare,
  },
}

export function WorkflowStepLogTimeline({ logs }: WorkflowStepLogTimelineProps) {
  if (logs.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-8">
        Sin actividad registrada aún.
      </p>
    )
  }

  return (
    <ol className="relative border-l border-border space-y-6 ml-3">
      {logs.map((log) => {
        const config = ACTION_CONFIG[log.action as keyof typeof ACTION_CONFIG] ?? {
          label: log.action,
          Icon: Circle,
          className: 'text-gray-500 bg-gray-50 border-gray-200',
        }
        const Icon = config.Icon

        return (
          <li key={log.id} className="ml-4">
            <div
              className={cn(
                'absolute -left-2 mt-1 flex h-4 w-4 items-center justify-center rounded-full border',
                config.className,
              )}
            >
              <Icon className="h-2.5 w-2.5" />
            </div>

            <div className="space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={cn('text-xs font-medium px-1.5 py-0.5 rounded border', config.className)}>
                  {config.label}
                </span>
                <span className="text-xs font-medium text-foreground">
                  Paso {log.step_order}: {log.step_name}
                </span>
              </div>

              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span>{log.performed_by_email}</span>
                <span>&bull;</span>
                <time dateTime={log.created_at}>
                  {formatDistanceToNow(new Date(log.created_at), {
                    addSuffix: true,
                    locale: es,
                  })}
                </time>
              </div>

              {log.comment && (
                <blockquote className="mt-1.5 border-l-2 border-border pl-3 text-xs text-muted-foreground italic">
                  {log.comment}
                </blockquote>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
