/**
 * TypeScript types for NCALayer WebSocket integration.
 *
 * Dual-mode dispatch (SPIKE-02, confirmed 2026-05-28):
 *  - NCALayer 1.x (macOS): kz.gov.pki.knca.commonUtils + array args + raw XML → responseObject
 *  - NCALayer 2.x (Windows): kz.gov.pki.knca.basics + object args + base64 XML → result
 *
 * Private keys NEVER leave the device. useNCALayer() is browser-only — backend never calls NCALayer.
 */

/** A signing certificate returned by NCALayer getKeyInfo (keyType === 'SIGNATURE' only). */
export interface Certificate {
  serialNumber: string
  subjectCommonName: string
  issuerCommonName: string
  notBefore: Date
  notAfter: Date
}

/**
 * Connection and operation lifecycle states for the useNCALayer hook.
 *
 * disconnected → connect() → connecting → (version broadcast) → connected
 *             → signXml / createCMSSignatureFromBase64 → signing → connected
 *             → onerror / onclose → error
 */
export type NCALayerStatus =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'signing'
  | 'error'

/** Shape returned by useNCALayer() hook. */
export interface NCALayerHookResult {
  /** Current connection/operation status. */
  status: NCALayerStatus
  /** Detected NCALayer version string (e.g. "1.4", "2.1") or null before connect. */
  version: string | null
  /** SIGNATURE certificates available for signing (AUTH certs excluded). */
  certificates: Certificate[]
  /** Human-readable error description, set on status==='error'. */
  error: string | null
  /** Open the WebSocket connection. No-op if already connected. */
  connect: () => void
  /** Fetch SIGNATURE certificates from NCALayer. Updates the certificates state. */
  getCertificates: () => Promise<Certificate[]>
  /**
   * Sign an XML document via NCALayer dual-mode dispatch.
   *
   * 1.x: sends raw XML string (NOT base64) to commonUtils.signXml → returns responseObject (plain XMLDSig).
   * 2.x: sends base64-encoded XML to basics.sign → returns decoded result.
   *
   * IMPORTANT (SPIKE-02 pitfall): NCALayer 1.x feeds arg[2] directly to Java SAX parser.
   * Passing base64 causes SAXParseException. Always pass raw XML for 1.x.
   */
  signXml: (xml: string) => Promise<string>
  /**
   * Create a CMS/PKCS#7 signature from a base64-encoded data blob.
   * Used for goszakup Gamma price encryption step (step 9 in application flow).
   */
  createCMSSignatureFromBase64: (base64Data: string) => Promise<string>
}
