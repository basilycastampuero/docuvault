import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useAuthStore } from '@/features/auth/store'
import { useAuditLogs } from '../hooks'
import { AuditLogFilters } from '../components/AuditLogFilters'
import { AuditLogTable } from '../components/AuditLogTable'
import type { ListAuditLogsParams } from '../api'
import type { UserRole } from '@/shared/types'

const ALLOWED_ROLES: UserRole[] = ['auditor', 'org_admin', 'super_admin']

export function AuditLogPage() {
  const navigate = useNavigate()
  const role = useAuthStore((s) => s.user?.role)
  const [filters, setFilters] = useState<ListAuditLogsParams>({})
  const [page, setPage] = useState(1)

  const { data, isLoading } = useAuditLogs({ ...filters, page })

  if (role && !ALLOWED_ROLES.includes(role)) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <p className="text-lg font-medium text-muted-foreground">Acceso no autorizado</p>
        <Button variant="outline" onClick={() => navigate('/')}>
          Ir al inicio
        </Button>
      </div>
    )
  }

  const handleFilter = (params: ListAuditLogsParams) => {
    setFilters(params)
    setPage(1)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Auditoría</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Registro inmutable de todas las acciones realizadas en la plataforma.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filtros</CardTitle>
        </CardHeader>
        <CardContent>
          <AuditLogFilters onFilter={handleFilter} />
        </CardContent>
      </Card>

      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((n) => (
            <Skeleton key={n} className="h-14 w-full" />
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          <AuditLogTable logs={data?.items ?? []} />

          {data && data.meta.count > 0 && (
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <span>
                {data.meta.count} registro{data.meta.count !== 1 ? 's' : ''} encontrado
                {data.meta.count !== 1 ? 's' : ''}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!data.meta.previous}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Anterior
                </Button>
                <span>
                  Página {data.meta.page} de{' '}
                  {Math.ceil(data.meta.count / data.meta.page_size)}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!data.meta.next}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Siguiente
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
