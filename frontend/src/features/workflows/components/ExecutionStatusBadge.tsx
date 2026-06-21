import { Badge } from '@/components/ui/badge'
import type { WorkflowStatus } from '@/shared/types'
import { cn } from '@/lib/utils'

interface ExecutionStatusBadgeProps {
  status: WorkflowStatus
}

const CONFIG: Record<WorkflowStatus, { label: string; className: string }> = {
  pending: {
    label: 'Pendiente',
    className: 'bg-gray-100 text-gray-600 hover:bg-gray-100',
  },
  in_progress: {
    label: 'En progreso',
    className: 'bg-blue-100 text-blue-700 hover:bg-blue-100 animate-pulse',
  },
  completed: {
    label: 'Completado',
    className: 'bg-green-100 text-green-700 hover:bg-green-100',
  },
  rejected: {
    label: 'Rechazado',
    className: 'bg-red-100 text-red-700 hover:bg-red-100',
  },
  cancelled: {
    label: 'Cancelado',
    className: 'bg-gray-100 text-gray-500 hover:bg-gray-100',
  },
}

export function ExecutionStatusBadge({ status }: ExecutionStatusBadgeProps) {
  const { label, className } = CONFIG[status]
  return (
    <Badge variant="secondary" className={cn('text-xs font-medium', className)}>
      {label}
    </Badge>
  )
}
