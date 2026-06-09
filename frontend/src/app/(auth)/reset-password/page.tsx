'use client'

import { Suspense, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { api } from '@/lib/api'

const resetPasswordSchema = z.object({
  new_password: z.string().min(8, 'Минимум 8 символов'),
})

type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>

function ResetPasswordForm() {
  const searchParams = useSearchParams()
  const token = searchParams.get('token')

  const [success, setSuccess] = useState(false)
  const [apiError, setApiError] = useState<string>('')

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
  })

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col gap-4 w-full max-w-sm p-8 text-center">
          <p className="text-red-500">Недействительная ссылка</p>
          <Link href="/login" className="text-blue-600 underline text-sm">
            Вернуться к входу
          </Link>
        </div>
      </div>
    )
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col gap-4 w-full max-w-sm p-8 text-center">
          <h1 className="text-2xl font-bold">Пароль изменён</h1>
          <p className="text-gray-600">
            Вы можете войти с новым паролем.
          </p>
          <Link href="/login" className="text-blue-600 underline text-sm">
            Войти
          </Link>
        </div>
      </div>
    )
  }

  const onSubmit = async (data: ResetPasswordFormValues) => {
    setApiError('')
    try {
      await api.post('/api/auth/reset-password', {
        token,
        new_password: data.new_password,
      })
      setSuccess(true)
    } catch (err) {
      setApiError(err instanceof Error ? err.message : 'Ошибка сброса пароля')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <form
        onSubmit={handleSubmit(onSubmit)}
        className="flex flex-col gap-4 w-full max-w-sm p-8"
      >
        <h1 className="text-2xl font-bold">Новый пароль</h1>

        <div>
          <input
            type="password"
            placeholder="Новый пароль (минимум 8 символов)"
            className="border rounded px-3 py-2 w-full"
            {...register('new_password')}
          />
          {errors.new_password && (
            <p className="text-red-500 text-sm mt-1">{errors.new_password.message}</p>
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
          {isSubmitting ? 'Сохранение...' : 'Сохранить пароль'}
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

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center">Загрузка...</div>}>
      <ResetPasswordForm />
    </Suspense>
  )
}
