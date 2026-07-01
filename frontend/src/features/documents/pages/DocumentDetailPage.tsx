import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { AlertCircle, ArrowLeft, Download, RefreshCw, Loader2, Folder, BrainCircuit, Play } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs'
import { Skeleton } from '@/components/ui/skeleton'
import { useAuthStore } from '@/features/auth/store'
import { OcrStatusBadge } from '../components/OcrStatusBadge'
import { DocumentVersionList } from '../components/DocumentVersionList'
import { DocumentMetadataForm } from '../components/DocumentMetadataForm'
import { useDocument, useDownloadDocument, useReprocessOcr, useRequestAiAnalysis } from '../hooks'
import { useWorkflowTemplates } from '@/features/workflows/hooks'
import { StartWorkflowDialog } from '@/features/workflows/components/StartWorkflowDialog'
import { WRITE_ROLES } from '@/shared/lib/roles'

interface AiAnalysis {
  status?: string
  error?: string
  summary?: string
  entities?: {
    dates: string[]
    amounts: string[]
    names: string[]
  }
  suggested_category?: string
}

interface AiAnalysisPanelProps {
  document: {
    ocr_status: string
    metadata: Record<string, unknown>
  }
  isPending: boolean
  onRequest: () => void
  onAnalysisReady: () => void
}

function AiAnalysisPanel({ document, isPending, onRequest, onAnalysisReady }: AiAnalysisPanelProps) {
  const analysis = document.metadata?.ai_analysis as AiAnalysis | undefined

  useEffect(() => {
    if (analysis) onAnalysisReady()
  }, [analysis, onAnalysisReady])

  if (analysis?.status === 'failed') {
    return (
      <div className="space-y-3">
        <div className="flex items-start gap-2 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
          <p>El análisis falló permanentemente. Puede intentarlo de nuevo.</p>
        </div>
        <Button size="sm" variant="outline" onClick={onRequest} disabled={isPending}>
          {isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          Reintentar
        </Button>
      </div>
    )
  }

  if (analysis) {
    return (
      <div className="space-y-4">
        {analysis.summary && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
              Resumen
            </p>
            <p className="text-sm">{analysis.summary}</p>
          </div>
        )}
        {analysis.suggested_category && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
              Categoría sugerida
            </p>
            <Badge variant="outline">{analysis.suggested_category}</Badge>
          </div>
        )}
        {analysis.entities && (() => {
          const all = [
            ...(analysis.entities!.dates ?? []),
            ...(analysis.entities!.amounts ?? []),
            ...(analysis.entities!.names ?? []),
          ]
          return all.length > 0 ? (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
                Entidades detectadas
              </p>
              <div className="flex flex-wrap gap-1.5">
                {all.map((entity, i) => (
                  <Badge key={i} variant="secondary" className="text-xs">
                    {entity}
                  </Badge>
                ))}
              </div>
            </div>
          ) : null
        })()}
      </div>
    )
  }

  if (document.ocr_status !== 'completed') {
    return (
      <p className="text-sm text-muted-foreground">
        El análisis IA requiere que el OCR esté completado. Estado actual del OCR:{' '}
        <span className="font-medium">{document.ocr_status}</span>.
      </p>
    )
  }

  if (isPending) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
        <Loader2 className="h-4 w-4 animate-spin" />
        Procesando análisis IA...
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        El documento está listo para ser analizado por IA. El análisis extrae un resumen,
        entidades clave y sugiere una categoría.
      </p>
      <Button size="sm" onClick={onRequest}>
        <BrainCircuit className="mr-2 h-4 w-4" />
        Solicitar análisis
      </Button>
    </div>
  )
}

