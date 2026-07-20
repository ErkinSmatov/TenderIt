# Phase 6: Notifications — Pattern Map

**Mapped:** 2026-07-20
**Files analyzed:** 9 new/modified files
**Analogs found:** 9 / 9

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/routers/notifications.py` | router | request-response | `backend/app/routers/tenders.py` | exact |
| `backend/alembic/versions/0008_add_telegram_link_token.py` | migration | CRUD | `backend/alembic/versions/0004_create_applications.py` | exact |
| `backend/app/routers/telegram_webhook.py` | router (extend) | event-driven | self (extend in-place) | self |
| `backend/app/models/user.py` | model (extend) | CRUD | self (extend in-place) | self |
| `backend/app/config.py` | config (extend) | — | self (extend in-place) | self |
| `backend/app/main.py` | config (extend) | — | self (extend in-place) | self |
| `frontend/src/app/(dashboard)/settings/notifications/page.tsx` | page | request-response + polling | `frontend/src/app/(dashboard)/profile/page.tsx` | exact |
| `frontend/src/components/notifications/TelegramConnectCard.tsx` | component | request-response + polling | `frontend/src/components/tenders/DashboardWatchlist.tsx` | role-match |
| `frontend/src/components/notifications/WatchlistSettingsTable.tsx` | component | CRUD | `frontend/src/components/tenders/DashboardWatchlist.tsx` | exact |
| `frontend/src/components/layout/Sidebar.tsx` | layout (extend) | — | self (extend in-place) | self |

---

## Pattern Assignments

### `backend/app/routers/notifications.py` (router, request-response)

**Analog:** `backend/app/routers/tenders.py`

**Imports pattern** (tenders.py lines 1–29):
```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models.user import User

router = APIRouter()
```

**What to add:** `import secrets`, `from datetime import datetime, timezone, timedelta`, `from app.config import settings`.

**Auth pattern** (tenders.py lines 35–38, 54–57, 79–82, 99–102 — all routes):
```python
async def some_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
```
Every endpoint in tenders.py uses `Depends(get_current_user)` as the first dependency. Copy the same pattern for all three notifications endpoints.

**Core CRUD pattern — DELETE returning 204** (tenders.py lines 79–96):
```python
@router.delete("/watchlist/{number_anno}", status_code=204)
async def remove_watchlist_entry(
    number_anno: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    removed = await remove_from_watchlist(db, current_user.id, number_anno.strip())
    if not removed:
        raise HTTPException(
            status_code=404,
            detail=f"Тендер {number_anno} не найден в вашем списке отслеживания",
        )
    return Response(status_code=204)
```
Copy `-> Response` return type + `return Response(status_code=204)` pattern for `DELETE /notifications/telegram`.

**What to change vs tenders.py:**
- No `response_model=` schemas needed — notifications endpoints return plain dicts or 204.
- No service layer — all DB mutations happen directly in the endpoint (simple enough).
- Add `secrets.token_urlsafe(32)` + `datetime.now(timezone.utc) + timedelta(minutes=15)` in POST handler.
- `deep_link = f"https://t.me/{settings.telegram_bot_username}?start={token}"` — uses new config field.

---

### `backend/alembic/versions/0008_add_telegram_link_token.py` (migration, CRUD)

**Analog:** `backend/alembic/versions/0004_create_applications.py`

**Header pattern** (0004 lines 31–41):
```python
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```
**For 0008:** `revision = "0008"`, `down_revision = "0007"`. No `postgresql` dialect import needed (no JSONB/ARRAY).

**add_column on users pattern** (0004 lines 45–49):
```python
def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True),
    )
