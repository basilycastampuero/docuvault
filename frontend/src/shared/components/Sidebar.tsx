import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  FileText,
  Folder,
  GitBranch,
  ClipboardList,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/features/auth/store'
import type { UserRole } from '@/shared/types'

interface NavItem {
  label: string
  to: string
  icon: React.ComponentType<{ className?: string }>
  allowedRoles?: UserRole[]
}

const navItems: NavItem[] = [
  { label: 'Dashboard', to: '/', icon: LayoutDashboard },
  { label: 'Documentos', to: '/documents', icon: FileText },
  { label: 'Carpetas', to: '/folders', icon: Folder },
  { label: 'Workflows', to: '/workflows', icon: GitBranch },
  {
    label: 'Auditoría',
    to: '/audit-logs',
    icon: ClipboardList,
    allowedRoles: ['auditor', 'org_admin', 'super_admin'],
  },
]

export function Sidebar() {
  const userRole = useAuthStore((s) => s.user?.role)

  const visibleItems = navItems.filter((item) => {
    if (!item.allowedRoles) return true
    if (!userRole) return false
    return item.allowedRoles.includes(userRole)
  })

  return (
    <aside className="flex h-full w-60 flex-col border-r border-border bg-card px-3 py-6">
      {/* Logo */}
      <div className="mb-8 px-2">
        <span className="text-xl font-bold tracking-tight text-foreground">
          SasVault
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1">
        {visibleItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
              )
            }
          >
            <item.icon className="h-4 w-4 shrink-0" />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