const STATUS_LABELS: Record<string, string> = {
  draft: 'Borrador',
  under_review: 'En revisión',
  approved: 'Aprobado',
  rejected: 'Rechazado',
  archived: 'Archivado',
}

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-600',
  under_review: 'bg-yellow-100 text-yellow-700',
  approved: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
  archived: 'bg-gray-200 text-gray-500',
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const role = useAuthStore((s) => s.user?.role)
  const canWrite = role ? (WRITE_ROLES as readonly string[]).includes(role) : false
  const [aiUnavailable, setAiUnavailable] = useState(false)
  const [pollForAi, setPollForAi] = useState(false)

  const { data: document, isLoading, error } = useDocument(id ?? '', pollForAi)
  const download = useDownloadDocument()
  const reprocessOcr = useReprocessOcr()
  const requestAiAnalysis = useRequestAiAnalysis()

  const { data: templatesData } = useWorkflowTemplates()
  const activeTemplates = templatesData?.items.filter((t) => t.is_active) ?? []
  const [workflowDialogOpen, setWorkflowDialogOpen] = useState(false)

  if (!id) {
    navigate('/documents')
    return null
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Skeleton className="h-9 w-24" />
          <Skeleton className="h-8 w-64" />
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-4">
            <Skeleton className="h-40" />
            <Skeleton className="h-60" />
          </div>
          <Skeleton className="h-80" />
        </div>
      </div>
    )
  }

  if (error || !document) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <p className="text-lg font-medium text-muted-foreground">Documento no encontrado</p>
        <Button variant="outline" onClick={() => navigate('/documents')}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Volver a documentos
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1 min-w-0">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors mb-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Volver
          </button>
          <h1 className="text-2xl font-bold tracking-tight truncate">{document.name}</h1>
          <div className="flex items-center gap-2 flex-wrap">
            <Badge
              variant="secondary"
              className={STATUS_COLORS[document.status] ?? ''}
            >
              {STATUS_LABELS[document.status] ?? document.status}
            </Badge>
            <OcrStatusBadge status={document.ocr_status} />
            <span className="text-xs text-muted-foreground">v{document.version}</span>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {(document.ocr_status === 'failed' || document.ocr_status === 'pending') && canWrite && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => reprocessOcr.mutate(document.id)}
              disabled={reprocessOcr.isPending}
            >
              <RefreshCw className={`mr-2 h-4 w-4 ${reprocessOcr.isPending ? 'animate-spin' : ''}`} />
              Re-procesar OCR
            </Button>
          )}
          {canWrite && activeTemplates.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setWorkflowDialogOpen(true)}
            >
              <Play className="mr-2 h-4 w-4" />
              Iniciar workflow
            </Button>
          )}
          <Button
            onClick={() => download.mutate(document.id)}
            disabled={download.isPending}
          >
            <Download className="mr-2 h-4 w-4" />
            {download.isPending ? 'Descargando...' : 'Descargar'}
          </Button>
        </div>
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left column: tabs */}
        <div className="lg:col-span-2">
          <Tabs defaultValue="versions">
            <TabsList>
              <TabsTrigger value="versions">Versiones</TabsTrigger>
              {canWrite && <TabsTrigger value="edit">Editar metadata</TabsTrigger>}
              {document.ocr_content && (
                <TabsTrigger value="ocr">Contenido OCR</TabsTrigger>
              )}
              {!aiUnavailable && (
                <TabsTrigger value="ai">
                  <BrainCircuit className="mr-1.5 h-3.5 w-3.5" />
                  Análisis IA
                </TabsTrigger>
              )}
            </TabsList>

            <TabsContent value="versions" className="mt-4">
              <Card>
                <CardContent className="pt-6">
                  <DocumentVersionList document={document} />
                </CardContent>
              </Card>
            </TabsContent>

            {canWrite && (
              <TabsContent value="edit" className="mt-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Editar información</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <DocumentMetadataForm document={document} />
                  </CardContent>
                </Card>
              </TabsContent>
            )}

            {document.ocr_content && (
              <TabsContent value="ocr" className="mt-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Contenido extraído por OCR</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <pre className="text-sm whitespace-pre-wrap break-words text-muted-foreground font-sans">
                      {document.ocr_content}
                    </pre>
                  </CardContent>
                </Card>
              </TabsContent>
            )}

            {!aiUnavailable && (
              <TabsContent value="ai" className="mt-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Análisis IA</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <AiAnalysisPanel
                      document={document}
                      isPending={requestAiAnalysis.isPending || pollForAi}
                      onRequest={() => {
                        requestAiAnalysis.mutate(document.id, {
                          onSuccess: () => {
                            setPollForAi(true)
                          },
                          onError: (err) => {
                            if (
                              err instanceof Error &&
                              'code' in err &&
                              (err as { code: string }).code === 'AI_SERVICE_UNAVAILABLE'
                            ) {
                              setAiUnavailable(true)
                            }
                          },
                        })
                      }}
                      onAnalysisReady={() => setPollForAi(false)}
                    />
                  </CardContent>
                </Card>
              </TabsContent>
            )}
          </Tabs>
        </div>

        {/* Right column: metadata */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Información</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Tamaño</span>
                <span className="font-medium">{formatFileSize(document.file_size)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Tipo</span>
                <span className="font-medium truncate max-w-32" title={document.mime_type}>
                  {document.mime_type.split('/')[1]?.toUpperCase() ?? document.mime_type}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Versión actual</span>
                <span className="font-medium">v{document.version}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Creado por</span>
                <span className="font-medium truncate max-w-32" title={document.created_by_email}>
                  {document.created_by_email}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Creado</span>
                <span className="font-medium">
                  {format(new Date(document.created_at), 'dd MMM yyyy', { locale: es })}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Actualizado</span>
                <span className="font-medium">
                  {format(new Date(document.updated_at), 'dd MMM yyyy', { locale: es })}
                </span>
              </div>
              {document.folder && (
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Carpeta</span>
                  <Link
                    to={`/folders/${document.folder}`}
                    className="flex items-center gap-1 text-primary hover:underline font-medium"
                  >
                    <Folder className="h-3.5 w-3.5" />
                    {document.folder_name}
                  </Link>
                </div>
              )}
            </CardContent>
          </Card>

          {document.tags.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Etiquetas</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {document.tags.map((tag) => (
                    <Badge key={tag} variant="outline">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {document.description && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Descripción</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{document.description}</p>
              </CardContent>
            </Card>
          )}

          {/* Loader for OCR polling */}
          {(document.ocr_status === 'pending' || document.ocr_status === 'processing') && (
            <Card>
              <CardContent className="pt-6 flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Procesando OCR automáticamente...
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      <StartWorkflowDialog
        documentId={document.id}
        open={workflowDialogOpen}
        onOpenChange={setWorkflowDialogOpen}
      />
    </div>
  )
}
