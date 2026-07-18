'use client'

/**
 * ApplicationWizard — 4-step wizard for creating a tender application.
 *
 * Steps:
 *   1. Select watched tender (GET /api/watchlist)
 *   2. Enter lot prices (LotPriceForm)
 *   3. Select documents (DocumentSelect)
 *   4. Sign and submit (SigningStep → runSigningFlow)
 *
 * On successful signing: POST /api/applications → runSigningFlow → redirect /applications.
 * On failure: Alert with error message (APPL-06 error surfacing).
 *
 * useNCALayer + useCryptoSocket are initialised once at wizard mount and passed to
 * SigningStep (single WS connection per session).
 */

import { useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useNCALayer } from '@/hooks/useNCALayer'
import { useCryptoSocket } from '@/hooks/useCryptoSocket'
import { runSigningFlow } from '@/lib/goszakup'
import type { WatchlistEntry, Lot } from '@/types/tender'
import type { LotOffer, ApplicationCreate, ApplicationResponse } from '@/types/application'
import type { BeneficiaryData } from '@/lib/goszakup'
import LotPriceForm from './LotPriceForm'
import DocumentSelect from './DocumentSelect'
import SigningStep from './SigningStep'
import { Button } from '@/components/ui/button'
import { Alert } from '@/components/ui/alert'

type WizardStep = 1 | 2 | 3 | 4

/** Extract goszakup tender_buy_id from number_anno format "{trd_buy_id}-{version}". */
function parseTenderBuyId(numberAnno: string): number {
  return parseInt(numberAnno.split('-')[0], 10)
}

