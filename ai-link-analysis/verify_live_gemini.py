"""Verify live end-to-end Gemini AI analysis across 3 real public websites.

Usage:
    1. Set GEMINI_API_KEY in ai-link-analysis/.env or environment variable.
    2. Ensure ENABLE_DEMO_MODE_WITHOUT_API_KEY=false.
    3. Run:
       python ai-link-analysis/verify_live_gemini.py [--base-url http://127.0.0.1:8000]
"""

import argparse
import asyncio
import json
from pathlib import Path
import sys
import time

ROOT_DIR = Path(__file__).resolve().parent.parent
PACKAGES_DIR = ROOT_DIR / ".packages"
APP_DIR = ROOT_DIR / "ai-link-analysis"

if PACKAGES_DIR.exists() and str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import httpx  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.schemas import LinkAnalysisResponse  # noqa: E402
from app.services.analysis_service import AnalysisService  # noqa: E402

TEST_WEBSITES = [
    ("FinTech / Payments Infrastructure", "https://stripe.com"),
    ("Developer Ecosystem / Open Source", "https://www.python.org"),
    ("E-Commerce / SaaS Platform", "https://www.shopify.com"),
]


async def verify_direct_service() -> int:
    """Run direct AnalysisService verification with Gemini and save JSON evidence."""
    settings = get_settings()
    if settings.enable_demo_mode_without_api_key:
        print("[FAIL] ENABLE_DEMO_MODE_WITHOUT_API_KEY is True. Disable demo mode for production verification.")
        return 1

    if not settings.has_valid_gemini_key():
        print(
            "[BLOCKED] GEMINI_API_KEY is not configured in environment or .env.\n"
            "Please set GEMINI_API_KEY=<your_key> in ai-link-analysis/.env and re-run."
        )
        return 2

    service = AnalysisService(settings=settings)
    evidence_dir = APP_DIR / "verification_evidence"
    evidence_dir.mkdir(exist_ok=True)

    summary = []
    for category, url in TEST_WEBSITES:
        print(f"\n--- Analyzing [{category}] {url} ---")
        t0 = time.perf_counter()
        result: LinkAnalysisResponse = await service.analyze_url(url)
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        assert result.metadata.llm_provider == "gemini", (
            f"Expected provider 'gemini', got '{result.metadata.llm_provider}'"
        )
        assert len(result.competitor_analysis.competitors) >= 3
        assert len(result.target_search_queries.queries) == 5
        assert len(result.top_five_services.services) == 5

        slug = result.website_derived_facts.domain.replace(".", "_")
        out_path = evidence_dir / f"gemini_analysis_{slug}.json"
        out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

        item_summary = {
            "category": category,
            "requested_url": url,
            "final_url": result.url,
            "http_status_code": result.website_derived_facts.http_status_code,
            "llm_provider": result.metadata.llm_provider,
            "llm_model": result.metadata.llm_model,
            "execution_time_ms": elapsed_ms,
            "brand_name": result.competitor_analysis.brand_name,
            "competitors": [c.name for c in result.competitor_analysis.competitors],
            "top_services": [s.service_name for s in result.top_five_services.services],
            "evidence_file": str(out_path.name),
        }
        summary.append(item_summary)
        print(
            f"[PASS] {url} -> Provider: {result.metadata.llm_provider}/{result.metadata.llm_model} | "
            f"Brand: {result.competitor_analysis.brand_name} | "
            f"Competitors: {item_summary['competitors']} | Time: {elapsed_ms}ms"
        )

    summary_path = evidence_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n[SUCCESS] All 3 real websites verified with genuine Gemini AI. Evidence saved to {evidence_dir}")
    return 0


def verify_remote_endpoint(base_url: str) -> int:
    """Verify a running local or cloud-deployed FastAPI instance over HTTP."""
    base = base_url.rstrip("/")
    print(f"Verifying API at {base} ...")
    with httpx.Client(trust_env=False, timeout=90.0) as client:
        health = client.get(f"{base}/health")
        print(f"GET /health -> HTTP {health.status_code}: {health.text}")
        health.raise_for_status()
        health_data = health.json()
        if health_data.get("demo_mode_enabled"):
            print("[FAIL] Remote server has demo_mode_enabled=true!")
            return 1

        docs = client.get(f"{base}/docs")
        print(f"GET /docs -> HTTP {docs.status_code} ({len(docs.text)} bytes)")
        docs.raise_for_status()

        openapi = client.get(f"{base}/openapi.json")
        print(f"GET /openapi.json -> HTTP {openapi.status_code}")
        openapi.raise_for_status()

        for category, url in TEST_WEBSITES:
            resp = client.post(f"{base}/link-analysis", json={"url": url})
            print(f"POST /link-analysis ({url}) -> HTTP {resp.status_code}")
            if resp.status_code != 200:
                print(f"Error response: {resp.text}")
                return 1
            validated = LinkAnalysisResponse.model_validate(resp.json())
            print(
                f"  Verified provider={validated.metadata.llm_provider}, "
                f"model={validated.metadata.llm_model}, "
                f"brand={validated.competitor_analysis.brand_name}"
            )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default="",
        help="Optional base URL of running local or cloud server (e.g. https://ai-link-analysis-api.onrender.com)",
    )
    args = parser.parse_args()
    if args.base_url:
        raise SystemExit(verify_remote_endpoint(args.base_url))
    raise SystemExit(asyncio.run(verify_direct_service()))
