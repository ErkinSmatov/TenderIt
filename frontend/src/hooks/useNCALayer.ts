'use client'

/**
 * useNCALayer — browser-only React hook for NCALayer WebSocket integration.
 *
 * Architecture (CLAUDE.md Rule 1): NCALayer runs on the user's machine.
 * This hook is the SOLE interface to it. Backend NEVER connects to NCALayer.
 *
 * Dual-mode dispatch (SPIKE-02, confirmed 2026-05-28):
 *  - Version < 2 (macOS, NCALayer 1.x):
 *      module: kz.gov.pki.knca.commonUtils
 *      args:   positional array
 *      xmlToSign: RAW XML STRING (never base64 — Java SAX parser feeds on arg[2] directly)
 *      signed result: response.responseObject  ← plain XMLDSig string
 *
 *  - Version >= 2 (Windows, NCALayer 2.x):
 *      module: kz.gov.pki.knca.basics
 *      args:   named object
 *      xmlToSign: base64(utf8(xml))
 *      signed result: atob(response.result)
 *
 * URL: wss://127.0.0.1:13579 (confirmed port, SPIKE-02-FINDINGS.md D-S02-01)
 */

import { useState, useCallback, useRef } from 'react'
import type { Certificate, NCALayerHookResult, NCALayerStatus } from '@/types/ncalayer'

const NCALAYER_URL = 'wss://127.0.0.1:13579'

// ---------------------------------------------------------------------------
// Exported helper
// ---------------------------------------------------------------------------

/**
 * Returns true when the certificate expires within `days` days from now.
 * Used by CertificateInfo (SIGN-03) to render the < 30-day expiry warning.
 */
