/**
 * goszakup.ts — browser orchestration of the goszakup portal wizard steps.
 *
 * All portal HTTP calls go through the TenderIt backend proxy (/api/goszakup/*).
 * NO direct XHR to the portal from the browser (T-05-21: CORS + security).
 *
 * Flow (SPIKE-03-FINDINGS.md, GAMMA-ENCRYPTION-FINDINGS.md):
 *   1. Login: POST /api/goszakup/auth/login (NCALayer-signed XML)
 *   2. Create draft: POST /api/goszakup/proxy/create-draft
 *   3. Add lots: POST /api/goszakup/proxy/add-lots
 *   4. Confirm lots: POST /api/goszakup/proxy/lots-next
 *   5. Beneficiary: POST /api/goszakup/proxy/beneficiary (per lot)
 *   6. Docs step: POST /api/goszakup/proxy/docs-next
 *   7. Get encryption params: POST /api/goszakup/proxy/get-encr-info
 *   7b. CryptoSocket encrypt: cs.encryptOfferPrice(params) → {encryptData, ...}
 *   8. Save encrypted price: POST /api/goszakup/proxy/add-encrypt
 *   9. NCALayer CMS sign: nca.createCMSSignatureFromBase64(encryptData) → pkcs7Blob
 *   10. Save GOST signatures: POST /api/goszakup/proxy/save-gamma-signs
 *   11. Confirm price step: POST /api/goszakup/proxy/priceoffers-next
 *   12. Mark ready: POST /api/goszakup/proxy/mark-ready/{app_id}
 */

import { api } from '@/lib/api'
import type { NCALayerHookResult } from '@/types/ncalayer'
import type { CryptoSocketHookResult } from '@/types/cryptosocket'
import type { ApplicationResponse, LotOffer } from '@/types/application'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Progress callback — called at each step with a 0-11 progress index. */
export type SigningProgressCallback = (step: number, label: string) => void

/** Parameters for the full signing flow. */
export interface RunSigningFlowParams {
  /** TenderIt application ID (from POST /api/applications response). */
  appId: number
  /** goszakup portal tender_buy_id (from tender data). */
  tenderBuyId: number
  /** IIN of the company (for create-draft step). */
  iik: string
  /** goszakup subject_address (company's portal address ID). */
  subjectAddress: string
  /** List of lot IDs to include (from tender data). */
  lotIds: number[]
  /** Beneficiary data per app_lot_id. */
  beneficiaries: BeneficiaryData[]
  /** Document IDs from Document Vault to attach. */
  documentIds: number[]
  /** NCALayer hook instance from parent component (for login XML sign + step 9). */
  nca: NCALayerHookResult
  /** CryptoSocket hook instance from parent component (for step 7). */
  cs: CryptoSocketHookResult
  /** Optional progress callback. */
  onProgress?: SigningProgressCallback
  /** CryptoSocket version string (for get-encr-info step). */
  csVersion?: string
}

/** Beneficiary data for one app_lot_id. */
export interface BeneficiaryData {
  app_lot_id: number
  beneficiary_name: string
  beneficiary_doc_number: string
  beneficiary_doc_date: string  // YYYY-MM-DD
}

// ---------------------------------------------------------------------------
// Typed errors
// ---------------------------------------------------------------------------

export class GoszakupFlowError extends Error {
  constructor(
    public readonly step: string,
    message: string,
    public readonly cause?: unknown,
  ) {
    super(`[${step}] ${message}`)
    this.name = 'GoszakupFlowError'
  }
}

// ---------------------------------------------------------------------------
// Main orchestration function
// ---------------------------------------------------------------------------

/**
 * runSigningFlow — orchestrates all 12 wizard steps.
 *
 * Drives browser-side steps (NCALayer login, CryptoSocket encrypt, NCALayer sign)
 * and backend proxy steps via /api/goszakup/*.
 *
 * Security invariant: NO direct calls to the goszakup portal (T-05-21).
 * All portal HTTP calls go through /api/goszakup proxy endpoints.
 *
 * @returns The updated ApplicationResponse with status='waiting'.
 * @throws GoszakupFlowError on any step failure.
 */
