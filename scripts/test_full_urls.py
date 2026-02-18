#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run a full-ish pipeline test for arbitrary URLs:
- Local audit + crawl
- Agent 1 external intelligence
- Google search + competitor discovery (if keys available)
- Competitor audits (if any)
- Report generation (Agent 2)

Designed to be run inside Docker worker/backend containers.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List


def _add_repo_to_syspath() -> Path:
    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[1]
    backend_path = repo_root / "backend"
    for p in (repo_root, backend_path):
        p_str = str(p)
        if p_str not in sys.path:
            sys.path.insert(0, p_str)
    return repo_root


def _load_env(repo_root: Path) -> None:
    env_path = repo_root / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv
        except Exception:
            return
        load_dotenv(dotenv_path=env_path, override=False)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Full pipeline test for URLs.")
    parser.add_argument(
        "--urls",
        default="https://robot.com/,https://www.farmalife.com.ar/",
        help="Comma-separated list of URLs to test.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Timeout for Agent 1 LLM call (seconds).",
    )
    parser.add_argument(
        "--model",
        default="moonshotai/kimi-k2-instruct-0905",
        help="Model id for NV_MODEL_ANALYSIS.",
    )
    parser.add_argument(
        "--max-crawl",
        type=int,
        default=10,
        help="Max pages to crawl.",
    )
    parser.add_argument(
        "--max-audit",
        type=int,
        default=10,
        help="Max pages to audit.",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip LLM report generation.",
    )
    return parser.parse_args()


async def _run_for_url(
    url: str,
    audit_id: int,
    timeout_seconds: float,
    generate_report: bool,
) -> Dict[str, Any]:
    from app.core.config import settings
    from app.core.llm_kimi import get_llm_function
    from app.services.audit_local_service import AuditLocalService
    from app.services.crawler_service import crawl_site
    from app.services.pipeline_service import run_initial_audit

    llm_function = get_llm_function()

    logging.info(f"\n=== Testing URL: {url} ===")
    logging.info("Running local audit...")
    target_audit, _ = await AuditLocalService.run_local_audit(url)

    logging.info("Running initial pipeline (crawl + agent1 + search + competitors + report)...")
    result = await run_initial_audit(
        url=url,
        target_audit=target_audit,
        audit_id=audit_id,
        llm_function=llm_function,
        google_api_key=settings.GOOGLE_API_KEY,
        google_cx_id=settings.CSE_ID,
        crawler_service=crawl_site,
        audit_local_service=AuditLocalService.run_local_audit,
        generate_report=generate_report,
        enable_llm_external_intel=True,
        external_intel_mode="full",
        external_intel_timeout_seconds=timeout_seconds,
    )
    return result


def _summarize_result(result: Dict[str, Any]) -> None:
    external_intel = result.get("external_intelligence") or {}
    query_source = external_intel.get("query_source")
    queries = external_intel.get("queries_to_run") or []
    search_results = result.get("search_results") or {}
    competitor_audits = result.get("competitor_audits") or []
    report_md = result.get("report_markdown") or ""

    logging.info("Summary:")
    logging.info(f"  - query_source: {query_source}")
    logging.info(f"  - queries_to_run: {len(queries)}")
    logging.info(f"  - search_results: {len(search_results)}")
    logging.info(f"  - competitor_audits: {len(competitor_audits)}")
    logging.info(f"  - report_length: {len(report_md)} chars")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    repo_root = _add_repo_to_syspath()
    _load_env(repo_root)
    args = _parse_args()

    if args.model:
        os.environ["NV_MODEL_ANALYSIS"] = args.model
    if args.timeout:
        os.environ["AGENT1_LLM_TIMEOUT_SECONDS"] = str(args.timeout)
    if args.max_crawl:
        os.environ["MAX_CRAWL_PAGES"] = str(args.max_crawl)
    if args.max_audit:
        os.environ["MAX_AUDIT_PAGES"] = str(args.max_audit)

    urls = [u.strip() for u in (args.urls or "").split(",") if u.strip()]
    if not urls:
        logging.error("No URLs provided.")
        return 1

    any_fail = False
    for idx, url in enumerate(urls, start=1):
        try:
            result = asyncio.run(
                _run_for_url(
                    url=url,
                    audit_id=idx,
                    timeout_seconds=args.timeout,
                    generate_report=not args.no_report,
                )
            )
            _summarize_result(result)
        except Exception as exc:
            any_fail = True
            logging.error(f"[FAILED] {url}: {exc}")

    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
