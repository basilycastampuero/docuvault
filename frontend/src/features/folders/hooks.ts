import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { foldersApi, type CreateFolderData, type RenameFolderData } from './api'

export const folderKeys = {
  all: ['folders'] as const,
  list: () => [...folderKeys.all, 'list'] as const,
  detail: (id: string) => [...folderKeys.all, id] as const,
  children: (id: string, page: number) => [...folderKeys.all, id, 'children', page] as const,
  documents: (id: string, page: number) => [...folderKeys.all, id, 'documents', page] as const,
}

export function useFolders() {
  return useQuery({
    queryKey: folderKeys.list(),
    queryFn: () => foldersApi.list(),
  })
}

export function useFolder(id: string) {
  return useQuery({
    queryKey: folderKeys.detail(id),
    queryFn: () => foldersApi.getById(id),
    enabled: !!id,
  })
}

export function useFolderChildren(id: string, page = 1) {
  return useQuery({
    queryKey: folderKeys.children(id, page),
    queryFn: () => foldersApi.getChildren(id, page),
    enabled: !!id,
  })
}

export function useFolderDocuments(id: string, page = 1) {
  return useQuery({
    queryKey: folderKeys.documents(id, page),
    queryFn: () => foldersApi.getDocuments(id, page),
    enabled: !!id,
  })
}

export function useCreateFolder() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: CreateFolderData) => foldersApi.create(data),
    onSuccess: (_folder, variables) => {
      queryClient.invalidateQueries({ queryKey: folderKeys.list() })
      if (variables.parent_id) {
        queryClient.invalidateQueries({
          queryKey: folderKeys.all,
        })
      }
    },
  })
}

export function useRenameFolder() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: RenameFolderData }) =>
      foldersApi.rename(id, data),
    onSuccess: (_folder, variables) => {
      queryClient.invalidateQueries({ queryKey: folderKeys.detail(variables.id) })
      queryClient.invalidateQueries({ queryKey: folderKeys.list() })
      queryClient.invalidateQueries({ queryKey: folderKeys.all })
    },
  })
}

export function useDeleteFolder() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => foldersApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: folderKeys.all })
    },
  })
}
