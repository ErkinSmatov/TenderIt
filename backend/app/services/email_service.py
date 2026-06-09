"""Email service — send transactional emails via Resend SDK.

In debug mode (settings.debug=True) the email is NOT sent; the reset link
is printed to stdout so developers can follow the flow without a Resend key.

In production mode, the synchronous Resend SDK is called.  A try/except
swallows transient failures so that the API response is always returned to
the caller — a failed email must not leak as a 500 (T-02-04-02 timing).
"""

import sys

import resend

from app.config import settings


async def send_password_reset_email(to_email: str, reset_link: str) -> None:
    """Send a password-reset email or log the link in debug mode.

    Args:
        to_email:   Recipient email address.
        reset_link: Full reset URL including the token query parameter.
    """
    if settings.debug:
        # Dev mode: log to stdout, never call Resend (no API key needed)
        print(f"[DEV] Password reset link for {to_email}: {reset_link}", flush=True)
        return

    # Production: send via Resend SDK (blocking call; acceptable for MVP)
    resend.api_key = settings.resend_api_key
    try:
        resend.Emails.send(
            {
                "from": "noreply@tenderit.kz",
                "to": to_email,
                "subject": "Сброс пароля TenderIt",
                "html": (
                    f"<p>Для сброса пароля перейдите по ссылке:</p>"
                    f'<p><a href="{reset_link}">{reset_link}</a></p>'
                    f"<p>Ссылка действительна 15 минут.</p>"
                ),
            }
        )
    except Exception as exc:  # noqa: BLE001
        # Swallow transient failures — do not leak email-send errors to the API caller
        print(f"[EMAIL] Failed to send password reset to {to_email}: {exc}", file=sys.stderr, flush=True)
