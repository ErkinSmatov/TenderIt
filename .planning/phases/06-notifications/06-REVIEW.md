---
phase: 06-notifications
reviewed: 2026-07-21T12:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - backend/alembic/versions/0008_add_telegram_link_token.py
  - backend/app/config.py
  - backend/app/main.py
  - backend/app/models/user.py
  - backend/app/routers/notifications.py
  - backend/app/routers/telegram_webhook.py
  - backend/tests/test_notifications.py
  - frontend/src/app/(dashboard)/settings/notifications/page.tsx
  - frontend/src/components/layout/Sidebar.tsx
  - frontend/src/components/notifications/TelegramConnectCard.tsx
  - frontend/src/components/notifications/WatchlistSettingsTable.tsx
findings:
  critical: 3
  warning: 5
  info: 4
  total: 12
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-07-21T12:00:00Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Phase 06 implements Telegram account linking (deep-link token flow), a notification status endpoint, watchlist settings UI, and the `/start TOKEN` webhook handler. The data model and migration are sound. The JWT-scoped IDOR protections in `notifications.py` are correct. FastAPI session sharing between `get_current_user` and `get_db` is verified (both use the same `Depends(get_db)` factory and FastAPI caches per-request — commit in `notifications.py` will persist correctly).

Three blockers prevent shipping:

1. The Telegram webhook endpoint is fully unauthenticated when `TELEGRAM_WEBHOOK_SECRET` is not set (the default). The comparison `"" != ""` never raises 403, exposing tender submission and discovery actions to unauthenticated callers.
2. The `confirm` callback branch (Да/Нет buttons on the primary submission flow) never calls `bot.answer_callback_query()`, causing Telegram to display a "Bot didn't respond" error on every button press. This is a hard user-facing failure in the most critical user flow.
3. The IDOR check for both `confirm` and `disc` callbacks passes when both sides of the comparison are `None` — a user who has not linked Telegram would match any request sent without a `from_user` field.

---

## Critical Issues

### CR-01: Webhook accepts all requests when `telegram_webhook_secret` is empty (the default)

**File:** `backend/app/routers/telegram_webhook.py:190-192`

**Issue:** `settings.telegram_webhook_secret` defaults to `""` (config.py line 35). `request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")` returns `""` for any request that omits the header. The guard `if incoming_secret != settings.telegram_webhook_secret` evaluates to `"" != ""` which is `False`, so no 403 is raised and the request is processed. Any environment where `TELEGRAM_WEBHOOK_SECRET` is not explicitly set — including staging and early production — has a completely open webhook endpoint. An attacker who can reach the endpoint can POST crafted callback bodies to: trigger `auto_submit_application` ARQ jobs (`confirm:yes`), create discovery application drafts (`disc:participate`), or set tender matches to "skipped" (`disc:skip`).

**Fix:** Add a startup guard that refuses to start or at minimum logs a hard warning, and add an explicit non-empty check in the webhook handler:

```python
# In telegram_webhook.py, replace lines 190-192:
incoming_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
if not settings.telegram_webhook_secret or incoming_secret != settings.telegram_webhook_secret:
    raise HTTPException(status_code=403, detail="Forbidden")
```

Add to `config.py` `validate_secrets`:
```python
if not self.debug and not self.telegram_webhook_secret:
    raise ValueError(
        "telegram_webhook_secret must be set in production. "
        "Set TELEGRAM_WEBHOOK_SECRET env var."
    )
```

---

### CR-02: `confirm` callback branch never calls `bot.answer_callback_query()` — Да/Нет buttons broken

**File:** `backend/app/routers/telegram_webhook.py:240-250`

**Issue:** For `disc:*` callbacks the handler calls `bot.answer_callback_query(callback_query_id=query.id)` (lines 296-301). For `confirm:yes` and `confirm:no` callbacks the handler processes the action (enqueues a job or writes Redis) but never acknowledges the callback query. Telegram requires `answerCallbackQuery` within 30 seconds of receiving a `callback_query` update or it shows "This bot failed to respond" on the inline button. Every press of Да or Нет during the tender confirmation flow ends with a visible Telegram error to the user. This is the primary user-facing notification flow.

**Fix:** Add callback acknowledgment at the end of the `confirm` branch, matching the pattern already used in the `disc` branch:

```python
# Add after lines 240-250 (after the if/elif/else on action):
try:
    async with telegram.Bot(settings.telegram_bot_token) as bot:
        await bot.answer_callback_query(callback_query_id=query.id)
except Exception:
    pass  # Non-fatal — same pattern as disc branch

return {"ok": True}
```

---

### CR-03: IDOR check passes when both `caller_chat_id` and `owner.telegram_chat_id` are `None`

