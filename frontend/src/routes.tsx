import { createBrowserRouter } from 'react-router-dom'
import { LoginPage } from '@/features/auth/pages/LoginPage'
import { ProtectedRoute } from '@/shared/components/ProtectedRoute'
import { AppLayout } from '@/shared/components/AppLayout'
import { DashboardPage } from '@/features/dashboard/pages/DashboardPage'
import { DocumentListPage } from '@/features/documents/pages/DocumentListPage'
import { DocumentDetailPage } from '@/features/documents/pages/DocumentDetailPage'
import { FolderBrowserPage } from '@/features/folders/pages/FolderBrowserPage'
import { SearchPage } from '@/features/search/pages/SearchPage'
import { WorkflowTemplatesPage } from '@/features/workflows/pages/WorkflowTemplatesPage'
import { WorkflowTemplateDetailPage } from '@/features/workflows/pages/WorkflowTemplateDetailPage'
import { WorkflowExecutionsPage } from '@/features/workflows/pages/WorkflowExecutionsPage'
import { WorkflowExecutionDetailPage } from '@/features/workflows/pages/WorkflowExecutionDetailPage'
import { AuditLogPage } from '@/features/audit/pages/AuditLogPage'

export const router = createBrowserRouter([
  // Ruta pública
  { path: '/login', element: <LoginPage /> },

  // Rutas protegidas (requieren JWT válido)
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: '/', element: <DashboardPage /> },
          { path: '/documents', element: <DocumentListPage /> },
          { path: '/documents/:id', element: <DocumentDetailPage /> },
          { path: '/folders', element: <FolderBrowserPage /> },
          { path: '/folders/:id', element: <FolderBrowserPage /> },
          { path: '/search', element: <SearchPage /> },
          { path: '/workflows', element: <WorkflowTemplatesPage /> },
          { path: '/workflows/templates/:id', element: <WorkflowTemplateDetailPage /> },
          { path: '/workflows/executions', element: <WorkflowExecutionsPage /> },
          { path: '/workflows/executions/:id', element: <WorkflowExecutionDetailPage /> },
          { path: '/audit-logs', element: <AuditLogPage /> },
        ],
      },
    ],
  },
])
