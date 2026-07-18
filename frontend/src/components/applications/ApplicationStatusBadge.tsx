/**
 * ApplicationStatusBadge — maps each ApplicationStatus to a Russian label + colour.
 *
 * State machine: draft → signed → waiting → submitting → submitted | error
 * Labels and colours per 05-CONTEXT.md lines 132-149.
 */

import { cn } from '@/lib/utils'
import type { ApplicationStatus } from '@/types/application'

interface StatusConfig {
  label: string
  className: string
}

const STATUS_CONFIG: Record<ApplicationStatus, StatusConfig> = {
  draft: {
    label: 'Черновик',
    className: 'bg-gray-100 text-gray-600 border-gray-200',
  },
  signed: {
    label: 'Подписано',
    className: 'bg-blue-100 text-blue-700 border-blue-200',
  },
  waiting: {
    label: 'Ожидает открытия',
    className: 'bg-amber-100 text-amber-700 border-amber-200',
  },
  submitting: {
    label: 'Отправляется',
    className: 'bg-indigo-100 text-indigo-700 border-indigo-200 animate-pulse',
  },
  submitted: {
    label: 'Отправлено',
    className: 'bg-green-100 text-green-700 border-green-200',
  },
  error: {
    label: 'Ошибка',
    className: 'bg-red-100 text-red-700 border-red-200',
  },
}

interface ApplicationStatusBadgeProps {
  status: ApplicationStatus
  className?: string
}

export default function ApplicationStatusBadge({
  status,
  className,
}: ApplicationStatusBadgeProps) {
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
