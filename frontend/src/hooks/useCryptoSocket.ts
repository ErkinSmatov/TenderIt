'use client'

/**
 * useCryptoSocket — browser-only React hook for CryptoSocket (TumarCSP) WebSocket.
 *
 * CryptoSocket by НИЛ «Гамма Технологии» performs sealed-bid Gamma price encryption
 * (step 7 of the goszakup application flow, GAMMA-ENCRYPTION-FINDINGS.md).
 *
 * Architecture (CLAUDE.md Rule 1 analogue):
 *   CryptoSocket runs on the user's machine at ws://127.0.0.1:6126/tumarcsp.
 *   This hook is the SOLE interface to it. Backend NEVER connects to CryptoSocket.
 *
 * COMPLETELY DIFFERENT from NCALayer:
 *   - NCALayer: wss://127.0.0.1:13579 (GOST XML signing)
 *   - CryptoSocket: ws://127.0.0.1:6126/tumarcsp (Gamma price encryption)
 *   - DO NOT add gammaEncrypt to useNCALayer (architecture constraint).
 *
 * Protocol (GAMMA-ENCRYPTION-FINDINGS.md):
 *   Connect → send SetAPIKey → on {"result":"true"} → status='connected'
 *   encryptOfferPrice → send EFCAPI.EncryptOfferPrice → resolve on next message
 *
 * License key: NEXT_PUBLIC_CRYPTOSOCKET_API_KEY must be set in the environment.
 * This key is domain-locked and must be obtained from Gamma Technologies (gamma.kz).
 * For development on localhost/127.0.0.1 a dev key may be available.
 */

import { useState, useCallback, useRef } from 'react'
import type {
  CryptoSocketHookResult,
  CryptoSocketStatus,
  GammaEncryptParams,
  GammaEncryptResult,
} from '@/types/cryptosocket'

const CRYPTOSOCKET_URL = 'ws://127.0.0.1:6126/tumarcsp'

// API key from environment — domain-locked, obtained from Gamma Technologies
// Set NEXT_PUBLIC_CRYPTOSOCKET_API_KEY in .env.local for development
const CS_API_KEY = process.env.NEXT_PUBLIC_CRYPTOSOCKET_API_KEY ?? ''

export function useCryptoSocket(): CryptoSocketHookResult {
  const [status, setStatus] = useState<CryptoSocketStatus>('disconnected')
  const [error, setError] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)

  // ── connect ──────────────────────────────────────────────────────────────

  const connect = useCallback(() => {
    if (wsRef.current) return // already connecting or connected

    setStatus('connecting')
    const ws = new WebSocket(CRYPTOSOCKET_URL)
    wsRef.current = ws

    ws.onopen = () => {
      // Authenticate immediately on connect (GAMMA-ENCRYPTION-FINDINGS.md step 1)
      ws.send(
        JSON.stringify({
          TumarCSP: 'SYSAPI',
          Function: 'SetAPIKey',
          Param: { apiKey: CS_API_KEY },
        })
      )

      // Wait for auth response
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data as string) as Record<string, unknown>
          if (msg.result === 'true') {
            setStatus('connected')
            setError(null)
          } else {
            setStatus('error')
            const code = (msg.code as string | undefined) ?? ''
            setError(
              `CryptoSocket SetAPIKey failed (code: ${code}). ` +
              'Проверьте, что CryptoSocket (TumarCSP) запущен и ключ API действителен.'
            )
          }
        } catch {
          setStatus('error')
          setError('CryptoSocket: непредвиденный ответ при авторизации.')
        }
        // Clear auth handler — subsequent messages come via encryptOfferPrice
        ws.onmessage = null
      }
    }

    ws.onerror = () => {
      setStatus('error')
      setError(
        'Не удалось подключиться к CryptoSocket (TumarCSP). ' +
        'Убедитесь, что программа CryptoSocket запущена (порт 6126).'
      )
      wsRef.current = null
    }

    ws.onclose = () => {
      wsRef.current = null
      setStatus((prev) => (prev === 'error' ? 'error' : 'disconnected'))
    }
  }, [])

  // ── encryptOfferPrice ─────────────────────────────────────────────────────

  const encryptOfferPrice = useCallback(
    (params: GammaEncryptParams): Promise<GammaEncryptResult> => {
      return new Promise<GammaEncryptResult>((resolve, reject) => {
        const ws = wsRef.current
        if (!ws || ws.readyState !== WebSocket.OPEN) {
          reject(new Error('CryptoSocket не подключён'))
          return
        }

        setStatus('encrypting')

        ws.onmessage = (ev) => {
          setStatus('connected')
          try {
            const msg = JSON.parse(ev.data as string) as Record<string, unknown>
            if (msg.result === 'true') {
              resolve({
                encryptData: msg.encryptData as string,
                encryptKey: msg.encryptKey as string,
                sign: msg.sign as string,
                salt: msg.salt as string,
              })
            } else {
              const code = (msg.code as string | undefined) ?? ''
              const errMsg = (msg.error as string | undefined) ?? 'Ошибка шифрования цены'
              reject(new Error(`EFCAPI.EncryptOfferPrice error (${code}): ${errMsg}`))
            }
          } catch (e) {
            reject(new Error('CryptoSocket: не удалось разобрать ответ шифрования'))
          }
          ws.onmessage = null
        }

        // Send EFCAPI.EncryptOfferPrice request (GAMMA-ENCRYPTION-FINDINGS.md)
        ws.send(
          JSON.stringify({
            TumarCSP: 'EFCAPI',
            Function: 'EncryptOfferPrice',
            Param: {
              pl_sum: params.pl_sum,
              d_sum: params.d_sum,
              d_messageUp: params.d_messageUp,
              d_messageDown: params.d_messageDown,
              id_priceoffer: params.id_priceoffer,
              public_key: params.public_key,
            },
          })
        )
      })
    },
    []
  )

  // ── Return ───────────────────────────────────────────────────────────────

  return {
    status,
    error,
    connect,
    encryptOfferPrice,
  }
}
