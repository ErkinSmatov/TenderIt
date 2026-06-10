/**
 * StatusBadge — renders a coloured pill for a goszakup tender status.
 *
 * Colour mapping (03-UI-SPEC.md):
 *   Open / accepting applications ("прием заявок")  → green
 *   Completed / cancelled ("завершен" / "отменен")   → gray (secondary)
 *   Everything else                                  → amber (outline)
 *
 * SPIKE-01 actual status_name_ru for "open": "Опубликовано (прием заявок)".
 * We match on substring to be robust to minor API variations.
 */

import { cn } from '@/lib/utils'

interface StatusBadgeProps {
  statusName: string | null
}

function getBadgeClasses(name: string | null): string {
  const lower = (name ?? '').toLowerCase()
  if (lower.includes('прием заявок')) {
    return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20'
  }
  if (lower.includes('завершен') || lower.includes('отменен')) {
    return 'bg-muted text-muted-foreground border-transparent'
  }
  return 'bg-amber-500/15 text-amber-400 border-amber-500/20'
}

export default function StatusBadge({ statusName }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium',
        getBadgeClasses(statusName),
      )}
    >
      {statusName ?? 'Неизвестно'}
    </span>
  )
}
