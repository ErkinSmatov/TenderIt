'use client'

/**
 * /discovery-filters — Filter settings page for discovery matching (DISC-10).
 *
 * Flow:
 *   1. useQuery fetches GET /api/discovery/filters to pre-fill form (404 = no filter yet, handled).
 *   2. Form fields: keywords, СПГЗ codes, region, min/max amount.
 *   3. On submit: useMutation → PUT /api/discovery/filters → shows "Фильтры сохранены".
 */

import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { ClientFilterResponse } from '@/types/discovery'
import { Alert } from '@/components/ui/alert'

interface FilterFormData {
  keywordsRaw: string     // comma-separated string input
  spgzCodesRaw: string    // comma-separated string input
  region: string
  minAmount: string       // numeric as string (empty = no limit)
  maxAmount: string
}

export default function DiscoveryFiltersPage() {
  const queryClient = useQueryClient()

  const { data: currentFilter, isLoading } = useQuery<ClientFilterResponse>({
    queryKey: ['discovery-filters'],
    queryFn: () => api.get<ClientFilterResponse>('/api/discovery/filters'),
    retry: false, // 404 = no filter yet, not an error to retry
  })

  const [form, setForm] = useState<FilterFormData>({
    keywordsRaw: '',
    spgzCodesRaw: '',
    region: '',
    minAmount: '',
    maxAmount: '',
  })
  const [saved, setSaved] = useState(false)

  // Pre-fill form when existing filter loads
  useEffect(() => {
    if (currentFilter) {
      setForm({
        keywordsRaw: currentFilter.keywords.join(', '),
        spgzCodesRaw: currentFilter.spgz_codes.join(', '),
        region: currentFilter.region || '',
        minAmount: currentFilter.min_amount || '',
        maxAmount: currentFilter.max_amount || '',
      })
    }
  }, [currentFilter])

  const mutation = useMutation({
    mutationFn: (data: object) =>
      api.put<ClientFilterResponse>('/api/discovery/filters', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['discovery-filters'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    },
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const keywords = form.keywordsRaw
      .split(',')
      .map((k) => k.trim())
      .filter(Boolean)
    const spgz_codes = form.spgzCodesRaw
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    mutation.mutate({
      keywords,
      spgz_codes,
      region: form.region.trim() || null,
      min_amount: form.minAmount ? parseFloat(form.minAmount) : null,
      max_amount: form.maxAmount ? parseFloat(form.maxAmount) : null,
    })
  }

  return (
    <div className="max-w-lg space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Фильтры подборки</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Тендеры, совпадающие с фильтрами, появятся в «Подборке» и придут в Telegram
        </p>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Загрузка...</p>}

      {!isLoading && (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <label className="text-sm font-medium">Ключевые слова</label>
            <input
              type="text"
              value={form.keywordsRaw}
              onChange={(e) =>
                setForm((f) => ({ ...f, keywordsRaw: e.target.value }))
              }
              placeholder="строительство, ремонт, услуги"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
            <p className="text-xs text-muted-foreground">
              Введите через запятую. Тендер подойдёт, если название содержит любое слово.
            </p>
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium">СПГЗ коды</label>
            <input
              type="text"
              value={form.spgzCodesRaw}
              onChange={(e) =>
                setForm((f) => ({ ...f, spgzCodesRaw: e.target.value }))
              }
              placeholder="12.34.56, 78.90.12"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
            <p className="text-xs text-muted-foreground">Точное совпадение кода СПГЗ/КТРУ.</p>
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium">Регион</label>
            <input
              type="text"
              value={form.region}
              onChange={(e) =>
                setForm((f) => ({ ...f, region: e.target.value }))
              }
              placeholder="Алматы"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-sm font-medium">Сумма от (₸)</label>
              <input
                type="number"
                min="0"
                value={form.minAmount}
                onChange={(e) =>
                  setForm((f) => ({ ...f, minAmount: e.target.value }))
                }
                placeholder="0"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Сумма до (₸)</label>
              <input
                type="number"
                min="0"
                value={form.maxAmount}
                onChange={(e) =>
                  setForm((f) => ({ ...f, maxAmount: e.target.value }))
                }
                placeholder="Без ограничений"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>
          </div>

          {mutation.isError && (
            <Alert className="text-destructive border-destructive/50 bg-destructive/10 text-sm">
              Не удалось сохранить фильтры. Попробуйте снова.
            </Alert>
          )}

          {saved && (
            <p className="text-sm text-green-600">Фильтры сохранены</p>
          )}

          <button
            type="submit"
            disabled={mutation.isPending}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {mutation.isPending ? 'Сохраняем...' : 'Сохранить'}
          </button>
        </form>
      )}
    </div>
  )
}