```

**What to copy for 0008 upgrade():**
```python
def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("telegram_link_token", sa.String(64), nullable=True),
    )
    op.create_index(
        "idx_users_telegram_link_token",
        "users",
        ["telegram_link_token"],
        unique=True,
    )
    op.add_column(
        "users",
        sa.Column(
            "telegram_link_token_expires_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
```

**downgrade pattern** (0004 lines 114–118):
```python
def downgrade() -> None:
    op.drop_table("applications")
    op.drop_column("users", "telegram_chat_id")
```
**For 0008 downgrade():** drop in reverse order — drop `telegram_link_token_expires_at`, then drop index, then drop `telegram_link_token`.

---

### `backend/app/routers/telegram_webhook.py` (extend in-place, event-driven)

**Insertion point** (telegram_webhook.py lines 127–130):
```python
    if not update.callback_query:
        # Non-callback update (e.g. plain message) — accept silently
        return {"ok": True}
```

**What to insert before `return {"ok": True}`:**
```python
    if not update.callback_query:
        # Phase 6: handle /start TOKEN message for Telegram account linking (NOTIF-04)
        if update.message and update.message.text:
            await _handle_start_command(update.message, db)
        return {"ok": True}
```

**New helper function — add above the endpoint (before line 108):**
Uses the existing `async with telegram.Bot(settings.telegram_bot_token) as bot` pattern from lines 227–230:
```python
async with telegram.Bot(settings.telegram_bot_token) as bot:
    await bot.answer_callback_query(callback_query_id=query.id)
```
The new `_handle_start_command` reuses the same `async with telegram.Bot(...)` context manager for `bot.send_message()`.

**Security invariants to preserve:**
- Line 121–123: `X-Telegram-Bot-Api-Secret-Token` guard MUST remain as the FIRST check — all new code runs after it automatically.
- `bot=None` in `Update.de_json(body, bot=None)` (line 126) is correct — do not change.
- Existing `confirm` and `disc` branches (lines 141–230) — do NOT touch.

**Token parsing pattern** (from RESEARCH.md, verified against PTB source):
```python
text = message.text or ""
if not text.startswith("/start "):   # 7 chars: "/start " — space mandatory
    return
token = text[7:].strip()
if not token:
    return
```
Do NOT use `text.split()[1]` (IndexError) or `context.args` (unavailable in raw webhook mode).

---

### `backend/app/models/user.py` (extend in-place, CRUD)

**Existing field pattern** (user.py lines 22–23):
```python
# Phase 5 (D-05-06): Telegram chat ID for submission notification flow
telegram_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
```

**What to append after `telegram_chat_id` field:**
```python
# Phase 6 (D-09): Telegram deep-link token for account linking flow (NOTIF-04)
telegram_link_token: Mapped[Optional[str]] = mapped_column(
    String(64), nullable=True, unique=True, index=True
)
telegram_link_token_expires_at: Mapped[Optional[datetime]] = mapped_column(
    sa.TIMESTAMP(timezone=True), nullable=True
)
```

**Existing imports that already cover needs** (user.py lines 1–9):
```python
from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base
```
Need to add `import sqlalchemy as sa` for `sa.TIMESTAMP`. `String` is already imported.

---

### `backend/app/config.py` (extend in-place)

**Existing Telegram settings block** (config.py lines 32–35):
```python
# Phase 5: Telegram bot for tender-open notifications + confirm flow (D-05-06)
telegram_bot_token: str = ""
webhook_base_url: str = "http://localhost:8000"
telegram_webhook_secret: str = ""
```

**What to append after `telegram_webhook_secret`:**
```python
# Phase 6: Telegram bot username for deep-link generation (NOTIF-04)
# Set TELEGRAM_BOT_USERNAME env var. Empty default → deep_link broken but non-fatal in dev.
telegram_bot_username: str = ""
```

---

### `backend/app/main.py` (extend in-place)

**Existing router import pattern** (main.py lines 13–16):
```python
from app.routers import auth, company, documents, health, tenders
from app.routers import applications, goszakup_proxy
from app.routers import telegram_webhook
from app.routers import discovery
```

**What to add:** `from app.routers import notifications` — append to line 16 or as a new line after `discovery`.

**Existing include_router pattern** (main.py lines 76–84):
```python
application.include_router(tenders.router, prefix="/api", tags=["tenders"])
application.include_router(documents.router, prefix="/api", tags=["documents"])
application.include_router(applications.router, prefix="/api", tags=["applications"])
application.include_router(goszakup_proxy.router, prefix="/api/goszakup", tags=["goszakup-proxy"])
application.include_router(telegram_webhook.router, prefix="/api", tags=["telegram"])
application.include_router(discovery.router, prefix="/api", tags=["discovery"])
```

**What to append after discovery:**
```python
application.include_router(notifications.router, prefix="/api", tags=["notifications"])
```

---

### `frontend/src/app/(dashboard)/settings/notifications/page.tsx` (page, request-response + polling)

**Analog:** `frontend/src/app/(dashboard)/profile/page.tsx`

**Page shell pattern** (profile/page.tsx lines 1–54):
```tsx
'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'

export default function ProfilePage() {
  // ...state...
  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-semibold">Профиль компании</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Данные вашей организации для тендерных заявок
        </p>
      </div>
      {/* child components */}
    </div>
  )
}
```

**Copy the outer `div` structure exactly** (`space-y-6 max-w-2xl` + `h1` + `p.text-muted-foreground`). This matches every other settings-style page in the dashboard.

**What to change vs profile/page.tsx:**
- Use `useQuery` from `@tanstack/react-query` instead of `useEffect` + `useState` (polling requirement).
- Add `pollingActive` state + `timeoutRef` for conditional polling (see Pattern 5 in RESEARCH.md).
- Render `<TelegramConnectCard />` and `<WatchlistSettingsTable />` as children — no inline form.

**React Query polling pattern** (applications/[id]/page.tsx lines 84–89):
```tsx
const { data: application, error, isLoading } = useQuery<ApplicationResponse>({
  queryKey: ['application', id],
  queryFn: () => api.get<ApplicationResponse>(`/api/applications/${id}`),
  refetchInterval: 30000,
  retry: false,
})
```
For notifications page: change `refetchInterval` from a constant to a function (v5 conditional polling):
```tsx
refetchInterval: (query) => {
  if (!pollingActive) return false
  if (query.state.data?.telegram_connected) return false
  return 3000
},
```
**Critical:** `(query) => ...` is React Query **v5** syntax. Do NOT use `(data, error) => ...` (v4 — will fail with `^5.100.14`).

---

### `frontend/src/components/notifications/TelegramConnectCard.tsx` (component, request-response + polling)

**Analog:** `frontend/src/components/tenders/DashboardWatchlist.tsx`

**Card shell pattern** (DashboardWatchlist.tsx lines 34–93):
```tsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

return (
  <section aria-labelledby="watchlist-heading">
    <Card>
      <CardHeader>
        <CardTitle id="watchlist-heading" className="flex items-center gap-2">
          <BookmarkIcon className="h-4 w-4 text-primary" aria-hidden="true" />
          Отслеживаемые тендеры
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* states: loading, empty, filled */}
      </CardContent>
    </Card>
  </section>
)
```
Copy the `Card` / `CardHeader` / `CardTitle` / `CardContent` structure with icon + `aria-labelledby`.

**Mutation pattern** (TenderMatchCard.tsx lines 42–54):
```tsx
import { useMutation, useQueryClient } from '@tanstack/react-query'

