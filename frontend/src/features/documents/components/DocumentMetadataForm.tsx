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
import { updateDocumentSchema, type UpdateDocumentFormValues } from '../validation'
import { useUpdateDocument } from '../hooks'
import type { Document } from '@/shared/types'

interface DocumentMetadataFormProps {
  document: Document
  onSuccess?: () => void
}

export function DocumentMetadataForm({ document, onSuccess }: DocumentMetadataFormProps) {
  const updateDocument = useUpdateDocument()

  const form = useForm<UpdateDocumentFormValues>({
    resolver: zodResolver(updateDocumentSchema),
    defaultValues: {
      name: document.name,
      description: document.description ?? '',
      tags: document.tags.join(', '),
    },
  })

  useEffect(() => {
    form.reset({
      name: document.name,
      description: document.description ?? '',
      tags: document.tags.join(', '),
    })
  }, [document.id, form])

  const onSubmit = (values: UpdateDocumentFormValues) => {
    const tags = values.tags
      ? values.tags
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean)
      : []

    updateDocument.mutate(
      {
        id: document.id,
        data: {
          name: values.name,
          description: values.description,
          tags,
        },
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
