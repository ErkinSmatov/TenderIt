"""GoszakupPortalClient — backend HTTP proxy for v3bl.goszakup.gov.kz.

Security invariants:
- NEVER log phpsessid, csrf, or signed_xml values (T-05-03 mitigation).
  Log only the event (e.g. "login succeeded"), not the secret payload.
- Every method uses a per-call AsyncClient (never a shared/singleton client).
  Shared clients cause event-loop lifetime issues in async contexts.
- All requests: Content-Type: application/x-www-form-urlencoded (SPIKE-03 finding).
- Auth: PHPSESSID cookie passed in every authenticated request.

Confirmed endpoints from SPIKE-03-FINDINGS.md (2026-07-09):
  login:   POST /user/sendsign/kz
  step 1:  POST /ru/application/ajax_create_application/{tender_buy_id}
  step 2:  POST /ru/application/ajax_add_lots/{tender_buy_id}/{application_id}
  step 3:  POST /ru/application/ajax_lots_next/{tender_buy_id}/{application_id}
  step 4:  POST /ru/beneficiary/ajax_save_info
  step 5:  POST /ru/application/ajax_docs_next/{tender_buy_id}/{application_id}
  step 6:  POST /ru/application/ajax_get_encr_info/{tender_buy_id}/{application_id}
  step 8:  POST /ru/application/ajax_add_encrypt/{tender_buy_id}/{application_id}
  step 10: POST /ru/application/ajax_save_gamma_signs/{tender_buy_id}/{application_id}
  step 11: POST /ru/application/ajax_priceoffers_next/{tender_buy_id}/{application_id}
  submit:  POST /ru/application/ajax_public_application/{tender_buy_id}/{application_id}

CSRF refresh finding (RESEARCH open question #3):
  The goszakup portal does NOT return an updated CSRF token in Set-Cookie headers or
  JSON response bodies for AJAX step calls (steps 1-11). The CSRF token is established
  once during session creation and remains constant for the session lifetime.
  _extract_csrf_from_response() is a safety net that almost always returns the unchanged
  current_csrf.  This is the standard PHP session CSRF pattern.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlencode

import httpx

PORTAL_BASE = "https://v3bl.goszakup.gov.kz"

logger = logging.getLogger(__name__)


def _extract_csrf_from_response(resp: httpx.Response, current_csrf: str) -> str:
    """Try to extract an updated CSRF token from a portal response.

    Checks (in order):
    1. Set-Cookie header for a 'csrf' or similar cookie name.
    2. JSON body for a 'csrf' key (only if Content-Type is JSON).

    Finding (RESEARCH open question #3): The goszakup portal does NOT include CSRF
    in Set-Cookie or JSON bodies for AJAX calls.  This function almost always returns
    current_csrf unchanged.

    Returns the updated CSRF string, or `current_csrf` unchanged if nothing new found.
    """
    for cookie_name in ("csrf", "csrfToken", "_token", "csrf_token"):
        val = resp.cookies.get(cookie_name)
        if val:
            return val

    ct = resp.headers.get("content-type", "")
    if "application/json" in ct:
        try:
            data = resp.json()
            if isinstance(data, dict) and "csrf" in data:
                return str(data["csrf"])
        except Exception:
            pass

    return current_csrf


class GoszakupPortalClient:
    """Backend proxy for v3bl.goszakup.gov.kz (PHP portal, form-encoded requests).

    Architecture: browser performs steps 1-11; ARQ worker calls step 12 (public_application).
    Session data stored in Redis by redis_service helpers (goszakup_session:{user_id}).

    NEVER instantiate a shared instance — each method opens its own AsyncClient.
    """

    # ── Authentication ────────────────────────────────────────────────────────

    async def login_with_signed_xml(self, signed_xml: str) -> str:
        """Authenticate with goszakup portal via NCALayer-signed XML.

        POSTs `sign={signed_xml}` to `/user/sendsign/kz` and returns PHPSESSID cookie.

        Flow (D-05-02 Scenario B):
          1. Browser calls NCALayer signXml('<root><key>{challenge}</key></root>')
          2. Browser POSTs signed XML to /api/goszakup/auth → this method
          3. This method POSTs to portal, extracts Set-Cookie: PHPSESSID

        Security:
          - signed_xml is NOT logged (T-05-03 mitigation).
          - PHPSESSID is NOT logged (T-05-03 mitigation).

        Returns:
            PHPSESSID cookie value (str).

        Raises:
            ValueError: if no PHPSESSID in portal response (login failed).
            httpx.HTTPStatusError: on non-2xx portal response.
        """
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.post(
                f"{PORTAL_BASE}/user/sendsign/kz",
                data={"sign": signed_xml},
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            resp.raise_for_status()

        phpsessid = resp.cookies.get("PHPSESSID")
        if not phpsessid:
            logger.warning("goszakup login: no PHPSESSID in portal response (login failed)")
            raise ValueError("goszakup login failed: no PHPSESSID in response")

        logger.info("goszakup login: session established for portal auth")
        return phpsessid

    async def get_initial_csrf(self, phpsessid: str) -> str:
        """Fetch the initial CSRF token by loading the portal profile page after login.

        After login the PHP session is active but CSRF must be extracted from portal HTML.
        This method GETs /ru/profile with the session cookie and parses the CSRF token.

        Security: phpsessid is NOT logged (T-05-03 mitigation).

        Returns:
            CSRF token string, or empty string if extraction fails.
        """
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(
                f"{PORTAL_BASE}/ru/profile",
                cookies={"PHPSESSID": phpsessid},
            )

        for pattern in (
            r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']csrf-token["\']',
            r'<input[^>]+name=["\']csrf["\'][^>]+value=["\']([^"\']+)["\']',
            r'"csrf"\s*:\s*"([^"]+)"',
        ):
            m = re.search(pattern, resp.text, re.IGNORECASE)
            if m:
                return m.group(1)

        logger.warning("goszakup get_initial_csrf: CSRF not found in portal HTML")
        return ""

    # ── Step 1: create_application ────────────────────────────────────────────

    async def create_application(
        self,
        tender_buy_id: int,
        phpsessid: str,
        csrf: str,
        subject_address: str,
        iik: str,
        contact_phone: str = "",
        tax_payer_type: str = "UL",
    ) -> int:
        """Step 1: POST ajax_create_application → returns applicationId (int).

        URL: POST /ru/application/ajax_create_application/{tender_buy_id}
        Body: csrf=...&subject_address={addr}&iik={iik}&contact_phone=...&tax_payer_type=UL
        Response: {"id": <applicationId>}

        Security: phpsessid and csrf NOT logged (T-05-03).
        """
        url = f"{PORTAL_BASE}/ru/application/ajax_create_application/{tender_buy_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                data={
                    "csrf": csrf,
                    "subject_address": subject_address,
                    "iik": iik,
                    "contact_phone": contact_phone,
                    "tax_payer_type": tax_payer_type,
                },
                cookies={"PHPSESSID": phpsessid},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()

        result = resp.json()
        application_id = result.get("id")
        if application_id is None:
            raise ValueError(
                f"create_application: no 'id' in portal response: {list(result.keys())}"
            )
        logger.info("goszakup create_application: draft created, buy=%s", tender_buy_id)
        return int(application_id)

    # ── Step 2: add_lots ──────────────────────────────────────────────────────

    async def add_lots(
        self,
        tender_buy_id: int,
        application_id: int,
        lot_ids: list[int],
        phpsessid: str,
        csrf: str,
    ) -> None:
        """Step 2: POST ajax_add_lots — add selected lot IDs to the application draft.

        URL: POST /ru/application/ajax_add_lots/{tender_buy_id}/{application_id}
        Body: csrf=...&selectLots[]={lotId}&selectLots[]={lotId2}...
        Response: HTTP 200, text/html
        """
        url = f"{PORTAL_BASE}/ru/application/ajax_add_lots/{tender_buy_id}/{application_id}"
        fields: list[tuple[str, str]] = [("csrf", csrf)]
        for lot_id in lot_ids:
            fields.append(("selectLots[]", str(lot_id)))
        body = urlencode(fields)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                content=body,
                cookies={"PHPSESSID": phpsessid},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()

        logger.info(
            "goszakup add_lots: %d lots to buy=%s app=%s",
            len(lot_ids), tender_buy_id, application_id,
        )

    # ── Step 3: lots_next ─────────────────────────────────────────────────────

    async def lots_next(
        self,
        tender_buy_id: int,
        application_id: int,
        phpsessid: str,
        csrf: str,
    ) -> None:
        """Step 3: POST ajax_lots_next — confirm lots selection (next=1&confirmed=0).

        URL: POST /ru/application/ajax_lots_next/{tender_buy_id}/{application_id}
        Body: next=1&confirmed=0&csrf=...
        Response: HTTP 200, text/html
        """
        url = f"{PORTAL_BASE}/ru/application/ajax_lots_next/{tender_buy_id}/{application_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                data={"next": "1", "confirmed": "0", "csrf": csrf},
                cookies={"PHPSESSID": phpsessid},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()

        logger.info("goszakup lots_next: buy=%s app=%s", tender_buy_id, application_id)

    # ── Step 4: save_beneficiary ──────────────────────────────────────────────

    async def save_beneficiary(
        self,
        app_lot_id: int,
        phpsessid: str,
        csrf: str,
        beneficiary_name: str,
        beneficiary_doc_number: str,
        beneficiary_doc_date: str,  # YYYY-MM-DD
        beneficiary_id: str = "",
    ) -> dict:
        """Step 4: POST ajax_save_info — save beneficiary info per lot.

        URL: POST /ru/beneficiary/ajax_save_info
        Body: csrf=...&citizenship=398&res_country=398&...&option_1=1&option_4=2&app_lot_id=...
        Response: {"status": "ok", ...}

        Kazakhstan citizenship code 398 (D-05-03 default).
        option_1..3=1 (yes), option_4=2 (no).
        """
        url = f"{PORTAL_BASE}/ru/beneficiary/ajax_save_info"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                data={
                    "csrf": csrf,
                    "beneficiary_name": beneficiary_name,
                    "citizenship": "398",
                    "res_country": "398",
                    "beneficiary_doc_number": beneficiary_doc_number,
                    "beneficiary_doc_date": beneficiary_doc_date,
                    "option_1": "1",
                    "option_2": "1",
                    "option_3": "1",
                    "option_4": "2",
                    "app_lot_id": str(app_lot_id),
                    "beneficiary_id": beneficiary_id,
                },
                cookies={"PHPSESSID": phpsessid},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()

        logger.info("goszakup save_beneficiary: app_lot_id=%s", app_lot_id)
        ct = resp.headers.get("content-type", "")
        return resp.json() if "application/json" in ct else {}

    # ── Step 5: docs_next ─────────────────────────────────────────────────────

    async def docs_next(
        self,
        tender_buy_id: int,
        application_id: int,
        phpsessid: str,
        csrf: str,
    ) -> None:
        """Step 5: POST ajax_docs_next — skip documents step (next=1).

        URL: POST /ru/application/ajax_docs_next/{tender_buy_id}/{application_id}
        Body: next=1&csrf=...
        Response: HTTP 200, text/html
        """
        url = f"{PORTAL_BASE}/ru/application/ajax_docs_next/{tender_buy_id}/{application_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                data={"next": "1", "csrf": csrf},
                cookies={"PHPSESSID": phpsessid},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()

        logger.info("goszakup docs_next: buy=%s app=%s", tender_buy_id, application_id)

    # ── Step 6: get_encr_info ─────────────────────────────────────────────────

    async def get_encr_info(
        self,
        tender_buy_id: int,
        application_id: int,
        lp_id: int,
        version: str,
        phpsessid: str,
        csrf: str,
    ) -> dict:
        """Step 6: POST ajax_get_encr_info — retrieve encryption params for a lot price.

        URL: POST /ru/application/ajax_get_encr_info/{tender_buy_id}/{application_id}
        Body: lpId={lp_id}&version={version}&csrf=...
        Response: JSON with public_key, id_priceoffer, and other encryption params.

        `version` is the CryptoSocket version string (not NCALayer version).
        The browser uses the returned params to call CryptoSocket EFCAPI.EncryptOfferPrice.
        """
        url = f"{PORTAL_BASE}/ru/application/ajax_get_encr_info/{tender_buy_id}/{application_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                data={"lpId": str(lp_id), "version": version, "csrf": csrf},
                cookies={"PHPSESSID": phpsessid},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()

        logger.info(
            "goszakup get_encr_info: buy=%s app=%s lpId=%s", tender_buy_id, application_id, lp_id
        )
        return resp.json()

    # ── Step 8: add_encrypt ───────────────────────────────────────────────────

    async def add_encrypt(
        self,
        tender_buy_id: int,
        application_id: int,
        item_id: int,
        encrypted_data: str,
        session_key: str,
        salt: str,
        info: str,
        sign: str,
        phpsessid: str,
        csrf: str,
    ) -> dict:
        """Step 8: POST ajax_add_encrypt — save CryptoSocket-encrypted price blobs.

        URL: POST /ru/application/ajax_add_encrypt/{tender_buy_id}/{application_id}
        Body: itemID={lp_id}&encryptedData=...&sessionKey=...&salt=...&info=...&sign=...&csrf=...
        Response: {"status": "ok"}

        Field mapping from CryptoSocket (GAMMA-ENCRYPTION-FINDINGS.md):
          encryptData  → encryptedData
          encryptKey   → sessionKey
          salt         → salt
          sign         → sign
          id_priceoffer → info (low priority — needs live DevTools verification)

        Security: encrypted blobs NOT logged (T-05-23 mitigation).
        """
        url = f"{PORTAL_BASE}/ru/application/ajax_add_encrypt/{tender_buy_id}/{application_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                data={
                    "itemID": str(item_id),
                    "encryptedData": encrypted_data,
                    "sessionKey": session_key,
                    "salt": salt,
                    "info": info,
                    "sign": sign,
                    "csrf": csrf,
                },
                cookies={"PHPSESSID": phpsessid},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()

        # NOT logging encrypted blobs — T-05-23
        logger.info(
            "goszakup add_encrypt: buy=%s app=%s itemID=%s", tender_buy_id, application_id, item_id
        )
        return resp.json()

    # ── Step 10: save_gamma_signs ──────────────────────────────────────────────

    async def save_gamma_signs(
        self,
        tender_buy_id: int,
        application_id: int,
        signs: dict[int, tuple[str, str]],  # {lp_id: (xml_data, sign_data)}
        phpsessid: str,
        csrf: str,
    ) -> dict:
        """Step 10: POST ajax_save_gamma_signs — save NCALayer GOST CMS signatures.

        URL: POST /ru/application/ajax_save_gamma_signs/{tender_buy_id}/{application_id}
        Body: xmlData[{lpId}]={encryptedData}&signData[{lpId}]={pkcs7Blob}&csrf=...
        Response: {"status": "ok"}

        `signs` maps lp_id → (encrypted_data, pkcs7_sign_blob).
        Security: sign blobs NOT logged (T-05-23).
        """
        url = (
            f"{PORTAL_BASE}/ru/application/ajax_save_gamma_signs"
            f"/{tender_buy_id}/{application_id}"
        )
        fields: list[tuple[str, str]] = [("csrf", csrf)]
        for lp_id, (xml_data, sign_data) in signs.items():
            fields.append((f"xmlData[{lp_id}]", xml_data))
            fields.append((f"signData[{lp_id}]", sign_data))
        body = urlencode(fields)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                content=body,
                cookies={"PHPSESSID": phpsessid},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()

        # NOT logging sign blobs — T-05-23
        logger.info(
            "goszakup save_gamma_signs: buy=%s app=%s lots=%s",
            tender_buy_id, application_id, list(signs.keys()),
        )
        return resp.json()

    # ── Step 11: priceoffers_next ──────────────────────────────────────────────

    async def priceoffers_next(
        self,
        tender_buy_id: int,
        application_id: int,
        offers: dict[int, dict[int, str]],  # {app_lot_id: {lp_id: encrypted_price}}
        phpsessid: str,
        csrf: str,
    ) -> None:
        """Step 11: POST ajax_priceoffers_next — confirm encrypted price offers.

        URL: POST /ru/application/ajax_priceoffers_next/{tender_buy_id}/{application_id}
        Body: csrf=...&offer[{app_lot_id}][{lp_id}][price]={encryptedData}&is_construction_pilot=
        Response: HTTP 200, text/html

        `offers` maps app_lot_id → {lp_id → encrypted_price (encryptData blob)}.
        """
        url = (
            f"{PORTAL_BASE}/ru/application/ajax_priceoffers_next"
            f"/{tender_buy_id}/{application_id}"
        )
        fields: list[tuple[str, str]] = [
            ("csrf", csrf),
            ("is_construction_pilot", ""),
        ]
        for app_lot_id, lot_offers in offers.items():
            for lp_id, price in lot_offers.items():
                fields.append((f"offer[{app_lot_id}][{lp_id}][price]", price))
        body = urlencode(fields)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                content=body,
                cookies={"PHPSESSID": phpsessid},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()

        logger.info("goszakup priceoffers_next: buy=%s app=%s", tender_buy_id, application_id)

    # ── Step 12: public_application (ARQ final submit) ────────────────────────

    async def public_application(
        self,
        tender_buy_id: int,
        application_id: int,
        phpsessid: str,
        csrf: str,
    ) -> dict:
        """Step 12 (ARQ final submit): POST ajax_public_application.

        Called by ARQ worker when tender status_id == 220 (OPEN_FOR_APPLICATIONS_STATUS_ID).
        Browser has already completed steps 1-11; this submits the finalized application.

        URL: POST /ru/application/ajax_public_application/{tender_buy_id}/{application_id}
        Body: public_app=Y&agree_price=false&agree_contract_project=false
              &agree_covid19=false&csrf={csrf}
        Cookie: PHPSESSID={phpsessid}

        Returns:
            dict — parsed JSON response from portal:
              Success: {"status": "ok"}
              Error:   {"status": "error", "message": "..."}

        Security:
          - phpsessid and csrf are NOT logged (T-05-03 mitigation).
          - Only event is logged.

        Raises:
            httpx.HTTPStatusError: on non-2xx portal response.
        """
        url = (
            f"{PORTAL_BASE}/ru/application/ajax_public_application"
            f"/{tender_buy_id}/{application_id}"
        )
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                data={
                    "public_app": "Y",
                    "agree_price": "false",
                    "agree_contract_project": "false",
                    "agree_covid19": "false",
                    "csrf": csrf,
                },
                cookies={"PHPSESSID": phpsessid},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()

        result = resp.json()
        # Log only status — NOT csrf/phpsessid (T-05-03)
        logger.info(
            "goszakup public_application: tender=%s app=%s status=%s",
            tender_buy_id,
            application_id,
            result.get("status"),
        )
        return result
