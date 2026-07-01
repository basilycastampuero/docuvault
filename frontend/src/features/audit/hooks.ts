import { useQuery } from '@tanstack/react-query'
import { auditApi, type ListAuditLogsParams } from './api'

export const auditKeys = {
  all: ['audit-logs'] as const,
  list: (params: ListAuditLogsParams = {}) => [...auditKeys.all, 'list', params] as const,
}

export function useAuditLogs(
  params: ListAuditLogsParams = {},
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: auditKeys.list(params),
    queryFn: () => auditApi.list(params),
    enabled: options?.enabled ?? true,
  })
}
