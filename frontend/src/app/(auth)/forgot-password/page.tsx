'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { api } from '@/lib/api'

const forgotPasswordSchema = z.object({
  email: z.string().email('Некорректный email'),
})

type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState(false)
  const [apiError, setApiError] = useState<string>('')

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
  })

  const onSubmit = async (data: ForgotPasswordFormValues) => {
    setApiError('')
    try {
      await api.post('/api/auth/forgot-password', { email: data.email })
      setSent(true)
    } catch {
      // Always show success — even on network error we show the same message
      // to prevent enumeration at the UI layer.
      setSent(true)
    }
  }

  if (sent) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col gap-4 w-full max-w-sm p-8 text-center">
          <h1 className="text-2xl font-bold">Проверьте почту</h1>
          <p className="text-gray-600">
            Если email зарегистрирован, ссылка отправлена. Проверьте почту.
          </p>
          <Link href="/login" className="text-blue-600 underline text-sm">
            Вернуться к входу
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <form
        onSubmit={handleSubmit(onSubmit)}
        className="flex flex-col gap-4 w-full max-w-sm p-8"
      >
        <h1 className="text-2xl font-bold">Забыли пароль?</h1>
        <p className="text-sm text-gray-600">
          Введите email — мы пришлём ссылку для сброса пароля.
        </p>

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

        {apiError && (
          <p className="text-red-500 text-sm">{apiError}</p>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          className="bg-blue-600 text-white rounded px-4 py-2 disabled:opacity-50"
        >
          {isSubmitting ? 'Отправка...' : 'Отправить ссылку'}
        </button>

        <p className="text-sm text-center">
          <Link href="/login" className="text-blue-600 underline">
            Вернуться к входу
          </Link>
        </p>
      </form>
    </div>
  )
}
