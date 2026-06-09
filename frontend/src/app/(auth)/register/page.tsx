'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { api } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'

const registerSchema = z.object({
  email: z.string().email('Некорректный email'),
  password: z.string().min(8, 'Минимум 8 символов'),
})

type RegisterFormValues = z.infer<typeof registerSchema>

interface TokenResponse {
  user_id: number
  email: string
}

export default function RegisterPage() {
  const router = useRouter()
  const [apiError, setApiError] = useState<string>('')
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
  })

  const onSubmit = async (data: RegisterFormValues) => {
    setApiError('')
    try {
      const response = await api.post<TokenResponse>('/api/auth/register', data)
      useAuthStore.getState().setAuth(response.user_id)
      router.push('/dashboard')
    } catch (err) {
      setApiError(err instanceof Error ? err.message : 'Ошибка регистрации')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <form
        onSubmit={handleSubmit(onSubmit)}
        className="flex flex-col gap-4 w-full max-w-sm p-8"
      >
        <h1 className="text-2xl font-bold">Регистрация</h1>

        <div>
          <input
            type="email"
            placeholder="Email"
            className="border rounded px-3 py-2 w-full"
            {...register('email')}
          />
          {errors.email && (
            <p className="text-red-500 text-sm mt-1">{errors.email.message}</p>
          )}
        </div>

        <div>
          <input
            type="password"
            placeholder="Пароль (минимум 8 символов)"
            className="border rounded px-3 py-2 w-full"
            {...register('password')}
          />
          {errors.password && (
            <p className="text-red-500 text-sm mt-1">{errors.password.message}</p>
          )}
        </div>

        {apiError && (
          <p className="text-red-500 text-sm">{apiError}</p>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          className="bg-blue-600 text-white rounded px-4 py-2 disabled:opacity-50"
        >
          {isSubmitting ? 'Регистрация...' : 'Зарегистрироваться'}
        </button>

        <p className="text-sm text-center">
          Уже есть аккаунт?{' '}
          <a href="/login" className="text-blue-600 underline">
            Войти
          </a>
        </p>
      </form>
    </div>
  )
}