const skipMutation = useMutation({
  mutationFn: () => api.post<{ ok: boolean }>(`/api/discovery/${match.id}/skip`, {}),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['discovery-matches'] })
  },
})
```
For disconnect: `useMutation` with `mutationFn: () => api.delete('/api/notifications/telegram')` + `onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notification-status'] })`.

**Button disabled/loading pattern** (TenderMatchCard.tsx lines 113–122):
```tsx
<button
  onClick={() => participateMutation.mutate()}
  disabled={participateMutation.isPending}
  className={cn(buttonVariants({ size: 'sm' }), 'disabled:opacity-50')}
>
  {participateMutation.isPending ? 'Подождите...' : 'Участвуем'}
</button>
```
Copy `disabled={mutation.isPending}` + ternary label pattern for both "Подключить" and "Отключить" buttons.

**Alert component for feedback** (CompanyProfileForm.tsx lines 123–133):
```tsx
import { Alert } from '@/components/ui/alert'

{apiError && (
  <Alert className="text-destructive border-destructive/50 bg-destructive/10 text-xs py-2">
    {apiError}
  </Alert>
)}
```
Reuse `Alert` with the same className pattern for error states.

**What to change vs DashboardWatchlist.tsx:**
- The component owns the `useQuery` for `['notification-status']` + polling state (`pollingActive`, `timeoutRef`).
- Two conditional renders: connected state (chat_id set) shows "Telegram подключён ✓" + disconnect button; disconnected state shows connect button (or deep-link + polling UI after click).
- Connect click: `api.post('/api/notifications/telegram/link-token', {})` → `setDeepLink(result.deep_link)` → `setPollingActive(true)`.
- No `queryClient.invalidateQueries` needed after connect — polling detects `telegram_connected: true` and stops naturally.

