'use client'

/**
 * InstallGuide — SIGN-05
 *
 * Shown when NCALayer is unreachable (status === 'disconnected' | 'error').
 * Guides the user to download and launch NCALayer before signing.
 */

import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'

/** Official NCALayer download page (pki.gov.kz). */
const NCALAYER_DOWNLOAD_URL = 'https://pki.gov.kz/ncalayer/'

export default function InstallGuide() {
  return (
    <Alert className="border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
      <AlertTitle className="text-sm font-semibold">NCALayer не найден</AlertTitle>
      <AlertDescription className="mt-1 space-y-2 text-sm">
        <p>
          Для подписания документов ЭЦП необходима программа{' '}
          <strong>NCALayer</strong>, установленная на вашем компьютере.
        </p>
        <ol className="list-decimal list-inside space-y-1">
          <li>
            Скачайте NCALayer с официального сайта:{' '}
            <a
              href={NCALAYER_DOWNLOAD_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-2 hover:opacity-80"
            >
              pki.gov.kz/ncalayer
            </a>
          </li>
          <li>Установите и запустите NCALayer.</li>
          <li>
            Откройте в браузере{' '}
            <a
              href="https://127.0.0.1:13579"
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-2 hover:opacity-80"
            >
              https://127.0.0.1:13579
            </a>{' '}
            и доверьте самоподписанный сертификат NCALayer.
          </li>
          <li>Вернитесь на эту страницу и нажмите «Подключить».</li>
        </ol>
      </AlertDescription>
    </Alert>
  )
}
