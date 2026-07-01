import { useNavigate } from 'react-router-dom'
import { Folder, MoreVertical, Pencil, Trash2 } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import type { Folder as FolderType } from '@/shared/types'
import { useAuthStore } from '@/features/auth/store'
import { WRITE_ROLES } from '@/shared/lib/roles'

interface FolderCardProps {
  folder: FolderType
  onRename: (folder: FolderType) => void
  onDelete: (folder: FolderType) => void
}

export function FolderCard({ folder, onRename, onDelete }: FolderCardProps) {
  const navigate = useNavigate()
  const role = useAuthStore((s) => s.user?.role)
  const canWrite = role ? WRITE_ROLES.includes(role) : false

  return (
    <Card
      className="group cursor-pointer transition-colors hover:bg-accent"
      onClick={() => navigate(`/folders/${folder.id}`)}
    >
      <CardContent className="flex items-center justify-between p-4">
        <div className="flex items-center gap-3 min-w-0">
          <Folder className="h-8 w-8 shrink-0 text-primary" />
          <span className="truncate font-medium text-sm">{folder.name}</span>
        </div>

        {canWrite && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 shrink-0 opacity-0 group-hover:opacity-100"
                onClick={(e) => e.stopPropagation()}
              >
                <MoreVertical className="h-4 w-4" />
                <span className="sr-only">Opciones</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
              <DropdownMenuItem
                onClick={(e) => {
                  e.stopPropagation()
                  onRename(folder)
                }}
              >
                <Pencil className="mr-2 h-4 w-4" />
                Renombrar
              </DropdownMenuItem>
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onClick={(e) => {
                  e.stopPropagation()
                  onDelete(folder)
                }}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Eliminar
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </CardContent>
    </Card>
  )
}
