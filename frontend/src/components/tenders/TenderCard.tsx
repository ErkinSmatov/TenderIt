/**
 * TenderCard — full detail card for a goszakup tender.
 *
 * Shows: title, customer, announcement number, total amount (KZT),
 * deadline (DD.MM.YYYY), status badge, and lot list.
 *
 * The `children` slot renders the WatchlistButton below the fields.
 *
 * Markup: <article> per a11y requirements (03-UI-SPEC.md).
 */

import type { ReactNode } from 'react'
import type { Tender } from '@/types/tender'
import StatusBadge from './StatusBadge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const kztFormatter = new Intl.NumberFormat('ru-KZ', {
  style: 'currency',
  currency: 'KZT',
  maximumFractionDigits: 0,
})

function formatDate(isoOrRaw: string | null): string {
  if (!isoOrRaw) return '—'
  const d = new Date(isoOrRaw)
  if (isNaN(d.getTime())) return '—'
  const day = String(d.getDate()).padStart(2, '0')
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const year = d.getFullYear()
  return `${day}.${month}.${year}`
}

interface Field {
  label: string
  value: ReactNode
}

function LabelValue({ label, value }: Field) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</span>
      <span className="text-sm text-foreground">{value}</span>
    </div>
  )
}

interface TenderCardProps {
  tender: Tender
  children?: ReactNode
}

export default function TenderCard({ tender, children }: TenderCardProps) {
  const lots = tender.lots_data ?? []

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base leading-snug">
          {tender.name_ru ?? '—'}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <LabelValue
            label="Заказчик"
            value={tender.customer_name_ru ?? '—'}
          />
          <LabelValue
            label="Номер объявления"
            value={<span className="font-mono">{tender.number_anno}</span>}
          />
          <LabelValue
            label="Сумма"
            value={
              tender.total_sum != null
                ? kztFormatter.format(tender.total_sum)
                : '—'
            }
          />
          <LabelValue
            label="Дедлайн"
            value={formatDate(tender.end_date)}
          />
          <LabelValue
            label="Статус"
            value={<StatusBadge statusName={tender.status_name_ru} />}
          />
        </div>

        {lots.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
              Лоты ({lots.length})
            </p>
            <ul className="space-y-1.5">
              {lots.map((lot, i) => (
                <li
                  key={lot.id ?? i}
                  className="flex justify-between items-start text-sm gap-4"
                >
                  <span className="text-foreground">
                    {lot.lotNumber ? `Лот ${lot.lotNumber}: ` : ''}
                    {lot.nameRu ?? '—'}
                  </span>
                  <span className="shrink-0 text-muted-foreground tabular-nums">
                    {lot.amount != null ? kztFormatter.format(lot.amount) : '—'}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {children && <div>{children}</div>}
      </CardContent>
    </Card>
  )
}
