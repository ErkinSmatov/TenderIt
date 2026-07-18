'use client'

/**
 * DocumentSelect — Step 3 of ApplicationWizard.
 *
 * Multi-select list of non-expired documents from GET /api/documents/attachable.
 * Phase-4 endpoint returns only documents that have not expired.
 */

import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { DocumentResponse } from '@/types/document'
import { CATEGORY_LABELS } from '@/types/document'
import { Alert } from '@/components/ui/alert'

interface DocumentSelectProps {
  value: number[]
  onChange: (ids: number[]) => void
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function DocumentSelect({ value, onChange }: DocumentSelectProps) {
  const { data: documents, error, isLoading } = useQuery<DocumentResponse[]>({
    queryKey: ['documents', 'attachable'],
    queryFn: () => api.get<DocumentResponse[]>('/api/documents/attachable'),
    retry: false,
  })

  function toggle(id: number) {
    if (value.includes(id)) {
      onChange(value.filter((v) => v !== id))
    } else {
      onChange([...value, id])
    }
  }

  if (isLoading) {
    return (
      <p className="text-sm text-muted-foreground animate-pulse">
        Загрузка документов...
      </p>
    )
  }

  if (error) {
    return (
      <Alert className="text-destructive border-destructive/50 bg-destructive/10 text-sm">
        Не удалось загрузить документы. Проверьте соединение и попробуйте ещё раз.
      </Alert>
    )
  }

  const docs = documents ?? []

  if (docs.length === 0) {
    return (
      <Alert className="text-muted-foreground border-border bg-card text-sm">
        Нет доступных документов. Загрузите документы в{' '}
        <a href="/documents" className="underline hover:text-foreground">
          хранилище документов
        </a>{' '}
        перед созданием заявки.
      </Alert>
    )
  }

  return (
    <div className="space-y-2">
      {docs.map((doc) => {
        const selected = value.includes(doc.id)
        return (
          <label
            key={doc.id}
            className={
              'flex items-start gap-3 rounded-lg border px-4 py-3 cursor-pointer transition-colors ' +
              (selected
                ? 'border-primary bg-primary/5'
                : 'border-border bg-card hover:bg-muted/50')
            }
          >
            <input
              type="checkbox"
              checked={selected}
              onChange={() => toggle(doc.id)}
              className="mt-0.5 accent-primary"
              aria-label={doc.file_name}
            />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{doc.file_name}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {CATEGORY_LABELS[doc.category]} · {formatSize(doc.file_size)}
                {doc.expires_at && (
                  <> · действует до {new Date(doc.expires_at).toLocaleDateString('ru-RU')}</>
                )}
              </p>
            </div>
          </label>
        )
      })}

      {value.length > 0 && (
        <p className="text-xs text-muted-foreground pt-1">
          Выбрано: {value.length} {value.length === 1 ? 'документ' : 'документа'}
        </p>
      )}
    </div>
  )
}
