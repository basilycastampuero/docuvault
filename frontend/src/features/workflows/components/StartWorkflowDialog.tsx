import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useWorkflowTemplates, useStartWorkflowFromDocument } from '../hooks'

interface StartWorkflowDialogProps {
  documentId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function StartWorkflowDialog({
  documentId,
  open,
  onOpenChange,
}: StartWorkflowDialogProps) {
  const navigate = useNavigate()
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('')
  const [conflictError, setConflictError] = useState<string | null>(null)

  const { data: templatesData } = useWorkflowTemplates()
  const activeTemplates = templatesData?.items.filter((t) => t.is_active) ?? []

  const startWorkflow = useStartWorkflowFromDocument()

  const handleOpenChange = (value: boolean) => {
    if (!value) {
      setSelectedTemplateId('')
      setConflictError(null)
    }
    onOpenChange(value)
  }

  const handleConfirm = () => {
    if (!selectedTemplateId) return
    setConflictError(null)

    startWorkflow.mutate(
      { documentId, templateId: selectedTemplateId },
      {
        onSuccess: (execution) => {
          handleOpenChange(false)
          navigate(`/workflows/executions/${execution.id}`)
        },
        onError: (err) => {
          if (
            err instanceof Error &&
            'code' in err &&
            (err as { code: string }).code === 'WORKFLOW_ALREADY_ACTIVE'
          ) {
            setConflictError('Este documento ya tiene una ejecución de workflow activa.')
          } else {
            setConflictError('Ocurrió un error al iniciar el workflow. Inténtalo de nuevo.')
          }
        },
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Iniciar workflow</DialogTitle>
          <DialogDescription>
            Selecciona una plantilla de workflow para iniciar el proceso de aprobación de
            este documento.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <Select
            value={selectedTemplateId}
            onValueChange={(value) => {
              setSelectedTemplateId(value)
              setConflictError(null)
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="Selecciona una plantilla" />
            </SelectTrigger>
            <SelectContent>
              {activeTemplates.map((template) => (
                <SelectItem key={template.id} value={template.id}>
                  {template.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {conflictError && (
            <div className="flex items-start gap-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
              <p>{conflictError}</p>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={startWorkflow.isPending}
          >
            Cancelar
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={!selectedTemplateId || startWorkflow.isPending}
          >
            {startWorkflow.isPending ? 'Iniciando...' : 'Iniciar'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
