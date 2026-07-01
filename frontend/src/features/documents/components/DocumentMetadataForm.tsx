import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { updateDocumentSchema, type UpdateDocumentFormValues } from '../validation'
import { useUpdateDocument, useFolderTree } from '../hooks'
import type { Document } from '@/shared/types'

// Sentinel value for "no folder" in the Select. Mapped to null before the API call.
const ROOT_SENTINEL = '__root__'

interface DocumentMetadataFormProps {
  document: Document
  onSuccess?: () => void
}

export function DocumentMetadataForm({ document, onSuccess }: DocumentMetadataFormProps) {
  const updateDocument = useUpdateDocument()
  const { data: folders } = useFolderTree()

  const form = useForm<UpdateDocumentFormValues>({
    resolver: zodResolver(updateDocumentSchema),
    defaultValues: {
      name: document.name,
      description: document.description ?? '',
      tags: document.tags.join(', '),
      folder_id: document.folder ?? ROOT_SENTINEL,
    },
  })

  useEffect(() => {
    form.reset({
      name: document.name,
      description: document.description ?? '',
      tags: document.tags.join(', '),
      folder_id: document.folder ?? ROOT_SENTINEL,
    })
  }, [document.id, form])

  const onSubmit = (values: UpdateDocumentFormValues) => {
    const tags = values.tags
      ? values.tags
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean)
      : []

    // Only include folder_id in the payload when the user actually changed it,
    // to avoid a no-op audit log entry on every metadata save.
    const data: Parameters<typeof updateDocument.mutate>[0]['data'] = {
      name: values.name,
      description: values.description,
      tags,
    }
    if (form.formState.dirtyFields.folder_id) {
      data.folder_id = values.folder_id === ROOT_SENTINEL ? null : (values.folder_id ?? null)
    }

    updateDocument.mutate(
      {
        id: document.id,
        data,
      },
      { onSuccess },
    )
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Nombre</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Descripción</FormLabel>
              <FormControl>
                <Input placeholder="Sin descripción" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="tags"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Etiquetas (separadas por coma)</FormLabel>
              <FormControl>
                <Input placeholder="contrato, legal, 2024" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="folder_id"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Carpeta</FormLabel>
              <Select
                value={field.value ?? ROOT_SENTINEL}
                onValueChange={field.onChange}
              >
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Sin carpeta" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  <SelectItem value={ROOT_SENTINEL}>Sin carpeta</SelectItem>
                  {folders?.map((folder) => (
                    <SelectItem key={folder.id} value={folder.id}>
                      {folder.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="flex justify-end">
          <Button
            type="submit"
            disabled={updateDocument.isPending || !form.formState.isDirty}
          >
            {updateDocument.isPending ? 'Guardando...' : 'Guardar cambios'}
          </Button>
        </div>
      </form>
    </Form>
  )
}
