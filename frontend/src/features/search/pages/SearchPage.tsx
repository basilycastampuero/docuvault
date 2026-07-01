import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search, Loader2 } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { AppPagination } from '@/shared/components/Pagination'
import { DocumentCard } from '@/features/documents/components/DocumentCard'
import { useSearch } from '../hooks'

export function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialQuery = searchParams.get('q') ?? ''
  const [inputValue, setInputValue] = useState(initialQuery)
  const [page, setPage] = useState(1)

  const { data, isLoading } = useSearch(initialQuery, page)

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = inputValue.trim()
    if (trimmed) {
      setSearchParams({ q: trimmed })
      setPage(1)
    }
  }

  const totalPages = data ? Math.ceil(data.meta.count / data.meta.page_size) : 1

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">Buscar documentos</h1>
        <p className="text-muted-foreground text-sm">
          Búsqueda en nombres, descripciones y contenido OCR
        </p>
      </div>

      {/* Search input */}
      <form onSubmit={handleSearch} className="flex items-center gap-2 max-w-xl">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Buscar documentos..."
            className="pl-9"
            autoFocus
          />
        </div>
      </form>

      {/* Results */}
      {!initialQuery && (
        <p className="text-center text-muted-foreground py-12">
          Escribe algo para buscar documentos
        </p>
      )}

      {initialQuery && isLoading && (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      )}

      {initialQuery && data && (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            {data.meta.count === 0
              ? `Sin resultados para "${initialQuery}"`
              : `${data.meta.count} ${data.meta.count === 1 ? 'resultado' : 'resultados'} para "${initialQuery}"`}
          </p>

          {data.items.length > 0 && (
            <>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {data.items.map((doc) => (
                  <DocumentCard key={doc.id} document={doc as unknown as import('@/shared/types').Document} />
                ))}
              </div>
              <AppPagination page={page} totalPages={totalPages} onPageChange={setPage} />
            </>
          )}
        </div>
      )}
    </div>
  )
}
