'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert } from '@/components/ui/alert'

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
    setSavedAt(null)
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
    <Card>
      <CardHeader>
        <CardTitle>Реквизиты организации</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="bin">БИН организации</Label>
            <Input
              id="bin"
              type="text"
              placeholder="12 цифр"
              className="font-mono"
              aria-invalid={!!errors.bin}
              {...register('bin')}
            />
            {errors.bin && (
              <p className="text-destructive text-xs">{errors.bin.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="company_name">Наименование компании</Label>
            <Input
              id="company_name"
              type="text"
              placeholder="ТОО / АО / ИП ..."
              aria-invalid={!!errors.company_name}
              {...register('company_name')}
            />
            {errors.company_name && (
              <p className="text-destructive text-xs">{errors.company_name.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="legal_address">Юридический адрес</Label>
            <textarea
              id="legal_address"
              rows={3}
              placeholder="г. Алматы, ул. ..."
              aria-invalid={!!errors.legal_address}
              className="w-full resize-none rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm transition-colors outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
              {...register('legal_address')}
            />
            {errors.legal_address && (
              <p className="text-destructive text-xs">{errors.legal_address.message}</p>
            )}
          </div>

          {apiError && (
            <Alert className="text-destructive border-destructive/50 bg-destructive/10 text-xs py-2">
              {apiError}
            </Alert>
          )}

          {savedAt && (
            <Alert className="text-sm border-primary/30 bg-primary/10 text-primary py-2">
              Профиль сохранён
            </Alert>
          )}

          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Сохранение...' : 'Сохранить'}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
