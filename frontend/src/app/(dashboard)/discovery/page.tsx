'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { TenderMatchListResponse } from '@/types/discovery'
import TenderMatchCard from '@/components/discovery/TenderMatchCard'
import { Alert } from '@/components/ui/alert'
import { cn } from '@/lib/utils'

const STATUS_TABS = [
  { value: '', label: 'Все' },
  { value: 'matched', label: 'Новые' },
  { value: 'notified', label: 'Уведомлены' },
  { value: 'participating', label: 'Участвуем' },
  { value: 'skipped', label: 'Пропущены' },
]

const PAGE_SIZE = 20

export default function DiscoveryPage() {
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)

  const { data, error, isLoading } = useQuery<TenderMatchListResponse>({
    queryKey: ['discovery-matches', status, page],
    queryFn: () => {
      const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) })
      if (status) params.set('status', status)
      return api.get<TenderMatchListResponse>(`/api/discovery/matches?${params}`)
    },
    retry: false,
  })

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 1

  function handleStatusChange(newStatus: string) {
    setStatus(newStatus)
    setPage(1)
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">Подборка</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Тендеры по вашим фильтрам
            {data != null && (
              <span className="ml-1.5">· {data.total}</span>
            )}
          </p>
        </div>
        <Link href="/discovery-filters" className="text-sm text-primary hover:underline">
          Настроить фильтры
        </Link>
      </div>

      {/* Status filter tabs */}
      <div className="flex gap-0 border-b border-border">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => handleStatusChange(tab.value)}
            className={cn(
              'px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
              status === tab.value
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error && (
        <Alert className="text-destructive border-destructive/50 bg-destructive/10 text-sm">
          Не удалось загрузить подборку. Проверьте соединение и попробуйте ещё раз.
        </Alert>
      )}

      {isLoading && (
        <p className="text-sm text-muted-foreground">Загрузка...</p>
      )}

      {!isLoading && !error && data && data.items.length === 0 && (
        <div className="rounded-lg border border-dashed border-border py-12 text-center">
          <p className="text-sm text-muted-foreground">
            {status ? 'Нет тендеров в этой категории' : 'Подходящих тендеров пока нет'}
          </p>
          {!status && (
            <p className="text-xs text-muted-foreground mt-1">
              <Link href="/discovery-filters" className="underline">
                Настройте фильтры
              </Link>
              , чтобы получать подборку тендеров
            </p>
          )}
        </div>
      )}

      {!isLoading && !error && data && data.items.length > 0 && (
        <>
          <div className="space-y-4">
            {data.items.map((match) => (
              <TenderMatchCard key={match.id} match={match} />
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="text-sm text-muted-foreground hover:text-foreground disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                ← Назад
              </button>
              <span className="text-sm text-muted-foreground">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="text-sm text-muted-foreground hover:text-foreground disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Вперёд →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
