'use client'

/**
 * DraftFillView — fills a discovery-created draft application.
 *
 * Mounted only when application.status === 'draft'. Keeps NCALayer/CryptoSocket
 * hooks in a child component so they're only initialised for draft pages.
 *
 * Steps:
 *   1. Enter lot prices (LotPriceForm) + select documents (DocumentSelect)
 *   2. Sign (SigningStep) → PATCH /api/applications/{id} → runSigningFlow
 */

import { useState, useCallback } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import { useNCALayer } from '@/hooks/useNCALayer'
import { useCryptoSocket } from '@/hooks/useCryptoSocket'
import { runSigningFlow } from '@/lib/goszakup'
import type { ApplicationResponse, LotOffer } from '@/types/application'
import type { Lot } from '@/types/tender'
import type { BeneficiaryData } from '@/lib/goszakup'
import LotPriceForm from './LotPriceForm'
import DocumentSelect from './DocumentSelect'
import SigningStep from './SigningStep'
import ApplicationStatusBadge from './ApplicationStatusBadge'
import { Button } from '@/components/ui/button'

interface DraftFillViewProps {
  application: ApplicationResponse
}

function parseTenderBuyId(numberAnno: string): number {
  return parseInt(numberAnno.split('-')[0], 10)
}

export default function DraftFillView({ application }: DraftFillViewProps) {
  const router = useRouter()
  const ncaLayer = useNCALayer()
  const cryptoSocket = useCryptoSocket()

  const lots: Lot[] = (application.tender_lots_data ?? []) as Lot[]

  const [lotOffers, setLotOffers] = useState<LotOffer[]>([])
  const [selectedDocIds, setSelectedDocIds] = useState<number[]>([])
  const [iik, setIik] = useState('')
  const [subjectAddress, setSubjectAddress] = useState('')
  const [step, setStep] = useState<'form' | 'sign'>('form')
  const [isLoading, setIsLoading] = useState(false)
  const [progress, setProgress] = useState<{ step: number; label: string } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const canProceed =
    lots.length === 0 ||
    lots.every((lot) => {
      const offer = lotOffers.find((o) => o.lot_id === (lot.id ?? 0))
      return offer && isFinite(parseFloat(offer.unit_price)) && parseFloat(offer.unit_price) > 0
    })

  const handleSign = useCallback(async () => {
    if (!application.tender_number_anno) {
      setError('Номер тендера не найден. Попробуйте обновить страницу.')
      return
    }
    setError(null)
    setIsLoading(true)
    setProgress({ step: 0, label: 'Сохранение данных заявки...' })

    try {
      // Step 1: persist lot prices + documents on the existing draft
      await api.patch(`/api/applications/${application.id}`, {
        lots_data: lotOffers,
        document_ids: selectedDocIds,
      })

      const tenderBuyId = parseTenderBuyId(application.tender_number_anno)
      const validLotIds = lots.map((l) => l.id ?? 0).filter(Boolean)
      const beneficiaries: BeneficiaryData[] = lots.map((_, idx) => ({
        app_lot_id: idx + 1,
        beneficiary_name: '',
        beneficiary_doc_number: '',
        beneficiary_doc_date: new Date().toISOString().split('T')[0],
      }))

      // Step 2: run full signing + portal submission flow
      await runSigningFlow({
        appId: application.id,
        tenderBuyId,
        iik: iik.trim(),
        subjectAddress: subjectAddress.trim(),
        lotIds: validLotIds,
        beneficiaries,
        documentIds: selectedDocIds,
        nca: ncaLayer,
        cs: cryptoSocket,
        onProgress: (stepIdx, label) => setProgress({ step: stepIdx, label }),
      })

      router.push('/applications')
    } catch (e: unknown) {
      setError(
        e instanceof Error
          ? e.message
          : 'Произошла неизвестная ошибка при подписании. Попробуйте ещё раз.',
      )
    } finally {
      setIsLoading(false)
      setProgress(null)
    }
  }, [application, lots, lotOffers, selectedDocIds, iik, subjectAddress, ncaLayer, cryptoSocket, router])

  return (
    <div className="max-w-xl space-y-6">
      {/* Header */}
      <div>
        <Link href="/applications" className="text-sm text-muted-foreground hover:text-foreground">
          ← Назад к заявкам
        </Link>
        <div className="flex items-start justify-between gap-3 mt-3">
          <div>
            <h1 className="text-xl font-semibold">Оформление заявки</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {application.tender_number_anno ?? `Тендер #${application.tender_id}`}
            </p>
          </div>
          <ApplicationStatusBadge status={application.status} />
        </div>
      </div>

      {/* Step progress bar */}
      <div className="flex gap-1">
        {(['form', 'sign'] as const).map((s) => (
          <div
            key={s}
            className={`flex-1 h-1 rounded-full transition-colors ${
              s === 'form' ? 'bg-primary' : step === 'sign' ? 'bg-primary/60' : 'bg-muted'
            }`}
          />
        ))}
      </div>

      {/* Step 1: lot prices + documents */}
      {step === 'form' && (
        <div className="space-y-6">
          <div className="space-y-3">
            <h2 className="text-base font-semibold">Цены по лотам</h2>
            {lots.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Данные лотов не найдены — возможно, тендер ещё не загрузился в базу.
              </p>
            ) : (
              <LotPriceForm lots={lots} value={lotOffers} onChange={setLotOffers} />
            )}
          </div>

          <div className="space-y-3">
            <h2 className="text-base font-semibold">Документы</h2>
            <p className="text-sm text-muted-foreground">
              Выберите документы из хранилища или пропустите этот шаг
            </p>
            <DocumentSelect value={selectedDocIds} onChange={setSelectedDocIds} />
          </div>

          <div className="flex justify-end">
            <Button onClick={() => setStep('sign')} disabled={!canProceed}>
              Далее — Подписание
            </Button>
          </div>
        </div>
      )}

      {/* Step 2: sign */}
      {step === 'sign' && (
        <div className="space-y-4">
          <h2 className="text-base font-semibold">Подписание ЭЦП</h2>
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
            <Button variant="outline" onClick={() => { setStep('form'); setError(null) }}>
              Назад
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
