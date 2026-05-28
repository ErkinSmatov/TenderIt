"""
SPIKE-01: Verify goszakup.gov.kz v3 GraphQL API

Executes all SPIKE-01 measurements in sequence:
  Step 1 — Endpoint reachability check (simple __typename query)
  Step 2 — Full schema introspection (saves spike-01-schema.json)
  Step 3 — TrdBuy live query with tenacity retry (saves spike-01-trdbuy-sample.json)
  Step 4 — Rate limit probe: 15 requests, 1 per second (saves spike-01-rate-limit-probe.json)

Usage:
  cd backend && GOSZAKUP_API_TOKEN=your_token python -m spikes.spike_goszakup

Token source: https://goszakup.gov.kz/ru/developer/ows_v3
The script reads the token from the GOSZAKUP_API_TOKEN environment variable.
Never hardcode tokens — they are secrets (T-02-01 in threat model).
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GRAPHQL_URL = "https://ows.goszakup.gov.kz/v3/graphql"
FINDINGS_DIR = Path(__file__).parent / "findings"

FULL_INTROSPECTION_QUERY = """
{
  __schema {
    queryType {
      name
      fields {
        name
        description
        type {
          name
          kind
          ofType {
            name
            kind
          }
        }
      }
    }
    mutationType {
      name
      fields {
        name
        description
        args {
          name
          type {
            name
            kind
            ofType {
              name
              kind
            }
          }
        }
      }
    }
    subscriptionType {
      name
    }
    types {
      name
      kind
      description
      fields {
        name
        description
        type {
          name
          kind
          ofType {
            name
            kind
          }
        }
      }
    }
  }
}
"""

TRDBUY_QUERY = """
{
  TrdBuy(limit: 5) {
    id
    nameRu
    statusRu
    publishDate
  }
}
"""

RATE_PROBE_QUERY = """
{
  TrdBuy(limit: 1) {
    id
  }
}
"""


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _headers(token: str) -> dict:
    """Build request headers. Token is sent as Bearer — never printed to stdout."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _separator(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Step 1: Endpoint reachability
# ---------------------------------------------------------------------------

