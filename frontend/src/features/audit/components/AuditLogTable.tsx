import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import type { AuditLog, AuditAction } from '@/shared/types'

const ACTION_CONFIG: Record<AuditAction, { label: string; className: string }> = {
  create: { label: 'Crear', className: 'bg-green-100 text-green-700' },
  update: { label: 'Actualizar', className: 'bg-blue-100 text-blue-700' },
  delete: { label: 'Eliminar', className: 'bg-red-100 text-red-700' },
  view: { label: 'Ver', className: 'bg-gray-100 text-gray-600' },
  download: { label: 'Descargar', className: 'bg-purple-100 text-purple-700' },
  login: { label: 'Ingreso', className: 'bg-teal-100 text-teal-700' },
  logout: { label: 'Salida', className: 'bg-gray-100 text-gray-500' },
  restore: { label: 'Restaurar', className: 'bg-yellow-100 text-yellow-700' },
  status_change: { label: 'Cambio estado', className: 'bg-orange-100 text-orange-700' },
}

interface AuditLogTableProps {
  logs: AuditLog[]
}

export function AuditLogTable({ logs }: AuditLogTableProps) {
  if (logs.length === 0) {
    return (
      <p className="text-center py-12 text-sm text-muted-foreground">
        No se encontraron registros con los filtros aplicados.
      </p>
    )
  }

  return (
    <div className="rounded-md border border-border overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-32">Acción</TableHead>
            <TableHead>Entidad</TableHead>
            <TableHead>Usuario</TableHead>
            <TableHead className="w-40">Fecha</TableHead>
            <TableHead className="hidden lg:table-cell">IP</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {logs.map((log) => {
            const actionCfg = ACTION_CONFIG[log.action] ?? {
              label: log.action,
              className: 'bg-gray-100 text-gray-600',
            }

            return (
              <TableRow key={log.id}>
                <TableCell>
                  <Badge
                    variant="secondary"
                    className={`text-xs font-medium ${actionCfg.className} hover:${actionCfg.className}`}
                  >
                    {actionCfg.label}
                  </Badge>
                </TableCell>
                <TableCell>
                  <span className="text-sm font-medium">{log.entity_type}</span>
                  <br />
                  <span className="text-xs text-muted-foreground font-mono truncate block max-w-40">
                    {log.entity_id}
                  </span>
                </TableCell>
                <TableCell>
                  <span className="text-sm">
                    {log.user?.email ?? <span className="text-muted-foreground italic">Sistema</span>}
                  </span>
                </TableCell>
                <TableCell>
                  <span className="text-sm">
                    {format(new Date(log.created_at), 'dd MMM yyyy HH:mm', { locale: es })}
                  </span>
                </TableCell>
                <TableCell className="hidden lg:table-cell">
                  <span className="text-xs text-muted-foreground font-mono">
                    {log.ip_address ?? '—'}
                  </span>
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
