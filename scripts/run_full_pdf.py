#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run a real, full PDF generation for one or more URLs.
This will:
1) create an audit in the DB
2) run the full audit pipeline (Agent1, Google search, competitors, etc.)
3) generate the complete PDF with PageSpeed + GEO tools
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import List


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
    parser = argparse.ArgumentParser(description="Generate full PDF for URLs.")
    parser.add_argument(
        "--urls",
        default="https://robot.com/,https://www.farmalife.com.ar/",
        help="Comma-separated list of URLs.",
    )
    parser.add_argument(
        "--model",
        default="moonshotai/kimi-k2-instruct-0905",
        help="NV_MODEL_ANALYSIS model id.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Agent1 timeout seconds.",
    )
    parser.add_argument(
        "--user-email",
        default="local@example.com",
        help="Owner email for audit records.",
    )
    parser.add_argument(
        "--user-id",
        default="local-user",
        help="Owner user_id for audit records.",
    )
    parser.add_argument(
        "--force-pagespeed",
        action="store_true",
        help="Force PageSpeed refresh during PDF generation.",
    )
    parser.add_argument(
        "--force-report",
        action="store_true",
        help="Force report regeneration during PDF generation.",
    )
    parser.add_argument(
        "--force-external-intel",
        action="store_true",
        help="Force external intelligence refresh during PDF generation.",
    )
    return parser.parse_args()


def _split_urls(raw: str) -> List[str]:
    return [u.strip() for u in (raw or "").split(",") if u.strip()]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    repo_root = _add_repo_to_syspath()
    _load_env(repo_root)
    args = _parse_args()

    if args.model:
        os.environ["NV_MODEL_ANALYSIS"] = args.model
    if args.timeout:
        os.environ["AGENT1_LLM_TIMEOUT_SECONDS"] = str(args.timeout)

    urls = _split_urls(args.urls)
    if not urls:
        logging.error("No URLs provided.")
        return 1

    from app.core.database import SessionLocal
    from app.schemas import AuditCreate
    from app.services.audit_service import AuditService
    from app.services.pdf_service import PDFService
    from app.workers.tasks import run_audit_task

    any_fail = False

    for url in urls:
        logging.info(f"\n=== FULL PDF for: {url} ===")
        try:
            with SessionLocal() as db:
                audit = AuditService.create_audit(
                    db,
                    AuditCreate(
                        url=url,
                        user_id=args.user_id,
                        user_email=args.user_email,
                        source="local-script",
                    ),
                )
                audit_id = int(audit.id)

            logging.info(f"Audit created: {audit_id}. Running full audit pipeline...")
            run_audit_task.run(audit_id)

            logging.info("Generating PDF with complete context...")
            with SessionLocal() as db:
                result = asyncio.run(
                    PDFService.generate_pdf_with_complete_context(
                        db=db,
                        audit_id=audit_id,
                        force_pagespeed_refresh=bool(args.force_pagespeed),
                        force_report_refresh=bool(args.force_report),
                        force_external_intel_refresh=bool(args.force_external_intel),
                        return_details=True,
                    )
                )

            pdf_path = result.get("pdf_path") if isinstance(result, dict) else result
            logging.info(f"PDF OK: {pdf_path}")
        except Exception as exc:
            any_fail = True
            logging.error(f"[FAILED] {url}: {exc}")

    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