async def step1_reachability(client: httpx.AsyncClient, token: str) -> bool:
    """POST {__typename} — verify the endpoint is alive and responds to Bearer auth."""
    _separator("STEP 1: Endpoint Reachability")
    payload = {"query": "{ __typename }"}
    t0 = time.monotonic()
    try:
        response = await client.post(GRAPHQL_URL, json=payload, headers=_headers(token))
    except httpx.ConnectError as exc:
        print(f"ECONNREFUSED — could not reach {GRAPHQL_URL}: {exc}")
        print("Check your internet connection or VPN settings.")
        sys.exit(1)

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    print(f"HTTP status : {response.status_code}")
    print(f"Response time: {elapsed_ms} ms")

    try:
        body = response.json()
        is_json = True
    except Exception:
        body = response.text
        is_json = False

    print(f"Valid JSON  : {is_json}")

    if response.status_code == 200:
        print("Result: REACHABLE and AUTHENTICATED")
        return True
    elif response.status_code == 401:
        print(f"Result: REACHABLE but NOT AUTHENTICATED (401)")
        print(f"Response body: {json.dumps(body, ensure_ascii=False, indent=2) if is_json else body}")
        print(
            "\nERROR: The GOSZAKUP_API_TOKEN you provided was rejected (401 Unauthorized).\n"
            "Obtain a valid token at: https://goszakup.gov.kz/ru/developer/ows_v3\n"
        )
        sys.exit(1)
    elif response.status_code == 403:
        print(f"Result: REACHABLE but FORBIDDEN (403)")
        print(f"Response body: {json.dumps(body, ensure_ascii=False, indent=2) if is_json else body}")
        print(
            "\nERROR: Token is valid but this account lacks API access (403 Forbidden).\n"
            "Contact АО 'Центр Электронных Финансов' to enable API access for your account.\n"
        )
        sys.exit(1)
    else:
        print(f"Unexpected status {response.status_code}:")
        print(json.dumps(body, ensure_ascii=False, indent=2) if is_json else body)
        print(f"\nERROR: Unexpected response from goszakup API (status={response.status_code}). Cannot continue.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Step 2: Full schema introspection
# ---------------------------------------------------------------------------

async def step2_introspection(client: httpx.AsyncClient, token: str) -> dict:
    """Run the full GraphQL introspection query and save the result."""
    _separator("STEP 2: Full Schema Introspection")

    payload = {"query": FULL_INTROSPECTION_QUERY}
    t0 = time.monotonic()
    response = await client.post(GRAPHQL_URL, json=payload, headers=_headers(token))
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    print(f"HTTP status : {response.status_code}")
    print(f"Response time: {elapsed_ms} ms")

    body = response.json()

    if "errors" in body and body["errors"]:
        print(f"GraphQL errors: {json.dumps(body['errors'], ensure_ascii=False, indent=2)}")
        if "data" not in body or body.get("data") is None:
            print("ERROR: Introspection returned only errors, no data. Cannot proceed.")
            sys.exit(1)

    schema = body.get("data", {}).get("__schema", {})

    # Save full schema
    FINDINGS_DIR.mkdir(parents=True, exist_ok=True)
    schema_path = FINDINGS_DIR / "spike-01-schema.json"
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(body, f, indent=2, ensure_ascii=False)
    print(f"\nFull schema saved → {schema_path}")

    # Print summary
    query_type = schema.get("queryType")
    mutation_type = schema.get("mutationType")
    all_types = schema.get("types", [])

    if query_type:
        fields = query_type.get("fields") or []
        print(f"\nqueryType: {query_type.get('name')}")
        print(f"  Root query fields ({len(fields)}):")
        for f in fields:
            print(f"    - {f['name']}")
    else:
        print("\nqueryType: NOT PRESENT (unexpected — GraphQL requires a query type)")

    if mutation_type:
        mut_fields = mutation_type.get("fields") or []
        print(f"\nmutationType: {mutation_type.get('name')} ← MUTATIONS AVAILABLE")
        print(f"  Mutation fields ({len(mut_fields)}):")
        for f in mut_fields:
            print(f"    - {f['name']}")
    else:
        print("\nmutationType: NOT PRESENT")
        print("  → Programmatic tender submission via GraphQL mutation is NOT possible.")
        print("  → Phase 5 must use an alternative approach (browser automation or undocumented REST).")

    object_types = [t for t in all_types if t.get("kind") == "OBJECT" and not t["name"].startswith("__")]
    print(f"\nOBJECT types ({len(object_types)}):")
    for t in object_types:
        print(f"  - {t['name']}")

    return schema


# ---------------------------------------------------------------------------
# Step 3: TrdBuy live query (with retry)
# ---------------------------------------------------------------------------

@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
async def _trdbuy_request(client: httpx.AsyncClient, token: str) -> httpx.Response:
    return await client.post(GRAPHQL_URL, json={"query": TRDBUY_QUERY}, headers=_headers(token))


async def step3_trdbuy(client: httpx.AsyncClient, token: str) -> None:
    """POST TrdBuy(limit: 5) and save the sample response."""
    _separator("STEP 3: TrdBuy Live Query")

    t0 = time.monotonic()
    response = await _trdbuy_request(client, token)
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    print(f"HTTP status : {response.status_code}")
    print(f"Response time: {elapsed_ms} ms")

    body = response.json()

    # Save full response
    sample_path = FINDINGS_DIR / "spike-01-trdbuy-sample.json"
    with open(sample_path, "w", encoding="utf-8") as f:
        json.dump(body, f, indent=2, ensure_ascii=False)
    print(f"TrdBuy sample saved → {sample_path}")

    data = body.get("data", {})
    items = data.get("TrdBuy") if data else None
    if items:
        print(f"\nFirst item returned:")
        print(json.dumps(items[0], ensure_ascii=False, indent=2))
    else:
        print(f"\nNo TrdBuy items in response.")
        if "errors" in body:
            print(f"Errors: {json.dumps(body['errors'], ensure_ascii=False, indent=2)}")


# ---------------------------------------------------------------------------
# Step 4: Rate limit probe
# ---------------------------------------------------------------------------

async def step4_rate_limit(client: httpx.AsyncClient, token: str) -> None:
    """Send 15 requests 1 second apart; record status codes and rate-limit headers."""
    _separator("STEP 4: Rate Limit Probe (15 requests, 1 req/sec)")

    results = []
    hit_429 = False

    for i in range(1, 16):
        t0 = time.monotonic()
        try:
            response = await client.post(
                GRAPHQL_URL,
                json={"query": RATE_PROBE_QUERY},
                headers=_headers(token),
            )
        except httpx.RequestError as exc:
            print(f"  Request {i:02d}: ERROR — {exc}")
            results.append({"request": i, "status": "ERROR", "error": str(exc)})
            break

        elapsed_ms = int((time.monotonic() - t0) * 1000)

        rl_headers = {
            k: v
            for k, v in response.headers.items()
            if k.lower().startswith(("x-ratelimit", "retry-after"))
        }

        record = {
            "request": i,
            "status": response.status_code,
            "elapsed_ms": elapsed_ms,
            "rate_limit_headers": rl_headers,
        }
        results.append(record)

        status_str = f"{response.status_code}"
        rl_str = f"  headers={rl_headers}" if rl_headers else ""
        print(f"  Request {i:02d}: {status_str} ({elapsed_ms} ms){rl_str}")

        if response.status_code == 429:
            print(f"\n  *** 429 TOO MANY REQUESTS triggered at request {i} ***")
            try:
                body_429 = response.json()
            except Exception:
                body_429 = response.text
            record["response_body"] = body_429
            print(f"  Response body: {json.dumps(body_429, ensure_ascii=False, indent=2) if isinstance(body_429, dict) else body_429}")
            hit_429 = True
            break

        # 1-second inter-request pause (T-02-03 mitigation — do not hammer the API)
        if i < 15:
            await asyncio.sleep(1.0)

    if not hit_429:
        print(f"\n  No 429 observed in {len(results)} requests.")

    # Save results
    probe_path = FINDINGS_DIR / "spike-01-rate-limit-probe.json"
    with open(probe_path, "w", encoding="utf-8") as f:
        json.dump({"results": results, "hit_429": hit_429}, f, indent=2, ensure_ascii=False)
    print(f"\nRate limit probe results saved → {probe_path}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def spike_goszakup() -> None:
    """Run the full SPIKE-01 sequence."""
    token = os.environ.get("GOSZAKUP_API_TOKEN", "").strip()
    if not token:
        print(
            "ERROR: GOSZAKUP_API_TOKEN environment variable is not set.\n"
            "\n"
            "Obtain an API token from: https://goszakup.gov.kz/ru/developer/ows_v3\n"
            "Then run:\n"
            "  cd backend && GOSZAKUP_API_TOKEN=your_token python -m spikes.spike_goszakup\n"
        )
        sys.exit(1)

    print(f"SPIKE-01: goszakup.gov.kz v3 GraphQL API verification")
    print(f"Target: {GRAPHQL_URL}")
    print(f"Findings will be saved to: {FINDINGS_DIR.resolve()}")
    # Token intentionally NOT printed (T-02-01: Information Disclosure mitigation)

    async with httpx.AsyncClient(timeout=30.0, http2=True) as client:
        await step1_reachability(client, token)
        await step2_introspection(client, token)
        await step3_trdbuy(client, token)
        await step4_rate_limit(client, token)

    print(f"\n{'=' * 60}")
    print("  SPIKE-01 COMPLETE")
    print(f"  Findings saved to: {FINDINGS_DIR.resolve()}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(spike_goszakup())
