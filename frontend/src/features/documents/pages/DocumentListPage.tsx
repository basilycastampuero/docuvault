import { useState } from 'react'
import { Upload, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { AppPagination } from '@/shared/components/Pagination'
import { useAuthStore } from '@/features/auth/store'
import { DocumentCard } from '../components/DocumentCard'
import { WRITE_ROLES } from '@/shared/lib/roles'
import { DocumentUploadDropzone } from '../components/DocumentUploadDropzone'
import { useDocuments, useDeleteDocument } from '../hooks'
import type { Document, DocumentStatus } from '@/shared/types'

const STATUS_OPTIONS: { label: string; value: DocumentStatus | 'all' }[] = [
  { label: 'Todos los estados', value: 'all' },
  { label: 'Borrador', value: 'draft' },
  { label: 'En revisión', value: 'under_review' },
  { label: 'Aprobado', value: 'approved' },
  { label: 'Rechazado', value: 'rejected' },
  { label: 'Archivado', value: 'archived' },
]

export function DocumentListPage() {
  const role = useAuthStore((s) => s.user?.role)
  const canWrite = role ? (WRITE_ROLES as readonly string[]).includes(role) : false

  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<DocumentStatus | 'all'>('all')
  const [uploadOpen, setUploadOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Document | null>(null)

  const { data, isLoading } = useDocuments({
    status: statusFilter === 'all' ? undefined : statusFilter,
    page,
    page_size: 20,
  })

  const deleteDocument = useDeleteDocument()

  const handleDeleteConfirm = () => {
    if (!deleteTarget) return
    deleteDocument.mutate(deleteTarget.id, {
      onSuccess: () => setDeleteTarget(null),
    })
  }

  const totalPages = data ? Math.ceil(data.meta.count / data.meta.page_size) : 1

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Documentos</h1>
        {canWrite && (
          <Button onClick={() => setUploadOpen(true)}>
            <Upload className="mr-2 h-4 w-4" />
            Subir documento
          </Button>
        )}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <Select
          value={statusFilter}
          onValueChange={(v) => {
            setStatusFilter(v as DocumentStatus | 'all')
            setPage(1)
          }}
        >
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {data && (
          <p className="text-sm text-muted-foreground">
            {data.meta.count} {data.meta.count === 1 ? 'documento' : 'documentos'}
          </p>
        )}
      </div>

      {/* Content */}
      {isLoading && (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      )}

      {data && data.items.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <p className="text-lg font-medium text-muted-foreground">No se encontraron documentos</p>
          <p className="text-sm text-muted-foreground mt-1">
            {statusFilter !== 'all'
              ? 'Prueba con otro filtro de estado.'
              : canWrite
                ? 'Sube tu primer documento.'
                : 'Aun no hay documentos disponibles.'}
          </p>
          {canWrite && statusFilter === 'all' && (
            <Button className="mt-4" onClick={() => setUploadOpen(true)}>
              <Upload className="mr-2 h-4 w-4" />
              Subir documento
            </Button>
          )}
        </div>
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.items.map((doc) => (
              <DocumentCard
                key={doc.id}
                document={doc}
                onDelete={canWrite ? (d) => setDeleteTarget(d) : undefined}
              />
            ))}
          </div>
          <AppPagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </>
      )}

      {/* Upload dialog */}
      <DocumentUploadDropzone
        open={uploadOpen}
        onOpenChange={setUploadOpen}
      />

      {/* Delete confirmation */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminar documento</AlertDialogTitle>
            <AlertDialogDescription>
              Estas seguro de que quieres eliminar "{deleteTarget?.name}"? Esta accion no se puede
              deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteDocument.isPending ? 'Eliminando...' : 'Eliminar'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
