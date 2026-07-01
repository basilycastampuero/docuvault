import { Badge } from '@/components/ui/badge'

const MIME_MAP: Record<string, { label: string; className: string }> = {
  'application/pdf': { label: 'PDF', className: 'bg-red-100 text-red-700 hover:bg-red-100' },
  'image/jpeg': { label: 'JPG', className: 'bg-sky-100 text-sky-700 hover:bg-sky-100' },
  'image/jpg': { label: 'JPG', className: 'bg-sky-100 text-sky-700 hover:bg-sky-100' },
  'image/png': { label: 'PNG', className: 'bg-sky-100 text-sky-700 hover:bg-sky-100' },
  'image/gif': { label: 'GIF', className: 'bg-sky-100 text-sky-700 hover:bg-sky-100' },
  'image/webp': { label: 'WEBP', className: 'bg-sky-100 text-sky-700 hover:bg-sky-100' },
  'image/tiff': { label: 'TIFF', className: 'bg-sky-100 text-sky-700 hover:bg-sky-100' },
  'application/msword': {
    label: 'DOC',
    className: 'bg-indigo-100 text-indigo-700 hover:bg-indigo-100',
  },
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': {
    label: 'DOCX',
    className: 'bg-indigo-100 text-indigo-700 hover:bg-indigo-100',
  },
  'application/vnd.ms-excel': {
    label: 'XLS',
    className: 'bg-emerald-100 text-emerald-700 hover:bg-emerald-100',
  },
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': {
    label: 'XLSX',
    className: 'bg-emerald-100 text-emerald-700 hover:bg-emerald-100',
  },
  'application/vnd.ms-powerpoint': {
    label: 'PPT',
    className: 'bg-orange-100 text-orange-700 hover:bg-orange-100',
  },
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': {
    label: 'PPTX',
    className: 'bg-orange-100 text-orange-700 hover:bg-orange-100',
  },
  'text/plain': { label: 'TXT', className: 'bg-gray-100 text-gray-600 hover:bg-gray-100' },
  'text/csv': {
    label: 'CSV',
    className: 'bg-emerald-100 text-emerald-700 hover:bg-emerald-100',
  },
}

function getMimeConfig(mimeType: string): { label: string; className: string } {
  const known = MIME_MAP[mimeType]
  if (known) return known
  const subtype = mimeType.split('/')[1] ?? mimeType
  return {
    label: subtype.split('.').pop()?.toUpperCase().slice(0, 6) ?? 'FILE',
    className: 'bg-gray-100 text-gray-600 hover:bg-gray-100',
  }
}

interface FileTypeBadgeProps {
  mimeType: string
}

export function FileTypeBadge({ mimeType }: FileTypeBadgeProps) {
  const { label, className } = getMimeConfig(mimeType)
  return (
    <Badge variant="secondary" className={`text-xs font-mono font-semibold ${className}`}>
      {label}
    </Badge>
  )
}