---

### `frontend/src/components/notifications/WatchlistSettingsTable.tsx` (component, CRUD)

**Analog:** `frontend/src/components/tenders/DashboardWatchlist.tsx` (exact match)

**Full pattern to copy** (DashboardWatchlist.tsx lines 22–94):
```tsx
const queryClient = useQueryClient()

const { data: entries, isLoading } = useQuery<WatchlistEntry[]>({
  queryKey: ['watchlist'],
  queryFn: () => api.get<WatchlistEntry[]>('/api/watchlist'),
  retry: false,
})

const invalidate = () =>
  queryClient.invalidateQueries({ queryKey: ['watchlist'] })
```
Copy the `useQuery` + `queryClient.invalidateQueries` pattern verbatim. Same `queryKey: ['watchlist']` — shares cache with DashboardWatchlist.

**Row render pattern** (DashboardWatchlist.tsx lines 60–89):
```tsx
{entries.map((entry) => (
  <div
    key={entry.tender.number_anno}
    className="flex items-center justify-between px-4 py-3"
  >
    <div className="flex flex-col gap-0.5 min-w-0 mr-4">
      <span className="text-sm font-medium truncate">
        {entry.tender.name_ru ?? entry.tender.number_anno}
      </span>
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground font-mono">
          {entry.tender.number_anno}
        </span>
        <StatusBadge statusName={entry.tender.status_name_ru} />
      </div>
    </div>
    <div className="shrink-0">
      <WatchlistButton numberAnno={entry.tender.number_anno} isWatching onChange={invalidate} compact />
    </div>
  </div>
))}
```

**What to change:** Replace `<WatchlistButton ... compact />` with a plain "Удалить" button that calls `DELETE /api/watchlist/{number_anno}` directly (D-02: no toggle, only delete). Use `useMutation` pattern from TenderMatchCard.tsx (lines 50–54). After delete success, call `invalidate()`.

---

### `frontend/src/components/layout/Sidebar.tsx` (extend in-place)

**Current navItems array** (Sidebar.tsx lines 4–18):
```tsx
import { LayoutDashboard, Search, Building2, FileText, ClipboardList, LogOut, Sparkles, ExternalLink } from 'lucide-react'

const navItems = [
  { href: '/dashboard', label: 'Обзор', icon: LayoutDashboard },
  { href: '/tenders', label: 'Тендеры', icon: Search },
  { href: '/applications', label: 'Заявки', icon: ClipboardList },
  { href: '/discovery', label: 'Подборка', icon: Sparkles },
  { href: '/profile', label: 'Профиль', icon: Building2 },
  { href: '/documents', label: 'Документы', icon: FileText },
]
```

**Two-part change:**

1. Add `Bell` to the import (Sidebar.tsx line 4):
```tsx
// BEFORE:
import { LayoutDashboard, Search, Building2, FileText, ClipboardList, LogOut, Sparkles, ExternalLink } from 'lucide-react'
// AFTER:
import { LayoutDashboard, Search, Building2, FileText, ClipboardList, LogOut, Sparkles, ExternalLink, Bell } from 'lucide-react'
```

2. Append to navItems array after `{ href: '/documents', ... }` (line 17):
```tsx
{ href: '/settings/notifications', label: 'Настройки', icon: Bell },
```

Final navItems order: Обзор, Тендеры, Заявки, Подборка, Профиль, Документы, **Настройки**.

