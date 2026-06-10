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
