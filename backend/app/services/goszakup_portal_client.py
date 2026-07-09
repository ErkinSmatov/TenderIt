"""GoszakupPortalClient — backend HTTP proxy for v3bl.goszakup.gov.kz.

Security invariants:
- NEVER log phpsessid, csrf, or signed_xml values (T-05-03 mitigation).
  Log only the event (e.g. "login succeeded"), not the secret payload.
- Every method uses a per-call AsyncClient (never a shared/singleton client).
  Shared clients cause event-loop lifetime issues in async contexts.
- All requests: Content-Type: application/x-www-form-urlencoded (SPIKE-03 finding).
- Auth: PHPSESSID cookie passed in every authenticated request.

Confirmed endpoints from SPIKE-03-FINDINGS.md (2026-07-09):
  login:  POST /user/sendsign/kz
  submit: POST /ru/application/ajax_public_application/{tender_buy_id}/{application_id}

Steps 1-11 (create_application, add_lots, beneficiary, gamma encryption etc.)
are added by plan 05-03. Only login + public_application (step 12) are here.
"""

from __future__ import annotations

import logging

import httpx

PORTAL_BASE = "https://v3bl.goszakup.gov.kz"

logger = logging.getLogger(__name__)


class GoszakupPortalClient:
    """Backend proxy for v3bl.goszakup.gov.kz (PHP portal, form-encoded requests).

    Architecture: browser performs steps 1-11; ARQ worker calls step 12 (public_application).
    Session data stored in Redis by redis_service helpers (goszakup_session:{user_id}).

    NEVER instantiate a shared instance — each method opens its own AsyncClient.
    """

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
            # Log only the event — NOT the response body (may contain partial HTML with PII)
            logger.warning("goszakup login: no PHPSESSID in portal response (login failed)")
            raise ValueError("goszakup login failed: no PHPSESSID in response")

        # Log event without the session value (T-05-03)
        logger.info("goszakup login: session established for portal auth")
        return phpsessid

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
        # Log only status (not csrf/phpsessid) — T-05-03
        logger.info(
            "goszakup public_application: tender=%s app=%s status=%s",
            tender_buy_id,
            application_id,
            result.get("status"),
        )
        return result
