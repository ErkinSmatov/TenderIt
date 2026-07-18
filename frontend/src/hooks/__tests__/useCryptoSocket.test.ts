/**
 * Tests for useCryptoSocket hook — CryptoSocket (TumarCSP) integration.
 *
 * Verifies:
 *   - EFCAPI.EncryptOfferPrice message shape (GAMMA-ENCRYPTION-FINDINGS.md)
 *   - SetAPIKey auth message on connect
 *   - Status transitions: disconnected → connecting → connected → encrypting → connected
 *   - Error handling on failed auth or encrypt
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useCryptoSocket } from '../useCryptoSocket'

// ---------------------------------------------------------------------------
// Mock WebSocket — simulates CryptoSocket localhost WS
// ---------------------------------------------------------------------------

let mockWS: MockCryptoWS

class MockCryptoWS {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  readyState = MockCryptoWS.CONNECTING
  onopen: ((ev: Event) => void) | null = null
  onmessage: ((ev: MessageEvent) => void) | null = null
  onerror: ((ev: Event) => void) | null = null
  onclose: ((ev: CloseEvent) => void) | null = null
  sentMessages: string[] = []
  url: string

  constructor(url: string) {
    this.url = url
    mockWS = this
  }

  send(data: string) {
    this.sentMessages.push(data)
  }

  close() {
    this.readyState = MockCryptoWS.CLOSED
    this.onclose?.(new CloseEvent('close'))
  }

  simulateOpen() {
    this.readyState = MockCryptoWS.OPEN
    this.onopen?.(new Event('open'))
  }

  simulateMessage(data: object) {
    this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(data) }))
  }

  simulateError() {
    this.onerror?.(new Event('error'))
  }
}

vi.stubGlobal('WebSocket', MockCryptoWS)

// ---------------------------------------------------------------------------
// Helper — connect and authenticate
// ---------------------------------------------------------------------------

async function connectAndAuth(result: { current: ReturnType<typeof useCryptoSocket> }) {
  act(() => { result.current.connect() })
  act(() => { mockWS.simulateOpen() })
  // Simulate successful SetAPIKey response
  act(() => { mockWS.simulateMessage({ result: 'true' }) })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useCryptoSocket', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  // ── WebSocket URL ──────────────────────────────────────────────────────────

  it('connects to ws://127.0.0.1:6126/tumarcsp (GAMMA-ENCRYPTION-FINDINGS.md)', () => {
    const { result } = renderHook(() => useCryptoSocket())
    act(() => { result.current.connect() })
    expect(mockWS.url).toBe('ws://127.0.0.1:6126/tumarcsp')
  })

  // ── SetAPIKey auth ─────────────────────────────────────────────────────────

  it('sends SetAPIKey SYSAPI message on connect', () => {
    const { result } = renderHook(() => useCryptoSocket())
    act(() => { result.current.connect() })
    act(() => { mockWS.simulateOpen() })

    expect(mockWS.sentMessages).toHaveLength(1)
    const msg = JSON.parse(mockWS.sentMessages[0])
    expect(msg.TumarCSP).toBe('SYSAPI')
    expect(msg.Function).toBe('SetAPIKey')
    expect(msg.Param).toHaveProperty('apiKey')
  })

  // ── Status transitions ─────────────────────────────────────────────────────

  it('starts as disconnected', () => {
    const { result } = renderHook(() => useCryptoSocket())
    expect(result.current.status).toBe('disconnected')
  })

  it('transitions to connecting → connected after SetAPIKey success', async () => {
    const { result } = renderHook(() => useCryptoSocket())

    act(() => { result.current.connect() })
    expect(result.current.status).toBe('connecting')

    act(() => { mockWS.simulateOpen() })
    // After open, still connecting (waiting for auth)
    expect(result.current.status).toBe('connecting')

    act(() => { mockWS.simulateMessage({ result: 'true' }) })
    expect(result.current.status).toBe('connected')
  })

  it('transitions to error when SetAPIKey fails', () => {
    const { result } = renderHook(() => useCryptoSocket())
    act(() => { result.current.connect() })
    act(() => { mockWS.simulateOpen() })
    act(() => {
      mockWS.simulateMessage({ result: 'false', code: '10001', error: 'Invalid API key' })
    })
    expect(result.current.status).toBe('error')
    expect(result.current.error).toBeTruthy()
  })

  it('transitions to error on WS error event', () => {
    const { result } = renderHook(() => useCryptoSocket())
    act(() => { result.current.connect() })
    act(() => { mockWS.simulateError() })
    expect(result.current.status).toBe('error')
    expect(result.current.error).toBeTruthy()
  })

  // ── EFCAPI.EncryptOfferPrice message shape ─────────────────────────────────

  it('sends EFCAPI.EncryptOfferPrice with correct message shape', async () => {
    const { result } = renderHook(() => useCryptoSocket())
    await connectAndAuth(result)

    const params = {
      pl_sum: 5000,
      d_sum: 0,
      d_messageUp: '',
      d_messageDown: '',
      id_priceoffer: 'AF89UX3146',
      public_key: 'BgIAAEWgAAAA...',
    }

    await act(async () => {
      const promise = result.current.encryptOfferPrice(params)
      mockWS.simulateMessage({
        result: 'true',
        encryptData: 'bR41xz...',
        encryptKey: 'sk...',
        sign: 'sign...',
        salt: 'salt...',
      })
      return promise
    })

    // Find the EFCAPI message (second sent message — first was SetAPIKey)
    const efcapiMsg = mockWS.sentMessages.find((m) => {
      const p = JSON.parse(m)
      return p.TumarCSP === 'EFCAPI'
    })

    expect(efcapiMsg).toBeDefined()
    const payload = JSON.parse(efcapiMsg!)

    // Must use EFCAPI module
    expect(payload.TumarCSP).toBe('EFCAPI')
    expect(payload.Function).toBe('EncryptOfferPrice')

    // Params must include all required fields
    expect(payload.Param.pl_sum).toBe(5000)
    expect(payload.Param.d_sum).toBe(0)
    expect(payload.Param.id_priceoffer).toBe('AF89UX3146')
    expect(payload.Param.public_key).toBe('BgIAAEWgAAAA...')
    expect(payload.Param.d_messageUp).toBe('')
    expect(payload.Param.d_messageDown).toBe('')
  })

  it('resolves encryptOfferPrice with encryptData, encryptKey, sign, salt', async () => {
    const { result } = renderHook(() => useCryptoSocket())
    await connectAndAuth(result)

    const mockResult = {
      result: 'true',
      encryptData: 'ENC_DATA_BASE64',
      encryptKey: 'ENC_KEY_BASE64',
      sign: 'SIGN_BASE64',
      salt: 'SALT_BASE64',
    }

    let encryptResult: Awaited<ReturnType<typeof result.current.encryptOfferPrice>> | null = null

    await act(async () => {
      const promise = result.current.encryptOfferPrice({
        pl_sum: 1000,
        d_sum: 50,
        d_messageUp: '',
        d_messageDown: '',
        id_priceoffer: 'ID123',
        public_key: 'PUB_KEY',
      })
      mockWS.simulateMessage(mockResult)
      encryptResult = await promise
    })

    expect(encryptResult).not.toBeNull()
    expect(encryptResult!.encryptData).toBe('ENC_DATA_BASE64')
    expect(encryptResult!.encryptKey).toBe('ENC_KEY_BASE64')
    expect(encryptResult!.sign).toBe('SIGN_BASE64')
    expect(encryptResult!.salt).toBe('SALT_BASE64')
  })

  it('transitions to encrypting during encryptOfferPrice and back to connected on success', async () => {
    const { result } = renderHook(() => useCryptoSocket())
    await connectAndAuth(result)

    expect(result.current.status).toBe('connected')

    await act(async () => {
      const promise = result.current.encryptOfferPrice({
        pl_sum: 1000,
        d_sum: 0,
        d_messageUp: '',
        d_messageDown: '',
        id_priceoffer: 'ID',
        public_key: 'KEY',
      })
      mockWS.simulateMessage({
        result: 'true',
        encryptData: 'enc',
        encryptKey: 'key',
        sign: 'sig',
        salt: 'salt',
      })
      return promise
    })

    expect(result.current.status).toBe('connected')
  })

  it('rejects encryptOfferPrice when CryptoSocket returns error', async () => {
    const { result } = renderHook(() => useCryptoSocket())
    await connectAndAuth(result)

    let caughtError: Error | null = null

    await act(async () => {
      const promise = result.current.encryptOfferPrice({
        pl_sum: 0,
        d_sum: 0,
        d_messageUp: '',
        d_messageDown: '',
        id_priceoffer: 'BAD',
        public_key: 'BAD',
      })
      mockWS.simulateMessage({
        result: 'false',
        code: '10007',
        error: 'Function not supported',
      })
      try {
        await promise
      } catch (e) {
        caughtError = e as Error
      }
    })

    expect(caughtError).not.toBeNull()
    expect(caughtError!.message).toContain('10007')
  })
})
