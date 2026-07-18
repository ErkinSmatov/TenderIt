'use client'

/**
 * /applications/new — New tender application page.
 *
 * Mounts ApplicationWizard which drives the 4-step flow:
 * select tender → lot prices → documents → sign with NCALayer + CryptoSocket.
 *
 * On success the wizard redirects to /applications.
 * Error surfacing is handled inside the wizard (APPL-06).
 */

import ApplicationWizard from '@/components/applications/ApplicationWizard'

export default function NewApplicationPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Новая заявка</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Подготовьте и подпишите заявку на тендер заранее
        </p>
      </div>

      <ApplicationWizard />
    </div>
  )
}
