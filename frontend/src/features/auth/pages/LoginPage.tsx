import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../store'
import { LoginForm } from '../components/LoginForm'

export function LoginPage() {
  const accessToken = useAuthStore((s) => s.accessToken)

  // Si ya hay sesión activa, redirigir al dashboard
  if (accessToken) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <LoginForm />
    </div>
  )
}
