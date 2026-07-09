"""goszakup_proxy router — backend proxy for v3bl.goszakup.gov.kz wizard steps.

This router is registered in main.py (prefix="/api/goszakup") so plan 05-03
can add step 1-11 proxy endpoints without touching main.py.

Architecture (D-05-01 + D-05-02, SPIKE-03 confirmed):
- Browser executes wizard steps 1-11 directly against the goszakup portal.
  TenderIt backend proxies each step because browser cannot do cross-origin XHR
  to goszakup and read the PHPSESSID (httpOnly) response cookie.
- Step 12 (final submit: ajax_public_application) is executed by the ARQ worker
  at tender open time (status_id == 220), using session stored in Redis.

Security:
- All routes require JWT auth — user_id from current_user.id, never body (T-05-02).
- PHPSESSID and CSRF tokens are NEVER logged (T-05-03 mitigation).
- Session stored in Redis with TTL 72000s (T-05-06 mitigation).

Step 1-11 proxy endpoints added in plan 05-03.
"""

from fastapi import APIRouter

router = APIRouter()

# step 1-11 proxy endpoints added in plan 05-03