export default function ApplicationWizard() {
  const router = useRouter()
  const ncaLayer = useNCALayer()
  const cryptoSocket = useCryptoSocket()

  const [step, setStep] = useState<WizardStep>(1)
  const [selectedEntry, setSelectedEntry] = useState<WatchlistEntry | null>(null)
  const [lotOffers, setLotOffers] = useState<LotOffer[]>([])
  const [selectedDocIds, setSelectedDocIds] = useState<number[]>([])
  const [iik, setIik] = useState('')
  const [subjectAddress, setSubjectAddress] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [progress, setProgress] = useState<{ step: number; label: string } | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Step 1: watchlist
  const {
    data: watchlist,
    isLoading: watchlistLoading,
    error: watchlistError,
  } = useQuery<WatchlistEntry[]>({
    queryKey: ['watchlist'],
    queryFn: () => api.get<WatchlistEntry[]>('/api/watchlist'),
    retry: false,
  })

  // Navigate helpers
  const canProceedStep1 = selectedEntry !== null
  const lots: Lot[] = selectedEntry?.tender.lots_data ?? []
  const canProceedStep2 =
    lots.length === 0 || // no lots — allow proceed
    lots.every((lot) => {
      const offer = lotOffers.find((o) => o.lot_id === (lot.id ?? 0))
      if (!offer) return false
      const unitPrice = parseFloat(offer.unit_price)
      return isFinite(unitPrice) && unitPrice > 0
    })
  // Step 3 — docs are optional per plan
  const canProceedStep3 = true

  function handleSelectTender(entry: WatchlistEntry) {
    setSelectedEntry(entry)
    setLotOffers([]) // reset prices on tender change
  }

  function handleNext() {
    setError(null)
    if (step < 4) setStep((s) => (s + 1) as WizardStep)
  }

  function handleBack() {
    setError(null)
    if (step > 1) setStep((s) => (s - 1) as WizardStep)
  }

  const handleSign = useCallback(async () => {
    if (!selectedEntry) return
    setError(null)
    setIsLoading(true)
    setProgress({ step: 0, label: 'Подготовка заявки...' })

    try {
      const tender = selectedEntry.tender
      const tenderBuyId = parseTenderBuyId(tender.number_anno)
      const validLotIds = lots.map((l) => l.id ?? 0).filter(Boolean)

      // Build beneficiaries: one per lot using lot's app_lot_id (placeholder — portal assigns IDs)
      // For MVP: app_lot_id is not known until portal steps 2-3; placeholder uses lot index.
      // The backend proxy will use the actual app_lot_id returned by create_application.
      const beneficiaries: BeneficiaryData[] = lots.map((lot, idx) => ({
        app_lot_id: idx + 1,
        beneficiary_name: '',   // auto-filled from company_profiles server-side (D-05-03)
        beneficiary_doc_number: '',
        beneficiary_doc_date: new Date().toISOString().split('T')[0],
      }))

      // Step 1: Create application draft row in TenderIt DB
      const appCreate: ApplicationCreate = {
        tender_id: 0, // tender numeric DB id not exposed on WatchlistEntry; backend resolves by number_anno
        lots_data: lotOffers,
        document_ids: selectedDocIds,
      }

      // POST /api/applications to create draft (backend resolves tender_id from number_anno via watchlist)
      const appResp = await api.post<ApplicationResponse>('/api/applications', {
        ...appCreate,
        tender_number_anno: tender.number_anno, // additional field backend uses to resolve tender_id
      })

      // Step 2: Run full 12-step signing + portal flow
      await runSigningFlow({
        appId: appResp.id,
        tenderBuyId,
        iik: iik.trim(),
        subjectAddress: subjectAddress.trim(),
        lotIds: validLotIds,
        beneficiaries,
        documentIds: selectedDocIds,
        nca: ncaLayer,
        cs: cryptoSocket,
        onProgress: (stepIdx, label) => {
          setProgress({ step: stepIdx, label })
        },
      })

      // Success: redirect to applications list
      router.push('/applications')
    } catch (e: unknown) {
      const msg =
        e instanceof Error
          ? e.message
          : 'Произошла неизвестная ошибка при подписании. Попробуйте ещё раз.'
      setError(msg)
    } finally {
      setIsLoading(false)
      setProgress(null)
    }
  }, [
    selectedEntry,
    lots,
    lotOffers,
    selectedDocIds,
    iik,
    subjectAddress,
    ncaLayer,
    cryptoSocket,
    router,
  ])

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6 max-w-xl">
      {/* Step indicator */}
      <nav className="flex gap-1" aria-label="Шаги мастера">
        {([1, 2, 3, 4] as WizardStep[]).map((s) => (
          <div
            key={s}
            className={
              'flex-1 h-1 rounded-full transition-colors ' +
              (s < step
                ? 'bg-primary'
                : s === step
                ? 'bg-primary/60'
                : 'bg-muted')
            }
          />
        ))}
      </nav>

      {/* ── Step 1: Select tender ─────────────────────────────────────────────── */}
      {step === 1 && (
        <div className="space-y-4">
          <div>
            <h2 className="text-base font-semibold">Выберите тендер</h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              Выберите тендер из списка отслеживаемых
            </p>
          </div>

          {watchlistLoading && (
            <p className="text-sm text-muted-foreground animate-pulse">
              Загрузка отслеживаемых тендеров...
            </p>
          )}

          {watchlistError && (
            <Alert className="text-destructive border-destructive/50 bg-destructive/10 text-sm">
              Не удалось загрузить список тендеров. Проверьте соединение и обновите страницу.
            </Alert>
          )}

          {!watchlistLoading && !watchlistError && (watchlist ?? []).length === 0 && (
            <Alert className="text-muted-foreground border-border bg-card text-sm">
              Нет отслеживаемых тендеров. Найдите тендер и добавьте его в{' '}
              <a href="/tenders" className="underline hover:text-foreground">
                список отслеживаемых
              </a>
              .
            </Alert>
          )}

          <div className="space-y-2">
            {(watchlist ?? []).map((entry) => {
              const isSelected =
                selectedEntry?.tender.number_anno === entry.tender.number_anno
              return (
                <button
                  key={entry.tender.number_anno}
                  type="button"
                  onClick={() => handleSelectTender(entry)}
                  className={
                    'w-full text-left rounded-lg border px-4 py-3 transition-colors ' +
                    (isSelected
                      ? 'border-primary bg-primary/5'
                      : 'border-border bg-card hover:bg-muted/50')
                  }
                  aria-pressed={isSelected}
                >
                  <p className="text-sm font-medium">
                    {entry.tender.name_ru ?? entry.tender.number_anno}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    № {entry.tender.number_anno}
                    {entry.tender.end_date
                      ? ` · до ${new Date(entry.tender.end_date).toLocaleDateString('ru-RU')}`
                      : ''}
                  </p>
                </button>
              )
            })}
          </div>

          <div className="flex justify-end">
            <Button onClick={handleNext} disabled={!canProceedStep1}>
              Далее
            </Button>
          </div>
        </div>
      )}

      {/* ── Step 2: Lot prices ───────────────────────────────────────────────── */}
      {step === 2 && (
        <div className="space-y-4">
          <div>
            <h2 className="text-base font-semibold">Укажите цену</h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              Введите цену за единицу для каждого лота
            </p>
          </div>

          <LotPriceForm
            lots={lots}
            value={lotOffers}
            onChange={setLotOffers}
          />

          <div className="flex justify-between">
            <Button variant="outline" onClick={handleBack}>
              Назад
            </Button>
            <Button onClick={handleNext} disabled={!canProceedStep2}>
              Далее
            </Button>
          </div>
        </div>
      )}

      {/* ── Step 3: Documents ────────────────────────────────────────────────── */}
      {step === 3 && (
        <div className="space-y-4">
          <div>
            <h2 className="text-base font-semibold">Выберите документы</h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              Выберите документы, которые нужно приложить к заявке
            </p>
          </div>

          <DocumentSelect
            value={selectedDocIds}
            onChange={setSelectedDocIds}
          />

          <div className="flex justify-between">
            <Button variant="outline" onClick={handleBack}>
              Назад
            </Button>
            <Button onClick={handleNext} disabled={!canProceedStep3}>
              Далее
            </Button>
          </div>
        </div>
      )}

      {/* ── Step 4: Sign ─────────────────────────────────────────────────────── */}
      {step === 4 && (
        <div className="space-y-4">
          <div>
            <h2 className="text-base font-semibold">Подписание</h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              Подключите NCALayer и CryptoSocket, затем подпишите заявку
            </p>
          </div>

          <SigningStep
            ncaLayer={ncaLayer}
            cryptoSocket={cryptoSocket}
            iik={iik}
            onIikChange={setIik}
            subjectAddress={subjectAddress}
            onSubjectAddressChange={setSubjectAddress}
            onSign={handleSign}
            isLoading={isLoading}
            progress={progress}
            error={error}
          />

          {!isLoading && (
            <div className="flex justify-start">
              <Button variant="outline" onClick={handleBack}>
                Назад
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
