import { createBrowserRouter } from 'react-router-dom'
import { LoginPage } from '@/features/auth/pages/LoginPage'
import { ProtectedRoute } from '@/shared/components/ProtectedRoute'
import { AppLayout } from '@/shared/components/AppLayout'

// ─── Placeholder para fases 5.2+ ──────────────────────────────────────────────

function DashboardPlaceholder() {
  return (
    <div className="flex flex-col gap-2">
      <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
      <p className="text-muted-foreground">
        Próximamente: resumen de documentos, actividad reciente y métricas.
      </p>
    </div>
  )
}

// ─── Router ───────────────────────────────────────────────────────────────────

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
          { path: '/', element: <DashboardPlaceholder /> },
          // 5.2: { path: '/documents', element: <DocumentsPage /> },
          // 5.2: { path: '/folders',   element: <FoldersPage /> },
          // 5.3: { path: '/workflows', element: <WorkflowsPage /> },
          // 5.3: { path: '/audit-logs', element: <AuditLogsPage /> },
        ],
      },
    ],
  },
])
