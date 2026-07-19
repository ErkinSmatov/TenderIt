/**
 * ApplicationCard — card component for a single application in the history list.
 *
 * Shows: tender_id (linked to /applications/{id}), status badge, created_at (ru-RU).
 * When status === 'error': surfaces error_message in a destructive Alert (APPL-06).
 */

import Link from 'next/link'
import type { ApplicationResponse } from '@/types/application'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import ApplicationStatusBadge from '@/components/applications/ApplicationStatusBadge'

function formatDate(iso: string): string {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

interface ApplicationCardProps {
  application: ApplicationResponse
}

export default function ApplicationCard({ application }: ApplicationCardProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base leading-snug">
            <Link
              href={`/applications/${application.id}`}
              className="hover:underline text-foreground"
            >
              Тендер #{application.tender_id}
            </Link>
          </CardTitle>
          <ApplicationStatusBadge status={application.status} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-col gap-0.5">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Создана
          </span>
          <span className="text-sm text-foreground">
            {formatDate(application.created_at)}
          </span>
        </div>

        {application.status === 'error' && application.error_message && (
          <Alert variant="destructive">
            <AlertTitle>Ошибка при отправке</AlertTitle>
            <AlertDescription>{application.error_message}</AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  )
}
