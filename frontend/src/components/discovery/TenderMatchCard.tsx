'use client'

/**
 * TenderMatchCard — card component for a single discovery match.
 *
 * Shows: tender title, customer, amount, deadline, region, source badge, status badge.
 * Action buttons: "Участвуем" (POST participate) and "Пропустить" (POST skip).
 * Buttons are hidden based on current match status per D-12.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import type { TenderMatchResponse } from '@/types/discovery'
import type { ApplicationResponse } from '@/types/application'
import TenderMatchStatusBadge from '@/components/discovery/TenderMatchStatusBadge'
import { cn } from '@/lib/utils'
import { buttonVariants } from '@/components/ui/button'

interface TenderMatchCardProps {
  match: TenderMatchResponse
}

function formatAmount(total_sum: string | null): string {
  if (!total_sum) return 'Сумма не указана'
  const n = parseFloat(total_sum)
  if (isNaN(n)) return 'Сумма не указана'
  return n.toLocaleString('ru-RU') + ' ₸'
}

function formatDeadline(end_date: string | null): string {
  if (!end_date) return 'Дедлайн не указан'
  const d = new Date(end_date)
  if (isNaN(d.getTime())) return 'Дедлайн не указан'
  return d.toLocaleDateString('ru-RU')
}

function SourceBadge({
  source,
  portalUrl,
}: {
  source: string | undefined | null
  portalUrl?: string | null
}) {
  const label = source === 'sk_kz' ? 'SK.KZ' : 'ГОСЗАКУП'
  const colorClass =
    source === 'sk_kz'
      ? 'border-blue-200 bg-blue-50 text-blue-700'
      : 'border-gray-200 bg-gray-100 text-gray-600'
  const badge = (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${colorClass}`}
    >
      {label}
    </span>
  )
  if (portalUrl) {
    return (
      <a href={portalUrl} target="_blank" rel="noopener noreferrer">
        {badge}
      </a>
    )
  }
  return badge
}

export default function TenderMatchCard({ match }: TenderMatchCardProps) {
  const router = useRouter()
  const queryClient = useQueryClient()

  const participateMutation = useMutation({
    mutationFn: () =>
      api.post<ApplicationResponse>(`/api/discovery/${match.id}/participate`, {}),
    onSuccess: (data) => {
      router.push(`/applications/${data.id}`)
    },
    onError: (err) => {
      console.error('Ошибка при подаче заявки:', err)
      // TODO: заменить на toast('Не удалось подать заявку. Попробуйте снова.')
    },
  })

  const skipMutation = useMutation({
    mutationFn: () => api.post<{ ok: boolean }>(`/api/discovery/${match.id}/skip`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['discovery-matches'] })
    },
    onError: (err) => {
      console.error('Ошибка при пропуске тендера:', err)
      // TODO: заменить на toast('Не удалось пропустить тендер. Попробуйте снова.')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.delete<void>(`/api/discovery/${match.id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['discovery-matches'] })
    },
    onError: (err) => {
      console.error('Ошибка при удалении подборки:', err)
      // TODO: заменить на toast('Не удалось удалить подборку. Попробуйте снова.')
    },
  })

  const isActionable = match.status !== 'participating' && match.status !== 'skipped'

  return (
    <div className="rounded-lg border border-border p-4 space-y-3">
      {/* Header: title + status badge + delete */}
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-medium leading-snug text-foreground">
          {match.tender_name_ru || 'Тендер без названия'}
        </h3>
        <div className="flex items-center gap-2 shrink-0">
          <TenderMatchStatusBadge status={match.status} />
          <button
            onClick={() => deleteMutation.mutate()}
            disabled={deleteMutation.isPending}
            title="Удалить из подборки"
            className="text-muted-foreground hover:text-destructive disabled:opacity-40 transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
              <path d="M10 11v6" />
              <path d="M14 11v6" />
              <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
            </svg>
          </button>
        </div>
      </div>

      {/* Customer */}
      <p className="text-xs text-muted-foreground">
        {match.customer_name_ru || 'Заказчик не указан'}
      </p>

      {/* Details grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
        <div>
          <span className="font-medium text-muted-foreground uppercase tracking-wide text-[10px]">
            Сумма
          </span>
          <p className="text-foreground mt-0.5">{formatAmount(match.total_sum)}</p>
        </div>
        <div>
          <span className="font-medium text-muted-foreground uppercase tracking-wide text-[10px]">
            Дедлайн
          </span>
          <p className="text-foreground mt-0.5">{formatDeadline(match.end_date)}</p>
        </div>
        <div>
          <span className="font-medium text-muted-foreground uppercase tracking-wide text-[10px]">
            Регион
          </span>
          <p className="text-foreground mt-0.5">{match.region || 'Регион не указан'}</p>
        </div>
        <div>
          <span className="font-medium text-muted-foreground uppercase tracking-wide text-[10px]">
            Источник
          </span>
          <p className="mt-0.5">
            <SourceBadge source={match.source} portalUrl={match.portal_url} />
          </p>
        </div>
      </div>

      {/* Action buttons — hidden when status is participating or skipped */}
      {isActionable && (
        <div className="flex items-center gap-2 pt-1">
          <button
            onClick={() => participateMutation.mutate()}
            disabled={participateMutation.isPending}
            className={cn(
              buttonVariants({ size: 'sm' }),
              'disabled:opacity-50',
            )}
          >
            {participateMutation.isPending ? 'Подождите...' : 'Участвуем'}
          </button>
          <button
            onClick={() => skipMutation.mutate()}
            disabled={skipMutation.isPending}
            className={cn(
              buttonVariants({ variant: 'outline', size: 'sm' }),
              'disabled:opacity-50',
            )}
          >
            {skipMutation.isPending ? 'Подождите...' : 'Пропустить'}
          </button>
        </div>
      )}

      {/* Manual submission note for sk.kz tenders when participating */}
      {match.source === 'sk_kz' && match.status === 'participating' && (
        <p className="mt-2 text-xs text-amber-600">
          Заявку нужно подать вручную на zakup.sk.kz
        </p>
      )}
    </div>
  )
}
