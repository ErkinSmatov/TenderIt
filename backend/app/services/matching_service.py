"""Matching service — pure async rule-based filter matching.

match_tenders_for_user: given a ClientFilter, returns IDs from new_tender_ids
that pass all active filter rules (AND logic across filter types).

Rules (all nullable fields default to "no filter"):
  - keywords: non-empty list → any keyword ILIKE matches name_ru OR name_kz
  - region: not None → tender.region == cf.region (exact match)
  - spgz_codes: non-empty list → tender.spgz_code IN cf.spgz_codes
  - min_amount: not None → tender.total_sum >= cf.min_amount
  - max_amount: not None → tender.total_sum <= cf.max_amount

Security:
  ILIKE uses SQLAlchemy parameterized queries — PostgreSQL % wildcard in ILIKE
  is a valid wildcard, not injectable (T-07-ilike: accepted risk).
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client_filter import ClientFilter
from app.models.tender import Tender


async def match_tenders_for_user(
    db: AsyncSession,
    user_id: int,
    cf: ClientFilter,
    new_tender_ids: list[int],
) -> list[int]:
    """Return tender_ids from new_tender_ids that match cf rules.

    Rules applied in AND logic across filter types (all active filters must pass):
    - keywords: cf.keywords is non-empty → OR-join ILIKE on name_ru + name_kz;
      empty list = no keyword filter (matches any tender)
    - region: cf.region is not None → exact match on tender.region
    - spgz_codes: cf.spgz_codes is non-empty → tender.spgz_code IN cf.spgz_codes
    - min_amount: cf.min_amount is not None → tender.total_sum >= cf.min_amount
    - max_amount: cf.max_amount is not None → tender.total_sum <= cf.max_amount

    Args:
        db: Async SQLAlchemy session (from ctx['db_session_factory'] in ARQ workers).
        user_id: Owning user ID (informational; not used in the query itself).
        cf: ClientFilter instance with the user's configured rules.
        new_tender_ids: IDs to evaluate (passed from poll_goszakup_discovery).

    Returns:
        List of tender IDs from new_tender_ids that satisfy all active filter rules.
        Empty list if new_tender_ids is empty or no tenders pass the filters.
    """
    if not new_tender_ids:
        return []

    stmt = select(Tender).where(Tender.id.in_(new_tender_ids))

    # Keyword filter: OR-join ILIKE across name_ru and name_kz.
    # Each keyword generates: (name_ru ILIKE '%kw%' OR name_kz ILIKE '%kw%')
    # The per-keyword clauses are then OR-joined: any keyword hit = match.
    if cf.keywords:
        keyword_clauses = [
            or_(
                Tender.name_ru.ilike(f"%{kw}%"),
                Tender.name_kz.ilike(f"%{kw}%"),
            )
            for kw in cf.keywords
        ]
        stmt = stmt.where(or_(*keyword_clauses))

    # Region filter: exact string match (e.g. "Алматы").
    # None = no region filter.
    if cf.region is not None:
        stmt = stmt.where(Tender.region == cf.region)

    # СПГЗ code filter: tender.spgz_code must be in the user's code list.
    # Empty list = no СПГЗ filter.
    if cf.spgz_codes:
        stmt = stmt.where(Tender.spgz_code.in_(cf.spgz_codes))

    # Amount range filters (both independent; NULL = no bound).
    if cf.min_amount is not None:
        stmt = stmt.where(Tender.total_sum >= cf.min_amount)
    if cf.max_amount is not None:
        stmt = stmt.where(Tender.total_sum <= cf.max_amount)

    result = await db.execute(stmt)
    return [t.id for t in result.scalars().all()]
