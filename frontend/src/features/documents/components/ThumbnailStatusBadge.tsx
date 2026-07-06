import { Badge } from '@/components/ui/badge'
import type { ThumbnailStatus } from '@/shared/types'
import { cn } from '@/lib/utils'

interface ThumbnailStatusBadgeProps {
  status: ThumbnailStatus
}

const CONFIG: Record<ThumbnailStatus, { label: string; className: string }> = {
  pending: {
    label: 'Miniatura pendiente',
    className: 'bg-gray-100 text-gray-600 hover:bg-gray-100',
  },
  processing: {
    label: 'Generando miniatura...',
    className: 'bg-blue-100 text-blue-700 hover:bg-blue-100 animate-pulse',
  },
  ready: {
    label: 'Miniatura lista',
    className: 'bg-green-100 text-green-700 hover:bg-green-100',
  },
  failed: {
    label: 'Miniatura fallida',
    className: 'bg-red-100 text-red-700 hover:bg-red-100',
  },
  skipped: {
    label: 'Sin miniatura',
    className: 'bg-gray-100 text-gray-500 hover:bg-gray-100',
  },
}

export function ThumbnailStatusBadge({ status }: ThumbnailStatusBadgeProps) {
  const cfg = CONFIG[status] ?? {
    label: String(status ?? 'Desconocido'),
    className: 'bg-gray-100 text-gray-500 hover:bg-gray-100',
  }
  const { label, className } = cfg
  return (
    <Badge variant="secondary" className={cn('text-xs font-medium', className)}>
      {label}
    </Badge>
  )
}
