'use client'

/**
 * CertificateInfo — SIGN-02 + SIGN-03
 *
 * Displays the selected signing certificate details and warns the user
 * when the certificate expires within 30 days (SIGN-03).
 *
 * Receives a Certificate from useNCALayer().certificates (SIGNATURE certs only).
 */

import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import type { Certificate } from '@/types/ncalayer'
import { certExpiresWithinDays } from '@/hooks/useNCALayer'

interface CertificateInfoProps {
  certificate: Certificate
}

function formatDate(date: Date): string {
  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
}

/** Remaining days until certificate expiry (can be negative if already expired). */
function daysUntilExpiry(notAfter: Date): number {
  return Math.floor((notAfter.getTime() - Date.now()) / (24 * 60 * 60 * 1000))
}

export default function CertificateInfo({ certificate }: CertificateInfoProps) {
  const isExpiringSoon = certExpiresWithinDays(certificate, 30)
  const daysLeft = daysUntilExpiry(certificate.notAfter)
  const expired = daysLeft < 0

  return (
    <div className="space-y-3">
      {/* Certificate fields */}
      <div className="rounded-lg border bg-card px-4 py-3 text-sm space-y-2">
        <div className="flex flex-col gap-0.5">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Владелец
          </span>
          <span className="font-medium">{certificate.subjectCommonName}</span>
        </div>

        <div className="flex flex-col gap-0.5">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Выдан
          </span>
          <span>{certificate.issuerCommonName}</span>
        </div>

        <div className="flex flex-col gap-0.5">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Действует до
          </span>
          <span className={expired ? 'text-destructive font-medium' : undefined}>
            {formatDate(certificate.notAfter)}
            {expired && ' (истёк)'}
          </span>
        </div>
      </div>

      {/* SIGN-03: persistent expiry warning when < 30 days remain */}
      {isExpiringSoon && (
        <Alert variant="destructive">
          <AlertTitle className="text-sm font-semibold">
            {expired
              ? 'Сертификат ЭЦП истёк'
              : `Сертификат истекает через ${daysLeft} дн. — обновите ЭЦП`}
          </AlertTitle>
          <AlertDescription className="mt-1 text-sm">
            {expired
              ? 'Подписание невозможно. Обратитесь в НЦА (pki.gov.kz) для получения нового сертификата.'
              : 'Обратитесь в НЦА (pki.gov.kz) для своевременного обновления сертификата до истечения срока.'}
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}
