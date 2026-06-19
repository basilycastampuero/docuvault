import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { useLogin } from '../hooks'
import { ApiError } from '@/shared/types'

// ─── Validation schema ────────────────────────────────────────────────────────

const loginSchema = z.object({
  email: z.string().email('Email inválido'),
  password: z.string().min(8, 'Mínimo 8 caracteres'),
})

type LoginFormValues = z.infer<typeof loginSchema>

// ─── Component ────────────────────────────────────────────────────────────────

export function LoginForm() {
  const loginMutation = useLogin()

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  })

  function onSubmit(values: LoginFormValues) {
    loginMutation.mutate(values)
  }

  // Extraer mensaje de error del backend con narrowing seguro
  let apiErrorMessage: string | null = null
  if (loginMutation.error) {
    const err: unknown = loginMutation.error
    if (err instanceof ApiError) {
      apiErrorMessage =
        err.code === 'INVALID_CREDENTIALS' || err.status === 401
          ? 'Email o contraseña incorrectos'
          : err.message
    } else if (err instanceof Error) {
      apiErrorMessage = err.message
    } else {
      apiErrorMessage = 'Error desconocido'
    }
  }

  return (
    <Card className="w-full max-w-md shadow-lg">
      <CardHeader className="space-y-1">
        <CardTitle className="text-2xl font-bold tracking-tight">
          SasVault
        </CardTitle>
        <CardDescription>
          Ingresa tus credenciales para acceder a la plataforma
        </CardDescription>
      </CardHeader>

      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          {/* Error global de la API */}
          {apiErrorMessage && (
            <div
              role="alert"
              className="rounded-md border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive"
            >
              {apiErrorMessage}
            </div>
          )}

          {/* Email */}
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="tu@empresa.com"
              aria-invalid={!!form.formState.errors.email}
              disabled={loginMutation.isPending}
              {...form.register('email')}
            />
            {form.formState.errors.email && (
              <p className="text-sm text-destructive" role="alert">
                {form.formState.errors.email.message}
              </p>
            )}
          </div>

          {/* Password */}
          <div className="space-y-2">
            <Label htmlFor="password">Contraseña</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              aria-invalid={!!form.formState.errors.password}
              disabled={loginMutation.isPending}
              {...form.register('password')}
            />
            {form.formState.errors.password && (
              <p className="text-sm text-destructive" role="alert">
                {form.formState.errors.password.message}
              </p>
            )}
          </div>

          {/* Submit */}
          <Button
            type="submit"
            className="w-full"
            disabled={loginMutation.isPending}
          >
            {loginMutation.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Ingresando...
              </>
            ) : (
              'Ingresar'
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
