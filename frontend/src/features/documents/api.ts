import { apiClient, unwrap, unwrapPaginated } from '@/lib/api-client'
import type { Envelope, PaginatedEnvelope, PaginatedMeta } from '@/shared/types'
import type { Document, DocumentVersion, DocumentStatus, Folder } from '@/shared/types'

export interface ListDocumentsParams {
  folder_id?: string
  status?: DocumentStatus
  page?: number
  page_size?: number
}

export interface UploadDocumentData {
  file: File
  name: string
  folder_id?: string
  description?: string
  tags?: string[]
  onUploadProgress?: (progress: number) => void
}

export interface UpdateDocumentData {
  name?: string
  description?: string
  tags?: string[]
  folder_id?: string | null
}

export interface UploadVersionData {
  file: File
  change_description?: string
  onUploadProgress?: (progress: number) => void
}

export const documentsApi = {
  list: async (
    params: ListDocumentsParams = {},
  ): Promise<{ items: Document[]; meta: PaginatedMeta }> => {
    const { onUploadProgress: _, ...queryParams } = params as ListDocumentsParams & {
      onUploadProgress?: unknown
    }
    const response = await apiClient.get<PaginatedEnvelope<Document>>('/documents/', {
      params: queryParams,
    })
    return unwrapPaginated(response)
  },

  getById: async (id: string): Promise<Document> => {
    const response = await apiClient.get<Envelope<Document>>(`/documents/${id}/`)
    return unwrap(response)
  },

  upload: async ({
    file,
    name,
    folder_id,
    description,
    tags,
    onUploadProgress,
  }: UploadDocumentData): Promise<Document> => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', name)
    if (folder_id) formData.append('folder_id', folder_id)
    if (description) formData.append('description', description)
    if (tags) tags.forEach((tag) => formData.append('tags', tag))

    const response = await apiClient.post<Envelope<Document>>('/documents/', formData, {
      onUploadProgress: (e) => {
        if (onUploadProgress && e.total) {
          onUploadProgress(Math.round((e.loaded * 100) / e.total))
        }
      },
    })
    return unwrap(response)
  },

  update: async (id: string, data: UpdateDocumentData): Promise<Document> => {
    const response = await apiClient.patch<Envelope<Document>>(`/documents/${id}/`, data)
    return unwrap(response)
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/documents/${id}/`)
  },

  getDownloadUrl: async (id: string): Promise<string> => {
    const response = await apiClient.get<Envelope<{ url: string; expires_in: number }>>(
      `/documents/${id}/download/`,
    )
    return unwrap(response).url
  },

  getVersions: async (
    id: string,
    page = 1,
  ): Promise<{ items: DocumentVersion[]; meta: Partial<PaginatedMeta> }> => {
    const response = await apiClient.get<PaginatedEnvelope<DocumentVersion>>(
      `/documents/${id}/versions/`,
      { params: { page } },
    )
    return unwrapPaginated(response)
  },

  uploadVersion: async (
    id: string,
    { file, change_description, onUploadProgress }: UploadVersionData,
  ): Promise<DocumentVersion> => {
    const formData = new FormData()
    formData.append('file', file)
    if (change_description) formData.append('change_description', change_description)

    const response = await apiClient.post<Envelope<DocumentVersion>>(
      `/documents/${id}/versions/`,
      formData,
      {
        onUploadProgress: (e) => {
          if (onUploadProgress && e.total) {
            onUploadProgress(Math.round((e.loaded * 100) / e.total))
          }
        },
      },
    )
    return unwrap(response)
  },

  reprocessOcr: async (id: string): Promise<void> => {
    await apiClient.post(`/documents/${id}/reprocess-ocr/`)
  },

  requestAiAnalysis: async (id: string): Promise<void> => {
    await apiClient.post(`/documents/${id}/analyze/`)
  },

  regenerateThumbnail: async (id: string): Promise<void> => {
    await apiClient.post(`/documents/${id}/regenerate-thumbnail/`)
  },
}

export const foldersApi = {
  getTree: async (): Promise<Folder[]> => {
    const response = await apiClient.get<Envelope<Folder[]>>('/folders/tree/')
    return unwrap(response)
  },
}
