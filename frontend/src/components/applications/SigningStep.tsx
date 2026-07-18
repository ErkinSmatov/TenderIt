'use client'

/**
 * SigningStep — Step 4 of ApplicationWizard.
 *
 * - Mounts NCALayerStatus (connection indicator) and CertificateInfo (cert details).
 * - "Подписать и сохранить" is disabled unless ncaLayer.status === 'connected'.
 * - Shows per-step progress during runSigningFlow execution.
 * - Shows error Alert on failure (APPL-06 error surfacing).
 * - Collects iik and subject_address (portal credentials needed for create-draft step).
 */

import type { NCALayerHookResult, Certificate } from '@/types/ncalayer'
import type { CryptoSocketHookResult } from '@/types/cryptosocket'
import NCALayerStatus from '@/components/signing/NCALayerStatus'
import CertificateInfo from '@/components/signing/CertificateInfo'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert } from '@/components/ui/alert'

interface SigningStepProps {
  ncaLayer: NCALayerHookResult
  cryptoSocket: CryptoSocketHookResult
  iik: string
  onIikChange: (v: string) => void
  subjectAddress: string
  onSubjectAddressChange: (v: string) => void
  onSign: () => void
  isLoading: boolean
  progress: { step: number; label: string } | null
  error: string | null
}

const TOTAL_STEPS = 12

export default function SigningStep({
  ncaLayer,
  cryptoSocket,
  iik,
  onIikChange,
  subjectAddress,
  onSubjectAddressChange,
  onSign,
  isLoading,
  progress,
  error,
}: SigningStepProps) {
  // Sign button requires NCALayer connected AND CryptoSocket connected
  const canSign =
    ncaLayer.status === 'connected' &&
    cryptoSocket.status === 'connected' &&
    !isLoading

  // NCALayerHookResult.certificates contains only SIGNATURE certs (AUTH excluded by hook).
  const signingCert: Certificate | null = ncaLayer.certificates[0] ?? null

  const progressPct =
    progress !== null
      ? Math.round(((progress.step + 1) / TOTAL_STEPS) * 100)
      : 0

  return (
    <div className="space-y-5">

      {/* NCALayer connection status */}
      <div className="space-y-2">
        <h3 className="text-sm font-medium">NCALayer (подпись документов)</h3>
        <NCALayerStatus ncaLayer={ncaLayer} />
      </div>

      {/* Certificate info (only when connected and cert available) */}
      {ncaLayer.status === 'connected' && signingCert && (
        <CertificateInfo certificate={signingCert} />
      )}

      {/* CryptoSocket status */}
      <div className="space-y-2">
        <h3 className="text-sm font-medium">CryptoSocket (шифрование цены)</h3>
        <div className="flex items-center justify-between gap-3 rounded-lg border bg-card px-4 py-3">
          <div className="flex items-center gap-2.5 text-sm">
            {cryptoSocket.status === 'connected' ? (
              <span className="size-2.5 rounded-full bg-green-500 shrink-0" aria-hidden="true" />
            ) : cryptoSocket.status === 'connecting' || cryptoSocket.status === 'encrypting' ? (
              <span className="size-2.5 rounded-full bg-amber-400 shrink-0 animate-pulse" aria-hidden="true" />
            ) : (
              <span className="size-2.5 rounded-full bg-red-500 shrink-0" aria-hidden="true" />
            )}
            <span>
              {cryptoSocket.status === 'connected' && (
                <span className="font-medium text-green-700 dark:text-green-400">
                  CryptoSocket подключён
                </span>
              )}
              {(cryptoSocket.status === 'connecting' || cryptoSocket.status === 'encrypting') && (
                <span className="text-amber-700 dark:text-amber-400">
                  {cryptoSocket.status === 'encrypting' ? 'Шифрование цены...' : 'Подключение...'}
                </span>
              )}
              {(cryptoSocket.status === 'disconnected' || cryptoSocket.status === 'error') && (
                <span className="text-muted-foreground">
                  {cryptoSocket.error ?? 'CryptoSocket не подключён (TumarCSP, порт 6126)'}
                </span>
              )}
            </span>
          </div>
          {(cryptoSocket.status === 'disconnected' || cryptoSocket.status === 'error') && (
            <Button
              size="sm"
              variant="outline"
              onClick={cryptoSocket.connect}
              aria-label="Подключить CryptoSocket"
            >
              Подключить
            </Button>
          )}
        </div>
      </div>

      {/* Portal credentials */}
      <div className="space-y-3 rounded-lg border bg-card px-4 py-3">
        <p className="text-sm font-medium">Реквизиты для портала закупок</p>
        <div className="space-y-1.5">
          <Label htmlFor="signing-iik" className="text-xs">
            ИИК (расчётный счёт поставщика)
          </Label>
          <Input
            id="signing-iik"
            type="text"
            placeholder="KZ00 0000 0000 0000 0000"
            value={iik}
            onChange={(e) => onIikChange(e.target.value)}
            aria-label="ИИК поставщика"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="signing-subject-address" className="text-xs">
            Адрес субъекта (subject_address на портале)
          </Label>
          <Input
            id="signing-subject-address"
            type="text"
            placeholder="ID адреса из goszakup"
            value={subjectAddress}
            onChange={(e) => onSubjectAddressChange(e.target.value)}
            aria-label="Адрес субъекта на портале закупок"
          />
        </div>
      </div>

      {/* Progress bar (visible during signing) */}
      {isLoading && progress !== null && (
        <div className="space-y-1.5">
          <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
            <div
              className="h-full bg-primary rounded-full transition-all duration-300"
              style={{ width: `${progressPct}%` }}
              role="progressbar"
              aria-valuenow={progressPct}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>
          <p className="text-xs text-muted-foreground">{progress.label}</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <Alert className="text-destructive border-destructive/50 bg-destructive/10 text-sm">
          {error}
        </Alert>
      )}

      {/* Sign button — disabled unless NCALayer + CryptoSocket connected */}
      <Button
        onClick={onSign}
        disabled={!canSign}
        className="w-full"
        aria-disabled={!canSign}
      >
        {isLoading ? 'Подписание...' : 'Подписать и сохранить'}
      </Button>

      {!ncaLayer.status.startsWith('connect') && ncaLayer.status !== 'connected' && (
        <p className="text-xs text-center text-muted-foreground">
          Для подписания необходимо подключить NCALayer и CryptoSocket (TumarCSP)
        </p>
      )}
    </div>
  )
}
