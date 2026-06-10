---
phase: 03-tender-lookup
plan: 03
status: complete
completed: "2026-06-10"
visual_checkpoint: approved
---

# Plan 03-03 Summary — Wave 3: Frontend Vertical Slice

## What Was Done

- `api.ts` расширен методом `delete` с tolerant 204 (no body).
- `frontend/src/types/tender.ts` — интерфейсы `Tender`, `Lot`, `WatchlistEntry`.
- `StatusBadge.tsx` — цветовые пилюли (зелёный/серый/жёлтый) по `status_name_ru`.
- `TenderCard.tsx` — `<article>` с 6 полями, KZT-форматирование, список лотов.
- `WatchlistButton.tsx` — добавить/удалить с `aria-pressed`, hover-анимация.
- `/tenders/page.tsx` — поиск (RHF + zod), useQuery, not-found + error states.
- `DashboardWatchlist.tsx` — список отслеживаемых с empty state, compact WatchlistButton.
- `dashboard/page.tsx` — ссылка "Поиск тендеров" + `<DashboardWatchlist />`.
- `app/page.tsx` — редирект с `/` на `/dashboard`.

---

## Props Contracts

| Компонент | Ключевые props |
|-----------|---------------|
| `StatusBadge` | `statusName: string \| null` |
| `TenderCard` | `tender: Tender; children?: ReactNode` |
| `WatchlistButton` | `numberAnno, isWatching, onChange?, compact?` |
| `DashboardWatchlist` | (нет props — queryClient внутри) |

---

## isWatching + Cache Invalidation Flow

1. `/tenders/page.tsx` делает `useQuery(['watchlist'])` → GET /api/watchlist.
2. `isWatching = watchlist?.some(e => e.tender.number_anno === tender.number_anno)`.
3. `WatchlistButton.onChange` вызывает `queryClient.invalidateQueries({ queryKey: ['watchlist'] })`.
4. `DashboardWatchlist` подписан на тот же ключ `['watchlist']` — автоматически обновляется.

---

## Visual Checkpoint

**Статус: ✅ APPROVED (2026-06-10)**

Все 9 шагов верификации пройдены:
- TenderCard рендерит все 6 полей для реального тендера
- Неизвестный номер → "не найден" без краша
- Добавление/удаление в watchlist работает и персистентно
- Dashboard показывает watchlist с empty state

---

## Деплой-зависимости (обнаружены при тестировании)

| Зависимость | Причина | Решение |
|------------|---------|---------|
| Redis (localhost:6379) | `store_refresh_token` при регистрации/логине | `brew install redis && brew services start redis` |
| `JWT_SECRET` в `.env` | `create_access_token` | Сгенерирован и проставлен `openssl rand -hex 32` |
| `JWT_SECRET` в `frontend/.env.local` | Next.js middleware `jwtVerify` | `.env.local` создан |
