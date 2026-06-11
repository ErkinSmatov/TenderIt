/**
 * TypeScript types for the TenderIt Document Vault feature.
 *
 * DocumentResponse mirrors backend schemas/document.py.
 * expiry_status is computed in the service layer, not in the ORM.
 */

export type DocumentCategory =
  | 'ustav'
  | 'license'
  | 'certificate'
  | 'registration'
  | 'other'

export type ExpiryStatus = 'ok' | 'warning_14' | 'warning_7' | 'expired'

export interface DocumentResponse {
  id: number
  file_name: string
  // file_key removed — internal MinIO storage path, not exposed by backend (CR-04)
  file_size: number
  mime_type: string
  category: DocumentCategory
  expires_at: string | null
  uploaded_at: string
  expiry_status: ExpiryStatus
}

export const CATEGORY_LABELS: Record<DocumentCategory, string> = {
  ustav: 'Устав',
  license: 'Лицензия',
  certificate: 'Сертификат',
  registration: 'Свидетельство о регистрации',
  other: 'Прочее',
}
