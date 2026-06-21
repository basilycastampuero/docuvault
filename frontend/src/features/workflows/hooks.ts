import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  workflowsApi,
  type ListTemplatesParams,
  type ListExecutionsParams,
  type CreateTemplateData,
  type UpdateTemplateData,
  type StartExecutionData,
  type AdvanceStepData,
} from './api'

// ─── Query keys ────────────────────────────────────────────────────────────────

export const workflowKeys = {
  all: ['workflows'] as const,
  templates: () => [...workflowKeys.all, 'templates'] as const,
  templateList: (params: ListTemplatesParams = {}) =>
    [...workflowKeys.templates(), 'list', params] as const,
  templateDetail: (id: string) => [...workflowKeys.templates(), id] as const,
  executions: () => [...workflowKeys.all, 'executions'] as const,
  executionList: (params: ListExecutionsParams = {}) =>
    [...workflowKeys.executions(), 'list', params] as const,
  executionDetail: (id: string) => [...workflowKeys.executions(), id] as const,
  executionLogs: (id: string, page: number) =>
    [...workflowKeys.executions(), id, 'logs', page] as const,
}

// ─── Template hooks ─────────────────────────────────────────────────────────────

export function useWorkflowTemplates(params: ListTemplatesParams = {}) {
  return useQuery({
    queryKey: workflowKeys.templateList(params),
    queryFn: () => workflowsApi.templates.list(params),
  })
}

export function useWorkflowTemplate(id: string) {
  return useQuery({
    queryKey: workflowKeys.templateDetail(id),
    queryFn: () => workflowsApi.templates.getById(id),
    enabled: !!id,
  })
}

export function useCreateWorkflowTemplate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: CreateTemplateData) => workflowsApi.templates.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workflowKeys.templates() })
    },
  })
}

export function useUpdateWorkflowTemplate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateTemplateData }) =>
      workflowsApi.templates.update(id, data),
    onSuccess: (_template, variables) => {
      queryClient.invalidateQueries({ queryKey: workflowKeys.templateDetail(variables.id) })
      queryClient.invalidateQueries({ queryKey: workflowKeys.templates() })
    },
  })
}

export function useDeleteWorkflowTemplate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => workflowsApi.templates.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workflowKeys.templates() })
    },
  })
}

// ─── Execution hooks ────────────────────────────────────────────────────────────

export function useWorkflowExecutions(params: ListExecutionsParams = {}) {
  return useQuery({
    queryKey: workflowKeys.executionList(params),
    queryFn: () => workflowsApi.executions.list(params),
  })
}

export function useWorkflowExecution(id: string) {
  return useQuery({
    queryKey: workflowKeys.executionDetail(id),
    queryFn: () => workflowsApi.executions.getById(id),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'pending' || status === 'in_progress') return 5000
      return false
    },
  })
}

export function useStartWorkflowExecution() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: StartExecutionData) => workflowsApi.executions.start(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workflowKeys.executions() })
    },
  })
}

export function useAdvanceWorkflowStep() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: AdvanceStepData }) =>
      workflowsApi.executions.advance(id, data),
    onSuccess: (_execution, variables) => {
      queryClient.invalidateQueries({ queryKey: workflowKeys.executionDetail(variables.id) })
      queryClient.invalidateQueries({ queryKey: workflowKeys.executions() })
    },
  })
}

export function useWorkflowExecutionLogs(id: string, page = 1) {
  return useQuery({
    queryKey: workflowKeys.executionLogs(id, page),
    queryFn: () => workflowsApi.executions.getLogs(id, page),
    enabled: !!id,
  })
}
