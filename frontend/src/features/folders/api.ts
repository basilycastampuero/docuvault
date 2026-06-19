import { apiClient, unwrap, unwrapPaginated } from '@/lib/api-client'
import type { Envelope, PaginatedEnvelope } from '@/shared/types'
import type { Folder, Document } from '@/shared/types'

export interface CreateFolderData {
  name: string
  parent_id?: string
}

export interface RenameFolderData {
  name: string
}

export const foldersApi = {
  list: async (): Promise<{ items: Folder[]; meta: import('@/shared/types').PaginatedMeta }> => {
    const response = await apiClient.get<PaginatedEnvelope<Folder>>('/folders/')
    return unwrapPaginated(response)
  },

  getById: async (id: string): Promise<Folder> => {
    const response = await apiClient.get<Envelope<Folder>>(`/folders/${id}/`)
    return unwrap(response)
  },

  create: async (data: CreateFolderData): Promise<Folder> => {
    const response = await apiClient.post<Envelope<Folder>>('/folders/', data)
    return unwrap(response)
  },

  rename: async (id: string, data: RenameFolderData): Promise<Folder> => {
    const response = await apiClient.patch<Envelope<Folder>>(`/folders/${id}/`, data)
    return unwrap(response)
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/folders/${id}/`)
  },

  getChildren: async (
    id: string,
    page = 1,
  ): Promise<{ items: Folder[]; meta: import('@/shared/types').PaginatedMeta }> => {
    const response = await apiClient.get<PaginatedEnvelope<Folder>>(
      `/folders/${id}/children/`,
      { params: { page } },
    )
    return unwrapPaginated(response)
  },

  getDocuments: async (
    id: string,
    page = 1,
  ): Promise<{ items: Document[]; meta: import('@/shared/types').PaginatedMeta }> => {
    const response = await apiClient.get<PaginatedEnvelope<Document>>(
      `/folders/${id}/documents/`,
      { params: { page } },
    )
    return unwrapPaginated(response)
  },
}
