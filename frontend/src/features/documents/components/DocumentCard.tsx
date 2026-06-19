import { useNavigate } from 'react-router-dom'
import { FileText, Download, MoreVertical, Trash2, Eye } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { es } from 'date-fns/locale'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import type { Document } from '@/shared/types'
import { useAuthStore } from '@/features/auth/store'
import { OcrStatusBadge } from './OcrStatusBadge'
import { useDownloadDocument } from '../hooks'

interface DocumentCardProps {
  document: Document
  onDelete?: (doc: Document) => void
}

const STATUS_LABELS: Record<string, string> = {
  draft: 'Borrador',
  under_review: 'En revisión',
  approved: 'Aprobado',
  rejected: 'Rechazado',
  archived: 'Archivado',
}

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-600',
  under_review: 'bg-yellow-100 text-yellow-700',
  approved: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
  archived: 'bg-gray-200 text-gray-500',
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const WRITE_ROLES = ['super_admin', 'org_admin', 'supervisor', 'editor']

export function DocumentCard({ document, onDelete }: DocumentCardProps) {
  const navigate = useNavigate()
  const role = useAuthStore((s) => s.user?.role)
  const canWrite = role ? WRITE_ROLES.includes(role) : false
  const download = useDownloadDocument()

  const timeAgo = formatDistanceToNow(new Date(document.created_at), {
    addSuffix: true,
    locale: es,
  })

  return (
    <Card
      className="group cursor-pointer transition-colors hover:bg-accent"
      onClick={() => navigate(`/documents/${document.id}`)}
    >
      <CardContent className="p-4 space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-start gap-3 min-w-0">
            <FileText className="h-8 w-8 shrink-0 text-primary mt-0.5" />
            <div className="min-w-0">
              <p className="font-medium text-sm truncate">{document.name}</p>
              <p className="text-xs text-muted-foreground">
                {formatFileSize(document.file_size)} · {timeAgo}
              </p>
            </div>
          </div>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 shrink-0 opacity-0 group-hover:opacity-100"
                onClick={(e) => e.stopPropagation()}
              >
                <MoreVertical className="h-4 w-4" />
                <span className="sr-only">Opciones</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
              <DropdownMenuItem
                onClick={(e) => {
                  e.stopPropagation()
                  navigate(`/documents/${document.id}`)
                }}
              >
                <Eye className="mr-2 h-4 w-4" />
                Ver detalles
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={(e) => {
                  e.stopPropagation()
                  download.mutate(document.id)
                }}
              >
                <Download className="mr-2 h-4 w-4" />
                Descargar
              </DropdownMenuItem>
              {canWrite && onDelete && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive"
                    onClick={(e) => {
                      e.stopPropagation()
                      onDelete(document)
                    }}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Eliminar
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Badge
            variant="secondary"
            className={`text-xs ${STATUS_COLORS[document.status] ?? ''}`}
          >
            {STATUS_LABELS[document.status] ?? document.status}
          </Badge>
          <OcrStatusBadge status={document.ocr_status} />
        </div>

        {document.tags.length > 0 && (
          <div className="flex gap-1 flex-wrap">
            {document.tags.slice(0, 3).map((tag) => (
              <Badge key={tag} variant="outline" className="text-xs">
                {tag}
              </Badge>
            ))}
            {document.tags.length > 3 && (
              <Badge variant="outline" className="text-xs text-muted-foreground">
                +{document.tags.length - 3}
              </Badge>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
