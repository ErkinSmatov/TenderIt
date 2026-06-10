'use client'

/**
 * /tenders — Tender search page.
 *
 * Flow:
 *   1. User types a tender number and submits the form.
 *   2. react-query fetches GET /api/tenders/{number_anno} (enabled only after submit).
 *   3. On success: shows TenderCard + WatchlistButton.
 *   4. On 404: shows "Тендер не найден" message.
 *   5. On other error: shows network error message.
 *
 * isWatching is derived from GET /api/watchlist (separate query, always active).
 * WatchlistButton.onChange invalidates ['watchlist'] so both queries stay in sync.
 */

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Tender, WatchlistEntry } from '@/types/tender'
import TenderCard from '@/components/tenders/TenderCard'
import WatchlistButton from '@/components/tenders/WatchlistButton'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Alert } from '@/components/ui/alert'

const searchSchema = z.object({
  number_anno: z
    .string()
    .min(1, 'Введите номер объявления')
    .max(100, 'Не более 100 символов'),
})

type SearchFormValues = z.infer<typeof searchSchema>

export default function TendersPage() {
  const [queryNumber, setQueryNumber] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<SearchFormValues>({
    resolver: zodResolver(searchSchema),
  })

  const onSubmit = (values: SearchFormValues) => {
    setQueryNumber(values.number_anno.trim())
  }

  // Tender lookup — enabled only after form submit
  const {
    data: tender,
    error: tenderError,
    isLoading,
    isFetching,
  } = useQuery<Tender>({
    queryKey: ['tender', queryNumber],
    queryFn: () => api.get<Tender>(`/api/tenders/${encodeURIComponent(queryNumber!)}`),
    enabled: queryNumber !== null,
    retry: false,
  })

  // Watchlist — always fetched so isWatching is up-to-date
  const { data: watchlist } = useQuery<WatchlistEntry[]>({
    queryKey: ['watchlist'],
    queryFn: () => api.get<WatchlistEntry[]>('/api/watchlist'),
    retry: false,
  })

  const isWatching = Boolean(
    tender &&
      watchlist?.some((e) => e.tender.number_anno === tender.number_anno),
  )

  const is404 =
    tenderError instanceof Error && tenderError.message.includes('не найден')

  const isLoaderVisible = isLoading || isFetching

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-semibold">Поиск тендеров</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Введите номер объявления с портала goszakup.gov.kz
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="number_anno">Номер объявления</Label>
          <div className="flex gap-2">
            <Input
              id="number_anno"
              type="text"
              placeholder="Например: 17163708-1"
              aria-invalid={!!errors.number_anno}
              className="flex-1"
              {...register('number_anno')}
            />
            <Button
              type="submit"
              disabled={isSubmitting || isLoaderVisible}
            >
              {isLoaderVisible ? (
                <>
                  <span role="status" className="sr-only">Загрузка...</span>
                  Поиск...
                </>
              ) : (
                'Найти'
              )}
            </Button>
          </div>
          {errors.number_anno && (
            <p className="text-destructive text-xs">{errors.number_anno.message}</p>
          )}
        </div>
      </form>

      {/* Results */}
      {queryNumber !== null && !isLoaderVisible && (
        <>
          {is404 && (
            <Alert className="text-muted-foreground border-border bg-card text-sm">
              Тендер с номером <strong className="text-foreground">{queryNumber}</strong> не найден
              на портале goszakup.gov.kz. Проверьте номер и попробуйте снова.
            </Alert>
          )}

          {tenderError && !is404 && (
            <Alert className="text-destructive border-destructive/50 bg-destructive/10 text-sm">
              Не удалось загрузить данные. Проверьте соединение и попробуйте ещё раз.
            </Alert>
          )}

          {tender && (
            <TenderCard tender={tender}>
              <WatchlistButton
                numberAnno={tender.number_anno}
                isWatching={isWatching}
                onChange={() =>
                  queryClient.invalidateQueries({ queryKey: ['watchlist'] })
                }
              />
            </TenderCard>
          )}
        </>
      )}
    </div>
  )
}