**File:** `backend/app/routers/telegram_webhook.py:226-235` (confirm) and `265-274` (disc)

**Issue:** Both IDOR checks use the pattern:

```python
caller_chat_id = query.from_user.id if query.from_user else None
# ...
if owner is None or owner.telegram_chat_id != caller_chat_id:
```

If `query.from_user` is absent → `caller_chat_id = None`. If the application/match owner has never linked Telegram → `owner.telegram_chat_id = None`. Then `None != None` evaluates to `False` and the check passes, granting the caller control over the owner's resources. Combined with CR-01 (open webhook when secret is empty), an unauthenticated attacker can send a crafted payload without a `from_user` field and manipulate any tender match or application that belongs to a user who has not linked Telegram.

The check must treat `None` on either side as a mismatch, not a match.

**Fix:**

```python
# Replace the IDOR guard in both locations:
caller_chat_id = query.from_user.id if query.from_user else None
# ...
if owner is None or caller_chat_id is None or owner.telegram_chat_id != caller_chat_id:
    logger.warning(...)
    return {"ok": True}
```

---

## Warnings

### WR-01: `timeoutRef` is not cleared on component unmount — memory leak

**File:** `frontend/src/components/notifications/TelegramConnectCard.tsx:65-68`

**Issue:** `handleConnectClick` registers a 60-second `setTimeout` and stores it in `timeoutRef.current`. There is no `useEffect` cleanup that cancels this timer when the component unmounts. If the user navigates away during the 60-second window, the timeout fires against an unmounted component and calls `setPollingActive(false)` and `setDeepLink(null)` — state updates on an unmounted component.

**Fix:**

```tsx
// Add alongside the existing useEffect (line 46):
useEffect(() => {
  return () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
  }
}, [])
```

---

### WR-02: Test `test_webhook_plain_message_no_dispatch` has an inverted assertion — will not catch regressions

**File:** `backend/tests/test_notifications.py:222-242`

**Issue:** The test is named `test_webhook_plain_message_no_dispatch`, strongly implying the handler should NOT be called for plain messages. The assertion on line 242 is `mock_handler.assert_called_once()` — asserting the handler WAS called. The comment on lines 238-240 acknowledges this inconsistency by explaining the handler "returns early internally." As written the test verifies nothing useful: it confirms the webhook dispatches to the handler for all text messages (already covered by the `/start` test) and does not verify that plain messages produce no side effects. If a future change accidentally calls the handler for non-text updates or skips it for `/start`, this test will not catch either regression.

**Fix:** Either rename the test to `test_webhook_plain_message_handler_guards_internally` to match its actual assertion, or rewrite it to test the handler directly with a plain text message and assert that no DB write or bot message occurs (unit test style, like T-06-10).

---

### WR-03: `secret_key` uses the default placeholder without production validation

**File:** `backend/app/config.py:22, 40-52`

**Issue:** Both `secret_key` and `jwt_secret` default to `_DEFAULT_SECRET = "change-me-in-production"`. The `validate_secrets` validator (lines 40-52) only checks `jwt_secret` in production (`debug=False`). `secret_key` is never validated. If `secret_key` is used for security-sensitive operations elsewhere in the codebase (e.g., for signing, CSRF tokens, or session encryption), a production deployment that omits `SECRET_KEY` will silently use the well-known default placeholder.

**Fix:**

```python
@model_validator(mode="after")
def validate_secrets(self) -> "Settings":
    if not self.debug:
        if self.jwt_secret == _DEFAULT_SECRET:
            raise ValueError("jwt_secret must be set in production. Set JWT_SECRET env var.")
        if self.secret_key == _DEFAULT_SECRET:
            raise ValueError("secret_key must be set in production. Set SECRET_KEY env var.")
    return self
```

---

### WR-04: `WatchlistSettingsTable` delete mutation silently swallows errors

**File:** `frontend/src/components/notifications/WatchlistSettingsTable.tsx:31-42`

**Issue:** The `deleteMutation` has `onSuccess` and `onSettled` handlers but no `onError` handler. If the DELETE request fails (network error, 404, 403, server error), the button briefly shows "..." and then silently returns to normal. The user has no indication the operation failed and may assume the entry was deleted. No error state is tracked in the component.

**Fix:**

```tsx
const [deleteError, setDeleteError] = useState<string | null>(null)

const deleteMutation = useMutation({
  mutationFn: (numberAnno: string) => api.delete(`/api/watchlist/${numberAnno}`),
  onMutate: (numberAnno: string) => {
    setDeletingId(numberAnno)
    setDeleteError(null)
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['watchlist'] })
  },
  onError: (e: Error) => {
    setDeleteError(e.message)
  },
  onSettled: () => {
    setDeletingId(null)
  },
})
```

