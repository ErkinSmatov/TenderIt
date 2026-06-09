'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { api } from '@/lib/api'

const profileSchema = z.object({
  bin: z.string().regex(/^\d{12}$/, 'Введите 12 цифр'),
  company_name: z
    .string()
    .min(1, 'Обязательное поле')
    .max(500, 'Не более 500 символов'),
  legal_address: z
    .string()
    .min(1, 'Обязательное поле')
    .max(1000, 'Не более 1000 символов'),
})

type ProfileFormValues = z.infer<typeof profileSchema>

interface CompanyProfileData {
  bin: string | null
  company_name: string | null
  legal_address: string | null
}

interface CompanyProfileFormProps {
  initialData: CompanyProfileData
}

export default function CompanyProfileForm({ initialData }: CompanyProfileFormProps) {
  const [savedAt, setSavedAt] = useState<Date | null>(null)
  const [apiError, setApiError] = useState<string>('')

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      bin: initialData.bin ?? '',
      company_name: initialData.company_name ?? '',
      legal_address: initialData.legal_address ?? '',
    },
  })

  const onSubmit = async (data: ProfileFormValues) => {
    setApiError('')
    try {
      await api.put('/api/company/profile', data)
      setSavedAt(new Date())
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Ошибка сохранения'
      if (message.includes('БИН') || message.includes('BIN')) {
        setError('bin', { message })
      } else {
        setApiError(message)
      }
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4 max-w-lg">
      <div>
        <label className="block text-sm font-medium mb-1" htmlFor="bin">
          БИН организации
        </label>
        <input
          id="bin"
          type="text"
          placeholder="12 цифр"
          className="border rounded px-3 py-2 w-full font-mono"
          {...register('bin')}
        />
        {errors.bin && (
          <p className="text-red-500 text-sm mt-1">{errors.bin.message}</p>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium mb-1" htmlFor="company_name">
          Наименование компании
        </label>
        <input
          id="company_name"
          type="text"
          placeholder="ТОО / АО / ИП ..."
          className="border rounded px-3 py-2 w-full"
          {...register('company_name')}
        />
        {errors.company_name && (
          <p className="text-red-500 text-sm mt-1">{errors.company_name.message}</p>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium mb-1" htmlFor="legal_address">
          Юридический адрес
        </label>
        <textarea
          id="legal_address"
          rows={3}
          placeholder="г. Алматы, ул. ..."
          className="border rounded px-3 py-2 w-full resize-none"
          {...register('legal_address')}
        />
        {errors.legal_address && (
          <p className="text-red-500 text-sm mt-1">{errors.legal_address.message}</p>
        )}
      </div>

      {apiError && (
        <p className="text-red-500 text-sm">{apiError}</p>
      )}

      {savedAt && (
        <p className="text-green-600 text-sm">Профиль сохранён</p>
      )}

      <button
        type="submit"
        disabled={isSubmitting}
        className="bg-blue-600 text-white rounded px-4 py-2 disabled:opacity-50 self-start"
      >
        {isSubmitting ? 'Сохранение...' : 'Сохранить'}
      </button>
    </form>
  )
}
