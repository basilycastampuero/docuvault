import { useForm } from 'react-hook-form'
import { Search, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { ListAuditLogsParams } from '../api'
import type { AuditAction } from '@/shared/types'

const AUDIT_ACTIONS: { value: AuditAction; label: string }[] = [
  { value: 'create', label: 'Crear' },
  { value: 'update', label: 'Actualizar' },
  { value: 'delete', label: 'Eliminar' },
  { value: 'view', label: 'Ver' },
  { value: 'download', label: 'Descargar' },
  { value: 'login', label: 'Inicio de sesión' },
  { value: 'logout', label: 'Cierre de sesión' },
  { value: 'restore', label: 'Restaurar' },
  { value: 'status_change', label: 'Cambio de estado' },
]

interface AuditLogFiltersProps {
  onFilter: (params: ListAuditLogsParams) => void
}

interface FilterFormValues {
  action: string
  entity_type: string
  user: string
  created_after: string
  created_before: string
}

export function AuditLogFilters({ onFilter }: AuditLogFiltersProps) {
  const { register, handleSubmit, reset, setValue, watch } = useForm<FilterFormValues>({
    defaultValues: {
      action: '',
      entity_type: '',
      user: '',
      created_after: '',
      created_before: '',
    },
  })

  const actionValue = watch('action')

  const onSubmit = (values: FilterFormValues) => {
    const params: ListAuditLogsParams = {}
    if (values.action) params.action = values.action as AuditAction
    if (values.entity_type) params.entity_type = values.entity_type
    if (values.user) params.user = values.user
    if (values.created_after) {
      params.created_after = new Date(values.created_after).toISOString()
    }
    if (values.created_before) {
      params.created_before = new Date(values.created_before).toISOString()
    }
    onFilter(params)
  }

  const handleClear = () => {
    reset()
    setValue('action', '')
    onFilter({})
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <div className="space-y-1.5">
          <Label className="text-xs">Acción</Label>
          <Select
            value={actionValue}
            onValueChange={(v) => setValue('action', v === '_all' ? '' : v)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Todas las acciones" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="_all">Todas</SelectItem>
              {AUDIT_ACTIONS.map(({ value, label }) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs">Tipo de entidad</Label>
          <Input
            placeholder="Ej: document"
            {...register('entity_type')}
          />
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs">Usuario (email)</Label>
          <Input
            placeholder="usuario@ejemplo.com"
            {...register('user')}
          />
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs">Desde</Label>
          <Input
            type="date"
            className="text-sm"
            {...register('created_after')}
          />
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs">Hasta</Label>
          <Input
            type="date"
            className="text-sm"
            {...register('created_before')}
          />
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button type="submit" size="sm">
          <Search className="mr-2 h-3.5 w-3.5" />
          Filtrar
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={handleClear}>
          <X className="mr-2 h-3.5 w-3.5" />
          Limpiar
        </Button>
      </div>
    </form>
  )
}
