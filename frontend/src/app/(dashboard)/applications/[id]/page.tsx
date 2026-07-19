'use client'

/**
 * /applications/[id] — Application detail page.
 *
 * APPL-04: Polls GET /api/applications/{id} every 30s to reflect live status transitions
 *          (draft → signed → waiting → submitting → submitted | error).
 * APPL-06: Surfaces raw portal error_message when status === 'error'.
 *
 * Shows: status badge, lots_data (lot + price), attached document count,
 *        state-history timeline (created_at, ready_at, submitted_at).
 */

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { ApplicationResponse, LotOffer } from '@/types/application'
import ApplicationStatusBadge from '@/components/applications/ApplicationStatusBadge'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatPrice(price: string): string {
  const num = parseFloat(price)
  if (isNaN(num)) return price
  return num.toLocaleString('ru-RU', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function LotRow({ lot }: { lot: LotOffer }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-border last:border-0">
      <span className="text-sm text-foreground">Лот #{lot.lot_id}</span>
      <div className="text-right">
        <div className="text-sm font-medium text-foreground">
          {formatPrice(lot.total_price)} ₸
        </div>
        <div className="text-xs text-muted-foreground">
          {formatPrice(lot.unit_price)} ₸ × {lot.quantity} шт.
        </div>
      </div>
    </div>
  )
}

function TimelineEvent({
  label,
  date,
}: {
  label: string
  date: string | null
}) {
  return (
    <div className="flex items-start gap-3">
      <div
        className={`mt-1 h-2 w-2 shrink-0 rounded-full ${date ? 'bg-primary' : 'bg-border'}`}
      />
      <div className="flex flex-col gap-0.5">
        <span className="text-sm font-medium text-foreground">{label}</span>
        <span className="text-xs text-muted-foreground">{formatDate(date)}</span>
      </div>
    </div>
  )
}

export default function ApplicationDetailPage() {
  const params = useParams()
  const id = params.id as string

  const { data: application, error, isLoading } = useQuery<ApplicationResponse>({
    queryKey: ['application', id],
    queryFn: () => api.get<ApplicationResponse>(`/api/applications/${id}`),
    refetchInterval: 30000,
    retry: false,
  })

  if (isLoading) {
    return (
      <div className="max-w-2xl">
        <p className="text-sm text-muted-foreground">Загрузка...</p>
      </div>
    )
  }

  if (error) {
    const is404 =
      error instanceof Error && error.message.toLowerCase().includes('404')
    return (
      <div className="max-w-2xl space-y-4">
        <Link
          href="/applications"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Назад к заявкам
        </Link>
        <Alert className="text-destructive border-destructive/50 bg-destructive/10 text-sm">
          {is404
            ? 'Заявка не найдена или у вас нет доступа к ней.'
            : 'Не удалось загрузить данные заявки. Проверьте соединение.'}
        </Alert>
      </div>
    )
  }

  if (!application) return null

  return (
    <div className="max-w-2xl space-y-6">
      {/* Header */}
      <div>
        <Link
          href="/applications"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Назад к заявкам
        </Link>
        <div className="flex items-start justify-between gap-4 mt-3">
          <div>
            <h1 className="text-xl font-semibold">
              Заявка на тендер #{application.tender_id}
            </h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              ID заявки: {application.id}
            </p>
          </div>
          <ApplicationStatusBadge status={application.status} />
        </div>
      </div>

      {/* Error surface (APPL-06) */}
      {application.status === 'error' && (
        <Alert variant="destructive">
          <AlertTitle>Ошибка при отправке на портал</AlertTitle>
          <AlertDescription>
            {application.error_message
              ? application.error_message
              : 'Неизвестная ошибка портала.'}
          </AlertDescription>
          <AlertDescription className="mt-2 text-xs opacity-80">
            Подписанная заявка сохранена и доступна для повторной отправки вручную.
          </AlertDescription>
        </Alert>
      )}

      {/* Lots */}
      {application.lots_data.length > 0 && (
        <div className="rounded-lg border border-border p-4 space-y-1">
          <h2 className="text-sm font-semibold text-foreground mb-2">
            Лоты ({application.lots_data.length})
          </h2>
          {application.lots_data.map((lot) => (
            <LotRow key={lot.lot_id} lot={lot} />
          ))}
        </div>
      )}

      {/* Documents */}
      <div className="flex flex-col gap-0.5">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Прикреплённые документы
        </span>
        <span className="text-sm text-foreground">
          {application.document_ids.length > 0
            ? `${application.document_ids.length} документ${
                application.document_ids.length === 1
                  ? ''
                  : application.document_ids.length < 5
                    ? 'а'
                    : 'ов'
              }`
            : 'Нет документов'}
        </span>
      </div>

      {/* State-history timeline */}
      <div className="rounded-lg border border-border p-4 space-y-3">
        <h2 className="text-sm font-semibold text-foreground">История статусов</h2>
        <div className="space-y-3">
          <TimelineEvent label="Создана" date={application.created_at} />
          <TimelineEvent label="Подписана" date={application.ready_at} />
          <TimelineEvent label="Отправлена" date={application.submitted_at} />
        </div>
      </div>

      {/* Retry count if > 0 */}
      {application.retry_count > 0 && (
        <p className="text-xs text-muted-foreground">
          Попыток отправки: {application.retry_count}
        </p>
      )}
    </div>
  )
}
