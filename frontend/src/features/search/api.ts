import { apiClient, unwrapPaginated } from '@/lib/api-client'
import type { PaginatedEnvelope, PaginatedMeta } from '@/shared/types'
import type { Document } from '@/shared/types'

export const searchApi = {
  search: async (
    query: string,
    page = 1,
  ): Promise<{ items: Document[]; meta: PaginatedMeta }> => {
    const response = await apiClient.get<PaginatedEnvelope<Document>>('/search/', {
      params: { q: query, page },
    })
    return unwrapPaginated(response)
  },
}
