# SPIKE-01: goszakup GraphQL API Findings

**Date:** <!-- Fill: e.g. 2026-06-10 -->
**Token obtained:** 2026-06-09 (1-year validity)
**Endpoint:** `https://ows.goszakup.gov.kz/v3/graphql`
**Test tender number used:** <!-- Fill: the value of TEST_TENDER_NUMBER you used -->

> **Wave 1 gate:** The `refBuyStatusId` value for "Принимаются заявки" (open for applications)
> in the **refBuyStatusId Reference** section below MUST be filled before Wave 1 begins.
> Phase 5 ARQ polling logic depends on this value to detect when a tender opens.

---

## Token Status

<!-- Fill one of: -->
- [ ] Confirmed working — HTTP 200 returned, TrdBuy data in response
- [ ] Token rejected — HTTP 401 received (check GOSZAKUP_API_TOKEN env var)
- [ ] Endpoint unreachable — network error

**Notes:** <!-- Any auth errors, timeouts, or unusual behaviour observed -->

---

## Real numberAnno Format

**Raw value returned by API:** <!-- Fill: e.g. "123456" or "RU-2025-123456-000001-1" -->

**Is it purely numeric?** <!-- Yes / No -->
**Does it have a prefix?** <!-- Yes (describe) / No -->
**Max length observed:** <!-- e.g. 12 characters -->

**Validation implication:**
The current decision (03-CONTEXT.md §3) accepts any non-empty string ≤ 100 chars with whitespace stripped.
If the format is more constrained, update this finding — Wave 1 may add a stricter validator.

---

## Date String Format

Raw values from a real TrdBuy response:

| Field | Raw string value | Format |
|-------|-----------------|--------|
| `startDate` | <!-- Fill: e.g. "2025-06-01T00:00:00.000Z" --> | <!-- ISO-8601 / Unix / Other --> |
| `endDate` | <!-- Fill --> | <!-- --> |
| `publishDate` | <!-- Fill --> | <!-- --> |
| `lastUpdateDate` | <!-- Fill (if present) --> | <!-- --> |

**Timezone:** <!-- UTC / Asia/Almaty (UTC+5) / Naive (no tz info) -->

**Parsing implication:**
If dates are ISO-8601 strings with timezone, `datetime.fromisoformat()` (Python 3.11+) handles them.
If they are naive (no tz suffix), a `+05:00` offset should be applied before storing as TIMESTAMPTZ.
Document the exact format here so the Wave 1 Pydantic `@field_validator` is correct.

---

## refBuyStatusId Reference

> **THIS TABLE GATES WAVE 1.** Record all status values observed.

| `refBuyStatusId` | `RefBuyStatus.nameRu` | `RefBuyStatus.code` | Meaning |
|------------------|-----------------------|---------------------|---------|
| <!-- e.g. 1 --> | <!-- e.g. "Принимаются заявки" --> | <!-- e.g. "ACCEPTING" --> | <!-- Open for applications — MARK THIS ROW --> |
| | | | |
| | | | |

**Value for "Принимаются заявки" (open for applications):** `refBuyStatusId = ____`

> This is the value Phase 5 ARQ polling will compare against `status_id` in the `tenders` table
> to detect when a watched tender transitions to the open state and trigger notifications.

**How to find all status values:**
- The tender you queried has one status. To find others, try tenders in different states,
  or call `GET https://ows.goszakup.gov.kz/v3/ref/buy-statuses` if that endpoint exists.
- Alternatively, introspect the `RefBuyStatus` type via GraphQL schema introspection.

---

## Redacted Sample Response

> **PII redaction required before committing:**
> Replace `customerBin` value with `"<REDACTED>"`.
> Do not include any IIN, passport data, or personal names.
> The API auth token must NEVER appear in this file.

```json
{
  "data": {
    "TrdBuy": [
      {
        "id": null,
        "numberAnno": "<!-- Fill -->",
        "nameRu": "<!-- Fill -->",
        "nameKz": null,
        "totalSum": null,
        "countLots": null,
        "customerBin": "<REDACTED>",
        "customerNameRu": "<!-- Fill -->",
        "customerNameKz": null,
        "refBuyStatusId": null,
        "RefBuyStatus": {
          "id": null,
          "nameRu": "<!-- Fill -->",
          "nameKz": null,
          "code": "<!-- Fill -->"
        },
        "startDate": "<!-- Fill raw string -->",
        "endDate": "<!-- Fill raw string -->",
        "publishDate": "<!-- Fill raw string -->",
        "lastUpdateDate": "<!-- Fill raw string if present -->",
        "Lots": []
      }
    ]
  }
}
```

---

## Open Questions After Spike

<!-- Fill any remaining unknowns after running the test -->

- [ ] Are there additional `refBuyStatusId` values beyond what this tender showed?
- [ ] Do dates use Kazakhstan local time (UTC+5) or UTC?
- [ ] What is the typical `numberAnno` format observed in the wild?

---

## Sign-Off

- [ ] All five sections above are filled
- [ ] `refBuyStatusId` for "Принимаются заявки" is recorded
- [ ] `customerBin` is redacted in the sample response
- [ ] No auth token value appears anywhere in this file
- [ ] Wave 1 is unblocked
