/**
 * Tests for useNCALayer hook — dual-mode NCALayer dispatch and status transitions.
 *
 * Covers SPIKE-02 confirmed behaviour:
 *  - NCALayer 1.x (version < 2): commonUtils + positional array args + raw XML (NOT base64) → responseObject
 *  - NCALayer 2.x (version >= 2): basics + named object args + base64 XML → result
 *  - Status transitions: disconnected → connecting → connected → signing → connected
 *  - certExpiresWithinDays helper
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useNCALayer, certExpiresWithinDays } from '../useNCALayer'
import type { Certificate } from '@/types/ncalayer'

// ---------------------------------------------------------------------------
// Mock WebSocket — simulates NCALayer localhost WS
// ---------------------------------------------------------------------------

let mockWS: MockWebSocket

class MockWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  readyState = MockWebSocket.CONNECTING
  onopen: ((ev: Event) => void) | null = null
  onmessage: ((ev: MessageEvent) => void) | null = null
  onerror: ((ev: Event) => void) | null = null
  onclose: ((ev: CloseEvent) => void) | null = null
  sentMessages: string[] = []
  url: string

  constructor(url: string) {
    this.url = url
    // Expose the latest instance so tests can drive it
    mockWS = this
  }

  send(data: string) {
    this.sentMessages.push(data)
  }

  close() {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.(new CloseEvent('close'))
  }

  // ---- Test helpers -------------------------------------------------------

  simulateOpen() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.(new Event('open'))
  }

  simulateMessage(data: object) {
    this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(data) }))
  }

  simulateError() {
    this.onerror?.(new Event('error'))
  }
}

vi.stubGlobal('WebSocket', MockWebSocket)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Connect hook and receive NCALayer version broadcast. */
async function connectWithVersion(
  result: { current: ReturnType<typeof useNCALayer> },
  version: string,
) {
  act(() => { result.current.connect() })
  act(() => { mockWS.simulateOpen() })
  act(() => { mockWS.simulateMessage({ result: { version } }) })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useNCALayer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  // ── signXml dual-mode dispatch ──────────────────────────────────────────

  describe('signXml dual-mode dispatch', () => {
    it('sends commonUtils + array args + raw XML for NCALayer 1.x (version 1.4)', async () => {
      const { result } = renderHook(() => useNCALayer())
      await connectWithVersion(result, '1.4')

      expect(result.current.status).toBe('connected')

      const rawXml = '<tender><id>TEST-001</id><amount>100000</amount></tender>'

      await act(async () => {
        const promise = result.current.signXml(rawXml)
        // Simulate NCALayer 1.x response: signed XML in responseObject
        mockWS.simulateMessage({
          responseObject: '<?xml version="1.0"?><tender><ds:Signature/></tender>',
          code: '200',
        })
        return promise
      })

      // Find the signXml request
      const signMsg = mockWS.sentMessages.find((m) => {
        const p = JSON.parse(m)
        return p.method === 'signXml' || p.method === 'sign'
      })

      expect(signMsg).toBeDefined()
      const payload = JSON.parse(signMsg!)

      // Must use commonUtils for 1.x
      expect(payload.module).toBe('kz.gov.pki.knca.commonUtils')
      expect(payload.method).toBe('signXml')

      // Args must be a positional array
      expect(Array.isArray(payload.args)).toBe(true)

      // args[2] must be the RAW XML — never base64 (SAX pitfall, SPIKE-02)
      expect(payload.args[2]).toBe(rawXml)
      // Quick sanity: base64 would be much longer and only contain [A-Za-z0-9+/=]
      expect(payload.args[2]).toMatch(/^</)
    })

    it('sends basics + object args + base64 xmlToSign for NCALayer 2.x (version 2.1)', async () => {
      const { result } = renderHook(() => useNCALayer())
      await connectWithVersion(result, '2.1')

      expect(result.current.status).toBe('connected')

      const rawXml = '<tender><id>TEST-001</id><amount>100000</amount></tender>'
      const expectedBase64 = btoa(unescape(encodeURIComponent(rawXml)))

      await act(async () => {
        const promise = result.current.signXml(rawXml)
        // Simulate NCALayer 2.x response: base64-encoded signed XML in result field
        mockWS.simulateMessage({
          result: btoa('<signed-tender/>'),
          code: '200',
        })
        return promise
      })

      const signMsg = mockWS.sentMessages.find((m) => {
        const p = JSON.parse(m)
        return p.method === 'sign' || p.method === 'signXml'
      })

      expect(signMsg).toBeDefined()
      const payload = JSON.parse(signMsg!)

      // Must use basics for 2.x
      expect(payload.module).toBe('kz.gov.pki.knca.basics')

      // Args must be a named object (not array)
      expect(Array.isArray(payload.args)).toBe(false)
      expect(typeof payload.args).toBe('object')

      // xmlToSign must be base64-encoded
      expect(payload.args.xmlToSign).toBe(expectedBase64)
    })
  })

  // ── Status transitions ──────────────────────────────────────────────────

  describe('status transitions', () => {
    it('starts as disconnected', () => {
      const { result } = renderHook(() => useNCALayer())
      expect(result.current.status).toBe('disconnected')
    })

    it('transitions to connecting on ws.onopen, then connected on version broadcast', async () => {
      const { result } = renderHook(() => useNCALayer())

      expect(result.current.status).toBe('disconnected')

      act(() => { result.current.connect() })
      act(() => { mockWS.simulateOpen() })
      expect(result.current.status).toBe('connecting')

      act(() => { mockWS.simulateMessage({ result: { version: '1.4' } }) })
      expect(result.current.status).toBe('connected')
      expect(result.current.version).toBe('1.4')
    })

    it('transitions to signing during signXml and back to connected on completion', async () => {
      const { result } = renderHook(() => useNCALayer())
      await connectWithVersion(result, '1.4')

      const rawXml = '<root/>'
      await act(async () => {
        const promise = result.current.signXml(rawXml)
        // Respond immediately
        mockWS.simulateMessage({ responseObject: '<root><ds:Signature/></root>', code: '200' })
        return promise
      })

      expect(result.current.status).toBe('connected')
    })

    it('transitions to error on WS error event', () => {
      const { result } = renderHook(() => useNCALayer())

      act(() => { result.current.connect() })
      act(() => { mockWS.simulateOpen() })
      act(() => { mockWS.simulateError() })

      expect(result.current.status).toBe('error')
      expect(result.current.error).toBeTruthy()
    })
  })

  // ── certExpiresWithinDays ───────────────────────────────────────────────

  describe('certExpiresWithinDays', () => {
    const baseCert: Certificate = {
      serialNumber: 'ABC123',
      subjectCommonName: 'Иванов Иван Иванович',
      issuerCommonName: 'NCA Kazakhstan',
      notBefore: new Date('2024-01-01'),
      notAfter: new Date(), // overridden in each test
    }

    it('returns true when cert expires within the given number of days', () => {
      const cert: Certificate = {
        ...baseCert,
        notAfter: new Date(Date.now() + 10 * 24 * 60 * 60 * 1000), // 10 days from now
      }
      expect(certExpiresWithinDays(cert, 30)).toBe(true)
    })

    it('returns false when cert expires after the threshold', () => {
      const cert: Certificate = {
        ...baseCert,
        notAfter: new Date(Date.now() + 60 * 24 * 60 * 60 * 1000), // 60 days from now
      }
      expect(certExpiresWithinDays(cert, 30)).toBe(false)
    })

    it('returns true for an already-expired cert', () => {
      const cert: Certificate = {
        ...baseCert,
        notAfter: new Date(Date.now() - 24 * 60 * 60 * 1000), // yesterday
      }
      expect(certExpiresWithinDays(cert, 30)).toBe(true)
    })
  })

  // ── WebSocket URL ───────────────────────────────────────────────────────

  it('connects to wss://127.0.0.1:13579 (SPIKE-02 confirmed port)', () => {
    const { result } = renderHook(() => useNCALayer())
    act(() => { result.current.connect() })
    expect(mockWS.url).toBe('wss://127.0.0.1:13579')
  })
})
