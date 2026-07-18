'use client'

/**
 * /applications — Applications history list page (APPL-05).
 *
 * Flow:
 *   1. useQuery fetches GET /api/applications on mount.
 *   2. Renders ApplicationCard list, newest-first.
 *   3. Empty state: "Пока нет заявок".
 *   4. Error state: Alert with retry suggestion.
 */

import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { ApplicationResponse } from '@/types/application'
import ApplicationCard from '@/components/applications/ApplicationCard'
import { Alert } from '@/components/ui/alert'
import { buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export default function ApplicationsPage() {
  const { data, error, isLoading } = useQuery<ApplicationResponse[]>({
    queryKey: ['applications'],
    queryFn: () => api.get<ApplicationResponse[]>('/api/applications'),
    retry: false,
  })

  // Sort newest-first by created_at
  const sorted = data
    ? [...data].sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      )
    : []

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">Заявки</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            История ваших заявок на тендеры
          </p>
        </div>
        <Link
          href="/applications/new"
          className={cn(buttonVariants({ size: 'sm' }))}
        >
          Создать заявку
        </Link>
      </div>

      {error && (
        <Alert className="text-destructive border-destructive/50 bg-destructive/10 text-sm">
          Не удалось загрузить список заявок. Проверьте соединение и попробуйте ещё раз.
        </Alert>
      )}

      {isLoading && (
        <p className="text-sm text-muted-foreground">Загрузка...</p>
      )}

      {!isLoading && !error && sorted.length === 0 && (
        <div className="rounded-lg border border-dashed border-border py-12 text-center">
          <p className="text-sm text-muted-foreground">Пока нет заявок</p>
          <p className="text-xs text-muted-foreground mt-1">
            Создайте первую заявку, нажав «Создать заявку»
          </p>
        </div>
      )}

      {!isLoading && !error && sorted.length > 0 && (
        <div className="space-y-4">
          {sorted.map((application) => (
            <ApplicationCard key={application.id} application={application} />
          ))}
        </div>
      )}
    </div>
  )
}
