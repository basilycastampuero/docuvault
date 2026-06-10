import { LogOut } from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useAuthStore } from '@/features/auth/store'
import { useLogout } from '@/features/auth/hooks'

// Mapeo de roles a etiquetas legibles en español
const ROLE_LABELS: Record<string, string> = {
  super_admin: 'Super Admin',
  org_admin: 'Administrador',
  supervisor: 'Supervisor',
  editor: 'Editor',
  viewer: 'Lector',
  auditor: 'Auditor',
}

function getInitials(firstName: string, lastName: string): string {
  const f = firstName.charAt(0).toUpperCase()
  const l = lastName.charAt(0).toUpperCase()
  return `${f}${l}`
}

export function Header() {
  const user = useAuthStore((s) => s.user)
  const logoutMutation = useLogout()

  const initials = user ? getInitials(user.first_name, user.last_name) : '?'
  const fullName = user ? `${user.first_name} ${user.last_name}`.trim() : ''
  const roleLabel = user ? (ROLE_LABELS[user.role] ?? user.role) : ''

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-card px-6">
      {/* Podría incluir breadcrumbs aquí en fases futuras */}
      <div />

      {/* User menu */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            className="flex items-center gap-3 rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-accent"
            aria-label="Menú de usuario"
          >
            <div className="hidden text-right sm:block">
              <p className="text-sm font-medium leading-none">{fullName}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">{roleLabel}</p>
            </div>
            <Avatar className="h-8 w-8">
              <AvatarFallback className="bg-primary text-primary-foreground text-xs font-semibold">
                {initials}
              </AvatarFallback>
            </Avatar>
          </button>
        </DropdownMenuTrigger>

        <DropdownMenuContent align="end" className="w-48">
          <DropdownMenuLabel className="font-normal">
            <p className="text-sm font-medium">{fullName}</p>
            <p className="text-xs text-muted-foreground">{user?.email}</p>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="cursor-pointer text-destructive focus:text-destructive"
            onClick={() => logoutMutation.mutate()}
            disabled={logoutMutation.isPending}
          >
            <LogOut className="mr-2 h-4 w-4" />
            {logoutMutation.isPending ? 'Cerrando...' : 'Cerrar sesión'}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  )
}
