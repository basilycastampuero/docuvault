// ─── Backend envelope types ────────────────────────────────────────────────────

export interface Envelope<T> {
  data: T
  meta: Record<string, unknown>
}

export interface PaginatedMeta {
  count: number
  next: string | null
  previous: string | null
  page: number
  page_size: number
}

export interface PaginatedEnvelope<T> {
  data: T[]
  meta: PaginatedMeta
}

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    details: Record<string, unknown>
  }
}

// ─── ApiError class ────────────────────────────────────────────────────────────

export class ApiError extends Error {
  code: string
  details: Record<string, unknown>
  status: number

  constructor(
    message: string,
    code: string,
    status: number,
    details: Record<string, unknown> = {},
  ) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
  }
}

// ─── Document domain types ─────────────────────────────────────────────────────

export type OcrStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'skipped'

export type DocumentStatus =
  | 'draft'
  | 'under_review'
  | 'approved'
  | 'rejected'
  | 'archived'

export interface Folder {
  id: string
  name: string
  parent: string | null
  owner: { id: string; email: string }
  created_at: string
  updated_at: string
}

export interface Document {
  id: string
  name: string
  description: string
  mime_type: string
  file_size: number
  checksum: string
  storage_path: string
  status: DocumentStatus
  version: number
  ocr_status: OcrStatus
  ocr_content: string
  tags: string[]
  metadata: Record<string, unknown>
  folder: { id: string; name: string } | null
  created_by: { id: string; email: string }
  created_at: string
  updated_at: string
}

export interface DocumentVersion {
  id: string
  version_number: number
  file_size: number
  mime_type: string
  checksum: string
  created_by: { id: string; email: string }
  change_description: string
  created_at: string
}

// ─── Auth domain types ─────────────────────────────────────────────────────────

export type UserRole =
  | 'super_admin'
  | 'org_admin'
  | 'supervisor'
  | 'editor'
  | 'viewer'
  | 'auditor'

export interface UserProfile {
  id: string
  email: string
  first_name: string
  last_name: string
  role: UserRole
  organization_id: string
  organization_name: string
  is_active: boolean
}

// ─── Workflow domain types ──────────────────────────────────────────────────────

export type WorkflowStatus = 'pending' | 'in_progress' | 'completed' | 'rejected' | 'cancelled'
export type WorkflowStepAction = 'approved' | 'rejected' | 'commented'

export interface WorkflowStep {
  id: string
  name: string
  order: number
  required_role: UserRole
  is_final: boolean
  actions: Record<string, unknown>
}

export interface WorkflowTemplate {
  id: string
  name: string
  description: string
  is_active: boolean
  config: Record<string, unknown>
  steps: WorkflowStep[]
  organization: string
  created_at: string
  updated_at: string
}

export interface WorkflowExecution {
  id: string
  template: { id: string; name: string }
  document: { id: string; name: string }
  current_step: WorkflowStep | null
  status: WorkflowStatus
  started_by: { id: string; email: string }
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface WorkflowStepLog {
  id: string
  step: { id: string; name: string; order: number }
  action: WorkflowStepAction
  performed_by: { id: string; email: string }
  comment: string
  created_at: string
}

// ─── Audit domain types ─────────────────────────────────────────────────────────

export type AuditAction =
  | 'create'
  | 'update'
  | 'delete'
  | 'view'
  | 'download'
  | 'login'
  | 'logout'
  | 'restore'
  | 'status_change'

export interface AuditLog {
  id: number
  user: { id: string; email: string } | null
  entity_type: string
  entity_id: string
  action: AuditAction
  old_values: Record<string, unknown>
  new_values: Record<string, unknown>
  ip_address: string | null
  user_agent: string
  metadata: Record<string, unknown>
  created_at: string
}