export function certExpiresWithinDays(cert: Certificate, days: number): boolean {
  const threshold = Date.now() + days * 24 * 60 * 60 * 1000
  return cert.notAfter.getTime() < threshold
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/** Parse CN from a Distinguished Name string like "CN=Иванов Иван,OU=...,O=...,C=KZ". */
function parseCN(dn: string): string {
  const match = dn.match(/CN=([^,]+)/)
  return match ? match[1].trim() : dn
}

/** Encode XML to base64 as required by NCALayer 2.x (basics module). */
function xmlToBase64(xml: string): string {
  // unescape(encodeURIComponent(s)) converts UTF-8 string to Latin-1-compatible bytes
  // so that btoa() can handle non-ASCII characters correctly.
  return btoa(unescape(encodeURIComponent(xml)))
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useNCALayer(): NCALayerHookResult {
  const [status, setStatus] = useState<NCALayerStatus>('disconnected')
  const [version, setVersion] = useState<string | null>(null)
  const [certificates, setCertificates] = useState<Certificate[]>([])
  const [error, setError] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  // versionRef allows signXml / getCertificates to read version without stale closure.
  const versionRef = useRef<string | null>(null)

  // ── connect ──────────────────────────────────────────────────────────────

  const connect = useCallback(() => {
    if (wsRef.current) return // already connected or connecting

    const ws = new WebSocket(NCALAYER_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setStatus('connecting')

      // NCALayer broadcasts version automatically on connect BEFORE any request.
      // Set up a one-shot handler to capture it.
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data as string) as Record<string, unknown>
          const result = msg.result as Record<string, unknown> | undefined
          if (result?.version && typeof result.version === 'string') {
            versionRef.current = result.version
            setVersion(result.version)
            setStatus('connected')
          }
        } catch {
          // ignore unparseable broadcast
        }
        // Clear handler; subsequent messages come via sendRequest()
        ws.onmessage = null
      }
    }

    ws.onerror = () => {
      setStatus('error')
      setError(
        'Не удалось подключиться к NCALayer. ' +
        'Убедитесь, что NCALayer запущен и его сертификат доверен в браузере.',
      )
      wsRef.current = null
    }

    ws.onclose = () => {
      // Only reset to disconnected if it wasn't an error (onerror fires before onclose).
      wsRef.current = null
      setStatus((prev) => (prev === 'error' ? 'error' : 'disconnected'))
    }
  }, [])

  // ── sendRequest ──────────────────────────────────────────────────────────

  /**
   * Send one JSON request to NCALayer and await the next message as the response.
   * NCALayer handles one request at a time — concurrent calls are not safe.
   */
  const sendRequest = useCallback(<T>(req: object): Promise<T> => {
    return new Promise<T>((resolve, reject) => {
      const ws = wsRef.current
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        reject(new Error('NCALayer не подключён'))
        return
      }
      ws.onmessage = (ev) => {
        try {
          resolve(JSON.parse(ev.data as string) as T)
        } catch (e) {
          reject(e)
        }
      }
      ws.send(JSON.stringify(req))
    })
  }, [])

  // ── isLegacy helper ──────────────────────────────────────────────────────

  /** True when connected NCALayer version is < 2 (macOS 1.x). */
  const getIsLegacy = useCallback((): boolean => {
    const v = versionRef.current
    return v === null || parseInt(v) < 2
  }, [])

  // ── getCertificates ──────────────────────────────────────────────────────

  const getCertificates = useCallback(async (): Promise<Certificate[]> => {
    const isLegacy = getIsLegacy()
    let resp: Record<string, unknown>

    if (isLegacy) {
      resp = await sendRequest<Record<string, unknown>>({
        module: 'kz.gov.pki.knca.commonUtils',
        method: 'getKeyInfo',
        args: ['PKCS12'],
      })
    } else {
      resp = await sendRequest<Record<string, unknown>>({
        module: 'kz.gov.pki.knca.basics',
        method: 'getKeyInfo',
        args: { tokenType: 'PKCS12' },
      })
    }

    // 1.x returns list in responseObject; 2.x in result
    const raw = (isLegacy
      ? (resp.responseObject as Record<string, unknown>[])
      : (resp.result as Record<string, unknown>[])) ?? []

    // Filter: only SIGNATURE certs (exclude AUTH — goszakup rejects AUTH-signed docs, SPIKE-02 D-S02-03)
    const certs: Certificate[] = raw
      .filter((c) => {
        const kt = String((c.keyType as string | undefined) ?? '')
        return kt === 'SIGNATURE' || kt === 'GOST_SIGNATURE'
      })
      .map((c) => ({
        serialNumber: String(c.serialNumber ?? c.certSN ?? ''),
        subjectCommonName: parseCN(
          String(c.subjectDn ?? c.subject ?? c.subjectCommonName ?? ''),
        ),
        issuerCommonName: parseCN(
          String(c.issuerDn ?? c.issuer ?? c.issuerCommonName ?? ''),
        ),
        notBefore: new Date(String(c.notBefore ?? '')),
        notAfter: new Date(String(c.notAfter ?? '')),
      }))

    setCertificates(certs)
    return certs
  }, [sendRequest, getIsLegacy])

  // ── signXml ──────────────────────────────────────────────────────────────

  const signXml = useCallback(
    async (xml: string): Promise<string> => {
      setStatus('signing')
      try {
        const isLegacy = getIsLegacy()

        if (isLegacy) {
          // CRITICAL (SPIKE-02 pitfall): arg[2] must be RAW XML string — never base64!
          // NCALayer 1.x feeds this directly to Java SAX parser.
          const resp = await sendRequest<Record<string, unknown>>({
            module: 'kz.gov.pki.knca.commonUtils',
            method: 'signXml',
            args: ['PKCS12', 'SIGNATURE', xml, '', ''],
          })
          return String(resp.responseObject) // plain XMLDSig string
        } else {
          // 2.x: base64-encode the XML before sending
          const resp = await sendRequest<Record<string, unknown>>({
            module: 'kz.gov.pki.knca.basics',
            method: 'sign',
            args: {
              tokenType: 'PKCS12',
              keyType: 'SIGNATURE',
              xmlToSign: xmlToBase64(xml),
            },
          })
          return atob(String(resp.result)) // decode base64 response
        }
      } finally {
        setStatus('connected')
      }
    },
    [sendRequest, getIsLegacy],
  )

  // ── createCMSSignatureFromBase64 ─────────────────────────────────────────

  /**
   * CMS/PKCS#7 signature from base64-encoded data.
   * Used for goszakup Gamma price encryption (step 9) and auth login signing.
   *
   * 1.x: commonUtils.createCMSSignatureFromBase64 (confirmed available, SPIKE-02 pre-population)
   * 2.x: basics.sign with format:"cms" (unconfirmed — best-effort from module convention)
   */
  const createCMSSignatureFromBase64 = useCallback(
    async (base64Data: string): Promise<string> => {
      setStatus('signing')
      try {
        const isLegacy = getIsLegacy()

        if (isLegacy) {
          const resp = await sendRequest<Record<string, unknown>>({
            module: 'kz.gov.pki.knca.commonUtils',
            method: 'createCMSSignatureFromBase64',
            args: ['PKCS12', 'SIGNATURE', base64Data, false],
          })
          return String(resp.responseObject) // PKCS#7 CMS blob
        } else {
          const resp = await sendRequest<Record<string, unknown>>({
            module: 'kz.gov.pki.knca.basics',
            method: 'sign',
            args: {
              tokenType: 'PKCS12',
              keyType: 'SIGNATURE',
              data: base64Data,
              format: 'cms',
            },
          })
          return String(resp.result)
        }
      } finally {
        setStatus('connected')
      }
    },
    [sendRequest, getIsLegacy],
  )

  // ── Return ───────────────────────────────────────────────────────────────

  return {
    status,
    version,
    certificates,
    error,
    connect,
    getCertificates,
    signXml,
    createCMSSignatureFromBase64,
  }
}
