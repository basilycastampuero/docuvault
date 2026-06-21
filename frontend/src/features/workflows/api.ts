import { apiClient, unwrap, unwrapPaginated } from '@/lib/api-client'
import type {
  Envelope,
  PaginatedEnvelope,
  PaginatedMeta,
  WorkflowTemplate,
  WorkflowExecution,
  WorkflowStepLog,
  WorkflowStepAction,
  UserRole,
} from '@/shared/types'

// ─── Templates ─────────────────────────────────────────────────────────────────

export interface ListTemplatesParams {
  page?: number
  page_size?: number
}

export interface CreateTemplateStepData {
  name: string
  order: number
  required_role: UserRole
  is_final: boolean
  actions: Record<string, unknown>
}

export interface CreateTemplateData {
  name: string
  description?: string
  steps: CreateTemplateStepData[]
}

export interface UpdateTemplateData {
  name?: string
  description?: string
  is_active?: boolean
}

// ─── Executions ────────────────────────────────────────────────────────────────

export interface ListExecutionsParams {
  document?: string
  status?: string
  page?: number
}

export interface StartExecutionData {
  document_id: string
  template_id: string
}

export interface AdvanceStepData {
  action: WorkflowStepAction
  comment?: string
}

// ─── API object ────────────────────────────────────────────────────────────────

export const workflowsApi = {
  templates: {
    list: async (
      params: ListTemplatesParams = {},
    ): Promise<{ items: WorkflowTemplate[]; meta: PaginatedMeta }> => {
      const response = await apiClient.get<PaginatedEnvelope<WorkflowTemplate>>(
        '/workflows/templates/',
        { params },
      )
      return unwrapPaginated(response)
    },

    getById: async (id: string): Promise<WorkflowTemplate> => {
      const response = await apiClient.get<Envelope<WorkflowTemplate>>(
        `/workflows/templates/${id}/`,
      )
      return unwrap(response)
    },

    create: async (data: CreateTemplateData): Promise<WorkflowTemplate> => {
      const response = await apiClient.post<Envelope<WorkflowTemplate>>(
        '/workflows/templates/',
        data,
      )
      return unwrap(response)
    },

    update: async (id: string, data: UpdateTemplateData): Promise<WorkflowTemplate> => {
      const response = await apiClient.patch<Envelope<WorkflowTemplate>>(
        `/workflows/templates/${id}/`,
        data,
      )
      return unwrap(response)
    },

    delete: async (id: string): Promise<void> => {
      await apiClient.delete(`/workflows/templates/${id}/`)
    },
  },

  executions: {
    list: async (
      params: ListExecutionsParams = {},
    ): Promise<{ items: WorkflowExecution[]; meta: PaginatedMeta }> => {
      const response = await apiClient.get<PaginatedEnvelope<WorkflowExecution>>(
        '/workflows/executions/',
        { params },
      )
      return unwrapPaginated(response)
    },

    getById: async (id: string): Promise<WorkflowExecution> => {
      const response = await apiClient.get<Envelope<WorkflowExecution>>(
        `/workflows/executions/${id}/`,
      )
      return unwrap(response)
    },

    start: async (data: StartExecutionData): Promise<WorkflowExecution> => {
      const response = await apiClient.post<Envelope<WorkflowExecution>>(
        '/workflows/executions/',
        data,
      )
      return unwrap(response)
    },

    advance: async (id: string, data: AdvanceStepData): Promise<WorkflowExecution> => {
      const response = await apiClient.post<Envelope<WorkflowExecution>>(
        `/workflows/executions/${id}/advance/`,
        data,
      )
      return unwrap(response)
    },

    getLogs: async (
      id: string,
      page = 1,
    ): Promise<{ items: WorkflowStepLog[]; meta: PaginatedMeta }> => {
      const response = await apiClient.get<PaginatedEnvelope<WorkflowStepLog>>(
        `/workflows/executions/${id}/logs/`,
        { params: { page } },
      )
      return unwrapPaginated(response)
    },
  },
}
