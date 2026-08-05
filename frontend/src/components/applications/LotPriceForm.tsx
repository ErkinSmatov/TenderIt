'use client'

import type { Lot } from '@/types/tender'
import type { LotOffer } from '@/types/application'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface LotPriceFormProps {
  lots: Lot[]
  value: LotOffer[]
  onChange: (offers: LotOffer[]) => void
}

function formatMoney(n: number): string {
  if (!isFinite(n)) return '—'
  return n.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function LotPriceForm({ lots, value, onChange }: LotPriceFormProps) {
  // count = количество единиц (quantity). amount = запланированная сумма (budget).
  function getQuantity(lot: Lot): number {
    return typeof lot.count === 'number' && lot.count > 0 ? lot.count : 1
  }

  function handleUnitPriceChange(lot: Lot, unitPriceStr: string) {
    const lotId = lot.id ?? 0
    const quantity = getQuantity(lot)
    const unitPrice = parseFloat(unitPriceStr.replace(',', '.'))
    const totalPrice = isFinite(unitPrice) ? unitPrice * quantity : 0

    const existing = value.filter((o) => o.lot_id !== lotId)
    const updated: LotOffer = {
      lot_id: lotId,
      unit_price: unitPriceStr,
      quantity,
      total_price: isFinite(unitPrice) ? totalPrice.toFixed(2) : '0.00',
    }
    onChange([...existing, updated])
  }

  function getUnitPrice(lotId: number): string {
    return value.find((o) => o.lot_id === lotId)?.unit_price ?? ''
  }

  function computeTotal(lot: Lot): number {
    const lotId = lot.id ?? 0
    const unitPriceStr = getUnitPrice(lotId)
    const unitPrice = parseFloat(unitPriceStr.replace(',', '.'))
    return isFinite(unitPrice) ? unitPrice * getQuantity(lot) : 0
  }

  if (lots.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        В этом тендере нет лотов с данными для заполнения.
      </p>
    )
  }

  return (
    <div className="space-y-4">
      {lots.map((lot, index) => {
        const lotId = lot.id ?? index
        const quantity = getQuantity(lot)
        const total = computeTotal(lot)
        const unitPriceStr = getUnitPrice(lotId)
        const unitPrice = parseFloat(unitPriceStr.replace(',', '.'))
        const hasValue = unitPriceStr !== '' && isFinite(unitPrice) && unitPrice > 0

        return (
          <div key={lotId} className="rounded-lg border bg-card px-4 py-3 space-y-3">
            {/* Lot info */}
            <div className="space-y-1">
              <p className="text-sm font-medium">
                Лот {lot.lotNumber ?? (index + 1)}
                {lot.nameRu ? ` — ${lot.nameRu}` : ''}
              </p>
              {lot.descriptionRu && (
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {lot.descriptionRu}
                </p>
              )}
              <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted-foreground mt-1">
                <span>Количество: <span className="text-foreground font-medium">{quantity}</span></span>
                {typeof lot.amount === 'number' && lot.amount > 0 && (
                  <span>
                    Запл. сумма:{' '}
                    <span className="text-foreground font-medium">{formatMoney(lot.amount)} ₸</span>
                  </span>
                )}
              </div>
            </div>

            {/* Price input */}
            <div className="space-y-1.5">
              <Label htmlFor={`unit-price-${lotId}`} className="text-xs">
                Цена за единицу (тенге)
              </Label>
              <Input
                id={`unit-price-${lotId}`}
                type="number"
                min="0"
                step="0.01"
                placeholder="0.00"
                value={getUnitPrice(lotId)}
                onChange={(e) => handleUnitPriceChange(lot, e.target.value)}
                className="w-48"
                aria-label={`Цена за единицу для лота ${lot.lotNumber ?? (index + 1)}`}
              />
            </div>

            {/* Computed total */}
            <div className="text-sm">
              <span className="text-muted-foreground">Итого: </span>
              <span className={hasValue ? 'font-semibold' : 'text-muted-foreground'}>
                {hasValue ? `${formatMoney(total)} ₸` : '—'}
              </span>
              {hasValue && typeof lot.amount === 'number' && lot.amount > 0 && (
                <span className={`ml-2 text-xs ${total <= lot.amount ? 'text-green-600 dark:text-green-400' : 'text-amber-600 dark:text-amber-400'}`}>
                  {total <= lot.amount ? '≤ запл. суммы' : '> запл. суммы'}
                </span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
