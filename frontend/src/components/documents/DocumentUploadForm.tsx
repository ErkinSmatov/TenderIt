'use client'

/**
 * DocumentUploadForm — file upload form for the Document Vault.
 *
 * Uses a ref for the file input (RHF register does not support file inputs natively).
 * Other fields (category, expires_at) use react-hook-form + zod.
 *
 * On success: invalidates ['documents'] query and resets the form.
 * On error: shows error in Alert (apiError state pattern from CompanyProfileForm).
 */

import { useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useQueryClient } from '@tanstack/react-query'
import { uploadFile } from '@/lib/api'
import type { DocumentResponse } from '@/types/document'
import { CATEGORY_LABELS } from '@/types/document'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert } from '@/components/ui/alert'

const MAX_FILE_SIZE = 20 * 1024 * 1024 // 20 MB

const uploadSchema = z.object({
  category: z.enum(['ustav', 'license', 'certificate', 'registration', 'other'], {
    required_error: 'Выберите категорию',
  }),
  expires_at: z.string().optional(),
})

type UploadFormValues = z.infer<typeof uploadSchema>

export default function DocumentUploadForm() {
  const queryClient = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [apiError, setApiError] = useState<string>('')
  const [uploadedAt, setUploadedAt] = useState<Date | null>(null)

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<UploadFormValues>({
    resolver: zodResolver(uploadSchema),
    defaultValues: {
      category: undefined,
      expires_at: '',
    },
  })

  const onSubmit = async (data: UploadFormValues) => {
    setApiError('')
    setUploadedAt(null)

    const file = fileRef.current?.files?.[0]
    if (!file) {
      setApiError('Выберите файл для загрузки')
      return
    }

    if (file.size > MAX_FILE_SIZE) {
      setApiError('Файл превышает 20 МБ')
      return
    }

    const formData = new FormData()
    formData.append('file', file)
    formData.append('category', data.category)
    if (data.expires_at) {
      formData.append('expires_at', data.expires_at)
    }

    try {
      await uploadFile<DocumentResponse>('/api/documents', formData)
      await queryClient.invalidateQueries({ queryKey: ['documents'] })
      reset()
      if (fileRef.current) {
        fileRef.current.value = ''
      }
      setUploadedAt(new Date())
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Ошибка загрузки'
      setApiError(message)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Загрузить документ</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="file">Файл</Label>
            <input
              id="file"
              type="file"
              ref={fileRef}
              className="flex h-9 w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm transition-colors outline-none file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="category">Категория</Label>
            <select
              id="category"
              className="flex h-9 w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm transition-colors outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
              aria-invalid={!!errors.category}
              {...register('category')}
            >
              <option value="">Выберите категорию</option>
              {(Object.entries(CATEGORY_LABELS) as [string, string][]).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            {errors.category && (
              <p className="text-destructive text-xs">{errors.category.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="expires_at">Срок действия (необязательно)</Label>
            <Input
              id="expires_at"
              type="date"
              aria-invalid={!!errors.expires_at}
              {...register('expires_at')}
            />
            {errors.expires_at && (
              <p className="text-destructive text-xs">{errors.expires_at.message}</p>
            )}
          </div>

          {apiError && (
            <Alert className="text-destructive border-destructive/50 bg-destructive/10 text-xs py-2">
              {apiError}
            </Alert>
          )}

          {uploadedAt && (
            <Alert className="text-sm border-primary/30 bg-primary/10 text-primary py-2">
              Документ загружен
            </Alert>
          )}

          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Загрузка...' : 'Загрузить'}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
