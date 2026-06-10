'use client'

/**
 * DashboardWatchlist — shows the user's watched tenders on the dashboard.
 *
 * States (03-UI-SPEC.md):
 *   Empty   → h2 + "Список пуст" + guidance copy
 *   Loading → spinner (sr-only)
 *   Filled  → list of rows, each with name, number, StatusBadge, and compact WatchlistButton
 *
 * Placed below the nav on the /dashboard page.
 */

import { BookmarkIcon } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { WatchlistEntry } from '@/types/tender'
import StatusBadge from '@/components/tenders/StatusBadge'
import WatchlistButton from '@/components/tenders/WatchlistButton'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export default function DashboardWatchlist() {
  const queryClient = useQueryClient()

  const { data: entries, isLoading } = useQuery<WatchlistEntry[]>({
    queryKey: ['watchlist'],
    queryFn: () => api.get<WatchlistEntry[]>('/api/watchlist'),
    retry: false,
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['watchlist'] })

  return (
    <section aria-labelledby="watchlist-heading">
      <Card>
        <CardHeader>
          <CardTitle id="watchlist-heading" className="flex items-center gap-2">
            <BookmarkIcon className="h-4 w-4 text-primary" aria-hidden="true" />
            Отслеживаемые тендеры
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <p role="status" className="text-muted-foreground text-sm py-4 text-center">
              <span className="sr-only">Загрузка...</span>
              Загрузка...
            </p>
          )}

          {!isLoading && (!entries || entries.length === 0) && (
            <div className="text-center py-8 space-y-1">
              <p className="text-sm font-medium text-muted-foreground">Список пуст</p>
              <p className="text-xs text-muted-foreground">
                Найдите тендер и нажмите «Добавить в список»
              </p>
            </div>
          )}

          {!isLoading && entries && entries.length > 0 && (
            <div className="divide-y divide-border -mx-4">
              {entries.map((entry) => (
                <div
                  key={entry.tender.number_anno}
                  className="flex items-center justify-between px-4 py-3"
                >
                  <div className="flex flex-col gap-0.5 min-w-0 mr-4">
                    <span className="text-sm font-medium truncate">
                      {entry.tender.name_ru ?? entry.tender.number_anno}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground font-mono">
                        {entry.tender.number_anno}
                      </span>
                      <StatusBadge statusName={entry.tender.status_name_ru} />
                    </div>
                  </div>
                  <div className="shrink-0">
                    <WatchlistButton
                      numberAnno={entry.tender.number_anno}
                      isWatching
                      onChange={invalidate}
                      compact
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </section>
  )
}
