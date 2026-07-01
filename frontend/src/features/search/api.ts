import { apiClient, unwrapPaginated } from '@/lib/api-client'
import type { PaginatedEnvelope, PaginatedMeta, SearchResult } from '@/shared/types'

export const searchApi = {
  search: async (
    query: string,
    page = 1,
  ): Promise<{ items: SearchResult[]; meta: PaginatedMeta }> => {
    const response = await apiClient.get<PaginatedEnvelope<SearchResult>>('/search/', {
      params: { q: query, page },
    })
    return unwrapPaginated(response)
  },
}
