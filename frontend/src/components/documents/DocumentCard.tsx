/**
 * DocumentCard — card component for a single document in the Document Vault.
 *
 * Shows: file_name, category (Russian label), upload date, expiry date,
 * ExpiryBadge (warning/expired states), Download and Delete buttons.
 */

import type { ReactNode } from 'react'
import type { DocumentResponse, ExpiryStatus } from '@/types/document'
import { CATEGORY_LABELS } from '@/types/document'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Download, Trash2 } from 'lucide-react'

function formatDate(isoOrRaw: string | null): string {
  if (!isoOrRaw) return '—'
  const d = new Date(isoOrRaw)
  if (isNaN(d.getTime())) return '—'
  const day = String(d.getDate()).padStart(2, '0')
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const year = d.getFullYear()
  return `${day}.${month}.${year}`
}

interface Field {
  label: string
  value: ReactNode
}

function LabelValue({ label, value }: Field) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
        {label}
      </span>
      <span className="text-sm text-foreground">{value}</span>
    </div>
  )
}

function ExpiryBadge({ status }: { status: ExpiryStatus }) {
  if (status === 'ok') return null
  const config = {
    warning_14: { variant: 'secondary' as const, label: 'Истекает через 14 дней' },
    warning_7: { variant: 'outline' as const, label: 'Истекает через 7 дней' },
    expired: { variant: 'destructive' as const, label: 'Истёк' },
  }
  const { variant, label } = config[status]
  return <Badge variant={variant}>{label}</Badge>
}

interface DocumentCardProps {
  document: DocumentResponse
  onDownload: (id: number) => void
  onDelete: (id: number) => void
}

export default function DocumentCard({ document, onDownload, onDelete }: DocumentCardProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base leading-snug break-all">
            {document.file_name}
          </CardTitle>
          <ExpiryBadge status={document.expiry_status} />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <LabelValue
            label="Категория"
            value={CATEGORY_LABELS[document.category]}
          />
          <LabelValue
            label="Загружен"
            value={formatDate(document.uploaded_at)}
          />
          <LabelValue
            label="Срок действия"
            value={document.expires_at ? formatDate(document.expires_at) : 'Не указан'}
          />
        </div>

        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onDownload(document.id)}
          >
            <Download className="h-4 w-4 mr-1.5" aria-hidden="true" />
            Скачать
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="text-destructive hover:text-destructive hover:bg-destructive/10"
            onClick={() => onDelete(document.id)}
          >
            <Trash2 className="h-4 w-4 mr-1.5" aria-hidden="true" />
            Удалить
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
