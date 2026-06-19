import { z } from 'zod'

export const ALLOWED_MIME_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/msword',
  'application/vnd.ms-excel',
  'image/jpeg',
  'image/png',
  'application/zip',
] as const

export const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.xlsx', '.doc', '.xls', '.jpg', '.jpeg', '.png', '.zip']

export const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50MB

const fileSchema = z
  .instanceof(File)
  .refine((f) => f.size <= MAX_FILE_SIZE, {
    message: `El archivo no puede superar ${MAX_FILE_SIZE / 1024 / 1024}MB`,
  })
  .refine(
    (f) => ALLOWED_MIME_TYPES.includes(f.type as (typeof ALLOWED_MIME_TYPES)[number]),
    {
      message: `Tipo de archivo no permitido. Formatos aceptados: ${ALLOWED_EXTENSIONS.join(', ')}`,
    },
  )

export const uploadDocumentSchema = z.object({
  file: fileSchema,
  name: z.string().min(1, 'El nombre es obligatorio').max(255),
  folder_id: z.string().uuid().optional(),
  description: z.string().max(1000).optional(),
  tags: z.string().optional(),
})

export type UploadDocumentFormValues = z.infer<typeof uploadDocumentSchema>

export const updateDocumentSchema = z.object({
  name: z.string().min(1, 'El nombre es obligatorio').max(255),
  description: z.string().max(1000).optional(),
  tags: z.string().optional(),
})

export type UpdateDocumentFormValues = z.infer<typeof updateDocumentSchema>

export function validateFile(file: File): string | null {
  if (file.size > MAX_FILE_SIZE) {
    return `El archivo supera el tamaño máximo de ${MAX_FILE_SIZE / 1024 / 1024}MB`
  }
  if (!ALLOWED_MIME_TYPES.includes(file.type as (typeof ALLOWED_MIME_TYPES)[number])) {
    return `Tipo de archivo no permitido. Formatos aceptados: ${ALLOWED_EXTENSIONS.join(', ')}`
  }
  return null
}
