/**
 * TenderMatchStatusBadge — maps each TenderMatchStatus to a Russian label + colour.
 *
 * Status machine: matched → notified → (participating | skipped)
 * Mirrors ApplicationStatusBadge.tsx pattern exactly.
 */

import { cn } from '@/lib/utils'
import type { TenderMatchStatus } from '@/types/discovery'

interface StatusConfig {
  label: string
  className: string
}

const STATUS_CONFIG: Record<TenderMatchStatus, StatusConfig> = {
  matched: {
    label: 'Новый',
    className: 'bg-blue-100 text-blue-700 border-blue-200',
  },
  notified: {
    label: 'Уведомлён',
    className: 'bg-amber-100 text-amber-700 border-amber-200',
  },
  participating: {
    label: 'Участвуем',
    className: 'bg-green-100 text-green-700 border-green-200',
  },
  skipped: {
    label: 'Пропущен',
    className: 'bg-gray-100 text-gray-600 border-gray-200',
  },
}

interface TenderMatchStatusBadgeProps {
  status: TenderMatchStatus
  className?: string
}

export default function TenderMatchStatusBadge({
  status,
  className,
}: TenderMatchStatusBadgeProps) {
  const { label, className: statusClassName } = STATUS_CONFIG[status]

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium',
        statusClassName,
        className,
      )}
    >
      {label}
    </span>
  )
}
