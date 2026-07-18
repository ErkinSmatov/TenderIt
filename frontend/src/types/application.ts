/**
 * TypeScript types for TenderIt application (заявка на тендер).
 *
 * Mirrors backend schemas/application.py ApplicationResponse.
 * ApplicationStatus values match backend state machine (D-05-04):
 *   draft → signed → waiting → submitting → submitted | error
 */

export type ApplicationStatus =
  | 'draft'
  | 'signed'
  | 'waiting'
  | 'submitting'
  | 'submitted'
  | 'error'

/**
 * A single lot offer — price entered by user for one lot in a tender.
 * unit_price * quantity = total_price (audit trail).
 */
export interface LotOffer {
  lot_id: number
  unit_price: string   // Decimal string (e.g. "100.00")
  quantity: number
  total_price: string  // Decimal string (e.g. "500.00")
}

/** Full application record returned by the backend API. */
export interface ApplicationResponse {
  id: number
  tender_id: number
  status: ApplicationStatus
  lots_data: LotOffer[]
  document_ids: number[]
  goszakup_application_id: number | null
  goszakup_tender_buy_id: number | null
  error_message: string | null
  retry_count: number
  created_at: string      // ISO datetime
  ready_at: string | null  // ISO datetime
  submitted_at: string | null  // ISO datetime
}

/** Request body for POST /api/applications. */
export interface ApplicationCreate {
  tender_id: number
  lots_data: LotOffer[]
  document_ids?: number[]
}
