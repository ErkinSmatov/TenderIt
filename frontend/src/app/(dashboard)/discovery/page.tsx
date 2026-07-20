'use client'

/**
 * /discovery — Discovery feed page (DISC-04).
 *
 * Flow:
 *   1. useQuery fetches GET /api/discovery/matches on mount.
 *   2. Renders TenderMatchCard list, newest-first.
 *   3. Empty state: link to /discovery-filters.
 *   4. Error state: Alert with retry suggestion.
 */

import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { TenderMatchResponse } from '@/types/discovery'
import TenderMatchCard from '@/components/discovery/TenderMatchCard'
import { Alert } from '@/components/ui/alert'

export default function DiscoveryPage() {
  const { data, error, isLoading } = useQuery<TenderMatchResponse[]>({
    queryKey: ['discovery-matches'],
    queryFn: () => api.get<TenderMatchResponse[]>('/api/discovery/matches'),
    retry: false,
  })

  // Sort newest-first by created_at (mirrors applications/page.tsx pattern)
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
          <h1 className="text-xl font-semibold">Подборка</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Тендеры по вашим фильтрам
          </p>
        </div>
        <Link href="/discovery-filters" className="text-sm text-primary hover:underline">
          Настроить фильтры
        </Link>
      </div>

      {error && (
        <Alert className="text-destructive border-destructive/50 bg-destructive/10 text-sm">
          Не удалось загрузить подборку. Проверьте соединение и попробуйте ещё раз.
        </Alert>
      )}

      {isLoading && (
        <p className="text-sm text-muted-foreground">Загрузка...</p>
      )}

      {!isLoading && !error && sorted.length === 0 && (
        <div className="rounded-lg border border-dashed border-border py-12 text-center">
          <p className="text-sm text-muted-foreground">Подходящих тендеров пока нет</p>
          <p className="text-xs text-muted-foreground mt-1">
            <Link href="/discovery-filters" className="underline">
              Настройте фильтры
            </Link>
            , чтобы получать подборку тендеров
          </p>
        </div>
      )}

      {!isLoading && !error && sorted.length > 0 && (
        <div className="space-y-4">
          {sorted.map((match) => (
            <TenderMatchCard key={match.id} match={match} />
          ))}
        </div>
      )}
    </div>
  )
}
