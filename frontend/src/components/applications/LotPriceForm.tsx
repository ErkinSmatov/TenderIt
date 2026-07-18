'use client'

/**
 * LotPriceForm — Step 2 of ApplicationWizard.
 *
 * One unit-price input per lot; computes totalPrice = unitPrice * quantity live.
 * Quantity is taken from the lot's `amount` field (SPIKE-03: per-lot unit count).
 * Price is the only user-facing input (D-05-03).
 */

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
  function handleUnitPriceChange(lot: Lot, unitPriceStr: string) {
    const lotId = lot.id ?? 0
    const quantity = typeof lot.amount === 'number' && lot.amount > 0 ? lot.amount : 1
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
    const quantity = typeof lot.amount === 'number' && lot.amount > 0 ? lot.amount : 1
    return isFinite(unitPrice) ? unitPrice * quantity : 0
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
        const quantity = typeof lot.amount === 'number' && lot.amount > 0 ? lot.amount : 1
        const total = computeTotal(lot)
        const unitPriceStr = getUnitPrice(lotId)
        const unitPrice = parseFloat(unitPriceStr.replace(',', '.'))
        const hasValue = unitPriceStr !== '' && isFinite(unitPrice) && unitPrice > 0

        return (
          <div
            key={lotId}
            className="rounded-lg border bg-card px-4 py-3 space-y-3"
          >
            {/* Lot header */}
            <div>
              <p className="text-sm font-medium">
                Лот {lot.lotNumber ?? (index + 1)}
                {lot.nameRu ? ` — ${lot.nameRu}` : ''}
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Количество: {quantity}
              </p>
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
              <span className="text-muted-foreground">Сумма: </span>
              <span className={hasValue ? 'font-semibold' : 'text-muted-foreground'}>
                {hasValue ? `${formatMoney(total)} ₸` : '—'}
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
