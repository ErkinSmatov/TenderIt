"""
Smoke tests for SPIKE-01: goszakup.gov.kz v3 GraphQL API.

These tests run against the live goszakup endpoint.
They are SKIPPED when GOSZAKUP_API_TOKEN is not set — safe to run in CI
without a token (they simply report as skipped, not failed).

To run against the live API:
  cd backend && GOSZAKUP_API_TOKEN=your_token pytest tests/spikes/test_spike01_goszakup.py -v

To run the TrdBuy query spike with a real tender number:
  cd backend && GOSZAKUP_API_TOKEN=your_token TEST_TENDER_NUMBER=12345 pytest tests/spikes/test_spike01_goszakup.py::test_trdbuy_query_returns_tender -v
"""

import json
import os

import httpx
import pytest

GRAPHQL_URL = "https://ows.goszakup.gov.kz/v3/graphql"
GOSZAKUP_TOKEN = os.environ.get("GOSZAKUP_API_TOKEN", "").strip()
HAS_TOKEN = bool(GOSZAKUP_TOKEN)

# Provide a real open tender number via env var.
# Default falls back to a publicly documented sample number — may not be open.
TEST_TENDER_NUMBER = os.environ.get("TEST_TENDER_NUMBER", "").strip()

TRDBUY_QUERY = """
query TenderByNumber($numberAnno: String!) {
  TrdBuy(filter: { numberAnno: $numberAnno }, limit: 1) {
    id
    numberAnno
    nameRu
    nameKz
    totalSum
    countLots
    customerBin
    customerNameRu
    customerNameKz
    refBuyStatusId
    RefBuyStatus {
      id
      nameRu
      nameKz
      code
    }
    startDate
    endDate
    publishDate
    lastUpdateDate
    Lots {
      id
      lotNumber
      nameRu
      nameKz
      descriptionRu
      amount
      refLotStatusId
    }
  }
}
"""

FULL_INTROSPECTION_QUERY = """
{
  __schema {
    queryType { name }
    mutationType { name }
    types { name kind }
  }
}
"""


