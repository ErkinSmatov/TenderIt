'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { ListX, Trash2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert } from '@/components/ui/alert'
import { cn } from '@/lib/utils'
import { buttonVariants } from '@/components/ui/button'

interface WatchlistTender {
  number_anno: string
  name_ru: string | null
  status_name_ru: string | null
}

interface WatchlistEntry {
  tender: WatchlistTender
}

export function WatchlistSettingsTable() {
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data: entries, isLoading } = useQuery<WatchlistEntry[]>({
    queryKey: ['watchlist'],
    queryFn: () => api.get<WatchlistEntry[]>('/api/watchlist'),
    retry: false,
  })

  const deleteMutation = useMutation({
    mutationFn: (numberAnno: string) => api.delete(`/api/watchlist/${numberAnno}`),
    onMutate: (numberAnno: string) => {
      setDeletingId(numberAnno)
      setDeleteError(null)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlist'] })
    },
    onError: (e: Error) => {
      setDeleteError(e.message)
    },
    onSettled: () => {
      setDeletingId(null)
    },
  })

  return (
    <section aria-labelledby="watchlist-settings-heading">
      <Card>
        <CardHeader>
          <CardTitle id="watchlist-settings-heading" className="flex items-center gap-2">
            <ListX className="h-4 w-4 text-primary" aria-hidden="true" />
            Отслеживаемые тендеры
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <p role="status" className="text-muted-foreground text-sm py-4 text-center">
              Загрузка...
            </p>
          )}

          {!isLoading && (!entries || entries.length === 0) && (
            <div className="text-center py-8">
              <p className="text-sm text-muted-foreground">Нет отслеживаемых тендеров</p>
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
                      {entry.tender.status_name_ru && (
                        <span className="text-xs text-muted-foreground">
                          {entry.tender.status_name_ru}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="shrink-0">
                    <button
                      onClick={() => deleteMutation.mutate(entry.tender.number_anno)}
                      disabled={deletingId === entry.tender.number_anno}
                      className={cn(
                        buttonVariants({ variant: 'ghost', size: 'sm' }),
                        'text-destructive hover:text-destructive hover:bg-destructive/10 disabled:opacity-50',
                      )}
                    >
                      {deletingId === entry.tender.number_anno ? (
                        '...'
                      ) : (
                        <>
                          <Trash2 className="h-3.5 w-3.5 mr-1.5" aria-hidden="true" />
                          Удалить
                        </>
                      )}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {deleteError && (
            <Alert className="text-destructive border-destructive/50 bg-destructive/10 text-xs py-2 mt-3">
              <div className="flex items-center justify-between gap-2">
                <span>Не удалось удалить запись: {deleteError}</span>
                <button
                  onClick={() => setDeleteError(null)}
                  className="text-xs underline shrink-0"
                >
                  Закрыть
                </button>
              </div>
            </Alert>
          )}
        </CardContent>
      </Card>
    </section>
  )
}
