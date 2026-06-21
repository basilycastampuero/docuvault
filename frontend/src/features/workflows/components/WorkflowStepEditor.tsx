import type { Control } from 'react-hook-form'
import { GripVertical, Trash2 } from 'lucide-react'
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { Button } from '@/components/ui/button'
import type { TemplateFormValues } from './WorkflowTemplateForm'

const ROLE_LABELS: Record<string, string> = {
  super_admin: 'Super admin',
  org_admin: 'Admin de organización',
  supervisor: 'Supervisor',
  editor: 'Editor',
  viewer: 'Visualizador',
  auditor: 'Auditor',
}

interface WorkflowStepEditorProps {
  index: number
  control: Control<TemplateFormValues>
  onRemove: () => void
  canRemove: boolean
}

export function WorkflowStepEditor({
  index,
  control,
  onRemove,
  canRemove,
}: WorkflowStepEditorProps) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-border bg-card p-4">
      <div className="mt-2 shrink-0 text-muted-foreground">
        <GripVertical className="h-4 w-4" />
      </div>

      <div className="flex-1 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <FormField
          control={control}
          name={`steps.${index}.name`}
          render={({ field }) => (
            <FormItem className="sm:col-span-1">
              <FormLabel className="text-xs">Nombre del paso</FormLabel>
              <FormControl>
                <Input placeholder="Ej: Revisión legal" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={control}
          name={`steps.${index}.required_role`}
          render={({ field }) => (
            <FormItem className="sm:col-span-1">
              <FormLabel className="text-xs">Rol requerido</FormLabel>
              <Select onValueChange={field.onChange} defaultValue={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Seleccionar rol" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {Object.entries(ROLE_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={control}
          name={`steps.${index}.is_final`}
          render={({ field }) => (
            <FormItem className="sm:col-span-1 flex flex-col">
              <FormLabel className="text-xs">Paso final</FormLabel>
              <div className="flex items-center gap-2 mt-2">
                <FormControl>
                  <Checkbox
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                </FormControl>
                <span className="text-sm text-muted-foreground">
                  {field.value ? 'Es el paso final' : 'No es el paso final'}
                </span>
              </div>
              <FormMessage />
            </FormItem>
          )}
        />
      </div>

      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="mt-6 shrink-0 text-muted-foreground hover:text-destructive"
        onClick={onRemove}
        disabled={!canRemove}
      >
        <Trash2 className="h-4 w-4" />
      </Button>
    </div>
  )
}
