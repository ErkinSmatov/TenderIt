/**
 * TypeScript types for TenderIt discovery & matching (Phase 7).
 *
 * TenderMatchStatus mirrors backend models/tender_match.py TenderMatchStatus enum:
 *   matched → notified → (skipped | participating)
 */

export type TenderMatchStatus = 'matched' | 'notified' | 'skipped' | 'participating'

/**
 * A discovery match record returned by GET /api/discovery/matches.
 * Contains denormalized tender fields from a JOIN in the discovery router.
 * source and portal_url are populated from the Tender JOIN (Phase 8).
 */
export interface TenderMatchResponse {
  id: number
  user_id: number
  tender_id: number
  status: TenderMatchStatus
  notified_at: string | null    // ISO datetime
  decided_at: string | null     // ISO datetime
  created_at: string            // ISO datetime
  // Denormalized tender fields (from JOIN in discovery router)
  tender_name_ru: string | null
  customer_name_ru: string | null
  total_sum: string | null      // Decimal as string (e.g. "1500000.00")
  end_date: string | null       // ISO datetime (= submission deadline)
  region: string | null
  source: string | null         // 'goszakup' | 'sk_kz' — null for records created before Phase 8
  portal_url: string | null     // direct link to tender on source portal; null for goszakup
}

/**
 * Paginated response for GET /api/discovery/matches.
 */
export interface TenderMatchListResponse {
  items: TenderMatchResponse[]
  total: number
  page: number
  page_size: number
}

/**
 * Filter settings for a single user. One active set per user (D-10).
 * Returned by GET /api/discovery/filters and PUT /api/discovery/filters.
 */
export interface ClientFilterResponse {
  id: number
  user_id: number
  keywords: string[]
  spgz_codes: string[]
  region: string | null
  min_amount: string | null    // Decimal as string
  max_amount: string | null    // Decimal as string
  created_at: string
  updated_at: string
}
