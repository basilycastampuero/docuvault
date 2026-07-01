import { MutationCache, QueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { parseApiError } from '@/lib/api-client'
import { ApiError } from '@/shared/types'

export const queryClient = new QueryClient({
  mutationCache: new MutationCache({
    onError: (error, _vars, _ctx, mutation) => {
      // Global feedback for any failed mutation.
      // Mutations with inline error UI can opt out via meta.suppressGlobalToast.
      if ((mutation.meta as Record<string, unknown>)?.suppressGlobalToast) return
      toast.error(parseApiError(error).message)
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      retry: (failureCount, error) => {
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
          return false
        }
        return failureCount < 2
      },
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: false,
    },
  },
})
