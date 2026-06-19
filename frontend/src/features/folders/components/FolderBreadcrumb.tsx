import { Link } from 'react-router-dom'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'

interface BreadcrumbEntry {
  id: string
  name: string
}

interface FolderBreadcrumbProps {
  trail: BreadcrumbEntry[]
  currentName: string
}

export function FolderBreadcrumb({ trail, currentName }: FolderBreadcrumbProps) {
  return (
    <Breadcrumb>
      <BreadcrumbList>
        <BreadcrumbItem>
          <BreadcrumbLink asChild>
            <Link to="/folders">Inicio</Link>
          </BreadcrumbLink>
        </BreadcrumbItem>

        {trail.map((entry) => (
          <>
            <BreadcrumbSeparator key={`sep-${entry.id}`} />
            <BreadcrumbItem key={entry.id}>
              <BreadcrumbLink asChild>
                <Link to={`/folders/${entry.id}`}>{entry.name}</Link>
              </BreadcrumbLink>
            </BreadcrumbItem>
          </>
        ))}

        <BreadcrumbSeparator />
        <BreadcrumbItem>
          <BreadcrumbPage>{currentName}</BreadcrumbPage>
        </BreadcrumbItem>
      </BreadcrumbList>
    </Breadcrumb>
  )
}
