#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone test for Agent 1 (KIMI) external intelligence.

Runs the same flow as PipelineService.analyze_external_intelligence using a
real audit context and fails if Agent 1 falls back to deterministic queries.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path


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
    parser = argparse.ArgumentParser(
        description="Run Agent 1 LLM flow with real audit context."
    )
    parser.add_argument(
        "--context",
        default="reports/audit_1/final_llm_context.json",
        help="Path to final_llm_context.json",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Timeout in seconds for the Agent 1 LLM call.",
    )
    parser.add_argument(
        "--model",
        default="moonshotai/kimi-k2-instruct-0905",
        help="Model id to use for NV_MODEL_ANALYSIS.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=1,
        help="Number of attempts before failing.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Seconds to sleep between retries.",
    )
    return parser.parse_args()


def _load_target_audit(context_path: Path) -> dict:
    if not context_path.exists():
        raise FileNotFoundError(f"Context file not found: {context_path}")
    with context_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    target = payload.get("target_audit")
    if not isinstance(target, dict) or not target:
        raise ValueError("target_audit is missing or invalid in context JSON.")
    return target


async def _run_agent1(target_audit: dict, timeout_seconds: float) -> dict:
    from app.core.llm_kimi import get_llm_function
    from app.services.pipeline_service import get_pipeline_service

    llm_function = get_llm_function()
    service = get_pipeline_service()
    external_intel, _ = await service.analyze_external_intelligence(
        target_audit,
        llm_function=llm_function,
        mode="full",
        retry_policy={"timeout_seconds": timeout_seconds},
    )
    return external_intel or {}


def _validate_result(external_intel: dict) -> None:
    query_source = str(external_intel.get("query_source") or "").strip()
    queries = external_intel.get("queries_to_run") or []
    if query_source not in {"agent1", "agent1_retry"}:
        raise RuntimeError(
            f"Agent 1 fallback detected. query_source={query_source!r}"
        )
    if not isinstance(queries, list) or len(queries) < 2:
        raise RuntimeError(
            f"Agent 1 returned insufficient queries: {len(queries)}"
        )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    repo_root = _add_repo_to_syspath()
    _load_env(repo_root)
    args = _parse_args()

    if args.model:
        os.environ["NV_MODEL_ANALYSIS"] = args.model
    if args.timeout:
        os.environ["AGENT1_LLM_TIMEOUT_SECONDS"] = str(args.timeout)

    context_path = Path(args.context)
    if not context_path.is_absolute():
        context_path = repo_root / context_path

    target_audit = _load_target_audit(context_path)

    attempts = max(1, int(args.retries))
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            logging.info(
                f"[agent1-test] attempt {attempt}/{attempts} "
                f"(timeout={args.timeout}s, model={args.model})"
            )
            external_intel = asyncio.run(
                _run_agent1(target_audit, args.timeout)
            )
            _validate_result(external_intel)
            logging.info(
                "[agent1-test] OK: Agent 1 produced queries without fallback."
            )
            return 0
        except Exception as exc:  # noqa: BLE001 - want full error surface
            last_error = exc
            logging.error(f"[agent1-test] FAILED: {exc}")
            if attempt < attempts and args.sleep > 0:
                time.sleep(args.sleep)

    if last_error:
        logging.error(f"[agent1-test] Giving up after {attempts} attempts.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
