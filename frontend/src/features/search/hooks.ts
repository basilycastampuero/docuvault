import { useQuery } from '@tanstack/react-query'
import { searchApi } from './api'

export const searchKeys = {
  results: (query: string, page: number) => ['search', query, page] as const,
}

export function useSearch(query: string, page = 1) {
  return useQuery({
    queryKey: searchKeys.results(query, page),
    queryFn: () => searchApi.search(query, page),
    enabled: query.trim().length > 0,
  })
}
