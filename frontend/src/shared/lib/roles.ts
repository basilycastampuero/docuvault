export const WRITE_ROLES = ['super_admin', 'org_admin', 'supervisor', 'editor'] as const
export type WriteRole = (typeof WRITE_ROLES)[number]

export const START_ROLES = ['super_admin', 'org_admin', 'supervisor', 'editor'] as const
export type StartRole = (typeof START_ROLES)[number]

export function canWrite(role: string | undefined): boolean {
  return role ? (WRITE_ROLES as readonly string[]).includes(role) : false
}
