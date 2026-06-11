'use client'

/**
 * /documents — Document Vault page.
 *
 * Flow:
 *   1. useQuery fetches GET /api/documents on mount (always enabled).
 *   2. DocumentUploadForm handles upload — invalidates ['documents'] on success.
 *   3. DocumentVault renders the list with expiry badges.
 *   4. onDownload: fetches pre-signed URL and opens in a new tab.
 *   5. onDelete: calls DELETE /api/documents/{id} and invalidates ['documents'].
 */

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { DocumentResponse } from '@/types/document'
import DocumentUploadForm from '@/components/documents/DocumentUploadForm'
import DocumentVault from '@/components/documents/DocumentVault'
import { Alert } from '@/components/ui/alert'

export default function DocumentsPage() {
  const queryClient = useQueryClient()

  const {
    data,
    error,
    isLoading,
  } = useQuery<DocumentResponse[]>({
    queryKey: ['documents'],
    queryFn: () => api.get<DocumentResponse[]>('/api/documents'),
    retry: false,
  })

  async function onDownload(id: number) {
    try {
      const { url } = await api.get<{ url: string; expires_in: number }>(
        '/api/documents/' + id + '/url',
      )
      window.open(url, '_blank')
    } catch {
      // Ignore — user will see nothing open, can retry
    }
  }

  async function onDelete(id: number) {
    try {
      await api.delete('/api/documents/' + id)
      await queryClient.invalidateQueries({ queryKey: ['documents'] })
    } catch {
      // Ignore — list will stay as-is, user can retry
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-semibold">Документы</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Хранилище документов компании — уставы, лицензии, сертификаты
        </p>
      </div>

      <DocumentUploadForm />

      {error && (
        <Alert className="text-destructive border-destructive/50 bg-destructive/10 text-sm">
          Не удалось загрузить список документов. Проверьте соединение и попробуйте ещё раз.
        </Alert>
      )}

      {!isLoading && !error && (
        <DocumentVault
          documents={data ?? []}
          onDownload={onDownload}
          onDelete={onDelete}
        />
      )}
    </div>
  )
}