export async function runSigningFlow(
  params: RunSigningFlowParams,
): Promise<ApplicationResponse> {
  const {
    appId,
    tenderBuyId,
    iik,
    subjectAddress,
    lotIds,
    beneficiaries,
    nca,
    cs,
    onProgress,
    csVersion = '1.0.0',
  } = params

  const progress = (step: number, label: string) => onProgress?.(step, label)

  try {
    // ─── Step 1: Login ───────────────────────────────────────────────────────
    progress(0, 'Авторизация на портале через NCALayer...')
    const loginXml = `<root><key>${tenderBuyId}</key></root>`
    let signedLoginXml: string
    try {
      signedLoginXml = await nca.signXml(loginXml)
    } catch (e) {
      throw new GoszakupFlowError('login', 'NCALayer не смог подписать XML для авторизации', e)
    }
    await api.post('/api/goszakup/auth/login', { signed_xml: signedLoginXml })

    // ─── Step 2: Create draft ─────────────────────────────────────────────────
    progress(1, 'Создание черновика заявки...')
    const draftResp = await api.post<{ application_id: number }>(
      '/api/goszakup/proxy/create-draft',
      {
        tender_buy_id: tenderBuyId,
        subject_address: subjectAddress,
        iik,
      },
    )
    const goszakupApplicationId = draftResp.application_id

    // ─── Step 3: Add lots ─────────────────────────────────────────────────────
    progress(2, 'Добавление лотов...')
    await api.post('/api/goszakup/proxy/add-lots', {
      application_id: goszakupApplicationId,
      tender_buy_id: tenderBuyId,
      lot_ids: lotIds,
    })

    // ─── Step 4: Confirm lots ─────────────────────────────────────────────────
    progress(3, 'Подтверждение лотов...')
    await api.post('/api/goszakup/proxy/lots-next', {
      application_id: goszakupApplicationId,
      tender_buy_id: tenderBuyId,
    })

    // ─── Step 5: Beneficiary (per lot) ────────────────────────────────────────
    progress(4, 'Сохранение данных бенефициара...')
    for (const ben of beneficiaries) {
      await api.post('/api/goszakup/proxy/beneficiary', {
        app_lot_id: ben.app_lot_id,
        beneficiary_name: ben.beneficiary_name,
        beneficiary_doc_number: ben.beneficiary_doc_number,
        beneficiary_doc_date: ben.beneficiary_doc_date,
      })
    }

    // ─── Step 6: Skip docs ────────────────────────────────────────────────────
    progress(5, 'Пропуск шага документов...')
    await api.post('/api/goszakup/proxy/docs-next', {
      application_id: goszakupApplicationId,
      tender_buy_id: tenderBuyId,
    })

    // ─── Steps 7-11: Per lot — get encr info, encrypt, sign, save ────────────
    // Currently MVP handles one lpId per lot.
    // Multiple lots: repeat steps 7-8 per lpId, then step 10-11 once with all lots.
    progress(6, 'Получение параметров шифрования...')

    const encrInfoResp = await api.post<Record<string, unknown>>(
      '/api/goszakup/proxy/get-encr-info',
      {
        application_id: goszakupApplicationId,
        tender_buy_id: tenderBuyId,
        lp_id: lotIds[0],  // first lot for MVP single-lot flow
        version: csVersion,
      },
    )

    const publicKey = encrInfoResp.public_key as string
    const idPriceoffer = encrInfoResp.id_priceoffer as string
    const lpId = lotIds[0]

    // Step 7b: CryptoSocket Gamma encrypt
    progress(7, 'Шифрование цены через CryptoSocket...')
    let encryptResult: Awaited<ReturnType<typeof cs.encryptOfferPrice>>
    try {
      encryptResult = await cs.encryptOfferPrice({
        pl_sum: 0,   // TODO: pass actual price from LotPriceForm
        d_sum: 0,
        d_messageUp: '',
        d_messageDown: '',
        id_priceoffer: idPriceoffer,
        public_key: publicKey,
      })
    } catch (e) {
      throw new GoszakupFlowError(
        'encrypt',
        'CryptoSocket не смог зашифровать цену. Проверьте, что CryptoSocket запущен.',
        e,
      )
    }

    // Step 8: Save encrypted price
    progress(8, 'Сохранение зашифрованной цены...')
    await api.post('/api/goszakup/proxy/add-encrypt', {
      application_id: goszakupApplicationId,
      tender_buy_id: tenderBuyId,
      item_id: lpId,
      encrypted_data: encryptResult.encryptData,
      session_key: encryptResult.encryptKey,
      salt: encryptResult.salt,
      info: idPriceoffer,  // low priority — needs live DevTools verification
      sign: encryptResult.sign,
    })

    // Step 9: NCALayer CMS sign of encrypted data
    progress(9, 'GOST-подпись зашифрованных данных через NCALayer...')
    let pkcs7Blob: string
    try {
      pkcs7Blob = await nca.createCMSSignatureFromBase64(encryptResult.encryptData)
    } catch (e) {
      throw new GoszakupFlowError(
        'gost-sign',
        'NCALayer не смог создать GOST CMS подпись. Введите PIN и попробуйте ещё раз.',
        e,
      )
    }

    // Step 10: Save GOST signatures
    progress(10, 'Сохранение GOST подписи...')
    await api.post('/api/goszakup/proxy/save-gamma-signs', {
      application_id: goszakupApplicationId,
      tender_buy_id: tenderBuyId,
      signs: [
        {
          lp_id: lpId,
          xml_data: encryptResult.encryptData,
          sign_data: pkcs7Blob,
        },
      ],
    })

    // Step 11: Confirm price step
    progress(11, 'Подтверждение шага цены...')
    await api.post('/api/goszakup/proxy/priceoffers-next', {
      application_id: goszakupApplicationId,
      tender_buy_id: tenderBuyId,
      offers: beneficiaries.map((ben) => ({
        app_lot_id: ben.app_lot_id,
        lp_id: lpId,
        price: encryptResult.encryptData,
      })),
    })

    // Step 12: Mark ready (transition to waiting, persist session for ARQ)
    progress(12, 'Заявка готова к автоматической подаче...')
    const appResp = await api.post<ApplicationResponse>(
      `/api/goszakup/proxy/mark-ready/${appId}`,
      {
        goszakup_application_id: goszakupApplicationId,
        goszakup_tender_buy_id: tenderBuyId,
      },
    )

    return appResp

  } catch (e) {
    if (e instanceof GoszakupFlowError) throw e
    throw new GoszakupFlowError('unknown', String(e), e)
  }
}
