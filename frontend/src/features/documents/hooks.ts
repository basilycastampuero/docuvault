import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  documentsApi,
  foldersApi,
  type ListDocumentsParams,
  type UploadDocumentData,
  type UpdateDocumentData,
  type UploadVersionData,
} from './api'

export const documentKeys = {
  all: ['documents'] as const,
  list: (params: ListDocumentsParams = {}) => [...documentKeys.all, 'list', params] as const,
  detail: (id: string) => [...documentKeys.all, id] as const,
  versions: (id: string, page: number) => [...documentKeys.all, id, 'versions', page] as const,
}

export const folderKeys = {
  tree: ['folders', 'tree'] as const,
}

export function useDocuments(params: ListDocumentsParams = {}) {
  return useQuery({
    queryKey: documentKeys.list(params),
    queryFn: () => documentsApi.list(params),
  })
}

export function useDocument(id: string, pollForAi = false) {
  return useQuery({
    queryKey: documentKeys.detail(id),
    queryFn: () => documentsApi.getById(id),
    enabled: !!id,
    refetchInterval: (query) => {
      const ocrStatus = query.state.data?.ocr_status
      const updateCount = query.state.dataUpdateCount ?? 0
      // Cap OCR polling at ~2 min (40 × 3s)
      if (updateCount > 40 && (ocrStatus === 'pending' || ocrStatus === 'processing')) return false
      if (ocrStatus === 'pending' || ocrStatus === 'processing') return 3000
      if (!pollForAi) return false
      const aiAnalysis = query.state.data?.metadata?.ai_analysis as
        | { status?: string }
        | undefined
      // Keep polling while no result exists OR while the previous attempt failed
      // (the user may have clicked "Reintentar"). Stop only on a successful result.
      if (!aiAnalysis || aiAnalysis.status === 'failed') return 3000
      return false
    },
  })
}

export function useDocumentVersions(id: string, page = 1) {
  return useQuery({
    queryKey: documentKeys.versions(id, page),
    queryFn: () => documentsApi.getVersions(id, page),
    enabled: !!id,
  })
}

export function useFolderTree() {
  return useQuery({
    queryKey: folderKeys.tree,
    queryFn: () => foldersApi.getTree(),
  })
}

export function useUploadDocument() {
  const queryClient = useQueryClient()
  const [uploadProgress, setUploadProgress] = useState(0)

  const mutation = useMutation({
    mutationFn: (data: UploadDocumentData) =>
      documentsApi.upload({
        ...data,
        onUploadProgress: setUploadProgress,
      }),
    onSuccess: () => {
      setUploadProgress(0)
      queryClient.invalidateQueries({ queryKey: documentKeys.all })
      queryClient.invalidateQueries({ queryKey: ['folders'] })
    },
    onError: () => {
      setUploadProgress(0)
    },
  })

  return { mutation, uploadProgress }
}

export function useUpdateDocument() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateDocumentData }) =>
      documentsApi.update(id, data),
    onSuccess: (_doc, variables) => {
      queryClient.invalidateQueries({ queryKey: documentKeys.detail(variables.id) })
      queryClient.invalidateQueries({ queryKey: documentKeys.all })
    },
  })
}

export function useDeleteDocument() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => documentsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: documentKeys.all })
    },
  })
}

export function useDownloadDocument() {
  return useMutation({
    mutationFn: (id: string) => documentsApi.getDownloadUrl(id),
    onSuccess: (url) => {
      window.open(url, '_blank')
    },
  })
}

export function useUploadVersion(documentId: string) {
  const queryClient = useQueryClient()
  const [uploadProgress, setUploadProgress] = useState(0)

  const mutation = useMutation({
    mutationFn: (data: UploadVersionData) =>
      documentsApi.uploadVersion(documentId, {
        ...data,
        onUploadProgress: setUploadProgress,
      }),
    onSuccess: () => {
      setUploadProgress(0)
      queryClient.invalidateQueries({ queryKey: documentKeys.detail(documentId) })
      queryClient.invalidateQueries({
        queryKey: documentKeys.versions(documentId, 1),
      })
    },
    onError: () => {
      setUploadProgress(0)
    },
  })

  return { mutation, uploadProgress }
}

export function useReprocessOcr() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => documentsApi.reprocessOcr(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: documentKeys.detail(id) })
    },
  })
}

export function useRequestAiAnalysis() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => documentsApi.requestAiAnalysis(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: documentKeys.detail(id) })
    },
    meta: { suppressGlobalToast: true },
  })
}
