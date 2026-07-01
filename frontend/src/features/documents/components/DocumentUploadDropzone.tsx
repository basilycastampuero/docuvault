import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, X, FileText } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Progress } from '@/components/ui/progress'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import {
  uploadDocumentSchema,
  type UploadDocumentFormValues,
  validateFile,
  ALLOWED_EXTENSIONS,
  MAX_FILE_SIZE,
} from '../validation'
import { useUploadDocument } from '../hooks'

interface DocumentUploadDropzoneProps {
  open: boolean
  folderId?: string
  onOpenChange: (open: boolean) => void
}

export function DocumentUploadDropzone({
  open,
  folderId,
  onOpenChange,
}: DocumentUploadDropzoneProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const { mutation: upload, uploadProgress } = useUploadDocument()

  const form = useForm<UploadDocumentFormValues>({
    resolver: zodResolver(uploadDocumentSchema),
    defaultValues: {
      name: '',
      folder_id: folderId,
      description: '',
      tags: '',
    },
  })

  const handleClose = useCallback(() => {
    setSelectedFile(null)
    setFileError(null)
    form.reset()
    onOpenChange(false)
  }, [form, onOpenChange])

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      const file = acceptedFiles[0]
      if (!file) return

      const error = validateFile(file)
      if (error) {
        setFileError(error)
        return
      }

      setFileError(null)
      setSelectedFile(file)
      form.setValue('file', file)
      if (!form.getValues('name')) {
        form.setValue('name', file.name.replace(/\.[^/.]+$/, ''))
      }
    },
    [form],
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: false,
    maxSize: MAX_FILE_SIZE,
    onDropRejected: (fileRejections) => {
      const rejection = fileRejections[0]
      if (rejection?.errors[0]?.code === 'file-too-large') {
        setFileError(`El archivo supera el tamaño máximo de ${MAX_FILE_SIZE / 1024 / 1024}MB`)
      } else {
        setFileError('Archivo no válido')
      }
    },
  })

  const onSubmit = (values: UploadDocumentFormValues) => {
    if (!selectedFile) return

    const tags = values.tags
      ? values.tags
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean)
      : []

    upload.mutate(
      {
        file: selectedFile,
        name: values.name,
        folder_id: values.folder_id,
        description: values.description,
        tags,
      },
      { onSuccess: handleClose },
    )
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Subir documento</DialogTitle>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            {/* Dropzone */}
            {!selectedFile ? (
              <div
                {...getRootProps()}
                className={cn(
                  'border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors',
                  isDragActive
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:border-primary/50 hover:bg-accent/50',
                )}
              >
                <input {...getInputProps()} />
                <Upload className="mx-auto h-10 w-10 text-muted-foreground mb-3" />
                <p className="text-sm font-medium">
                  {isDragActive ? 'Suelta el archivo aquí' : 'Arrastra un archivo o haz clic para seleccionar'}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  {ALLOWED_EXTENSIONS.join(', ')} · Máx. {MAX_FILE_SIZE / 1024 / 1024}MB
                </p>
                {fileError && (
                  <p className="text-xs text-destructive mt-2">{fileError}</p>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-3 rounded-lg border border-border p-3">
                <FileText className="h-8 w-8 shrink-0 text-primary" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium truncate">{selectedFile.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 shrink-0"
                  onClick={() => {
                    setSelectedFile(null)
                    form.resetField('file')
                  }}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            )}

            {/* Upload progress */}
            {upload.isPending && uploadProgress > 0 && (
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Subiendo...</span>
                  <span>{uploadProgress}%</span>
                </div>
                <Progress value={uploadProgress} className="h-1.5" />
              </div>
            )}

            {/* Name */}
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Nombre del documento</FormLabel>
                  <FormControl>
                    <Input placeholder="Nombre del documento" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Description */}
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Descripción (opcional)</FormLabel>
                  <FormControl>
                    <Input placeholder="Descripción breve" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Tags */}
            <FormField
              control={form.control}
              name="tags"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Etiquetas (opcional, separadas por coma)</FormLabel>
                  <FormControl>
                    <Input placeholder="contrato, legal, 2024" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter>
              <Button type="button" variant="outline" onClick={handleClose}>
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={!selectedFile || upload.isPending}
              >
                {upload.isPending ? 'Subiendo...' : 'Subir documento'}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