**Nav item render pattern** (Sidebar.tsx lines 45–63 — unchanged, works automatically):
```tsx
{navItems.map(({ href, label, icon: Icon }) => {
  const isActive = pathname === href
  return (
    <Link
      key={href}
      href={href}
      className={cn(
        'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
        isActive
          ? 'bg-sidebar-accent text-sidebar-accent-foreground'
          : 'text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
      )}
      aria-current={isActive ? 'page' : undefined}
    >
      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
      {label}
    </Link>
  )
})}
```
No changes to the render loop — the new nav item is picked up automatically.

---

## Shared Patterns

### JWT Authentication (all backend endpoints)
**Source:** `backend/app/routers/tenders.py` lines 35–38
**Apply to:** All three endpoints in `notifications.py`
```python
current_user: User = Depends(get_current_user),
db: AsyncSession = Depends(get_db),
```
`get_current_user` raises `401` automatically if JWT is absent/invalid. No additional auth code needed.

### Webhook Secret Guard (telegram_webhook.py extension)
**Source:** `backend/app/routers/telegram_webhook.py` lines 121–123
**Apply to:** The extension code runs AFTER this guard — no additional protection needed.
```python
incoming_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
if incoming_secret != settings.telegram_webhook_secret:
    raise HTTPException(status_code=403, detail="Forbidden")
```
The new `_handle_start_command` helper is called from inside the guarded handler, so it inherits this protection automatically (T-05-31 invariant preserved).

### Async Bot Context Manager (telegram_webhook.py → _handle_start_command)
**Source:** `backend/app/routers/telegram_webhook.py` lines 227–230
**Apply to:** `_handle_start_command` helper in telegram_webhook.py
```python
async with telegram.Bot(settings.telegram_bot_token) as bot:
    await bot.answer_callback_query(callback_query_id=query.id)
```
Replace `answer_callback_query` with `send_message(chat_id=..., text=...)`.

### React Query `useQuery` + `api.get` (all frontend data-fetching)
**Source:** `frontend/src/app/(dashboard)/applications/[id]/page.tsx` lines 84–89
**Apply to:** `TelegramConnectCard.tsx`, `WatchlistSettingsTable.tsx`, `notifications/page.tsx`
```tsx
const { data, error, isLoading } = useQuery<T>({
  queryKey: ['some-key'],
  queryFn: () => api.get<T>('/api/some/endpoint'),
  retry: false,
})
```

### `useMutation` + `invalidateQueries` (all frontend mutations)
**Source:** `frontend/src/components/discovery/TenderMatchCard.tsx` lines 42–54
**Apply to:** `TelegramConnectCard.tsx` (disconnect), `WatchlistSettingsTable.tsx` (delete)
```tsx
const mutation = useMutation({
  mutationFn: () => api.post/delete(...),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['relevant-key'] })
  },
})
```

### `Card` / `CardHeader` / `CardContent` Shell (all settings components)
**Source:** `frontend/src/components/tenders/DashboardWatchlist.tsx` lines 34–43
**Apply to:** `TelegramConnectCard.tsx`, `WatchlistSettingsTable.tsx`
```tsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
// ...
<Card>
  <CardHeader>
    <CardTitle className="flex items-center gap-2">
      <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
      Title
    </CardTitle>
  </CardHeader>
  <CardContent>
    {/* content */}
  </CardContent>
</Card>
```

### `Alert` Feedback Component (error / success states)
**Source:** `frontend/src/components/profile/CompanyProfileForm.tsx` lines 123–133
**Apply to:** `TelegramConnectCard.tsx`
```tsx
import { Alert } from '@/components/ui/alert'

{error && (
  <Alert className="text-destructive border-destructive/50 bg-destructive/10 text-xs py-2">
    {error}
  </Alert>
)}
```

---

## No Analog Found

All files have close analogs. No entries in this section.

---

## Metadata

**Analog search scope:** `backend/app/routers/`, `backend/alembic/versions/`, `backend/app/models/`, `backend/app/`, `frontend/src/app/(dashboard)/`, `frontend/src/components/`
**Files scanned:** 14
**Pattern extraction date:** 2026-07-20
