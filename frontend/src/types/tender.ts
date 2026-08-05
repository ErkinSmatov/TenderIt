/**
 * TypeScript types for the TenderIt tender-lookup feature.
 *
 * Key casing notes:
 * - Tender fields use snake_case (Pydantic default serialization from backend).
 * - lots_data items use camelCase (raw goszakup GraphQL response stored as JSONB).
 *   SPIKE-01 confirmed: lotNumber, nameRu, nameKz, descriptionRu, amount.
 */

/** A single lot from the goszakup TrdBuy response (camelCase — raw JSONB). */
export interface Lot {
  id?: number
  lotNumber?: string | null
  nameRu?: string | null
  nameKz?: string | null
  descriptionRu?: string | null
  /** count = количество единиц (quantity to supply). Confirmed 2026-07-23 via introspection. */
  count?: number | null
  /** amount = запланированная сумма (total budget). NOT quantity — do not use for price calc. */
  amount?: number | null
  refLotStatusId?: number | null
}

/** TenderResponse from GET /api/tenders/{number_anno} (snake_case). */
export interface Tender {
  number_anno: string
  name_ru: string | null
  name_kz: string | null
  total_sum: number | null
  customer_name_ru: string | null
  customer_name_kz: string | null
  /** refBuyStatusId: 220 = "Опубликовано (прием заявок)" (SPIKE-01) */
  status_id: number | null
  status_name_ru: string | null
  start_date: string | null
  end_date: string | null
  publish_date: string | null
  lots_data: Lot[] | null
  cached_at: string
}

/** WatchlistEntryResponse from POST /api/watchlist and GET /api/watchlist. */
export interface WatchlistEntry {
  tender: Tender
  notification_on: boolean
  added_at: string
}
