import { useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, X, FileText, Clock } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { AppPagination } from '@/shared/components/Pagination'
import { useAuthStore } from '@/features/auth/store'
import { useDocumentVersions, useUploadVersion } from '../hooks'
import { validateFile, ALLOWED_EXTENSIONS, MAX_FILE_SIZE } from '../validation'
import type { Document } from '@/shared/types'

const uploadVersionSchema = z.object({
  change_description: z.string().max(500).optional(),
})
type UploadVersionFormValues = z.infer<typeof uploadVersionSchema>

interface DocumentVersionListProps {
  document: Document
}

const WRITE_ROLES = ['super_admin', 'org_admin', 'supervisor', 'editor']

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function DocumentVersionList({ document }: DocumentVersionListProps) {
  const role = useAuthStore((s) => s.user?.role)
  const canWrite = role ? WRITE_ROLES.includes(role) : false

  const [page, setPage] = useState(1)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)

  const { data, isLoading } = useDocumentVersions(document.id, page)
  const { mutation: upload, uploadProgress } = useUploadVersion(document.id)

  const form = useForm<UploadVersionFormValues>({
    resolver: zodResolver(uploadVersionSchema),
    defaultValues: { change_description: '' },
  })

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (acceptedFiles) => {
      const file = acceptedFiles[0]
      if (!file) return
      const error = validateFile(file)
      if (error) {
        setFileError(error)
        return
      }
      setFileError(null)
      setSelectedFile(file)
    },
    multiple: false,
    maxSize: MAX_FILE_SIZE,
  })

  const handleClose = () => {
    setUploadOpen(false)
    setSelectedFile(null)
    setFileError(null)
    form.reset()
  }

  const onSubmit = (values: UploadVersionFormValues) => {
    if (!selectedFile) return
    upload.mutate(
      { file: selectedFile, change_description: values.change_description },
      { onSuccess: handleClose },
    )
  }

  const totalPages = data ? Math.ceil(data.meta.count / data.meta.page_size) : 1

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Versiones</h3>
        {canWrite && (
          <Button size="sm" onClick={() => setUploadOpen(true)}>
            <Upload className="mr-2 h-4 w-4" />
            Nueva versión
          </Button>
        )}
      </div>

      {isLoading && (
        <p className="text-sm text-muted-foreground text-center py-4">Cargando versiones...</p>
      )}

      {data && data.items.length > 0 && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Versión</TableHead>
                <TableHead>Tamaño</TableHead>
                <TableHead>Descripción</TableHead>
                <TableHead>Subido por</TableHead>
                <TableHead>Fecha</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((version) => (
                <TableRow key={version.id}>
                  <TableCell className="font-medium">v{version.version_number}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatFileSize(version.file_size)}
                  </TableCell>
                  <TableCell className="text-sm">
                    {version.change_description || (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {version.created_by_email}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    <div className="flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5" />
                      {format(new Date(version.created_at), 'dd MMM yyyy HH:mm', { locale: es })}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <AppPagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </>
      )}

      {data && data.items.length === 0 && (
        <p className="text-sm text-muted-foreground text-center py-4">
          No hay versiones registradas.
        </p>
      )}

      {/* Upload version dialog */}
      <Dialog open={uploadOpen} onOpenChange={(o) => !o && handleClose()}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Subir nueva versión</DialogTitle>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              {!selectedFile ? (
                <div
                  {...getRootProps()}
                  className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
                    isDragActive
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:border-primary/50'
                  }`}
                >
                  <input {...getInputProps()} />
                  <Upload className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
                  <p className="text-sm">Arrastra o haz clic para seleccionar</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {ALLOWED_EXTENSIONS.join(', ')} · Máx. {MAX_FILE_SIZE / 1024 / 1024}MB
                  </p>
                  {fileError && (
                    <p className="text-xs text-destructive mt-2">{fileError}</p>
                  )}
                </div>
              ) : (
                <div className="flex items-center gap-3 rounded-lg border p-3">
                  <FileText className="h-7 w-7 shrink-0 text-primary" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium truncate">{selectedFile.name}</p>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setSelectedFile(null)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              )}

              {upload.isPending && uploadProgress > 0 && (
                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>Subiendo...</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <Progress value={uploadProgress} className="h-1.5" />
                </div>
              )}

              <FormField
                control={form.control}
                name="change_description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Descripción del cambio (opcional)</FormLabel>
                    <FormControl>
                      <Input placeholder="Qué cambió en esta versión" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <DialogFooter>
                <Button type="button" variant="outline" onClick={handleClose}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={!selectedFile || upload.isPending}>
                  {upload.isPending ? 'Subiendo...' : 'Subir versión'}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
