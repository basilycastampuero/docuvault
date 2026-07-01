import { useNavigate } from 'react-router-dom'
import { FileText, Folder, Upload, Loader2 } from 'lucide-react'
import { Card, CardContent, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/features/auth/store'
import { DocumentCard } from '@/features/documents/components/DocumentCard'
import { useDocuments } from '@/features/documents/hooks'
import { useFolders } from '@/features/folders/hooks'
import { WRITE_ROLES } from '@/shared/lib/roles'

export function DashboardPage() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const role = user?.role
  const canWrite = role ? (WRITE_ROLES as readonly string[]).includes(role) : false

  const { data: recentDocs, isLoading: docsLoading } = useDocuments({ page: 1, page_size: 6 })
  const { data: foldersData, isLoading: foldersLoading } = useFolders()

  const docCount = recentDocs?.meta.count ?? 0
  const folderCount = foldersData?.items.length ?? 0

  return (
    <div className="space-y-8">
      {/* Welcome */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Bienvenido{user?.first_name ? `, ${user.first_name}` : ''}
        </h1>
        <p className="text-muted-foreground mt-1">
          Esto es lo que hay disponible en tu organización.
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card
          className="cursor-pointer hover:bg-accent transition-colors"
          onClick={() => navigate('/documents')}
        >
          <CardContent className="flex items-center gap-4 pt-6">
            <div className="rounded-full bg-primary/10 p-3">
              <FileText className="h-6 w-6 text-primary" />
            </div>
            <div>
              <p className="text-2xl font-bold">
                {docsLoading ? <Loader2 className="h-6 w-6 animate-spin" /> : docCount}
              </p>
              <p className="text-sm text-muted-foreground">
                {docCount === 1 ? 'Documento' : 'Documentos'}
              </p>
            </div>
          </CardContent>
        </Card>

        <Card
          className="cursor-pointer hover:bg-accent transition-colors"
          onClick={() => navigate('/folders')}
        >
          <CardContent className="flex items-center gap-4 pt-6">
            <div className="rounded-full bg-primary/10 p-3">
              <Folder className="h-6 w-6 text-primary" />
            </div>
            <div>
              <p className="text-2xl font-bold">
                {foldersLoading ? <Loader2 className="h-6 w-6 animate-spin" /> : folderCount}
              </p>
              <p className="text-sm text-muted-foreground">
                {folderCount === 1 ? 'Carpeta raíz' : 'Carpetas raíz'}
              </p>
            </div>
          </CardContent>
        </Card>

        {canWrite && (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-8 gap-3">
              <Upload className="h-8 w-8 text-muted-foreground" />
              <Button onClick={() => navigate('/documents')} variant="outline">
                Subir documento
              </Button>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Recent documents */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Documentos recientes</CardTitle>
          <Button variant="ghost" size="sm" onClick={() => navigate('/documents')}>
            Ver todos
          </Button>
        </div>

        {docsLoading && (
          <div className="flex justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {recentDocs && recentDocs.items.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-8">
            Aun no hay documentos. {canWrite && 'Sube el primero.'}
          </p>
        )}

        {recentDocs && recentDocs.items.length > 0 && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {recentDocs.items.map((doc) => (
              <DocumentCard key={doc.id} document={doc} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
