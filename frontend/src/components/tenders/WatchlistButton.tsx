'use client'

/**
 * WatchlistButton — add/remove a tender from the authenticated user's watchlist.
 *
 * Props:
 *   numberAnno  — tender number (e.g. "17163708-1")
 *   isWatching  — whether the tender is currently in the watchlist
 *   onChange    — called after a successful add or remove (parent invalidates react-query)
 *   compact     — true → text-xs px-2 py-1 (for dashboard list rows)
 *
 * States (03-UI-SPEC.md):
 *   Default  — bg-blue-600 text-white "Добавить в список"
 *   Active   — bg-gray-100 text-gray-700 border border-gray-300 "В списке"
 *              on hover → text-red-600 "Удалить из списка"
 *   Loading  — opacity-50 cursor-not-allowed (button disabled)
 *
 * a11y: aria-pressed, dynamic aria-label, focus ring.
 */

import { type ReactNode, useState } from 'react'
import { BookmarkPlus, BookmarkCheck, BookmarkX } from 'lucide-react'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'

interface WatchlistButtonProps {
  numberAnno: string
  isWatching: boolean
  onChange?: () => void
  compact?: boolean
}

export default function WatchlistButton({
  numberAnno,
  isWatching,
  onChange,
  compact = false,
}: WatchlistButtonProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [hovered, setHovered] = useState(false)

  const handleClick = async () => {
    if (loading) return
    setLoading(true)
    setError(null)
    try {
      if (isWatching) {
        await api.delete(`/api/watchlist/${encodeURIComponent(numberAnno)}`)
      } else {
        await api.post('/api/watchlist', { number_anno: numberAnno })
      }
      onChange?.()
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Ошибка'
      setError(
        isWatching
          ? `Не удалось удалить: ${msg}`
          : `Не удалось добавить: ${msg}`,
      )
    } finally {
      setLoading(false)
    }
  }

  const size = compact ? 'sm' : 'default'

  let icon: ReactNode
  let label: string
  let ariaLabel: string
  let variant: 'default' | 'outline' | 'destructive'

  if (loading) {
    icon = isWatching ? <BookmarkCheck className="h-3.5 w-3.5" /> : <BookmarkPlus className="h-3.5 w-3.5" />
    label = isWatching ? 'В списке' : 'Добавить...'
    ariaLabel = 'Загрузка...'
    variant = isWatching ? 'outline' : 'default'
  } else if (isWatching) {
    if (hovered) {
      icon = <BookmarkX className="h-3.5 w-3.5" />
      label = compact ? 'Удалить' : 'Удалить из списка'
      variant = 'destructive'
    } else {
      icon = <BookmarkCheck className="h-3.5 w-3.5" />
      label = 'В списке'
      variant = 'outline'
    }
    ariaLabel = 'Удалить из списка отслеживания'
  } else {
    icon = <BookmarkPlus className="h-3.5 w-3.5" />
    label = compact ? 'Добавить' : 'Добавить в список'
    ariaLabel = 'Добавить тендер в список отслеживания'
    variant = 'default'
  }

  return (
    <div>
      <Button
        type="button"
        variant={variant}
        size={size}
        onClick={handleClick}
        disabled={loading}
        aria-pressed={isWatching}
        aria-label={ariaLabel}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        {loading && <span role="status" className="sr-only">Загрузка...</span>}
        {icon}
        {label}
      </Button>
      {error && (
        <p className="text-destructive text-xs mt-1">{error}</p>
      )}
    </div>
  )
}
