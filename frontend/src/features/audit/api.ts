import { apiClient, unwrapPaginated } from '@/lib/api-client'
import type { PaginatedEnvelope, PaginatedMeta, AuditLog, AuditAction } from '@/shared/types'

export interface ListAuditLogsParams {
  action?: AuditAction
  entity_type?: string
  entity_id?: string
  user_email?: string
  created_after?: string
  created_before?: string
  page?: number
}

export const auditApi = {
  list: async (
    params: ListAuditLogsParams = {},
  ): Promise<{ items: AuditLog[]; meta: PaginatedMeta }> => {
    const cleanParams = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== ''),
    )
    const response = await apiClient.get<PaginatedEnvelope<AuditLog>>('/audit-logs/', {
      params: cleanParams,
    })
    return unwrapPaginated(response)
  },
}