def _auth_headers() -> dict:
    return {
        "Authorization": f"Bearer {GOSZAKUP_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_TOKEN, reason="GOSZAKUP_API_TOKEN not set")
async def test_goszakup_endpoint_reachable():
    """
    The goszakup endpoint must be reachable and return an HTTP response.
    A 200 means fully authenticated; 401 means the endpoint is alive but
    the token is invalid. Both are acceptable for reachability confirmation.
    A connection error (ECONNREFUSED / timeout) is the only real failure.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            GRAPHQL_URL,
            json={"query": "{ __typename }"},
            headers=_auth_headers(),
        )

    # 200 = authenticated and reachable
    # 401 = endpoint is alive, auth rejected (token issue, not connectivity issue)
    assert response.status_code in (200, 401), (
        f"Expected 200 or 401 from {GRAPHQL_URL}, got {response.status_code}. "
        f"This may indicate a network outage or an unexpected API change."
    )


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_TOKEN, reason="GOSZAKUP_API_TOKEN not set")
async def test_goszakup_schema_introspectable():
    """
    With a valid token, schema introspection must succeed.
    The response must include 'data' with a non-null '__schema' object.
    This confirms that the API allows introspection (not disabled server-side)
    and that our auth flow works end-to-end.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            GRAPHQL_URL,
            json={"query": FULL_INTROSPECTION_QUERY},
            headers=_auth_headers(),
        )

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}. "
        f"Response: {response.text[:500]}"
    )

    body = response.json()
    assert "data" in body, f"No 'data' key in response: {json.dumps(body)[:500]}"

    schema = body["data"].get("__schema")
    assert schema is not None, (
        f"'__schema' is null in response — introspection may be disabled: "
        f"{json.dumps(body)[:500]}"
    )

    # queryType must always be present in a valid GraphQL schema
    assert schema.get("queryType") is not None, (
        "GraphQL schema has no queryType — this is invalid per the GraphQL spec."
    )


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_TOKEN, reason="GOSZAKUP_API_TOKEN not set")
@pytest.mark.skipif(not TEST_TENDER_NUMBER, reason="TEST_TENDER_NUMBER not set — provide a real tender number")
async def test_trdbuy_query_returns_tender():
    """
    Wave 0 spike: confirm TrdBuy GraphQL query works and record field formats.

    Run with:
      GOSZAKUP_API_TOKEN=<token> TEST_TENDER_NUMBER=<real_number> pytest tests/spikes/test_spike01_goszakup.py::test_trdbuy_query_returns_tender -v

    This test:
    - Confirms the token authenticates against the live endpoint
    - Records the real numberAnno string format
    - Records the real date string format (startDate / endDate / publishDate)
    - Records the refBuyStatusId integer value for the queried tender
    - Does NOT print or log the Bearer token value (CLAUDE.md directive)

    After the test passes, fill in backend/spikes/findings/SPIKE-01-GRAPHQL-FINDINGS.md
    with the printed field values. The refBuyStatusId value for status "Принимаются заявки"
    (open for applications) GATES Wave 1.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            GRAPHQL_URL,
            json={
                "query": TRDBUY_QUERY,
                "variables": {"numberAnno": TEST_TENDER_NUMBER},
            },
            headers=_auth_headers(),
        )

    assert response.status_code == 200, (
        f"Expected HTTP 200, got {response.status_code}. "
        f"Response body (first 500 chars): {response.text[:500]}"
    )

    body = response.json()
    assert "data" in body, f"No 'data' key in GraphQL response: {json.dumps(body)[:500]}"
    assert "TrdBuy" in body["data"], (
        f"No 'TrdBuy' key in response data. Full data keys: {list(body['data'].keys())}"
    )

    items = body["data"]["TrdBuy"]
    assert isinstance(items, list), f"TrdBuy must be a list, got: {type(items)}"

    # If no result — tender not found. This is not a test failure, but it means
    # TEST_TENDER_NUMBER does not match any tender on the portal.
    if not items:
        print(
            f"\n[SPIKE-01] TrdBuy query returned empty array for numberAnno={TEST_TENDER_NUMBER!r}. "
            "The tender may not exist or the number format may be wrong. "
            "Try a different TEST_TENDER_NUMBER."
        )
        # Still a valid response shape — do not raise here
        return

    tender = items[0]

    # Print field values for the developer to record in SPIKE-01-GRAPHQL-FINDINGS.md
    # IMPORTANT: token value is never printed — only tender data fields
    print("\n" + "=" * 60)
    print("[SPIKE-01] TrdBuy query result — copy to SPIKE-01-GRAPHQL-FINDINGS.md")
    print("=" * 60)
    print(f"  numberAnno (raw value)  : {tender.get('numberAnno')!r}")
    print(f"  refBuyStatusId          : {tender.get('refBuyStatusId')!r}")
    print(f"  RefBuyStatus.nameRu     : {tender.get('RefBuyStatus', {}).get('nameRu')!r}")
    print(f"  RefBuyStatus.code       : {tender.get('RefBuyStatus', {}).get('code')!r}")
    print(f"  startDate (raw string)  : {tender.get('startDate')!r}")
    print(f"  endDate   (raw string)  : {tender.get('endDate')!r}")
    print(f"  publishDate (raw string): {tender.get('publishDate')!r}")
    print(f"  totalSum                : {tender.get('totalSum')!r}")
    print(f"  countLots               : {tender.get('countLots')!r}")
    lots = tender.get("Lots") or []
    print(f"  Lots count              : {len(lots)}")
    print("=" * 60)

    # Redact customerBin (PII) for the sample output
    redacted = dict(tender)
    if "customerBin" in redacted:
        redacted["customerBin"] = "<REDACTED>"
    print("\n[SPIKE-01] Redacted sample response (safe to commit):")
    print(json.dumps(redacted, ensure_ascii=False, indent=2)[:2000])
    print("=" * 60 + "\n")

    # Basic structural assertions — the tender object must have the key fields
    assert tender.get("numberAnno") is not None, "TrdBuy item missing 'numberAnno' field"
    assert tender.get("refBuyStatusId") is not None, "TrdBuy item missing 'refBuyStatusId' field — this is the Wave 1 gate value"
