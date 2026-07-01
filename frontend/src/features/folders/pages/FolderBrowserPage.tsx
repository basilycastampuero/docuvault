import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { Plus, Loader2, Upload } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { AppPagination } from '@/shared/components/Pagination'
import { useAuthStore } from '@/features/auth/store'
import { FolderBreadcrumb } from '../components/FolderBreadcrumb'
import { FolderCard } from '../components/FolderCard'
import { CreateFolderDialog } from '../components/CreateFolderDialog'
import {
  useFolders,
  useFolderChildren,
  useFolderDocuments,
  useFolder,
  useRenameFolder,
  useDeleteFolder,
} from '../hooks'
import type { Folder } from '@/shared/types'
import { DocumentCard } from '@/features/documents/components/DocumentCard'
import { DocumentUploadDropzone } from '@/features/documents/components/DocumentUploadDropzone'
import { WRITE_ROLES } from '@/shared/lib/roles'

const renameSchema = z.object({
  name: z.string().min(1, 'El nombre es obligatorio').max(255),
})
type RenameFormValues = z.infer<typeof renameSchema>

export function FolderBrowserPage() {
  const { id } = useParams<{ id?: string }>()
  const isRoot = !id

  const role = useAuthStore((s) => s.user?.role)
  const canWrite = role ? WRITE_ROLES.includes(role) : false

  const [createOpen, setCreateOpen] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [renameTarget, setRenameTarget] = useState<Folder | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Folder | null>(null)
  const [docPage, setDocPage] = useState(1)
  const [childPage, setChildPage] = useState(1)

  const rootFolders = useFolders()
  const currentFolder = useFolder(id ?? '')
  const children = useFolderChildren(id ?? '', childPage)
  const folderDocs = useFolderDocuments(id ?? '', docPage)

  const renameFolder = useRenameFolder()
  const deleteFolder = useDeleteFolder()

  const renameForm = useForm<RenameFormValues>({
    resolver: zodResolver(renameSchema),
    defaultValues: { name: renameTarget?.name ?? '' },
  })

  const handleRenameOpen = (folder: Folder) => {
    setRenameTarget(folder)
    renameForm.setValue('name', folder.name)
  }

  const handleRenameSubmit = (values: RenameFormValues) => {
    if (!renameTarget) return
    renameFolder.mutate(
      { id: renameTarget.id, data: { name: values.name } },
      { onSuccess: () => setRenameTarget(null) },
    )
  }

  const handleDeleteConfirm = () => {
    if (!deleteTarget) return
    deleteFolder.mutate(deleteTarget.id, {
      onSuccess: () => setDeleteTarget(null),
    })
  }

  const totalDocPages = folderDocs.data
    ? Math.ceil(folderDocs.data.meta.count / folderDocs.data.meta.page_size)
    : 1
  const totalChildPages = children.data
    ? Math.ceil(children.data.meta.count / children.data.meta.page_size)
    : 1

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          {isRoot ? (
            <h1 className="text-2xl font-bold tracking-tight">Carpetas</h1>
          ) : currentFolder.data ? (
            <div className="space-y-1">
              <FolderBreadcrumb trail={[]} currentName={currentFolder.data.name} />
              <h1 className="text-2xl font-bold tracking-tight">{currentFolder.data.name}</h1>
            </div>
          ) : null}
        </div>

        <div className="flex items-center gap-2">
          {canWrite && !isRoot && (
            <Button variant="outline" onClick={() => setUploadOpen(true)}>
              <Upload className="mr-2 h-4 w-4" />
              Subir documento
            </Button>
          )}
          {canWrite && (
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Nueva carpeta
            </Button>
          )}
        </div>
      </div>

      {/* Root folders or children */}
      {isRoot ? (
        <section>
          {rootFolders.isLoading && (
            <div className="flex justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}
          {rootFolders.data && rootFolders.data.items.length === 0 && (
            <p className="text-center text-muted-foreground py-12">
              No hay carpetas aun. Crea una para empezar.
            </p>
          )}
          {rootFolders.data && rootFolders.data.items.length > 0 && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {rootFolders.data.items.map((folder) => (
                <FolderCard
                  key={folder.id}
                  folder={folder}
                  onRename={handleRenameOpen}
                  onDelete={(f) => setDeleteTarget(f)}
                />
              ))}
            </div>
          )}
        </section>
      ) : (
        <>
          {/* Child folders */}
          {children.data && children.data.items.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                Subcarpetas
              </h2>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {children.data.items.map((folder) => (
                  <FolderCard
                    key={folder.id}
                    folder={folder}
                    onRename={handleRenameOpen}
                    onDelete={(f) => setDeleteTarget(f)}
                  />
                ))}
              </div>
              <AppPagination
                page={childPage}
                totalPages={totalChildPages}
                onPageChange={setChildPage}
              />
            </section>
          )}

          {/* Documents in this folder */}
          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
              Documentos
            </h2>
            {folderDocs.isLoading && (
              <div className="flex justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            )}
            {folderDocs.data && folderDocs.data.items.length === 0 && (
              <p className="text-center text-muted-foreground py-8">
                Esta carpeta no tiene documentos.
              </p>
            )}
            {folderDocs.data && folderDocs.data.items.length > 0 && (
              <>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {folderDocs.data.items.map((doc) => (
                    <DocumentCard key={doc.id} document={doc} />
                  ))}
                </div>
                <AppPagination
                  page={docPage}
                  totalPages={totalDocPages}
                  onPageChange={setDocPage}
                />
              </>
            )}
          </section>
        </>
      )}

      {/* Upload document dialog — key={id} forces remount on folder navigation so
          useForm reinitializes with the correct folderId (defaultValues are read once) */}
      {!isRoot && (
        <DocumentUploadDropzone
          key={id}
          open={uploadOpen}
          folderId={id}
          onOpenChange={setUploadOpen}
        />
      )}

      {/* Create folder dialog */}
      <CreateFolderDialog
        open={createOpen}
        parentId={id}
        onOpenChange={setCreateOpen}
      />

      {/* Rename dialog */}
      <Dialog open={!!renameTarget} onOpenChange={(o) => !o && setRenameTarget(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Renombrar carpeta</DialogTitle>
          </DialogHeader>
          <Form {...renameForm}>
            <form onSubmit={renameForm.handleSubmit(handleRenameSubmit)} className="space-y-4">
              <FormField
                control={renameForm.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Nuevo nombre</FormLabel>
                    <FormControl>
                      <Input autoFocus {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setRenameTarget(null)}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={renameFolder.isPending}>
                  {renameFolder.isPending ? 'Guardando...' : 'Guardar'}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminar carpeta</AlertDialogTitle>
            <AlertDialogDescription>
              Esta accion eliminara la carpeta "{deleteTarget?.name}" y todo su contenido.
              Esta accion no se puede deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteFolder.isPending ? 'Eliminando...' : 'Eliminar'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
