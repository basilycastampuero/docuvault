import { apiClient, unwrap, unwrapPaginated } from '@/lib/api-client'
import type { Envelope, PaginatedEnvelope, PaginatedMeta, AuditLog, AuditAction } from '@/shared/types'

export interface ListAuditLogsParams {
  action?: AuditAction
  entity_type?: string
  entity_id?: string
  user?: string
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

  getById: async (id: number): Promise<AuditLog> => {
    const response = await apiClient.get<Envelope<AuditLog>>(`/audit-logs/${id}/`)
    return unwrap(response)
  },
}
