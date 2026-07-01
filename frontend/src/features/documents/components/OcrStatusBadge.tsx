import { Badge } from '@/components/ui/badge'
import type { OcrStatus } from '@/shared/types'
import { cn } from '@/lib/utils'

interface OcrStatusBadgeProps {
  status: OcrStatus
}

const CONFIG: Record<OcrStatus, { label: string; className: string }> = {
  pending: {
    label: 'Pendiente',
    className: 'bg-gray-100 text-gray-600 hover:bg-gray-100',
  },
  processing: {
    label: 'Procesando...',
    className: 'bg-blue-100 text-blue-700 hover:bg-blue-100 animate-pulse',
  },
  completed: {
    label: 'OCR Completado',
    className: 'bg-green-100 text-green-700 hover:bg-green-100',
  },
  failed: {
    label: 'OCR Fallido',
    className: 'bg-red-100 text-red-700 hover:bg-red-100',
  },
  skipped: {
    label: 'Omitido',
    className: 'bg-gray-100 text-gray-500 hover:bg-gray-100',
  },
}

export function OcrStatusBadge({ status }: OcrStatusBadgeProps) {
  const cfg = CONFIG[status] ?? { label: String(status ?? 'Desconocido'), className: 'bg-gray-100 text-gray-500 hover:bg-gray-100' }
  const { label, className } = cfg
  return (
    <Badge variant="secondary" className={cn('text-xs font-medium', className)}>
      {label}
    </Badge>
  )
}
