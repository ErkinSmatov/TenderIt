/**
 * TypeScript types for CryptoSocket (TumarCSP) WebSocket integration.
 *
 * CryptoSocket by НИЛ «Гамма Технологии» (TUMAR-CSP)
 * WebSocket URL: ws://127.0.0.1:6126/tumarcsp
 *
 * Protocol (GAMMA-ENCRYPTION-FINDINGS.md):
 *   Step 1 — Auth on connect:
 *     { TumarCSP: "SYSAPI", Function: "SetAPIKey", Param: { apiKey: "<license-key-base64>" } }
 *     Response: { result: "true" }
 *
 *   Step 7 — Encrypt price (EFCAPI.EncryptOfferPrice):
 *     Request:  { TumarCSP: "EFCAPI", Function: "EncryptOfferPrice", Param: GammaEncryptParams }
 *     Response: GammaEncryptResult
 *
 * NOTE: CryptoSocket is completely separate from NCALayer.
 *   - NCALayer: wss://127.0.0.1:13579 (GOST XML signing, steps 1-login + step 9)
 *   - CryptoSocket: ws://127.0.0.1:6126/tumarcsp (Gamma price encryption, step 7)
 */

/** Connection and operation lifecycle states for the useCryptoSocket hook. */
export type CryptoSocketStatus =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'encrypting'
  | 'error'

/**
 * Parameters for EFCAPI.EncryptOfferPrice (step 7).
 *
 * Obtained from the portal's ajax_get_encr_info response (step 6)
 * and user-entered price data.
 *
 * pl_sum: integer part of the price (tenge)
 * d_sum: decimal part of the price (kopeck)
 * d_messageUp: upper bound message (typically empty string for standard bids)
 * d_messageDown: lower bound message (typically empty string for standard bids)
 * id_priceoffer: lot price-offer ID from portal step 6 response
 * public_key: base64 public key from portal step 6 response
 */
export interface GammaEncryptParams {
  pl_sum: number
  d_sum: number
  d_messageUp: string
  d_messageDown: string
  id_priceoffer: string
  public_key: string
}

/**
 * Response from EFCAPI.EncryptOfferPrice (step 7).
 *
 * Field mapping to portal POST ajax_add_encrypt (step 8):
 *   encryptData  → encryptedData  (portal field)
 *   encryptKey   → sessionKey     (portal field)
 *   salt         → salt           (portal field)
 *   sign         → sign           (portal field)
 */
export interface GammaEncryptResult {
  encryptData: string
  encryptKey: string
  sign: string
  salt: string
}

/** Shape returned by useCryptoSocket() hook. */
export interface CryptoSocketHookResult {
  /** Current connection/operation status. */
  status: CryptoSocketStatus
  /** Human-readable error description, set on status==='error'. */
  error: string | null
  /** Open the WebSocket connection and authenticate with the API key. */
  connect: () => void
  /**
   * Encrypt offer price via EFCAPI.EncryptOfferPrice.
   * Requires status === 'connected'. Transitions to 'encrypting' during the call.
   *
   * @throws Error if not connected or CryptoSocket returns error result.
   */
  encryptOfferPrice: (params: GammaEncryptParams) => Promise<GammaEncryptResult>
}
