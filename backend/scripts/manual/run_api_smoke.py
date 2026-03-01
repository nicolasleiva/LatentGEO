"""
Manual API smoke script.

This script is intentionally outside pytest discovery and is only for
manual diagnostics against a running backend.
"""

from __future__ import annotations

import argparse
import logging
import os
from typing import Any

import requests

logger = logging.getLogger("manual.api_smoke")
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def _post_json(url: str, params: dict[str, Any], payload: Any) -> None:
    logger.info("POST %s params=%s", url, params)
    response = requests.post(url, params=params, json=payload, timeout=30)
    logger.info("status=%s", response.status_code)
    if response.status_code >= 400:
        logger.error("response=%s", response.text)
        return
    try:
        data = response.json()
    except ValueError:
        logger.info("response-body=%s", response.text[:500])
        return
    if isinstance(data, list):
        logger.info("items=%s", len(data))
    else:
        logger.info("response-json-keys=%s", list(data.keys())[:20])


def run(base_url: str, audit_id: int, domain: str, brand_name: str) -> None:
    api_base = base_url.rstrip("/") + "/api/v1"
    _post_json(
        f"{api_base}/keywords/research/{audit_id}",
        {"domain": domain},
        [],
    )
    _post_json(
        f"{api_base}/backlinks/analyze/{audit_id}",
        {"domain": domain},
        None,
    )
    _post_json(
        f"{api_base}/rank-tracking/track/{audit_id}",
        {"domain": domain},
        ["seo auditor", "geo seo tool"],
    )
    _post_json(
        f"{api_base}/llm-visibility/check/{audit_id}",
        {"brand_name": brand_name},
        ["Is this brand visible in AI answers?"],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run manual API smoke checks.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("SMOKE_BASE_URL", "http://localhost:8000"),
        help="Backend base URL without /api/v1 suffix.",
    )
    parser.add_argument(
        "--audit-id",
        type=int,
        default=int(os.getenv("SMOKE_AUDIT_ID", "1")),
        help="Audit ID used by smoke requests.",
    )
    parser.add_argument(
        "--domain",
        default=os.getenv("SMOKE_DOMAIN", "www.robot.com"),
        help="Domain query parameter value.",
    )
    parser.add_argument(
        "--brand-name",
        default=os.getenv("SMOKE_BRAND_NAME", "LatentGEO"),
        help="Brand name for LLM visibility endpoint.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.base_url, args.audit_id, args.domain, args.brand_name)
