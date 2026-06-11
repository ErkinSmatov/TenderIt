/**
 * DocumentVault — container that renders the document list.
 *
 * Shows a summary Alert if any documents have expiry_status !== 'ok'.
 * Renders DocumentCard for each document, forwarding onDownload/onDelete.
 */

import type { DocumentResponse } from '@/types/document'
import DocumentCard from './DocumentCard'
import { Alert } from '@/components/ui/alert'

interface DocumentVaultProps {
  documents: DocumentResponse[]
  onDownload: (id: number) => void
  onDelete: (id: number) => void
}

export default function DocumentVault({ documents, onDownload, onDelete }: DocumentVaultProps) {
  const expiringCount = documents.filter((d) => d.expiry_status !== 'ok').length

  if (documents.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Нет загруженных документов. Загрузите первый документ выше.
      </p>
    )
  }

  return (
    <div className="space-y-4">
      {expiringCount > 0 && (
        <Alert className="text-sm border-orange-500/50 bg-orange-500/10 text-orange-700 dark:text-orange-400">
          {expiringCount}{' '}
          {expiringCount === 1 ? 'документ требует' : 'документ(а) требуют'} внимания — проверьте
          сроки действия
        </Alert>
      )}

      <div className="space-y-3">
        {documents.map((doc) => (
          <DocumentCard
            key={doc.id}
            document={doc}
            onDownload={onDownload}
            onDelete={onDelete}
          />
        ))}
      </div>
    </div>
  )
}
