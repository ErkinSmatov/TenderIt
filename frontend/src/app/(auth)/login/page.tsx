'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import Link from 'next/link'
import { api } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert } from '@/components/ui/alert'

const loginSchema = z.object({
  email: z.string().email('Некорректный email'),
  password: z.string().min(8, 'Минимум 8 символов'),
})

type LoginFormValues = z.infer<typeof loginSchema>

interface TokenResponse {
  user_id: number
  email: string
}

export default function LoginPage() {
  const router = useRouter()
  const [apiError, setApiError] = useState<string>('')
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  })

  const onSubmit = async (data: LoginFormValues) => {
    setApiError('')
    try {
      const response = await api.post<TokenResponse>('/api/auth/login', data)
      useAuthStore.getState().setAuth(response.user_id)
      router.push('/dashboard')
    } catch (err) {
      setApiError(err instanceof Error ? err.message : 'Ошибка входа')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm space-y-6">
        {/* Brand */}
        <div className="text-center">
          <span className="text-2xl font-bold tracking-tight">
            Tender<span className="text-primary">It</span>
          </span>
          <p className="mt-1 text-sm text-muted-foreground">
            Автоматическая подача тендерных заявок
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Вход</CardTitle>
            <CardDescription>Введите ваш email и пароль</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@company.kz"
                  aria-invalid={!!errors.email}
                  {...register('email')}
                />
                {errors.email && (
                  <p className="text-destructive text-xs">{errors.email.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="password">Пароль</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  aria-invalid={!!errors.password}
                  {...register('password')}
                />
                {errors.password && (
                  <p className="text-destructive text-xs">{errors.password.message}</p>
                )}
              </div>

              {apiError && (
                <Alert className="text-destructive border-destructive/50 bg-destructive/10 text-xs py-2">
                  {apiError}
                </Alert>
              )}

              <Button type="submit" disabled={isSubmitting} className="w-full">
                {isSubmitting ? 'Вход...' : 'Войти'}
              </Button>

              <p className="text-center text-sm text-muted-foreground">
                Нет аккаунта?{' '}
                <Link href="/register" className="text-primary hover:underline font-medium">
                  Зарегистрироваться
                </Link>
              </p>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