Render `deleteError` in the component below the list, similar to `TelegramConnectCard`'s `error` alert pattern.

---

### WR-05: `decided_at` written as naive UTC datetime — future timezone-aware comparisons will throw `TypeError`

**File:** `backend/app/routers/telegram_webhook.py:279, 289`

**Issue:** Both disc action branches write:

```python
match_obj.decided_at = datetime.now(timezone.utc).replace(tzinfo=None)
```

`TenderMatch.decided_at` is a naive TIMESTAMP column (no `timezone=True` in its `mapped_column`), so stripping tzinfo avoids an SQLAlchemy warning. However, the value stored is "UTC time in a timezone-unaware column." Any future code that compares `decided_at` against `datetime.now(timezone.utc)` (an aware datetime — as consistently used everywhere else in the reviewed codebase) will raise `TypeError: can't compare offset-naive and offset-aware datetimes`. The inconsistency is already present in the same model: `telegram_link_token_expires_at` on `User` is `TIMESTAMP(timezone=True)` and its expiry comparison on line 150 uses `datetime.now(timezone.utc)` directly (correct), while `decided_at` goes through `.replace(tzinfo=None)`.

**Fix:** Change the `decided_at` column to `sa.TIMESTAMP(timezone=True)` in the migration and model, and remove the `.replace(tzinfo=None)` calls:

```python
# In telegram_webhook.py lines 279 and 289 — change to:
match_obj.decided_at = datetime.now(timezone.utc)
```

```python
# In TenderMatch model — change decided_at column to:
decided_at: Mapped[Optional[datetime]] = mapped_column(
    sa.TIMESTAMP(timezone=True), nullable=True
)
```

---

## Info

### IN-01: `handleConnectClick` has no in-flight guard — rapid clicks generate multiple tokens

**File:** `frontend/src/components/notifications/TelegramConnectCard.tsx:57-72`

**Issue:** There is no loading state on the "Подключить Telegram" button. Multiple clicks before the first response arrives fire multiple POST `/api/notifications/telegram/link-token` requests. Each overwrites the previous token in the database. Multiple `setTimeout` calls will be created but only the last one is tracked in `timeoutRef.current`, so earlier timeouts fire without being clearable.

**Fix:** Track pending state and disable the button during the request:

```tsx
const [isConnecting, setIsConnecting] = useState(false)

async function handleConnectClick() {
  if (isConnecting) return
  setIsConnecting(true)
  try {
    const result = await api.post<{ deep_link: string }>(
      '/api/notifications/telegram/link-token', {},
    )
    // ... existing logic
  } catch (e) {
    setError((e as Error).message)
  } finally {
    setIsConnecting(false)
  }
}
```

---

### IN-02: Polling window (60 s) mismatches token validity (15 min) — silent UX failure

**File:** `frontend/src/components/notifications/TelegramConnectCard.tsx:65-68` and `backend/app/routers/notifications.py:45-46`

**Issue:** The frontend cancels polling and hides the "Открыть Telegram" link after 60 seconds, showing the "Подключить Telegram" button again. The backend token remains valid for 15 minutes. A user who opens the Telegram link between the 60-second and 15-minute marks will successfully link (the backend accepts the token), but polling is no longer running, so the frontend status stays "not connected." The UI appears broken: the user linked Telegram but the card still shows "Подключить Telegram." The next full page refresh would correct it, but the immediate experience is confusing.

**Fix:** Either extend the polling timeout to match the token expiry (15 minutes), or add a "Проверить статус" manual refresh button that appears after the timeout fires.

---

### IN-03: "Telegram бот" sidebar link renders `https://t.me/` when env var is not set

**File:** `frontend/src/components/layout/Sidebar.tsx:69-77`

**Issue:** `href={`https://t.me/${process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME}`}` resolves to `https://t.me/` (the Telegram landing page) when `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME` is not set. The link is always rendered regardless of whether the username is configured.

**Fix:** Conditionally render the link only when the env var is set:

```tsx
{process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME && (
  <a href={`https://t.me/${process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME}`} ...>
    Telegram бот
  </a>
)}
```

---

### IN-04: `telegram_chat_id` unnecessarily exposed in the status response

**File:** `backend/app/routers/notifications.py:63-66`

**Issue:** The `/notifications/status` response returns `telegram_chat_id` (the raw Telegram internal user identifier). The only consuming code visible in the reviewed frontend files checks `status.telegram_connected` — it does not use `telegram_chat_id`. Returning the raw internal identifier is unnecessary surface area even on an authenticated endpoint.

**Fix:** Remove `telegram_chat_id` from the response, or if it is needed by a client, document why:

```python
return {
    "telegram_connected": current_user.telegram_chat_id is not None,
}
```

---

_Reviewed: 2026-07-21T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
