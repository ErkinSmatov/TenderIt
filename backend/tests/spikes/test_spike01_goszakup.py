"""
Smoke tests for SPIKE-01: goszakup.gov.kz v3 GraphQL API.

These tests run against the live goszakup endpoint.
They are SKIPPED when GOSZAKUP_API_TOKEN is not set — safe to run in CI
without a token (they simply report as skipped, not failed).

To run against the live API:
  cd backend && GOSZAKUP_API_TOKEN=your_token pytest tests/spikes/test_spike01_goszakup.py -v
"""

import json
import os

import httpx
import pytest

GRAPHQL_URL = "https://ows.goszakup.gov.kz/v3/graphql"
GOSZAKUP_TOKEN = os.environ.get("GOSZAKUP_API_TOKEN", "").strip()
HAS_TOKEN = bool(GOSZAKUP_TOKEN)

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
