"""
Servicio para la generaciÃ³n de reportes en PDF.
"""

import asyncio
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urlparse

from ..core.config import settings
from ..core.llm_kimi import get_llm_function
from ..core.logger import get_logger
from ..models import Audit

logger = get_logger(__name__)

# Importar create_comprehensive_pdf desde el mismo directorio de servicios
try:
    from .create_pdf import FPDF_AVAILABLE, create_comprehensive_pdf

    PDF_GENERATOR_AVAILABLE = FPDF_AVAILABLE
except ImportError as e:
    logger.warning(
        f"No se pudo importar create_comprehensive_pdf: {e}. PDFs no estarÃ¡n disponibles."
    )
    PDF_GENERATOR_AVAILABLE = False

    def create_comprehensive_pdf(report_folder_path, metadata=None):
        logger.error("create_comprehensive_pdf no estÃ¡ disponible")
        raise ImportError("create_pdf module not available")


class PDFService:
    """Encapsula la lÃ³gica para crear archivos PDF a partir de contenido."""

    REPORT_CONTEXT_PROMPT_VERSION = "report_generation_v2"
    REPORT_SIGNATURE_REPORT_TYPE = "REPORT_CONTEXT_SIGNATURE"
    DETERMINISTIC_REPORT_MARKERS = (
        "full_deterministic_regenerated",
        "digital audit report (deterministic fallback)",
    )

    @staticmethod
    def _timeout_from_env(env_var: str, default_seconds: float) -> Optional[float]:
        raw_value = str(os.getenv(env_var, "")).strip()
        if not raw_value:
            return float(default_seconds)
        try:
            parsed = float(raw_value)
            if parsed <= 0:
                logger.info(
                    f"{env_var} configured as <= 0. Stage timeout disabled for this setting."
                )
                return None
            return parsed
        except ValueError:
            logger.warning(
                f"Invalid value for {env_var}={raw_value}. "
                f"Falling back to default {float(default_seconds):.1f}s"
            )
            return float(default_seconds)

    @staticmethod
    def _remaining_budget_seconds(
        started_at: float, total_budget_seconds: Optional[float]
    ) -> Optional[float]:
        if total_budget_seconds is None:
            return None
        elapsed = max(0.0, time.monotonic() - started_at)
        return max(0.0, total_budget_seconds - elapsed)

    @staticmethod
    def _effective_stage_timeout(
        stage_timeout_seconds: Optional[float],
        started_at: float,
        total_budget_seconds: Optional[float],
    ) -> Optional[float]:
        remaining_budget = PDFService._remaining_budget_seconds(
            started_at=started_at, total_budget_seconds=total_budget_seconds
        )
        if remaining_budget is None:
            return stage_timeout_seconds
        if stage_timeout_seconds is None:
            return remaining_budget
        return min(stage_timeout_seconds, remaining_budget)

    @staticmethod
    async def _run_stage_with_timeout(
        *,
        stage_name: str,
        coroutine_factory: Callable[[], Awaitable[Any]],
        stage_timeout_seconds: Optional[float],
        started_at: float,
        total_budget_seconds: Optional[float],
    ) -> Any:
        stage_started_at = time.monotonic()
        effective_timeout = PDFService._effective_stage_timeout(
            stage_timeout_seconds=stage_timeout_seconds,
            started_at=started_at,
            total_budget_seconds=total_budget_seconds,
        )

        if effective_timeout is not None and effective_timeout <= 0:
            logger.warning(
                f"Skipping {stage_name} because PDF generation time budget is exhausted."
            )
            return None

        try:
            coroutine = coroutine_factory()
            if effective_timeout is None:
                result = await coroutine
                stage_elapsed = time.monotonic() - stage_started_at
                logger.info(f"{stage_name} completed in {stage_elapsed:.1f}s")
                return result
            result = await asyncio.wait_for(coroutine, timeout=effective_timeout)
            stage_elapsed = time.monotonic() - stage_started_at
            logger.info(f"{stage_name} completed in {stage_elapsed:.1f}s")
            return result
        except asyncio.TimeoutError:
            logger.warning(
                f"{stage_name} timed out after "
                f"{effective_timeout if effective_timeout is not None else 0.0:.1f}s. "
                "Continuing with fallback data."
            )
            return None

    @staticmethod
    def _clean_previous_pdf_artifacts(reports_dir: str) -> None:
        """
        Limpia artefactos previos para evitar mezcla entre corridas con mismo audit_id.
        - pages/*.json
        - competitors/*.json
        - Reporte_Consolidado_*.pdf
        """
        import glob

        patterns = [
            os.path.join(reports_dir, "pages", "*.json"),
            os.path.join(reports_dir, "competitors", "*.json"),
            os.path.join(reports_dir, "Reporte_Consolidado_*.pdf"),
        ]

        for pattern in patterns:
            for file_path in glob.glob(pattern):
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.warning(
                        f"No se pudo limpiar artefacto previo {file_path}: {e}"
                    )

    @staticmethod
    def _upload_pdf_to_supabase(audit_id: int, pdf_file_path: str) -> tuple[str, int]:
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError(
                "SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY son obligatorios para PDFs."
            )
        if not settings.SUPABASE_STORAGE_BUCKET:
            raise RuntimeError("SUPABASE_STORAGE_BUCKET es obligatorio para PDFs.")

        from .supabase_service import SupabaseService

        with open(pdf_file_path, "rb") as f:
            file_content = f.read()

        file_size = len(file_content)
        storage_path = f"audits/{audit_id}/report.pdf"
        logger.info(
            f"storage_provider=supabase audit_id={audit_id} action=upload_pdf storage_path={storage_path}"
        )
        SupabaseService.upload_file(
            bucket=settings.SUPABASE_STORAGE_BUCKET,
            path=storage_path,
            file_content=file_content,
            content_type="application/pdf",
        )
        return f"supabase://{storage_path}", file_size

    @staticmethod
    def _reports_dir_for_audit(audit_id: int) -> str:
        try:
            audit_id_int = int(audit_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("audit_id must be a positive integer") from exc
        if audit_id_int <= 0:
            raise ValueError("audit_id must be a positive integer")

        root = Path(settings.REPORTS_BASE_DIR or "reports").resolve(strict=False)
        candidate = (root / f"audit_{audit_id_int}").resolve(strict=False)
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError("Unsafe PDF reports directory path") from exc
        return str(candidate)

    @staticmethod
    def _report_context_signature_path(audit_id: int) -> str:
        reports_dir = Path(PDFService._reports_dir_for_audit(int(audit_id))).resolve(
            strict=False
        )
        signature_path = (reports_dir / "report_context.sha256").resolve(strict=False)
        try:
            signature_path.relative_to(reports_dir)
        except ValueError as exc:
            raise ValueError("Unsafe report signature path") from exc
        return str(signature_path)

    @staticmethod
    def _serialize_for_signature(value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, dict):
            return {
                str(k): PDFService._serialize_for_signature(v)
                for k, v in sorted(value.items(), key=lambda item: str(item[0]))
            }
        if isinstance(value, list):
            return [PDFService._serialize_for_signature(v) for v in value]
        if isinstance(value, tuple):
            return [PDFService._serialize_for_signature(v) for v in value]
        return str(value)

    @staticmethod
    def _remove_volatile_signature_fields(value: Any) -> Any:
        """
        Remove volatile timestamps/ids that should not force report regeneration.
        """
        volatile_keys = {
            "fetch_time",
            "generated_at",
            "created_at",
            "updated_at",
            "timestamp",
            "analyzed_at",
            "processed_at",
            "run_id",
            "request_id",
            "trace_id",
        }
        if isinstance(value, dict):
            cleaned: Dict[str, Any] = {}
            for key, inner_value in value.items():
                key_str = str(key)
                if key_str.lower() in volatile_keys:
                    continue
                cleaned[key_str] = PDFService._remove_volatile_signature_fields(
                    inner_value
                )
            return cleaned
        if isinstance(value, list):
            return [PDFService._remove_volatile_signature_fields(v) for v in value]
        if isinstance(value, tuple):
            return [PDFService._remove_volatile_signature_fields(v) for v in value]
        return value

    @staticmethod
    def _normalize_external_intel_status(
        external_intelligence: Dict[str, Any],
        audit: Optional[Audit] = None,
    ) -> Dict[str, Any]:
        """
        Validate whether external intelligence is complete enough to skip Agent 1 refresh.
        """
        data = external_intelligence if isinstance(external_intelligence, dict) else {}
        if not data:
            return {"is_complete": False, "reason": "missing"}
        status_value = str(data.get("status", "")).strip().lower()
        if status_value == "unavailable":
            return {
                "is_complete": False,
                "reason": "unavailable",
                "has_category": False,
                "has_subcategory": False,
                "has_queries": False,
                "has_market": False,
                "queries_count": 0,
            }

        unknown_markers = {"", "unknown", "unknown category", "n/a", "none", "null"}

        category = str(data.get("category", "")).strip().lower()
        subcategory = str(data.get("subcategory", "")).strip().lower()
        market = str(data.get("market", "")).strip().lower()
        queries = data.get("queries_to_run", [])
        valid_queries = PDFService._extract_query_texts(queries)

        inferred_market = ""
        if audit is not None:
            inferred_market = str(getattr(audit, "market", "") or "").strip().lower()
            if not inferred_market:
                target = (
                    audit.target_audit if isinstance(audit.target_audit, dict) else {}
                )
                inferred_market = str(target.get("market", "") or "").strip().lower()

        has_category = category not in unknown_markers
        has_subcategory = subcategory not in unknown_markers
        has_queries = len(valid_queries) > 0
        has_market = (
            market not in unknown_markers or inferred_market not in unknown_markers
        )

        is_complete = has_category and has_subcategory and has_queries and has_market
        return {
            "is_complete": is_complete,
            "reason": "not_needed" if is_complete else "incomplete",
            "has_category": has_category,
            "has_subcategory": has_subcategory,
            "has_queries": has_queries,
            "has_market": has_market,
            "queries_count": len(valid_queries),
        }

    @staticmethod
    def _extract_query_texts(queries: Any) -> List[str]:
        if not isinstance(queries, list):
            return []

        normalized: List[str] = []
        for item in queries:
            if isinstance(item, str):
                query_text = item.strip()
            elif isinstance(item, dict):
                query_text = str(item.get("query", "")).strip()
            else:
                query_text = ""
            if query_text:
                normalized.append(query_text)
        return normalized

    @staticmethod
    def _compute_report_context_signature(
        audit: Audit,
        pagespeed_data: Dict[str, Any],
        keywords_data: Dict[str, Any],
        backlinks_data: Dict[str, Any],
        rank_tracking_data: Dict[str, Any],
        llm_visibility_data: List[Dict[str, Any]],
        ai_content_suggestions: List[Dict[str, Any]],
    ) -> str:
        def _safe_int(value: Any) -> Optional[int]:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        def _extract_list(
            data: Any, primary_key: str, alt_key: str
        ) -> List[Dict[str, Any]]:
            if isinstance(data, dict):
                items = data.get(primary_key)
                if not isinstance(items, list):
                    items = data.get(alt_key)
                if isinstance(items, list):
                    return [item for item in items if isinstance(item, dict)]
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
            return []

        mobile_data = (
            pagespeed_data.get("mobile", {}) if isinstance(pagespeed_data, dict) else {}
        )
        desktop_data = (
            pagespeed_data.get("desktop", {})
            if isinstance(pagespeed_data, dict)
            else {}
        )
        pagespeed_signature = {
            "mobile_available": bool(mobile_data),
            "desktop_available": bool(desktop_data),
        }

        keyword_rows = _extract_list(keywords_data, "items", "keywords")
        keyword_terms = sorted(
            {
                str(row.get("term") or row.get("keyword") or "").strip().lower()
                for row in keyword_rows
                if str(row.get("term") or row.get("keyword") or "").strip()
            }
        )
        keyword_signature = {
            "total": _safe_int(
                keywords_data.get("total")
                if isinstance(keywords_data, dict)
                else len(keyword_rows)
            )
            or len(keyword_rows),
            "sample_terms": keyword_terms[:20],
        }

        backlink_rows = _extract_list(backlinks_data, "top_backlinks", "items")
        backlink_domains = sorted(
            {
                str(row.get("source_url", "")).split("/")[2].lower()
                for row in backlink_rows
                if isinstance(row.get("source_url"), str)
                and row.get("source_url", "").startswith(("http://", "https://"))
            }
        )
        backlink_signature = {
            "total_backlinks": _safe_int(
                backlinks_data.get("total_backlinks")
                if isinstance(backlinks_data, dict)
                else len(backlink_rows)
            )
            or len(backlink_rows),
            "referring_domains": _safe_int(
                backlinks_data.get("referring_domains")
                if isinstance(backlinks_data, dict)
                else 0
            ),
            "sample_domains": backlink_domains[:20],
        }

        ranking_rows = _extract_list(rank_tracking_data, "rankings", "items")
        rank_keywords = sorted(
            {
                str(row.get("keyword", "")).strip().lower()
                for row in ranking_rows
                if str(row.get("keyword", "")).strip()
            }
        )
        ranking_signature = {
            "total_keywords": _safe_int(
                rank_tracking_data.get("total_keywords")
                if isinstance(rank_tracking_data, dict)
                else len(ranking_rows)
            )
            or len(ranking_rows),
            "sample_keywords": rank_keywords[:20],
        }

        llm_rows = [
            item for item in (llm_visibility_data or []) if isinstance(item, dict)
        ]
        ai_rows = [
            item for item in (ai_content_suggestions or []) if isinstance(item, dict)
        ]
        llm_signature = {
            "total": len(llm_rows),
            "visible_total": len(
                [
                    item
                    for item in llm_rows
                    if bool(
                        item.get(
                            "is_visible",
                            item.get("mentioned", item.get("visible")),
                        )
                    )
                ]
            ),
        }
        ai_signature = {
            "total": len(ai_rows),
            "high_priority_total": len(
                [
                    item
                    for item in ai_rows
                    if str(item.get("priority", "")).strip().lower() == "high"
                ]
            ),
        }

        target_audit_data = (
            audit.target_audit if isinstance(audit.target_audit, dict) else {}
        )
        target_content = (
            target_audit_data.get("content", {})
            if isinstance(target_audit_data.get("content"), dict)
            else {}
        )
        target_signature = {
            "url": target_audit_data.get("url") or getattr(audit, "url", ""),
            "domain": target_audit_data.get("domain") or getattr(audit, "domain", ""),
            "language": target_audit_data.get("language", ""),
            "market": target_audit_data.get("market", ""),
            "category": target_audit_data.get("category", ""),
            "title": target_content.get("title", ""),
            "geo_score": target_audit_data.get("geo_score"),
            "structure_score": target_audit_data.get("structure_score"),
            "eeat_score": target_audit_data.get("eeat_score"),
            "critical_issues_count": target_audit_data.get("critical_issues_count"),
            "high_issues_count": target_audit_data.get("high_issues_count"),
        }

        external_data = (
            audit.external_intelligence
            if isinstance(audit.external_intelligence, dict)
            else {}
        )
        external_queries = external_data.get("queries_to_run", [])
        normalized_external_queries = PDFService._extract_query_texts(external_queries)
        external_signature = {
            "category": external_data.get("category", ""),
            "subcategory": external_data.get("subcategory", ""),
            "market": external_data.get("market", ""),
            "is_ymyl": bool(external_data.get("is_ymyl")),
            "queries_count": len(normalized_external_queries),
        }

        search_data = (
            audit.search_results if isinstance(audit.search_results, dict) else {}
        )
        search_items = search_data.get("items", [])
        if not isinstance(search_items, list):
            search_items = []
        search_domains = sorted(
            {
                str(item.get("link", "")).split("/")[2].lower()
                for item in search_items
                if isinstance(item, dict)
                and isinstance(item.get("link"), str)
                and item.get("link", "").startswith(("http://", "https://"))
            }
        )
        search_signature = {
            "total_items": len(search_items),
            "top_domains": search_domains[:20],
        }

        competitor_rows = (
            audit.competitor_audits if isinstance(audit.competitor_audits, list) else []
        )
        competitor_compact = []
        for item in competitor_rows:
            if not isinstance(item, dict):
                continue
            competitor_compact.append(
                {
                    "url": item.get("url", ""),
                    "domain": item.get("domain", ""),
                    "geo_score": item.get("geo_score"),
                    "structure_score": item.get("structure_score"),
                    "eeat_score": item.get("eeat_score"),
                }
            )
        competitor_compact.sort(key=lambda row: str(row.get("url", "")))

        payload = {
            "prompt_version": PDFService.REPORT_CONTEXT_PROMPT_VERSION,
            "target_audit": target_signature,
            "external_intelligence": external_signature,
            "search_results": search_signature,
            "competitor_audits": competitor_compact,
            "pagespeed": pagespeed_signature,
            "keywords": keyword_signature,
            "backlinks": backlink_signature,
            "rank_tracking": ranking_signature,
            "llm_visibility": llm_signature,
            "ai_content_suggestions": ai_signature,
        }
        payload = PDFService._remove_volatile_signature_fields(payload)
        serialized = json.dumps(
            PDFService._serialize_for_signature(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _load_saved_report_signature(audit_id: int, db: Any = None) -> str:
        if settings.AUDIT_LOCAL_ARTIFACTS_ENABLED:
            signature_path = PDFService._report_context_signature_path(audit_id)
            if os.path.exists(signature_path):
                try:
                    with open(signature_path, "r", encoding="utf-8") as f:
                        signature = f.read().strip()
                    if signature:
                        return signature
                except Exception as exc:
                    logger.warning(f"Could not read report signature cache: {exc}")

        if db is None:
            return ""

        try:
            from ..models import Report

            cached_signature = (
                db.query(Report)
                .filter(
                    Report.audit_id == int(audit_id),
                    Report.report_type == PDFService.REPORT_SIGNATURE_REPORT_TYPE,
                )
                .order_by(Report.id.desc())
                .first()
            )
            if cached_signature and isinstance(cached_signature.file_path, str):
                return cached_signature.file_path.strip()
        except Exception as exc:
            logger.warning(f"Could not read report signature cache from DB: {exc}")

        return ""

    @staticmethod
    def _save_report_signature(audit_id: int, signature: str, db: Any = None) -> None:
        if not signature:
            return

        if settings.AUDIT_LOCAL_ARTIFACTS_ENABLED:
            signature_path = PDFService._report_context_signature_path(audit_id)
            os.makedirs(os.path.dirname(signature_path), exist_ok=True)
            try:
                with open(signature_path, "w", encoding="utf-8") as f:
                    f.write(signature)
            except Exception as exc:
                logger.warning(f"Could not persist report signature cache: {exc}")

        if db is None:
            return

        try:
            from ..models import Report

            cached_signature = (
                db.query(Report)
                .filter(
                    Report.audit_id == int(audit_id),
                    Report.report_type == PDFService.REPORT_SIGNATURE_REPORT_TYPE,
                )
                .order_by(Report.id.desc())
                .first()
            )
            if cached_signature is None:
                cached_signature = Report(
                    audit_id=int(audit_id),
                    report_type=PDFService.REPORT_SIGNATURE_REPORT_TYPE,
                    file_path=signature,
                )
                db.add(cached_signature)
            else:
                cached_signature.file_path = signature
            db.flush()
        except Exception as exc:
            logger.warning(f"Could not persist report signature cache in DB: {exc}")

    @staticmethod
    def _compact_report_inputs_for_retry(
        *,
        keywords_data: Dict[str, Any],
        backlinks_data: Dict[str, Any],
        rank_tracking_data: Dict[str, Any],
        llm_visibility_data: List[Dict[str, Any]],
        ai_content_suggestions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Reduce payload size for retry attempts when full report generation times out.
        This does not fabricate data; it only trims list-heavy sections.
        """

        def _clone(value: Any, default: Any) -> Any:
            try:
                return json.loads(json.dumps(value))
            except Exception:
                return default

        compact_keywords = (
            _clone(keywords_data, {}) if isinstance(keywords_data, dict) else {}
        )
        compact_backlinks = (
            _clone(backlinks_data, {}) if isinstance(backlinks_data, dict) else {}
        )
        compact_rankings = (
            _clone(rank_tracking_data, {})
            if isinstance(rank_tracking_data, dict)
            else {}
        )
        compact_llm_visibility = (
            _clone(llm_visibility_data, [])
            if isinstance(llm_visibility_data, list)
            else []
        )
        compact_ai_suggestions = (
            _clone(ai_content_suggestions, [])
            if isinstance(ai_content_suggestions, list)
            else []
        )

        if isinstance(compact_keywords.get("items"), list):
            compact_keywords["items"] = compact_keywords["items"][:80]
        if isinstance(compact_keywords.get("keywords"), list):
            compact_keywords["keywords"] = compact_keywords["keywords"][:80]
        if isinstance(compact_keywords.get("top_opportunities"), list):
            compact_keywords["top_opportunities"] = compact_keywords[
                "top_opportunities"
            ][:10]

        if isinstance(compact_backlinks.get("top_backlinks"), list):
            compact_backlinks["top_backlinks"] = compact_backlinks["top_backlinks"][:15]
        if isinstance(compact_backlinks.get("items"), list):
            compact_backlinks["items"] = compact_backlinks["items"][:15]

        if isinstance(compact_rankings.get("rankings"), list):
            compact_rankings["rankings"] = compact_rankings["rankings"][:50]
        if isinstance(compact_rankings.get("items"), list):
            compact_rankings["items"] = compact_rankings["items"][:50]

        compact_llm_visibility = compact_llm_visibility[:30]
        compact_ai_suggestions = compact_ai_suggestions[:25]

        return {
            "keywords_data": compact_keywords,
            "backlinks_data": compact_backlinks,
            "rank_tracking_data": compact_rankings,
            "llm_visibility_data": compact_llm_visibility,
            "ai_content_suggestions": compact_ai_suggestions,
        }

    @staticmethod
    def _build_keywords_payload(
        items: Optional[List[Dict[str, Any]]] = None, total: Optional[int] = None
    ) -> Dict[str, Any]:
        keyword_items = [
            row for row in (items or []) if isinstance(row, dict) and row.get("keyword")
        ]
        total_keywords = len(keyword_items) if total is None else max(int(total), 0)
        return {
            "items": keyword_items,
            "keywords": keyword_items,
            "total": total_keywords,
            "total_keywords": total_keywords,
            "top_opportunities": sorted(
                keyword_items,
                key=lambda row: PDFService._safe_float(
                    row.get("opportunity_score"), 0.0
                ),
                reverse=True,
            )[:10],
        }

    @staticmethod
    def _build_backlinks_payload(
        items: Optional[List[Dict[str, Any]]] = None,
        total: Optional[int] = None,
        referring_domains: Optional[int] = None,
        summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        backlink_items = [row for row in (items or []) if isinstance(row, dict)]
        total_backlinks = len(backlink_items) if total is None else max(int(total), 0)
        referring_domains_count = (
            len(
                {
                    urlparse(row["source_url"]).netloc
                    for row in backlink_items
                    if isinstance(row.get("source_url"), str)
                    and "://" in row["source_url"]
                }
            )
            if referring_domains is None
            else max(int(referring_domains), 0)
        )
        backlink_summary = summary if isinstance(summary, dict) else {}
        if not backlink_summary:
            backlink_summary = {
                "average_domain_authority": (
                    round(
                        sum(
                            float(row.get("domain_authority") or 0)
                            for row in backlink_items
                        )
                        / len(backlink_items),
                        1,
                    )
                    if backlink_items
                    else 0
                ),
                "dofollow_count": len(
                    [row for row in backlink_items if row.get("is_dofollow")]
                ),
                "nofollow_count": len(
                    [row for row in backlink_items if not row.get("is_dofollow")]
                ),
            }
        return {
            "items": backlink_items[:20],
            "top_backlinks": backlink_items[:20],
            "total": total_backlinks,
            "total_backlinks": total_backlinks,
            "referring_domains": referring_domains_count,
            "summary": backlink_summary,
        }

    @staticmethod
    def _build_rankings_payload(
        items: Optional[List[Dict[str, Any]]] = None, total: Optional[int] = None
    ) -> Dict[str, Any]:
        ranking_items = [row for row in (items or []) if isinstance(row, dict)]
        total_keywords = len(ranking_items) if total is None else max(int(total), 0)
        return {
            "items": ranking_items,
            "rankings": ranking_items,
            "total": total_keywords,
            "total_keywords": total_keywords,
            "distribution": {
                "top_3": len(
                    [
                        row
                        for row in ranking_items
                        if (row.get("position") or 100) <= 3
                        and (row.get("position") or 0) > 0
                    ]
                ),
                "top_10": len(
                    [
                        row
                        for row in ranking_items
                        if (row.get("position") or 100) <= 10
                        and (row.get("position") or 0) > 0
                    ]
                ),
                "top_20": len(
                    [
                        row
                        for row in ranking_items
                        if (row.get("position") or 100) <= 20
                        and (row.get("position") or 0) > 0
                    ]
                ),
                "beyond_20": len(
                    [
                        row
                        for row in ranking_items
                        if (row.get("position") or 100) > 20
                        or (row.get("position") or 0) == 0
                    ]
                ),
            },
        }

    @staticmethod
    def _build_signature_inputs_from_complete_context(
        complete_context: Dict[str, Any],
        fallback_pagespeed_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        context = complete_context if isinstance(complete_context, dict) else {}

        keyword_rows = (
            context.get("keywords", [])
            if isinstance(context.get("keywords", []), list)
            else []
        )
        backlinks_snapshot = (
            context.get("backlinks", {})
            if isinstance(context.get("backlinks", {}), dict)
            else {}
        )
        backlink_rows = (
            backlinks_snapshot.get("top_backlinks", [])
            if isinstance(backlinks_snapshot.get("top_backlinks", []), list)
            else []
        )
        ranking_rows = (
            context.get("rank_tracking", [])
            if isinstance(context.get("rank_tracking", []), list)
            else []
        )
        llm_rows = (
            context.get("llm_visibility", [])
            if isinstance(context.get("llm_visibility", []), list)
            else []
        )
        ai_rows = (
            context.get("ai_content_suggestions", [])
            if isinstance(context.get("ai_content_suggestions", []), list)
            else []
        )
        pagespeed_snapshot = (
            context.get("pagespeed", {})
            if isinstance(context.get("pagespeed", {}), dict)
            else {}
        )

        normalized_llm_rows: List[Dict[str, Any]] = []
        for row in llm_rows:
            if not isinstance(row, dict):
                continue
            normalized_llm_rows.append(
                {
                    "query": str(row.get("query", "")).strip(),
                    "is_visible": bool(
                        row.get("is_visible", row.get("mentioned", row.get("visible")))
                    ),
                }
            )

        normalized_ai_rows = [
            PDFService._normalize_ai_suggestion_row(row)
            for row in ai_rows
            if isinstance(row, dict)
        ]

        return {
            "pagespeed_data": (
                pagespeed_snapshot
                if isinstance(pagespeed_snapshot, dict) and pagespeed_snapshot
                else (
                    fallback_pagespeed_data
                    if isinstance(fallback_pagespeed_data, dict)
                    else {}
                )
            ),
            "keywords_data": PDFService._build_keywords_payload(
                keyword_rows,
                total=len(keyword_rows),
            ),
            "backlinks_data": PDFService._build_backlinks_payload(
                backlink_rows,
                total=backlinks_snapshot.get("total_backlinks", len(backlink_rows)),
                referring_domains=backlinks_snapshot.get("referring_domains", 0),
                summary=backlinks_snapshot.get("summary", {}),
            ),
            "rank_tracking_data": PDFService._build_rankings_payload(
                ranking_rows,
                total=len(ranking_rows),
            ),
            "llm_visibility_data": normalized_llm_rows,
            "ai_content_suggestions": normalized_ai_rows,
        }

    @staticmethod
    def _has_pdf_dataset(dataset_name: str, payload: Any) -> bool:
        if dataset_name == "pagespeed":
            return isinstance(payload, dict) and any(
                isinstance(payload.get(key), dict) and bool(payload.get(key))
                for key in ("mobile", "desktop")
            )
        if dataset_name == "keywords":
            return isinstance(payload, dict) and any(
                key in payload
                for key in ("items", "keywords", "total", "total_keywords")
            )
        if dataset_name == "backlinks":
            return isinstance(payload, dict) and any(
                key in payload
                for key in (
                    "items",
                    "top_backlinks",
                    "total",
                    "total_backlinks",
                    "referring_domains",
                )
            )
        if dataset_name == "rankings":
            return isinstance(payload, dict) and any(
                key in payload
                for key in ("items", "rankings", "total", "total_keywords", "distribution")
            )
        return bool(payload)

    @staticmethod
    def _detect_missing_pdf_context(
        *,
        audit: Audit,
        pagespeed_data: Any,
        keywords_data: Any,
        backlinks_data: Any,
        rank_tracking_data: Any,
    ) -> List[str]:
        missing: List[str] = []
        if not isinstance(getattr(audit, "target_audit", None), dict) or not audit.target_audit:
            missing.append("target_audit")
        return missing

    @staticmethod
    def _detect_optional_pdf_context_gaps(
        *,
        pagespeed_data: Any,
        keywords_data: Any,
        backlinks_data: Any,
        rank_tracking_data: Any,
    ) -> List[str]:
        def _has_observed_rows(dataset_name: str, payload: Any) -> bool:
            if dataset_name == "pagespeed":
                return PDFService._has_pdf_dataset(dataset_name, payload)
            if not isinstance(payload, dict):
                return False
            items = payload.get("items")
            if isinstance(items, list) and items:
                return True
            total = payload.get("total_keywords", payload.get("total_backlinks", payload.get("total")))
            try:
                return int(total or 0) > 0
            except (TypeError, ValueError):
                return False

        gaps: List[str] = []
        if not _has_observed_rows("pagespeed", pagespeed_data):
            gaps.append("pagespeed")
        if not _has_observed_rows("keywords", keywords_data):
            gaps.append("keywords")
        if not _has_observed_rows("backlinks", backlinks_data):
            gaps.append("backlinks")
        if not _has_observed_rows("rankings", rank_tracking_data):
            gaps.append("rankings")
        return gaps

    @staticmethod
    def _is_deterministic_report_markdown(markdown: Any) -> bool:
        text = str(markdown or "").strip().lower()
        if not text:
            return False
        return any(marker in text for marker in PDFService.DETERMINISTIC_REPORT_MARKERS)

    @staticmethod
    def _normalize_markdown_for_pdf_render(markdown: Any) -> str:
        text = str(markdown or "").replace("\r\n", "\n").strip()
        if not text:
            return ""

        lines = text.split("\n")
        output: List[str] = []
        idx = 0
        seen_real_content = False
        scaffold_titles = {
            "geo audit report",
            "digital audit report",
            "cover",
            "table of contents",
            "indice",
            "índice",
        }

        while idx < len(lines):
            line = lines[idx]
            heading_match = re.match(r"^\s*(#{1,6})\s+(.*)$", line)
            if not seen_real_content and heading_match:
                heading_title = heading_match.group(2).strip().lower()
                if heading_title in scaffold_titles:
                    idx += 1
                    while idx < len(lines):
                        next_line = lines[idx]
                        if re.match(r"^\s*#{1,6}\s+", next_line):
                            break
                        idx += 1
                    continue
            if not seen_real_content and not line.strip():
                idx += 1
                continue
            output.append(line)
            if line.strip():
                seen_real_content = True
            idx += 1

        normalized = "\n".join(output).strip()
        return normalized or text

    @staticmethod
    def _build_deterministic_full_report(
        *,
        audit: Audit,
        pagespeed_data: Dict[str, Any],
        keywords_data: Dict[str, Any],
        backlinks_data: Dict[str, Any],
        rank_tracking_data: Dict[str, Any],
        llm_visibility_data: List[Dict[str, Any]],
        ai_content_suggestions: List[Dict[str, Any]],
        fix_plan: Optional[List[Dict[str, Any]]] = None,
        reason: str = "llm_failure",
        data_gaps: Optional[List[str]] = None,
    ) -> str:
        """
        Build a deterministic report when LLM report generation is unavailable.
        Uses only collected audit data; it does not fabricate metrics.
        """

        def _safe_score(value: Any) -> str:
            if value is None:
                return "not_available"
            try:
                return str(round(float(value), 2))
            except (TypeError, ValueError):
                return "not_available"

        def _safe_text(value: Any, default: str = "not_available") -> str:
            text = str(value or "").strip()
            return text or default

        def _safe_int_value(value: Any, default: Optional[int] = None) -> Optional[int]:
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        def _safe_float_value(
            value: Any, default: Optional[float] = None
        ) -> Optional[float]:
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        def _as_dict(value: Any) -> Dict[str, Any]:
            return value if isinstance(value, dict) else {}

        def _avg(values: List[float]) -> Optional[float]:
            numeric = [value for value in values if value is not None]
            if not numeric:
                return None
            return round(sum(numeric) / len(numeric), 1)

        def _score_from_pages(attribute: str) -> Optional[float]:
            values: List[float] = []
            for page in page_rows:
                raw_value = getattr(page, attribute, None)
                numeric = _safe_float_value(raw_value)
                if numeric is not None:
                    values.append(numeric)
            return _avg(values)

        def _bool_flag(value: Any) -> str:
            return "yes" if bool(value) else "no"

        target = audit.target_audit if isinstance(audit.target_audit, dict) else {}
        external = _as_dict(audit.external_intelligence)
        competitors = (
            audit.competitor_audits if isinstance(audit.competitor_audits, list) else []
        )
        raw_pages = getattr(audit, "pages", None)
        try:
            page_rows = list(raw_pages or [])
        except Exception:
            page_rows = []

        site_metrics = _as_dict(target.get("site_metrics"))
        structure_data = _as_dict(target.get("structure"))
        content_data = _as_dict(target.get("content"))
        eeat_data = _as_dict(target.get("eeat"))
        schema_data = _as_dict(target.get("schema"))
        transparency_signals = _as_dict(eeat_data.get("transparency_signals"))
        citation_signals = _as_dict(eeat_data.get("citations_and_sources"))
        page_count = (
            len(page_rows)
            or _safe_int_value(target.get("audited_pages_count"))
            or _safe_int_value(getattr(audit, "total_pages", None), 0)
            or 0
        )
        issue_totals = {
            "critical": _safe_int_value(target.get("critical_issues_count")),
            "high": _safe_int_value(target.get("high_issues_count")),
            "medium": _safe_int_value(target.get("medium_issues_count")),
            "low": _safe_int_value(target.get("low_issues_count")),
        }
        if page_rows:
            issue_totals = {
                "critical": sum(_safe_int_value(getattr(page, "critical_issues", 0), 0) or 0 for page in page_rows),
                "high": sum(_safe_int_value(getattr(page, "high_issues", 0), 0) or 0 for page in page_rows),
                "medium": sum(_safe_int_value(getattr(page, "medium_issues", 0), 0) or 0 for page in page_rows),
                "low": sum(_safe_int_value(getattr(page, "low_issues", 0), 0) or 0 for page in page_rows),
            }
        else:
            issue_totals = {
                "critical": issue_totals["critical"] or _safe_int_value(getattr(audit, "critical_issues", None), 0) or 0,
                "high": issue_totals["high"] or _safe_int_value(getattr(audit, "high_issues", None), 0) or 0,
                "medium": issue_totals["medium"] or _safe_int_value(getattr(audit, "medium_issues", None), 0) or 0,
                "low": issue_totals["low"] or _safe_int_value(getattr(audit, "low_issues", None), 0) or 0,
            }
        data_gaps = [str(item).strip() for item in (data_gaps or []) if str(item).strip()]

        observed_queries = PDFService._extract_query_texts(external.get("queries_to_run"))
        avg_overall_score = _score_from_pages("overall_score")
        avg_h1_score = _score_from_pages("h1_score")
        avg_structure_score = _score_from_pages("structure_score")
        avg_content_score = _score_from_pages("content_score")
        avg_eeat_score = _score_from_pages("eeat_score")
        avg_schema_score = _score_from_pages("schema_score")
        risky_pages = sorted(
            [
                page
                for page in page_rows
                if hasattr(page, "path") or hasattr(page, "url")
            ],
            key=lambda page: (
                -(_safe_int_value(getattr(page, "critical_issues", 0), 0) or 0),
                -(_safe_int_value(getattr(page, "high_issues", 0), 0) or 0),
                _safe_float_value(getattr(page, "overall_score", None), 9999.0) or 9999.0,
            ),
        )[:8]

        mobile = (
            pagespeed_data.get("mobile", {}) if isinstance(pagespeed_data, dict) else {}
        )
        desktop = (
            pagespeed_data.get("desktop", {})
            if isinstance(pagespeed_data, dict)
            else {}
        )
        mobile_perf = mobile.get("performance_score")
        desktop_perf = desktop.get("performance_score")
        mobile_lcp = (
            mobile.get("core_web_vitals", {}).get("lcp")
            if isinstance(mobile.get("core_web_vitals"), dict)
            else None
        )

        keyword_items = []
        if isinstance(keywords_data, dict):
            keyword_items = (
                keywords_data.get("items") or keywords_data.get("keywords") or []
            )
        if not isinstance(keyword_items, list):
            keyword_items = []

        backlink_items = []
        if isinstance(backlinks_data, dict):
            backlink_items = (
                backlinks_data.get("top_backlinks") or backlinks_data.get("items") or []
            )
        if not isinstance(backlink_items, list):
            backlink_items = []

        ranking_items = []
        if isinstance(rank_tracking_data, dict):
            ranking_items = (
                rank_tracking_data.get("rankings")
                or rank_tracking_data.get("items")
                or []
            )
        if not isinstance(ranking_items, list):
            ranking_items = []
        geo_score = target.get("geo_score", "not_available")

        fix_plan = fix_plan if fix_plan is not None else getattr(audit, "fix_plan", [])
        if isinstance(fix_plan, str):
            try:
                fix_plan = json.loads(fix_plan)
            except Exception:
                fix_plan = []
        if not isinstance(fix_plan, list):
            fix_plan = []

        top_keywords = sorted(
            [item for item in keyword_items if isinstance(item, dict)],
            key=lambda row: PDFService._safe_float(row.get("opportunity_score"), 0.0),
            reverse=True,
        )[:5]
        top_backlinks = [
            item for item in backlink_items if isinstance(item, dict)
        ][:5]
        top_rankings = sorted(
            [item for item in ranking_items if isinstance(item, dict)],
            key=lambda row: PDFService._safe_int(row.get("position"), 9999),
        )[:5]
        roadmap_items = [
            item
            for item in fix_plan
            if isinstance(item, dict) and (item.get("issue") or item.get("title"))
        ][:6]
        category = _safe_text(external.get("category"))
        subcategory = _safe_text(external.get("subcategory"))
        market = _safe_text(external.get("market") or target.get("market"))
        competitor_domains = []
        for competitor in competitors[:5]:
            if isinstance(competitor, dict):
                comp_schema = _as_dict(competitor.get("schema"))
                comp_schema_presence = _as_dict(comp_schema.get("schema_presence"))
                competitor_domains.append(
                    "|".join(
                        [
                            _safe_text(
                                competitor.get("domain")
                                or competitor.get("url")
                                or f"competitor_{len(competitor_domains) + 1}"
                            ),
                            f"geo={_safe_score(competitor.get('geo_score'))}",
                            f"schema={_safe_text(comp_schema_presence.get('status'))}",
                        ]
                    )
                )
            else:
                competitor_domains.append(
                    "|".join(
                        [
                            _safe_text(
                                getattr(competitor, "domain", None)
                                or getattr(competitor, "url", None)
                                or f"competitor_{len(competitor_domains) + 1}"
                            ),
                            f"geo={_safe_score(getattr(competitor, 'geo_score', None))}",
                            "schema=not_available",
                        ]
                    )
                )
        competitor_domains = [str(value).strip() for value in competitor_domains if value]
        derived_roadmap_items: List[str] = []
        h1_coverage = _safe_float_value(site_metrics.get("h1_coverage_percent"))
        if h1_coverage is not None and h1_coverage < 100:
            derived_roadmap_items.append(
                f"Normalize H1 implementation across templates (observed coverage {h1_coverage:.1f}%)."
            )
        header_issue_pages = _safe_int_value(site_metrics.get("header_hierarchy_issue_pages"))
        if header_issue_pages:
            derived_roadmap_items.append(
                f"Repair heading hierarchy on {header_issue_pages} audited pages."
            )
        image_alt_coverage = _safe_float_value(site_metrics.get("image_alt_coverage_percent"))
        if image_alt_coverage is not None and image_alt_coverage < 100:
            derived_roadmap_items.append(
                f"Improve image alt coverage from {image_alt_coverage:.1f}% to full coverage."
            )
        faq_schema_pages = _safe_int_value(site_metrics.get("faq_schema_pages"), 0) or 0
        if faq_schema_pages == 0:
            derived_roadmap_items.append(
                "Add FAQ schema only where the audited content already supports question-and-answer blocks."
            )
        offer_schema_pages = _safe_int_value(site_metrics.get("offer_schema_pages"), 0) or 0
        pages_with_price = _safe_int_value(site_metrics.get("pages_with_price"), 0) or 0
        if offer_schema_pages == 0 and pages_with_price:
            derived_roadmap_items.append(
                f"Extend offer/price structured data to the {pages_with_price} pages that already expose price information."
            )

        reason_lines = {
            "llm_failure": [
                "- Report mode: grounded deterministic report using only observed audit data.",
                "- Reason: LLM regeneration was unavailable during this run.",
            ],
            "supporting_data_gap": [
                "- Report mode: grounded deterministic report using only observed audit, page, and competitor data.",
                "- Reason: multiple supporting datasets were unavailable, so the LLM path was intentionally skipped.",
            ],
            "missing_context": [
                "- Report mode: grounded deterministic report using only the validated subset of collected audit data.",
                "- Reason: core audit context was incomplete for LLM regeneration.",
            ],
        }
        active_reason_lines = reason_lines.get(reason, reason_lines["llm_failure"])

        report_lines = [
            "# 1. Executive Summary",
            f"- Target: {_safe_text(getattr(audit, 'domain', None) or getattr(audit, 'url', None))}",
            f"- Audit URL: {_safe_text(getattr(audit, 'url', None))}",
            f"- Market: {market}",
            f"- Category: {category}",
            f"- Subcategory: {subcategory}",
            f"- Generated at (UTC): {datetime.now(UTC).isoformat()}",
            *active_reason_lines,
            f"- Pages analysed: {page_count}",
            f"- Observed competitor records: {len(competitors)}",
            f"- Observed query set: {len(observed_queries)}",
            f"- GEO score: {_safe_score(geo_score)}",
            f"- Average audited page score: {_safe_score(avg_overall_score)}",
            f"- Average structure score: {_safe_score(avg_structure_score)}",
            f"- Average content score: {_safe_score(avg_content_score)}",
            f"- Average E-E-A-T score: {_safe_score(avg_eeat_score)}",
            f"- Issue totals: critical={issue_totals['critical']}, high={issue_totals['high']}, medium={issue_totals['medium']}, low={issue_totals['low']}",
            "",
            "### Observed Data Coverage",
            f"- PageSpeed dataset available: {_bool_flag(PDFService._has_pdf_dataset('pagespeed', pagespeed_data))}",
            f"- Keyword rows available: {len(keyword_items)}",
            f"- Backlink rows available: {len(backlink_items)}",
            f"- Ranking rows available: {len(ranking_items)}",
            f"- LLM visibility rows available: {len(llm_visibility_data) if isinstance(llm_visibility_data, list) else 0}",
            f"- AI content suggestions available: {len(ai_content_suggestions) if isinstance(ai_content_suggestions, list) else 0}",
            "",
            "# 2. Competitive Intelligence Matrix",
            f"- Competitor records available: {len(competitors)}",
            f"- Reference domains: {', '.join(competitor_domains) if competitor_domains else 'not_available'}",
            "",
            "### Competitive Gap Analysis",
            f"- External category: {category}",
            f"- External subcategory: {subcategory}",
            f"- Market context: {market}",
            f"- Observed query seeds: {', '.join(observed_queries[:8]) if observed_queries else 'not_available'}",
            "",
            "# 3. Technical Performance & Financial Impact",
            f"- Mobile performance score: {_safe_score(mobile_perf)}",
            f"- Desktop performance score: {_safe_score(desktop_perf)}",
            f"- Mobile LCP: {_safe_score(mobile_lcp)}",
            f"- Pages analysed in site metrics: {_safe_text(site_metrics.get('pages_analyzed'))}",
            f"- Product pages observed: {_safe_text(site_metrics.get('product_page_count'))}",
            f"- Average images per page: {_safe_score(site_metrics.get('avg_images_per_page'))}",
            "",
            "### Core Web Vitals & Performance Economics",
            "- Financial impact is not estimated unless revenue and traffic inputs are explicitly present in the collected audit context.",
            f"- Header hierarchy issue pages: {_safe_text(site_metrics.get('header_hierarchy_issue_pages'))}",
            f"- Homepage H1 status: {_safe_text(site_metrics.get('homepage_h1_status'))}",
            "",
            "# 4. SEO Foundation",
            f"- Critical issues: {issue_totals['critical']}",
            f"- High issues: {issue_totals['high']}",
            f"- Medium issues: {issue_totals['medium']}",
            f"- Low issues: {issue_totals['low']}",
            f"- H1 coverage percent: {_safe_score(site_metrics.get('h1_coverage_percent'))}",
            f"- Header hierarchy coverage percent: {_safe_score(site_metrics.get('header_hierarchy_coverage_percent'))}",
            f"- Meta description coverage percent: {_safe_score(site_metrics.get('meta_description_coverage_percent'))}",
            f"- Meta keywords coverage percent: {_safe_score(site_metrics.get('meta_keywords_coverage_percent'))}",
            f"- Schema coverage percent: {_safe_score(site_metrics.get('schema_coverage_percent'))}",
            "",
            "# 5. Content Strategy & GEO Optimisation",
            f"- Average H1 score: {_safe_score(avg_h1_score)}",
            f"- Average schema score: {_safe_score(avg_schema_score)}",
            f"- Average text sample length: {_safe_score(site_metrics.get('avg_text_sample_length'))}",
            f"- AI content suggestions available: {len(ai_content_suggestions) if isinstance(ai_content_suggestions, list) else 0}",
            f"- LLM visibility records available: {len(llm_visibility_data) if isinstance(llm_visibility_data, list) else 0}",
            "",
            "# 6. Authority & Backlink Profile",
            f"- Backlinks captured: {len(backlink_items)}",
            f"- Referring domains: {_safe_text(backlinks_data.get('referring_domains') if isinstance(backlinks_data, dict) else None, '0')}",
            f"- About page detected: {_bool_flag(transparency_signals.get('about'))}",
            f"- Contact page detected: {_bool_flag(transparency_signals.get('contact'))}",
            f"- Privacy page detected: {_bool_flag(transparency_signals.get('privacy'))}",
            f"- Observed authoritative links: {_safe_text(citation_signals.get('authoritative_links'), '0')}",
        ]

        if top_backlinks:
            report_lines.append("### Observed Backlinks")
            for row in top_backlinks:
                report_lines.append(
                    f"- {_safe_text(row.get('source_url'))} | authority={_safe_score(row.get('domain_authority'))} | dofollow={bool(row.get('is_dofollow'))}"
                )
        else:
            report_lines.append("- No backlink rows were available for this run.")

        report_lines.extend(
            [
                "",
                "# 7. Keyword Strategy & Intent Mapping",
                f"- Keywords collected: {len(keyword_items)}",
                f"- Rankings collected: {len(ranking_items)}",
                f"- External query seeds: {', '.join(observed_queries[:10]) if observed_queries else 'not_available'}",
            ]
        )
        if top_keywords:
            report_lines.append("### Top Opportunities")
            for row in top_keywords:
                report_lines.append(
                    f"- {_safe_text(row.get('keyword'))} | volume={_safe_score(row.get('search_volume'))} | difficulty={_safe_score(row.get('difficulty'))} | source={_safe_text(row.get('metrics_source'))}"
                )
        else:
            report_lines.append("- Keyword research is not available in this run.")

        report_lines.extend(
            [
                "",
                "# 8. LLM Visibility & AI Mentions",
                f"- LLM visibility entries: {len(llm_visibility_data) if isinstance(llm_visibility_data, list) else 0}",
                f"- Visible mentions: {len([row for row in llm_visibility_data if isinstance(row, dict) and row.get('is_visible')]) if isinstance(llm_visibility_data, list) else 0}",
                "",
                "# 9. Product Intelligence",
                f"- Category context: {category}",
                f"- Subcategory context: {subcategory}",
                f"- Product pages observed: {_safe_text(site_metrics.get('product_page_count'))}",
                f"- Pages with price observed: {_safe_text(site_metrics.get('pages_with_price'))}",
                f"- Price samples observed: {_safe_text(site_metrics.get('price_samples_count'))}",
                f"- Average observed price: {_safe_score(site_metrics.get('avg_price'))}",
                f"- Price currency: {_safe_text(site_metrics.get('price_currency'))}",
                f"- Product schema pages: {_safe_text(site_metrics.get('product_schema_pages'))}",
                f"- Offer schema pages: {_safe_text(site_metrics.get('offer_schema_pages'))}",
                f"- Review schema pages: {_safe_text(site_metrics.get('review_schema_pages'))}",
                f"- FAQ schema pages: {_safe_text(site_metrics.get('faq_schema_pages'))}",
                "",
                "# 10. 90-Day Strategic Roadmap",
            ]
        )
        if roadmap_items:
            for idx, item in enumerate(roadmap_items, start=1):
                report_lines.append(
                    f"- P{idx}: {_safe_text(item.get('title') or item.get('issue'))}"
                )
        elif derived_roadmap_items:
            for idx, item in enumerate(derived_roadmap_items[:6], start=1):
                report_lines.append(f"- P{idx}: {item}")
        else:
            report_lines.append(
                "- No validated action plan items were available at PDF generation time."
            )

        report_lines.extend(["", "### Highest-Risk URLs"])
        if risky_pages:
            for page in risky_pages:
                report_lines.append(
                    f"- {_safe_text(getattr(page, 'path', None) or getattr(page, 'url', None))} | overall={_safe_score(getattr(page, 'overall_score', None))} | critical={_safe_text(getattr(page, 'critical_issues', None), '0')} | high={_safe_text(getattr(page, 'high_issues', None), '0')} | schema={_safe_score(getattr(page, 'schema_score', None))}"
                )
        else:
            report_lines.append("- Individual page rows were not available in this run.")

        report_lines.extend(
            [
                "",
                "# 11. Appendices",
                "- Appendix C reflects the validated `fix_plan.json` when present.",
                "- Appendix D reflects only datasets physically available in this run.",
                "",
                "### Data Quality Notes",
            ]
        )
        report_lines.extend(
            [
                f"- Keywords collected: {len(keyword_items)}",
                f"- Backlinks collected: {len(backlink_items)}",
                f"- Rankings collected: {len(ranking_items)}",
                f"- LLM visibility entries: {len(llm_visibility_data) if isinstance(llm_visibility_data, list) else 0}",
                f"- AI content suggestions: {len(ai_content_suggestions) if isinstance(ai_content_suggestions, list) else 0}",
                f"- Schema types observed: {', '.join(schema_data.get('schema_types', [])) if isinstance(schema_data.get('schema_types'), list) and schema_data.get('schema_types') else 'not_available'}",
                f"- Transparency signals: about={_bool_flag(transparency_signals.get('about'))}, contact={_bool_flag(transparency_signals.get('contact'))}, privacy={_bool_flag(transparency_signals.get('privacy'))}",
            ]
        )
        if data_gaps:
            report_lines.append(
                f"- Missing supporting datasets for this run: {', '.join(sorted(set(data_gaps)))}"
            )
        if top_rankings:
            report_lines.extend(["", "### Observed Rankings"])
            for row in top_rankings:
                report_lines.append(
                    f"- {_safe_text(row.get('keyword'))} | position={_safe_score(row.get('position'))} | url={_safe_text(row.get('url'))}"
                )
        else:
            report_lines.append("- Ranking data was not available in this run.")

        report_lines.extend(
            [
                "",
                "### Notes",
                "- This report contains only observed data from this run.",
                "- No unverified revenue, market-share, traffic, or ROI claims were added.",
                "- Any missing metric is marked as not_available and should be enriched in subsequent runs.",
            ]
        )

        return "\n".join(report_lines).strip()

    @staticmethod
    def _extract_seed_tokens(raw: Any) -> List[str]:
        if raw is None:
            return []
        values: List[str] = []
        if isinstance(raw, str):
            values.append(raw)
        elif isinstance(raw, dict):
            for value in raw.values():
                values.extend(PDFService._extract_seed_tokens(value))
        elif isinstance(raw, list):
            for value in raw:
                values.extend(PDFService._extract_seed_tokens(value))
        else:
            values.append(str(raw))

        tokens: List[str] = []
        for text in values:
            cleaned = (
                str(text)
                .replace("|", " ")
                .replace("/", " ")
                .replace("_", " ")
                .replace("-", " ")
                .strip()
            )
            if not cleaned:
                continue
            tokens.append(cleaned)
            for token in cleaned.split():
                token_norm = token.strip().lower()
                if len(token_norm) >= 3:
                    tokens.append(token_norm)
        return tokens

    @staticmethod
    def _build_seed_keywords(audit: Audit, domain: str) -> List[str]:
        external = (
            audit.external_intelligence
            if isinstance(audit.external_intelligence, dict)
            else {}
        )
        target = audit.target_audit if isinstance(audit.target_audit, dict) else {}
        content = (
            target.get("content", {})
            if isinstance(target.get("content", {}), dict)
            else {}
        )

        onsite_core_terms: List[str] = []
        try:
            from .pipeline_service import PipelineService

            onsite_core_terms = PipelineService._extract_core_terms_from_target(
                target, max_terms=8, include_generic=False
            )
        except Exception:
            onsite_core_terms = []

        raw_seed_sources = [
            domain,
            target.get("domain"),
            target.get("market"),
            external.get("category"),
            external.get("subcategory"),
            external.get("market"),
            external.get("business_type"),
            external.get("industry_context"),
            content.get("title"),
            content.get("meta_description"),
            content.get("meta_keywords"),
            target.get("audited_page_paths"),
            onsite_core_terms,
        ]
        if domain:
            raw_seed_sources.extend(domain.split("."))

        seen = set()
        ordered_seeds: List[str] = []
        for token in PDFService._extract_seed_tokens(raw_seed_sources):
            normalized = " ".join(str(token).strip().lower().split())
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered_seeds.append(str(token).strip())
            if len(ordered_seeds) >= 25:
                break
        return ordered_seeds

    @staticmethod
    def _extract_external_queries(audit: Audit) -> List[str]:
        external = (
            audit.external_intelligence
            if isinstance(audit.external_intelligence, dict)
            else {}
        )
        raw_queries = external.get("queries_to_run", [])
        ordered_queries: List[str] = []
        seen = set()

        if not isinstance(raw_queries, list):
            return ordered_queries

        for raw_query in raw_queries:
            if isinstance(raw_query, str):
                term = raw_query.strip()
            elif isinstance(raw_query, dict):
                term = str(raw_query.get("query") or "").strip()
            else:
                term = str(raw_query or "").strip()

            normalized = " ".join(term.lower().split())
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered_queries.append(term)

        return ordered_queries

    @staticmethod
    def _collect_geo_query_terms(
        *,
        audit: Audit,
        domain: str,
        keywords_data_list: List[Dict[str, Any]],
        seed_keywords: List[str],
        limit: int,
    ) -> List[str]:
        ordered_terms: List[str] = []
        seen = set()

        def _add_term(raw_term: Any) -> None:
            term = str(raw_term or "").strip()
            normalized = " ".join(term.lower().split())
            if not normalized or normalized in seen:
                return
            seen.add(normalized)
            ordered_terms.append(term)

        for row in keywords_data_list or []:
            if not isinstance(row, dict):
                continue
            _add_term(row.get("keyword") or row.get("term") or row.get("query"))
            if len(ordered_terms) >= limit:
                return ordered_terms[:limit]

        for raw_query in PDFService._extract_external_queries(audit):
            _add_term(raw_query)
            if len(ordered_terms) >= limit:
                return ordered_terms[:limit]

        for seed in seed_keywords or []:
            _add_term(seed)
            if len(ordered_terms) >= limit:
                return ordered_terms[:limit]

        if not ordered_terms and domain:
            _add_term(domain.split(".")[0])

        return ordered_terms[:limit]

    @staticmethod
    def _normalize_ai_suggestion_row(raw: Any) -> Dict[str, Any]:
        if isinstance(raw, dict):
            outline = raw.get("outline", raw.get("content_outline", {}))
            target_keyword = raw.get("target_keyword")
            return {
                "title": str(raw.get("title") or raw.get("topic") or "").strip(),
                "target_keyword": str(target_keyword or "").strip(),
                "content_type": str(
                    raw.get("content_type") or raw.get("suggestion_type") or ""
                ).strip(),
                "priority": str(raw.get("priority") or "medium").strip() or "medium",
                "estimated_traffic": PDFService._safe_int(
                    raw.get("estimated_traffic"), 0
                ),
                "difficulty": PDFService._safe_int(raw.get("difficulty"), 0),
                "outline": outline if isinstance(outline, (dict, list)) else {},
            }

        outline = getattr(raw, "content_outline", None)
        target_keyword = getattr(raw, "target_keyword", None)
        if not target_keyword and isinstance(outline, dict):
            target_keyword = outline.get("target_keyword")

        return {
            "title": str(getattr(raw, "topic", "") or getattr(raw, "title", "")).strip(),
            "target_keyword": str(target_keyword or "").strip(),
            "content_type": str(
                getattr(raw, "suggestion_type", "")
                or getattr(raw, "content_type", "")
            ).strip(),
            "priority": str(getattr(raw, "priority", "medium") or "medium").strip()
            or "medium",
            "estimated_traffic": PDFService._safe_int(
                getattr(raw, "estimated_traffic", 0), 0
            ),
            "difficulty": PDFService._safe_int(getattr(raw, "difficulty", 0), 0),
            "outline": outline if isinstance(outline, (dict, list)) else {},
        }

    @staticmethod
    def _build_pdf_metadata(audit: Audit) -> Dict[str, str]:
        audit_url = str(getattr(audit, "url", "") or "").strip()
        if audit_url and "://" not in audit_url:
            audit_url = f"https://{audit_url}"
        parsed = urlparse(audit_url) if audit_url else None
        domain = (getattr(audit, "domain", "") or "").strip()
        if not domain and parsed:
            domain = (parsed.hostname or "").lower()
        domain = domain[4:] if domain.startswith("www.") else domain

        prepared_by = str(getattr(audit, "user_email", "") or "").strip()
        if not prepared_by or "|" in prepared_by:
            prepared_by = "Auditor GEO"
        cover_subject = domain or audit_url or "Digital Audit"
        footer_left = audit_url or "N/A"
        footer_right = domain or "Audit"

        return {
            "prepared_by": str(prepared_by),
            "footer_left": str(footer_left),
            "footer_right": str(footer_right),
            "report_title_prefix": "GEO Audit Report",
            "cover_title": f"GEO Audit Report\n{cover_subject}",
        }

    @staticmethod
    def _load_complete_audit_context(db, audit_id: int) -> dict:
        """
        Load complete context from ALL audit features for LLM.

        This ensures the LLM has access to:
        - PageSpeed data (mobile + desktop)
        - Keywords research data
        - Backlinks analysis
        - Rank tracking data
        - LLM visibility analysis
        - AI content suggestions
        - Target audit data
        - External intelligence
        - Search results
        - Competitor audits

        Returns:
            Complete context dictionary for LLM
        """
        from .audit_service import AuditService

        logger.info(f"Loading complete audit context for audit {audit_id}")

        audit = AuditService.get_audit(db, audit_id)
        if not audit:
            logger.warning(f"Audit {audit_id} not found for context loading")
            return {}

        # Load related data from database
        keywords = []
        if hasattr(audit, "keywords"):
            for k in audit.keywords:
                volume_value = (
                    k.volume
                    if hasattr(k, "volume")
                    else k.search_volume if hasattr(k, "search_volume") else 0
                ) or 0
                difficulty_value = (
                    k.difficulty if hasattr(k, "difficulty") else 0
                ) or 0
                cpc_value = (k.cpc if hasattr(k, "cpc") else 0) or 0
                metrics_source = (
                    "google_ads"
                    if (volume_value > 0 or difficulty_value > 0 or cpc_value > 0)
                    else "not_available"
                )
                keywords.append(
                    {
                        "keyword": (
                            k.term
                            if hasattr(k, "term")
                            else k.keyword if hasattr(k, "keyword") else ""
                        ),
                        "search_volume": volume_value,
                        "difficulty": difficulty_value,
                        "cpc": cpc_value,
                        "intent": k.intent if hasattr(k, "intent") else "",
                        "current_rank": getattr(k, "current_rank", None),
                        "opportunity_score": getattr(k, "opportunity_score", None),
                        "metrics_source": metrics_source,
                    }
                )

        backlinks = {
            "total_backlinks": (
                len(audit.backlinks) if hasattr(audit, "backlinks") else 0
            ),
            "referring_domains": (
                len(
                    set(
                        (
                            b.source_url.split("/")[2]
                            if "/" in b.source_url
                            else b.source_url
                        )
                        for b in audit.backlinks
                    )
                )
                if hasattr(audit, "backlinks")
                else 0
            ),
            "top_backlinks": [],
        }
        if hasattr(audit, "backlinks"):
            for b in audit.backlinks[:20]:  # Top 20
                backlinks["top_backlinks"].append(
                    {
                        "source_url": b.source_url,
                        "target_url": b.target_url,
                        "anchor_text": (
                            b.anchor_text if hasattr(b, "anchor_text") else ""
                        ),
                        "domain_authority": (
                            b.domain_authority if hasattr(b, "domain_authority") else 0
                        )
                        or 0,
                        "page_authority": getattr(b, "page_authority", 0) or 0,
                        "spam_score": getattr(b, "spam_score", 0) or 0,
                        "link_type": (
                            "dofollow"
                            if getattr(b, "is_dofollow", True)
                            else "nofollow"
                        ),
                    }
                )

        rank_tracking = []
        if hasattr(audit, "rank_trackings"):
            for r in audit.rank_trackings:
                rank_tracking.append(
                    {
                        "keyword": r.keyword,
                        "position": (r.position or 100),
                        "url": r.url,
                        "search_engine": getattr(r, "search_engine", "google"),
                        "location": r.location if hasattr(r, "location") else "US",
                        "device": r.device if hasattr(r, "device") else "desktop",
                        "previous_position": getattr(r, "previous_position", None),
                        "change": (
                            ((r.position or 100) - getattr(r, "previous_position", 0))
                            if getattr(r, "previous_position", None)
                            else 0
                        ),
                    }
                )

        llm_visibility = []
        if hasattr(audit, "llm_visibilities"):
            for visibility in audit.llm_visibilities:
                llm_visibility.append(
                    {
                        "query": visibility.query,
                        "llm_platform": (
                            visibility.llm_name
                            if hasattr(visibility, "llm_name")
                            else getattr(visibility, "llm_platform", "")
                        ),
                        "mentioned": (
                            visibility.is_visible
                            if hasattr(visibility, "is_visible")
                            else getattr(visibility, "mentioned", False)
                        ),
                        "position": (
                            visibility.rank
                            if hasattr(visibility, "rank")
                            else getattr(visibility, "position", None)
                        ),
                        "context": (
                            visibility.citation_text
                            if hasattr(visibility, "citation_text")
                            else getattr(visibility, "context", "")
                        ),
                        "sentiment": getattr(visibility, "sentiment", "neutral"),
                        "competitors_mentioned": getattr(
                            visibility, "competitors_mentioned", []
                        ),
                    }
                )

        ai_content_suggestions = []
        if hasattr(audit, "ai_content_suggestions") and audit.ai_content_suggestions:
            # Load from database
            for a in audit.ai_content_suggestions:
                ai_content_suggestions.append(
                    {
                        "title": (
                            a.topic if hasattr(a, "topic") else getattr(a, "title", "")
                        ),
                        "target_keyword": getattr(a, "target_keyword", ""),
                        "content_type": (
                            a.suggestion_type
                            if hasattr(a, "suggestion_type")
                            else getattr(a, "content_type", "")
                        ),
                        "priority": a.priority if hasattr(a, "priority") else "medium",
                        "estimated_traffic": getattr(a, "estimated_traffic", 0) or 0,
                        "difficulty": getattr(a, "difficulty", 0) or 0,
                        "outline": (
                            a.content_outline
                            if hasattr(a, "content_outline")
                            else getattr(a, "outline", {})
                        ),
                    }
                )
        else:
            logger.info(
                "AI content suggestions not found in DB for audit %s. "
                "They will be refreshed later in the PDF pipeline if required.",
                audit_id,
            )

        context = {
            # Core audit data
            "target_audit": audit.target_audit or {},
            "external_intelligence": audit.external_intelligence or {},
            "search_results": audit.search_results or {},
            "competitor_audits": audit.competitor_audits or [],
            # PageSpeed data (complete)
            "pagespeed": audit.pagespeed_data or {},
            # Keywords data
            "keywords": keywords,
            "keywords_summary": {
                "total_keywords": len(keywords),
                "high_volume_keywords": len(
                    [k for k in keywords if k.get("search_volume", 0) > 1000]
                ),
                "low_difficulty_opportunities": len(
                    [k for k in keywords if k.get("difficulty", 100) < 30]
                ),
                "average_difficulty": (
                    sum(k.get("difficulty", 0) for k in keywords) / len(keywords)
                    if keywords
                    else 0
                ),
            },
            # Backlinks data
            "backlinks": backlinks,
            "backlinks_summary": {
                "total_backlinks": backlinks["total_backlinks"],
                "referring_domains": backlinks["referring_domains"],
                "average_domain_authority": (
                    sum(
                        b.get("domain_authority", 0) for b in backlinks["top_backlinks"]
                    )
                    / len(backlinks["top_backlinks"])
                    if backlinks["top_backlinks"]
                    else 0
                ),
                "dofollow_count": len(
                    [
                        b
                        for b in backlinks["top_backlinks"]
                        if b.get("link_type") == "dofollow"
                    ]
                ),
                "nofollow_count": len(
                    [
                        b
                        for b in backlinks["top_backlinks"]
                        if b.get("link_type") == "nofollow"
                    ]
                ),
            },
            # Rank tracking data
            "rank_tracking": rank_tracking,
            "rank_tracking_summary": {
                "total_tracked_keywords": len(rank_tracking),
                "top_10_rankings": len(
                    [r for r in rank_tracking if r.get("position", 100) <= 10]
                ),
                "top_3_rankings": len(
                    [r for r in rank_tracking if r.get("position", 100) <= 3]
                ),
                "average_position": (
                    sum(r.get("position", 100) for r in rank_tracking)
                    / len(rank_tracking)
                    if rank_tracking
                    else 0
                ),
                "improved_rankings": len(
                    [r for r in rank_tracking if r.get("change", 0) < 0]
                ),  # Negative change = improvement
                "declined_rankings": len(
                    [r for r in rank_tracking if r.get("change", 0) > 0]
                ),
            },
            # LLM visibility data
            "llm_visibility": llm_visibility,
            "llm_visibility_summary": {
                "total_queries_analyzed": len(llm_visibility),
                "mentions_count": len(
                    [entry for entry in llm_visibility if entry.get("mentioned")]
                ),
                "average_position": (
                    sum(
                        entry.get("position", 100)
                        for entry in llm_visibility
                        if entry.get("mentioned") and entry.get("position")
                    )
                    / len(
                        [
                            entry
                            for entry in llm_visibility
                            if entry.get("mentioned") and entry.get("position")
                        ]
                    )
                    if any(
                        entry.get("mentioned") and entry.get("position")
                        for entry in llm_visibility
                    )
                    else 0
                ),
                "platforms": list(
                    set(
                        entry.get("llm_platform")
                        for entry in llm_visibility
                        if entry.get("llm_platform")
                    )
                ),
                "positive_sentiment": len(
                    [
                        entry
                        for entry in llm_visibility
                        if entry.get("sentiment") == "positive"
                    ]
                ),
                "neutral_sentiment": len(
                    [
                        entry
                        for entry in llm_visibility
                        if entry.get("sentiment") == "neutral"
                    ]
                ),
                "negative_sentiment": len(
                    [
                        entry
                        for entry in llm_visibility
                        if entry.get("sentiment") == "negative"
                    ]
                ),
            },
            # AI content suggestions
            "ai_content_suggestions": ai_content_suggestions,
            "content_suggestions_summary": {
                "total_suggestions": len(ai_content_suggestions),
                "high_priority": len(
                    [a for a in ai_content_suggestions if a.get("priority") == "high"]
                ),
                "medium_priority": len(
                    [a for a in ai_content_suggestions if a.get("priority") == "medium"]
                ),
                "low_priority": len(
                    [a for a in ai_content_suggestions if a.get("priority") == "low"]
                ),
                "estimated_total_traffic": sum(
                    a.get("estimated_traffic", 0) for a in ai_content_suggestions
                ),
            },
        }

        logger.info(
            f"Complete context loaded for audit {audit_id}: {len(keywords)} keywords, {backlinks['total_backlinks']} backlinks, {len(rank_tracking)} rankings, {len(llm_visibility)} LLM visibility entries, {len(ai_content_suggestions)} content suggestions"
        )
        return context

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _build_deterministic_fallback_report(
        audit_url: str,
        pagespeed_data: Dict[str, Any],
        keywords_data: Dict[str, Any],
        backlinks_data: Dict[str, Any],
        rank_tracking_data: Dict[str, Any],
        llm_visibility_data: List[Dict[str, Any]],
        ai_content_suggestions: List[Dict[str, Any]],
    ) -> str:
        """
        Build a no-LLM fallback report using only existing collected data.
        This avoids complete PDF failure when LLM providers are transiently unavailable.
        """
        keyword_items = []
        if isinstance(keywords_data, dict):
            raw_keywords = (
                keywords_data.get("items") or keywords_data.get("keywords") or []
            )
            if isinstance(raw_keywords, list):
                keyword_items = [k for k in raw_keywords if isinstance(k, dict)]

        backlink_items = []
        if isinstance(backlinks_data, dict):
            raw_backlinks = (
                backlinks_data.get("top_backlinks") or backlinks_data.get("items") or []
            )
            if isinstance(raw_backlinks, list):
                backlink_items = [b for b in raw_backlinks if isinstance(b, dict)]

        ranking_items = []
        if isinstance(rank_tracking_data, dict):
            raw_rankings = (
                rank_tracking_data.get("rankings")
                or rank_tracking_data.get("items")
                or []
            )
            if isinstance(raw_rankings, list):
                ranking_items = [r for r in raw_rankings if isinstance(r, dict)]

        mobile_score = (
            pagespeed_data.get("mobile", {}).get("performance_score")
            if isinstance(pagespeed_data, dict)
            else None
        )
        desktop_score = (
            pagespeed_data.get("desktop", {}).get("performance_score")
            if isinstance(pagespeed_data, dict)
            else None
        )

        top_keywords = sorted(
            keyword_items,
            key=lambda row: PDFService._safe_float(row.get("opportunity_score"), 0.0),
            reverse=True,
        )[:10]

        top_rankings = sorted(
            ranking_items,
            key=lambda row: PDFService._safe_int(row.get("position"), 9999),
        )[:10]

        lines = [
            "# Digital Audit Report (Deterministic Fallback)",
            "",
            f"Generated: {datetime.now(UTC).isoformat()}",
            f"Target URL: {audit_url}",
            "",
            "## Executive Snapshot",
            f"- Keywords captured: {len(keyword_items)}",
            f"- Backlinks captured: {len(backlink_items)}",
            f"- Rankings captured: {len(ranking_items)}",
            f"- LLM visibility records: {len(llm_visibility_data) if isinstance(llm_visibility_data, list) else 0}",
            f"- AI content suggestions: {len(ai_content_suggestions) if isinstance(ai_content_suggestions, list) else 0}",
            f"- PageSpeed mobile score: {mobile_score if mobile_score is not None else 'Insufficient data'}",
            f"- PageSpeed desktop score: {desktop_score if desktop_score is not None else 'Insufficient data'}",
            "",
            "## Top Keyword Opportunities",
        ]

        if top_keywords:
            for row in top_keywords:
                kw = row.get("keyword") or row.get("term") or "unknown keyword"
                opp = row.get("opportunity_score")
                volume = row.get("search_volume", row.get("volume", 0))
                diff = row.get("difficulty", 0)
                lines.append(
                    f"- {kw}: opportunity={opp if opp is not None else 'Insufficient data'}, volume={volume}, difficulty={diff}"
                )
        else:
            lines.append("- Insufficient data")

        lines.extend(["", "## Top Backlinks"])
        if backlink_items:
            for row in backlink_items[:10]:
                source = row.get("source_url") or "unknown source"
                target = row.get("target_url") or "unknown target"
                authority = row.get("domain_authority", 0)
                lines.append(f"- {source} -> {target} (authority={authority})")
        else:
            lines.append("- Insufficient data")

        lines.extend(["", "## Top Ranking Signals"])
        if top_rankings:
            for row in top_rankings:
                keyword = row.get("keyword") or "unknown keyword"
                position = row.get("position", "Insufficient data")
                url = row.get("url", "Insufficient data")
                lines.append(f"- {keyword}: position={position}, url={url}")
        else:
            lines.append("- Insufficient data")

        lines.extend(
            [
                "",
                "## Reliability Note",
                "- This report was generated without live LLM regeneration due to a transient provider connectivity issue.",
                "- All values above are derived from persisted audit/GEO datasets only (no fabricated data).",
            ]
        )

        return "\n".join(lines).strip()

    @staticmethod
    def create_from_audit(audit: Audit, markdown_content: str) -> str:
        """
        Genera el PDF de auditoria y lo sube a Supabase Storage.
        """
        if not PDF_GENERATOR_AVAILABLE:
            logger.error(
                "PDF generator no esta disponible. Instalar fpdf2: pip install fpdf2"
            )
            raise ImportError("PDF generator not available")

        logger.info(f"Iniciando generacion de PDF para auditoria {audit.id}")

        original_markdown = getattr(audit, "report_markdown", None)
        if markdown_content:
            audit.report_markdown = markdown_content

        pages = list(getattr(audit, "pages", []) or [])
        competitors = list(getattr(audit, "competitors", []) or [])
        try:
            return asyncio.run(
                PDFService.generate_comprehensive_pdf(
                    audit=audit,
                    pages=pages,
                    competitors=competitors,
                )
            )
        finally:
            audit.report_markdown = original_markdown

    @staticmethod
    def _is_pagespeed_stale(pagespeed_data: dict, max_age_hours: int = 24) -> bool:
        """
        Check if PageSpeed data is stale and needs refresh.

        Args:
            pagespeed_data: Cached PageSpeed data
            max_age_hours: Maximum age in hours before considering stale

        Returns:
            True if data is stale or invalid
        """
        if not pagespeed_data:
            return True

        # Check for mobile data (required)
        mobile_data = pagespeed_data.get("mobile", {})
        if not mobile_data or "error" in mobile_data:
            return True

        # Check timestamp
        fetch_time = mobile_data.get("metadata", {}).get("fetch_time")
        if not fetch_time:
            return True

        try:
            from datetime import datetime, timedelta, timezone

            # Parse ISO format timestamp
            if not isinstance(fetch_time, str):
                logger.warning(f"fetch_time is not a string: {type(fetch_time)}")
                return True

            if "Z" in fetch_time:
                fetch_datetime = datetime.fromisoformat(
                    fetch_time.replace("Z", "+00:00")
                )
            else:
                fetch_datetime = datetime.fromisoformat(fetch_time)

            # Make sure both datetimes are timezone-aware
            if fetch_datetime.tzinfo is None:
                fetch_datetime = fetch_datetime.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            age = now - fetch_datetime
            is_stale = age > timedelta(hours=max_age_hours)

            logger.info(
                f"PageSpeed data age: {age.total_seconds() / 3600:.1f} hours, stale: {is_stale}"
            )
            return is_stale
        except Exception as e:
            logger.warning(f"Error checking PageSpeed staleness: {e}")
            return True

    @staticmethod
    async def generate_pdf_with_complete_context(
        db,
        audit_id: int,
        force_pagespeed_refresh: bool = False,
        force_report_refresh: bool = False,
        force_external_intel_refresh: bool = False,
        return_details: bool = False,
    ) -> Any:
        """
        Generate PDF report with complete context from all features.

        This method:
        1. Automatically runs PageSpeed if not cached or stale
        2. Loads ALL audit data (keywords, backlinks, rankings, etc.)
        3. Regenerates markdown report with complete context for LLM
        4. Generates PDF with the updated report

        Args:
            db: Database session
            audit_id: Audit ID
            force_pagespeed_refresh: If True, re-run PageSpeed even if cached
            force_report_refresh: If True, re-run report regeneration even on cache hit
            force_external_intel_refresh: If True, re-run Agent 1 external intelligence
            return_details: If True, return a dict with cache metadata

        Returns:
            Path to generated PDF file or detailed payload when return_details=True
        """
        from ..core.config import settings
        from .audit_service import AuditService
        from .pagespeed_service import PageSpeedService
        from .pipeline_service import PipelineService

        logger.info(
            f"=== Starting PDF generation with complete context for audit {audit_id} ==="
        )
        always_full_mode = os.getenv(
            "PDF_ALWAYS_FULL_MODE", "false"
        ).strip().lower() in {"1", "true", "yes", "on"}
        deterministic_fallback_enabled = (
            False if always_full_mode else settings.PDF_ALLOW_DETERMINISTIC_FALLBACK
        )

        started_at = time.monotonic()
        total_budget_seconds = PDFService._timeout_from_env(
            "PDF_GENERATION_MAX_SECONDS", 1100.0
        )
        pagespeed_timeout_seconds = PDFService._timeout_from_env(
            "PDF_PAGESPEED_TIMEOUT_SECONDS", 75.0
        )
        geo_stage_timeout_seconds = PDFService._timeout_from_env(
            "PDF_GEO_STAGE_TIMEOUT_SECONDS", 90.0
        )
        keyword_stage_timeout_seconds = PDFService._timeout_from_env(
            "PDF_KEYWORD_STAGE_TIMEOUT_SECONDS",
            max(
                geo_stage_timeout_seconds or 0.0,
                float(settings.NVIDIA_TIMEOUT_SECONDS) + 15.0,
            ),
        )
        backlink_stage_timeout_seconds = PDFService._timeout_from_env(
            "PDF_BACKLINK_STAGE_TIMEOUT_SECONDS",
            max(geo_stage_timeout_seconds or 0.0, 120.0),
        )
        rankings_stage_timeout_seconds = PDFService._timeout_from_env(
            "PDF_RANKINGS_STAGE_TIMEOUT_SECONDS",
            max(
                geo_stage_timeout_seconds or 0.0,
                max(120.0, float(settings.SERPER_TIMEOUT_SECONDS) * 12.0),
            ),
        )
        llm_visibility_stage_timeout_seconds = PDFService._timeout_from_env(
            "PDF_LLM_VISIBILITY_STAGE_TIMEOUT_SECONDS",
            max(
                geo_stage_timeout_seconds or 0.0,
                float(settings.NVIDIA_TIMEOUT_SECONDS) + 15.0,
            ),
        )
        ai_content_stage_timeout_seconds = PDFService._timeout_from_env(
            "PDF_AI_CONTENT_STAGE_TIMEOUT_SECONDS",
            max(
                geo_stage_timeout_seconds or 0.0,
                float(settings.NVIDIA_TIMEOUT_SECONDS) + 15.0,
            ),
        )
        report_timeout_seconds = PDFService._timeout_from_env(
            "PDF_REPORT_TIMEOUT_SECONDS", 300.0
        )
        external_intel_timeout_seconds = PDFService._timeout_from_env(
            "PDF_EXTERNAL_INTEL_TIMEOUT_SECONDS", 45.0
        )
        product_intel_timeout_seconds = PDFService._timeout_from_env(
            "PDF_PRODUCT_INTEL_TIMEOUT_SECONDS", 45.0
        )

        timeout_total_label = (
            f"{total_budget_seconds:.1f}s"
            if total_budget_seconds is not None
            else "disabled"
        )
        timeout_pagespeed_label = (
            f"{pagespeed_timeout_seconds:.1f}s"
            if pagespeed_timeout_seconds is not None
            else "disabled"
        )
        timeout_geo_label = (
            f"{geo_stage_timeout_seconds:.1f}s"
            if geo_stage_timeout_seconds is not None
            else "disabled"
        )
        timeout_keyword_label = (
            f"{keyword_stage_timeout_seconds:.1f}s"
            if keyword_stage_timeout_seconds is not None
            else "disabled"
        )
        timeout_backlink_label = (
            f"{backlink_stage_timeout_seconds:.1f}s"
            if backlink_stage_timeout_seconds is not None
            else "disabled"
        )
        timeout_rankings_label = (
            f"{rankings_stage_timeout_seconds:.1f}s"
            if rankings_stage_timeout_seconds is not None
            else "disabled"
        )
        timeout_llm_visibility_label = (
            f"{llm_visibility_stage_timeout_seconds:.1f}s"
            if llm_visibility_stage_timeout_seconds is not None
            else "disabled"
        )
        timeout_ai_content_label = (
            f"{ai_content_stage_timeout_seconds:.1f}s"
            if ai_content_stage_timeout_seconds is not None
            else "disabled"
        )
        timeout_report_label = (
            f"{report_timeout_seconds:.1f}s"
            if report_timeout_seconds is not None
            else "disabled"
        )
        timeout_external_intel_label = (
            f"{external_intel_timeout_seconds:.1f}s"
            if external_intel_timeout_seconds is not None
            else "disabled"
        )
        timeout_product_intel_label = (
            f"{product_intel_timeout_seconds:.1f}s"
            if product_intel_timeout_seconds is not None
            else "disabled"
        )
        logger.info(
            "PDF timeouts configured: "
            f"total={timeout_total_label}, "
            f"pagespeed={timeout_pagespeed_label}, "
            f"geo_stage_default={timeout_geo_label}, "
            f"keywords={timeout_keyword_label}, "
            f"backlinks={timeout_backlink_label}, "
            f"rankings={timeout_rankings_label}, "
            f"llm_visibility={timeout_llm_visibility_label}, "
            f"ai_content={timeout_ai_content_label}, "
            f"report={timeout_report_label}, "
            f"external_intel={timeout_external_intel_label}, "
            f"product_intel={timeout_product_intel_label}, "
            f"always_full_mode={always_full_mode}"
        )

        # 1. Load audit
        audit = AuditService.get_audit(db, audit_id)
        if not audit:
            raise ValueError(f"Audit {audit_id} not found")
        pagespeed_generation_warnings: List[str] = []

        # 2. Check if PageSpeed data exists and is recent
        pagespeed_data = audit.pagespeed_data
        needs_refresh = (
            force_pagespeed_refresh
            or not pagespeed_data
            or PDFService._is_pagespeed_stale(pagespeed_data)
        )

        # 3. Run PageSpeed if needed
        if needs_refresh:
            logger.info(
                f"Running PageSpeed analysis for audit {audit_id} before PDF generation"
            )
            try:
                refreshed_pagespeed = await PDFService._run_stage_with_timeout(
                    stage_name="PageSpeed analysis",
                    coroutine_factory=lambda: PageSpeedService.analyze_both_strategies(
                        url=str(audit.url), api_key=settings.GOOGLE_PAGESPEED_API_KEY
                    ),
                    stage_timeout_seconds=pagespeed_timeout_seconds,
                    started_at=started_at,
                    total_budget_seconds=total_budget_seconds,
                )
                if not refreshed_pagespeed:
                    raise TimeoutError("PageSpeed analysis did not complete in time")
                pagespeed_data = refreshed_pagespeed

                # Store in database
                AuditService.set_pagespeed_data(db, audit_id, pagespeed_data)
                logger.info("âœ“ PageSpeed data collected and stored")
            except Exception as e:
                logger.error(f"PageSpeed collection failed: {e}")
                pagespeed_generation_warnings.append(
                    "PageSpeed data could not be refreshed in time for this PDF run."
                )
                # Fallback to existing (stale) data if available
                # Fallback to existing (stale) data if available
                try:
                    db.refresh(audit)
                    if audit.pagespeed_data:
                        logger.warning(
                            "Falling back to existing (stale) PageSpeed data"
                        )
                        pagespeed_data = audit.pagespeed_data
                    else:
                        pagespeed_data = None
                except Exception:
                    pagespeed_data = (
                        audit.pagespeed_data if audit.pagespeed_data else None
                    )
        else:
            logger.info("âœ“ Using cached PageSpeed data (fresh)")

        # 4. Prepare GEO Tools context for PDF (cached by default, optional fresh refresh)
        logger.info("Preparing GEO Tools (Keywords, Backlinks, Rankings) for PDF...")
        force_fresh_geo = os.getenv("PDF_FORCE_FRESH_GEO", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if always_full_mode:
            force_fresh_geo = True
        if force_fresh_geo:
            logger.info("PDF_FORCE_FRESH_GEO=true, running fresh GEO data collection")
        else:
            logger.info(
                "Using cached GEO data for PDF generation. Set PDF_FORCE_FRESH_GEO=true to refresh."
            )

        def _safe_float(value: Any, default: float = 0.0) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        def _keyword_opportunity_score(row: Any) -> float:
            if not isinstance(row, dict):
                return 0.0
            return _safe_float(row.get("opportunity_score"), 0.0)

        complete_context = PDFService._load_complete_audit_context(db, audit_id)
        cached_keywords = (
            complete_context.get("keywords", [])
            if isinstance(complete_context.get("keywords", []), list)
            else []
        )
        cached_backlinks = (
            complete_context.get("backlinks", {})
            if isinstance(complete_context.get("backlinks", {}), dict)
            else {}
        )
        cached_rankings = (
            complete_context.get("rank_tracking", [])
            if isinstance(complete_context.get("rank_tracking", []), list)
            else []
        )
        cached_llm_visibility = (
            complete_context.get("llm_visibility", [])
            if isinstance(complete_context.get("llm_visibility", []), list)
            else []
        )
        cached_ai_suggestions = (
            complete_context.get("ai_content_suggestions", [])
            if isinstance(complete_context.get("ai_content_suggestions", []), list)
            else []
        )

        # Initialize from cached context first (fast path)
        keywords_data_list = cached_keywords[:200]
        keywords_data = PDFService._build_keywords_payload(
            keywords_data_list, total=len(cached_keywords)
        )
        backlinks_top = (
            cached_backlinks.get("top_backlinks", [])
            if isinstance(cached_backlinks.get("top_backlinks", []), list)
            else []
        )
        has_cached_backlinks = any(
            key in cached_backlinks
            for key in ("top_backlinks", "total_backlinks", "referring_domains", "summary")
        )
        backlinks_data = (
            PDFService._build_backlinks_payload(
                backlinks_top,
                total=cached_backlinks.get("total_backlinks", len(backlinks_top)),
                referring_domains=cached_backlinks.get("referring_domains", 0),
                summary=cached_backlinks.get("summary", {}),
            )
            if has_cached_backlinks
            else {}
        )
        rankings_list = cached_rankings[:100]
        rank_tracking_data = PDFService._build_rankings_payload(
            rankings_list, total=len(cached_rankings)
        )
        llm_visibility_data = cached_llm_visibility[:60]
        ai_content_suggestions_list = cached_ai_suggestions[:50]

        # Import services here to avoid circular imports if any
        try:
            from .ai_content_service import AIContentService
            from .backlink_service import BacklinkService
            from .keyword_service import KeywordService
            from .llm_visibility_service import LLMVisibilityService
            from .rank_tracker_service import RankTrackerService

            audit_url = str(audit.url)
            domain = urlparse(audit_url).netloc.replace("www.", "")
            seed_keywords = PDFService._build_seed_keywords(audit, domain)
            brand_name = (domain.split(".")[0] if domain else "").strip()

            def _safe_int(value: Any, default: int = 0) -> int:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return default

            def _normalize_keyword_row(raw: Any) -> Dict[str, Any]:
                if isinstance(raw, dict):
                    term = raw.get("term") or raw.get("keyword")
                    volume = raw.get("volume", raw.get("search_volume", 0))
                    difficulty = raw.get("difficulty", 0)
                    cpc = raw.get("cpc", 0.0)
                    intent = raw.get("intent", "")
                    opportunity_score = raw.get("opportunity_score", 50)
                    metrics_source = raw.get("metrics_source")
                else:
                    term = getattr(raw, "term", None) or getattr(raw, "keyword", None)
                    volume = getattr(raw, "volume", getattr(raw, "search_volume", 0))
                    difficulty = getattr(raw, "difficulty", 0)
                    cpc = getattr(raw, "cpc", 0.0)
                    intent = getattr(raw, "intent", "")
                    opportunity_score = getattr(raw, "opportunity_score", 50)
                    metrics_source = getattr(raw, "metrics_source", None)

                term_value = str(term).strip() if term is not None else ""
                volume_value = _safe_int(volume, 0)
                difficulty_value = _safe_int(difficulty, 0)
                try:
                    cpc_value = float(cpc or 0.0)
                except (TypeError, ValueError):
                    cpc_value = 0.0
                if not metrics_source:
                    has_real_metrics = (
                        volume_value > 0 or difficulty_value > 0 or cpc_value > 0.0
                    )
                    metrics_source = (
                        "google_ads" if has_real_metrics else "not_available"
                    )
                return {
                    "keyword": term_value,
                    "search_volume": volume_value,
                    "difficulty": difficulty_value,
                    "cpc": cpc_value,
                    "intent": intent or "",
                    "opportunity_score": _safe_int(opportunity_score, 50),
                    "metrics_source": metrics_source,
                }

            def _payload_has_observed_rows(dataset_name: str, payload: Any) -> bool:
                if dataset_name in {"llm_visibility", "ai_content_suggestions"}:
                    return isinstance(payload, list) and len(payload) > 0
                if not isinstance(payload, dict):
                    return False

                if dataset_name == "keywords":
                    rows = payload.get("items") or payload.get("keywords") or []
                    total = payload.get("total_keywords", payload.get("total"))
                elif dataset_name == "backlinks":
                    rows = payload.get("items") or payload.get("top_backlinks") or []
                    total = payload.get("total_backlinks", payload.get("total"))
                elif dataset_name == "rankings":
                    rows = payload.get("items") or payload.get("rankings") or []
                    total = payload.get("total_keywords", payload.get("total"))
                else:
                    rows = []
                    total = 0

                if isinstance(rows, list) and rows:
                    return True
                try:
                    return int(total or 0) > 0
                except (TypeError, ValueError):
                    return False

            should_refresh_keywords = force_fresh_geo or not _payload_has_observed_rows(
                "keywords", keywords_data
            )
            should_refresh_backlinks = force_fresh_geo or not _payload_has_observed_rows(
                "backlinks", backlinks_data
            )
            should_refresh_rankings = force_fresh_geo or not _payload_has_observed_rows(
                "rankings", rank_tracking_data
            )
            should_refresh_llm_visibility = force_fresh_geo or not _payload_has_observed_rows(
                "llm_visibility", llm_visibility_data
            )
            should_refresh_ai_suggestions = force_fresh_geo or not _payload_has_observed_rows(
                "ai_content_suggestions", ai_content_suggestions_list
            )
            refreshed_geo_context = any(
                (
                    should_refresh_keywords,
                    should_refresh_backlinks,
                    should_refresh_rankings,
                    should_refresh_llm_visibility,
                    should_refresh_ai_suggestions,
                )
            )

            if refreshed_geo_context:
                logger.info(
                    "Selective GEO refresh for PDF: "
                    f"keywords={should_refresh_keywords}, "
                    f"backlinks={should_refresh_backlinks}, "
                    f"rankings={should_refresh_rankings}, "
                    f"llm_visibility={should_refresh_llm_visibility}, "
                    f"ai_content={should_refresh_ai_suggestions}"
                )
            else:
                logger.info("All supporting GEO datasets are already available in cache.")

            # 1. Keywords (refresh when forced or missing)
            if should_refresh_keywords:
                try:
                    keyword_svc = KeywordService(db)
                    logger.info("  - Performing fresh keyword research for PDF...")
                    keywords_objs = await PDFService._run_stage_with_timeout(
                        stage_name="Keyword research",
                        coroutine_factory=lambda: keyword_svc.research_keywords(
                            audit_id, domain, seed_keywords=seed_keywords
                        ),
                        stage_timeout_seconds=keyword_stage_timeout_seconds,
                        started_at=started_at,
                        total_budget_seconds=total_budget_seconds,
                    )
                    if keywords_objs is None:
                        raise TimeoutError("Keyword research timed out")

                    keywords_data_list = [
                        _normalize_keyword_row(k) for k in (keywords_objs or [])
                    ]
                    keywords_data_list = [
                        k for k in keywords_data_list if k.get("keyword")
                    ][:200]

                    keywords_data = PDFService._build_keywords_payload(
                        keywords_data_list
                    )
                except Exception as e:
                    logger.error(f"Error generating Keywords for PDF: {e}")

            # Fallback to DB if empty
            if not keywords_data or not keywords_data.get("items"):
                try:
                    db.refresh(audit)
                    if audit.keywords:
                        logger.info(
                            f"Using existing Keywords from DB as fallback (found {len(audit.keywords)})"
                        )
                        keywords_objs = audit.keywords
                        keywords_data_list = [
                            _normalize_keyword_row(k) for k in (keywords_objs or [])
                        ]
                        keywords_data_list = [
                            k for k in keywords_data_list if k.get("keyword")
                        ]
                        keywords_data = PDFService._build_keywords_payload(
                            keywords_data_list
                        )
                except Exception as fb_err:
                    logger.error(f"Fallback for Keywords failed: {fb_err}")

            # 2. Backlinks (refresh when forced or cache is missing)
            if should_refresh_backlinks:
                try:
                    backlink_svc = BacklinkService(db)
                    logger.info("  - Performing fresh backlinks analysis for PDF...")
                    backlinks_objs = await PDFService._run_stage_with_timeout(
                        stage_name="Backlinks analysis",
                        coroutine_factory=lambda: backlink_svc.analyze_backlinks(
                            audit_id, domain
                        ),
                        stage_timeout_seconds=backlink_stage_timeout_seconds,
                        started_at=started_at,
                        total_budget_seconds=total_budget_seconds,
                    )
                    if backlinks_objs is None:
                        raise TimeoutError("Backlinks analysis timed out")

                    backlinks_list = [
                        {
                            "source_url": b.source_url,
                            "target_url": b.target_url,
                            "anchor_text": b.anchor_text,
                            "domain_authority": b.domain_authority or 0,
                            "is_dofollow": b.is_dofollow,
                        }
                        for b in backlinks_objs
                    ]

                    backlinks_data = PDFService._build_backlinks_payload(
                        backlinks_list
                    )
                except Exception as e:
                    logger.error(f"Error generating Backlinks for PDF: {e}")

            # Fallback to DB if empty
            if not backlinks_data or not backlinks_data.get("items"):
                try:
                    # db.refresh(audit) # Already refreshed above if keywords failed, but safe to do again?
                    # Optimization: check if we need refresh? doing it again handles case where only backlinks failed.
                    db.refresh(audit)
                    if audit.backlinks:
                        logger.info(
                            f"Using existing Backlinks from DB as fallback (found {len(audit.backlinks)})"
                        )
                        backlinks_objs = audit.backlinks
                        backlinks_list = [
                            {
                                "source_url": b.source_url,
                                "target_url": b.target_url,
                                "anchor_text": b.anchor_text,
                                "domain_authority": b.domain_authority or 0,
                                "is_dofollow": b.is_dofollow,
                            }
                            for b in backlinks_objs
                        ]

                        backlinks_data = PDFService._build_backlinks_payload(
                            backlinks_list
                        )
                except Exception as fb_err:
                    logger.error(f"Fallback for Backlinks failed: {fb_err}")

            # 3. Rankings (refresh when forced or cache is missing)
            if should_refresh_rankings:
                try:
                    rank_svc = RankTrackerService(db)
                    logger.info("  - Performing fresh rankings tracking for PDF...")
                    kw_terms = PDFService._collect_geo_query_terms(
                        audit=audit,
                        domain=domain,
                        keywords_data_list=keywords_data_list,
                        seed_keywords=seed_keywords,
                        limit=20,
                    )

                    if kw_terms:
                        rankings_objs = await PDFService._run_stage_with_timeout(
                            stage_name="Rankings tracking",
                            coroutine_factory=lambda: rank_svc.track_rankings(
                                audit_id, domain, kw_terms
                            ),
                            stage_timeout_seconds=rankings_stage_timeout_seconds,
                            started_at=started_at,
                            total_budget_seconds=total_budget_seconds,
                        )
                        if rankings_objs is None:
                            raise TimeoutError("Rankings tracking timed out")
                    else:
                        rankings_objs = []

                    rankings_list = []
                    for r in rankings_objs:
                        if isinstance(r, dict):
                            rankings_list.append(
                                {
                                    "keyword": r.get("keyword", ""),
                                    "position": r.get("position", 0),
                                    "url": r.get("url", ""),
                                    "change": r.get("change", 0),
                                }
                            )
                        else:
                            rankings_list.append(
                                {
                                    "keyword": getattr(r, "keyword", ""),
                                    "position": getattr(r, "position", 0),
                                    "url": getattr(r, "url", ""),
                                    "change": 0,
                                }
                            )

                    rank_tracking_data = PDFService._build_rankings_payload(
                        rankings_list
                    )
                except Exception as e:
                    logger.error(f"Error generating Rankings for PDF: {e}")

            # Fallback to DB if empty
            if not rank_tracking_data or not rank_tracking_data.get("items"):
                # Check audit.rank_trackings (note the relationship name might be singular or plural, check model)
                # Based on test file it is 'rank_trackings'
                try:
                    db.refresh(audit)
                    if getattr(audit, "rank_trackings", None):
                        logger.info(
                            f"Using existing Rankings from DB as fallback (found {len(audit.rank_trackings)})"
                        )
                        rankings_objs = audit.rank_trackings
                        rankings_list = [
                            {
                                "keyword": r.keyword,
                                "position": r.position,
                                "url": r.url,
                                "change": 0,
                            }
                            for r in rankings_objs
                        ]

                        rank_tracking_data = PDFService._build_rankings_payload(
                            rankings_list
                        )
                except Exception as fb_err:
                    logger.error(f"Fallback for Rankings failed: {fb_err}")

            # 4. LLM Visibility (refresh when forced or missing cache)
            if should_refresh_llm_visibility:
                try:
                    llm_queries = PDFService._collect_geo_query_terms(
                        audit=audit,
                        domain=domain,
                        keywords_data_list=keywords_data_list,
                        seed_keywords=seed_keywords,
                        limit=10,
                    )
                    if llm_queries:
                        visibility_svc = LLMVisibilityService(db)
                        refreshed_visibility = await PDFService._run_stage_with_timeout(
                            stage_name="LLM visibility analysis",
                            coroutine_factory=lambda: visibility_svc.check_visibility(
                                audit_id,
                                brand_name or domain,
                                llm_queries,
                            ),
                            stage_timeout_seconds=llm_visibility_stage_timeout_seconds,
                            started_at=started_at,
                            total_budget_seconds=total_budget_seconds,
                        )
                        if refreshed_visibility is None:
                            raise TimeoutError("LLM visibility analysis timed out")
                        llm_visibility_data = [
                            row
                            for row in (refreshed_visibility or [])
                            if isinstance(row, dict)
                        ]
                    else:
                        llm_visibility_data = []
                except Exception as e:
                    logger.error(f"Error generating LLM Visibility for PDF: {e}")
                    # Fallback to DB
                    try:
                        db.refresh(audit)
                        if audit.llm_visibilities:
                            llm_visibility_data = [
                                {
                                    "query": visibility.query,
                                    "llm_name": visibility.llm_name,
                                    "is_visible": visibility.is_visible,
                                    "rank": visibility.rank,
                                    "citation_text": visibility.citation_text,
                                }
                                for visibility in audit.llm_visibilities
                            ]
                    except Exception:  # nosec B110
                        pass

            # 5. AI Content Suggestions (refresh when forced or missing cache)
            if should_refresh_ai_suggestions:
                try:
                    ai_topics = PDFService._collect_geo_query_terms(
                        audit=audit,
                        domain=domain,
                        keywords_data_list=keywords_data_list,
                        seed_keywords=seed_keywords,
                        limit=8,
                    )
                    if ai_topics:
                        ai_content_svc = AIContentService(db)
                        ai_content_suggestions_list = await PDFService._run_stage_with_timeout(
                            stage_name="AI content suggestions",
                            coroutine_factory=lambda: ai_content_svc.generate_suggestions(
                                audit_id, domain, ai_topics
                            ),
                            stage_timeout_seconds=ai_content_stage_timeout_seconds,
                            started_at=started_at,
                            total_budget_seconds=total_budget_seconds,
                        )
                        if ai_content_suggestions_list is None:
                            raise TimeoutError("AI content suggestions timed out")
                        ai_content_suggestions_list = [
                            PDFService._normalize_ai_suggestion_row(row)
                            for row in (ai_content_suggestions_list or [])
                        ]
                    else:
                        ai_content_suggestions_list = []
                except Exception as e:
                    logger.error(
                        f"Error generating AI Content Suggestions for PDF: {e}"
                    )
                    # Fallback to DB
                    try:
                        db.refresh(audit)
                        if audit.ai_content_suggestions:
                            ai_content_suggestions_list = [
                                PDFService._normalize_ai_suggestion_row(a)
                                for a in audit.ai_content_suggestions
                            ]
                    except Exception:  # nosec B110
                        pass

            logger.info(
                f"âœ“ GEO Tools data ready: {len(keywords_data.get('items', []))} keywords, {len(backlinks_data.get('top_backlinks', []))} backlinks, {len(rank_tracking_data.get('rankings', []))} rankings"
            )

        except Exception as tool_error:
            logger.error(
                f"Critical error initializing GEO tools services: {tool_error}",
                exc_info=True,
            )
            # Fallback is handled by initialization values
            refreshed_geo_context = False

        # 5. Load COMPLETE context from ALL features (refresh only if we ran fresh GEO)
        if refreshed_geo_context:
            complete_context = PDFService._load_complete_audit_context(db, audit_id)
        logger.info(
            f"âœ“ Complete context loaded with {len(complete_context)} feature types"
        )

        # 5.1 Ensure external intelligence quality for PDF report generation.
        # Initial audits run Agent 1 in fast mode; for PDF we only upgrade to full mode when needed.
        external_intelligence_current = (
            audit.external_intelligence
            if isinstance(audit.external_intelligence, dict)
            else {}
        )
        external_intel_status = PDFService._normalize_external_intel_status(
            external_intelligence_current, audit=audit
        )
        external_intel_complete = bool(external_intel_status.get("is_complete"))
        external_intel_refresh_reason = (
            "forced"
            if force_external_intel_refresh
            else str(external_intel_status.get("reason", "incomplete"))
        )
        should_refresh_external_intel = force_external_intel_refresh or (
            not external_intel_complete
        )
        external_intel_refreshed = False

        logger.info(
            "External intelligence refresh decision: "
            f"refresh={should_refresh_external_intel}, "
            f"reason={external_intel_refresh_reason}, "
            f"complete={external_intel_complete}, "
            f"checks={external_intel_status}"
        )

        if should_refresh_external_intel:
            logger.info(
                "Refreshing Agent 1 in FULL mode before report regeneration "
                f"(reason={external_intel_refresh_reason})"
            )
            try:
                llm_function = get_llm_function()
                target_for_external = (
                    audit.target_audit if isinstance(audit.target_audit, dict) else {}
                )

                async def _run_external_full():
                    from .pipeline_service import get_pipeline_service

                    pipeline_service = get_pipeline_service()
                    return await pipeline_service.analyze_external_intelligence(
                        target_for_external,
                        llm_function=llm_function,
                        mode="full",
                        retry_policy={
                            "max_retries": 1,
                            "timeout_seconds": external_intel_timeout_seconds,
                            "retry_timeout_seconds": min(
                                external_intel_timeout_seconds or 20.0, 15.0
                            ),
                        },
                    )

                external_result = await PDFService._run_stage_with_timeout(
                    stage_name="External intelligence (Agent 1 full)",
                    coroutine_factory=_run_external_full,
                    stage_timeout_seconds=external_intel_timeout_seconds,
                    started_at=started_at,
                    total_budget_seconds=total_budget_seconds,
                )

                if isinstance(external_result, tuple) and len(external_result) >= 1:
                    refreshed_external = (
                        external_result[0]
                        if isinstance(external_result[0], dict)
                        else {}
                    )
                else:
                    refreshed_external = {}

                if refreshed_external:
                    audit.external_intelligence = refreshed_external
                    refreshed_category = refreshed_external.get("category")
                    if (
                        isinstance(refreshed_category, str)
                        and refreshed_category.strip()
                    ):
                        audit.category = refreshed_category.strip()
                    db.commit()
                    external_intel_refreshed = True
                    logger.info("âœ“ External intelligence refreshed for PDF context")
            except Exception as external_err:
                from .pipeline_service import get_pipeline_service

                pipeline_service = get_pipeline_service()
                fallback_target = (
                    audit.target_audit if isinstance(audit.target_audit, dict) else {}
                )
                audit.external_intelligence = (
                    pipeline_service._build_unavailable_external_intelligence(
                        fallback_target,
                        error_code="AGENT1_UNAVAILABLE",
                        error_message=str(external_err),
                        analysis_mode="full",
                    )
                )
                db.commit()
                logger.warning(
                    "External intelligence full refresh failed; strict unavailable state persisted. "
                    f"audit_id={audit_id} provider=kimi_async_openai mode=full"
                )
        else:
            external_intel_refresh_reason = "not_needed"

        # If Agent 1 remains incomplete only due missing queries, fill deterministic queries
        # to avoid repeated expensive refresh attempts on every PDF click.
        latest_external_intel = (
            audit.external_intelligence
            if isinstance(audit.external_intelligence, dict)
            else {}
        )
        PDFService._normalize_external_intel_status(latest_external_intel, audit=audit)
        # No deterministic query completion; avoid fallbacks to prevent synthetic data.

        # 6. Regenerate markdown report with complete context (or reuse cached report)
        logger.info("Evaluating report regeneration strategy...")
        fallback_markdown_report = (audit.report_markdown or "").strip()
        fallback_fix_plan = audit.fix_plan
        if isinstance(fallback_fix_plan, str):
            try:
                fallback_fix_plan = json.loads(fallback_fix_plan)
            except Exception:
                fallback_fix_plan = []
        if not isinstance(fallback_fix_plan, list):
            fallback_fix_plan = []

        llm_viz_for_report = (
            llm_visibility_data if isinstance(llm_visibility_data, list) else []
        )
        ai_suggestions_for_report = (
            ai_content_suggestions_list
            if isinstance(ai_content_suggestions_list, list)
            else []
        )
        try:
            db.refresh(audit)
        except Exception:
            refreshed_audit = AuditService.get_audit(db, audit_id)
            if refreshed_audit is not None:
                audit = refreshed_audit
        signature_inputs = PDFService._build_signature_inputs_from_complete_context(
            complete_context=complete_context,
            fallback_pagespeed_data=(
                pagespeed_data if isinstance(pagespeed_data, dict) else {}
            ),
        )

        current_signature = PDFService._compute_report_context_signature(
            audit=audit,
            pagespeed_data=signature_inputs["pagespeed_data"],
            keywords_data=signature_inputs["keywords_data"],
            backlinks_data=signature_inputs["backlinks_data"],
            rank_tracking_data=signature_inputs["rank_tracking_data"],
            llm_visibility_data=signature_inputs["llm_visibility_data"],
            ai_content_suggestions=signature_inputs["ai_content_suggestions"],
        )
        cached_signature = PDFService._load_saved_report_signature(audit_id, db=db)
        cached_markdown_is_deterministic = PDFService._is_deterministic_report_markdown(
            fallback_markdown_report
        )
        has_valid_cached_markdown = (
            len(fallback_markdown_report.strip()) > 100
            and not cached_markdown_is_deterministic
        )
        missing_context = PDFService._detect_missing_pdf_context(
            audit=audit,
            pagespeed_data=pagespeed_data,
            keywords_data=keywords_data,
            backlinks_data=backlinks_data,
            rank_tracking_data=rank_tracking_data,
        )
        optional_context_gaps = PDFService._detect_optional_pdf_context_gaps(
            pagespeed_data=pagespeed_data,
            keywords_data=keywords_data,
            backlinks_data=backlinks_data,
            rank_tracking_data=rank_tracking_data,
        )
        generation_warnings: List[str] = []
        report_markdown_for_pdf = fallback_markdown_report
        report_persisted = False
        if cached_markdown_is_deterministic:
            generation_warnings.append(
                "Ignoring cached deterministic fallback report and attempting regeneration."
            )
        if missing_context:
            generation_warnings.append(
                "Validated PDF context is incomplete: "
                + ", ".join(sorted(missing_context))
            )
        if optional_context_gaps:
            generation_warnings.append(
                "Supporting PDF datasets are unavailable for this run: "
                + ", ".join(sorted(optional_context_gaps))
            )
        generation_warnings.extend(pagespeed_generation_warnings)

        signature_match = bool(
            current_signature
            and cached_signature
            and current_signature == cached_signature
        )
        safe_cached_markdown_available = (
            has_valid_cached_markdown
            and signature_match
            and not missing_context
        )
        report_cache_hit = (not force_report_refresh) and safe_cached_markdown_available
        report_regenerated = False
        generation_mode = (
            "report_cache_hit"
            if report_cache_hit
            else ("full_regenerated" if always_full_mode else "report_regenerated")
        )
        logger.info(
            "Report cache decision: "
            f"cache_hit={report_cache_hit}, "
            f"force_report_refresh={force_report_refresh}, "
            f"has_valid_cached_markdown={has_valid_cached_markdown}, "
            f"cached_markdown_is_deterministic={cached_markdown_is_deterministic}, "
            f"missing_context={missing_context}, "
            f"signature_match={signature_match}, "
            f"current_sig={current_signature[:12] if current_signature else 'none'}, "
            f"cached_sig={cached_signature[:12] if cached_signature else 'none'}"
        )
        if has_valid_cached_markdown and not cached_markdown_is_deterministic and not signature_match:
            generation_warnings.append(
                "Ignoring persisted markdown report because its context signature does not match the current audit context."
            )

        if report_cache_hit:
            logger.info(
                "âœ“ Report context signature matched. Reusing cached markdown report."
            )
            audit.report_markdown = fallback_markdown_report
            audit.fix_plan = fallback_fix_plan
            db.commit()
            report_markdown_for_pdf = fallback_markdown_report

        deterministic_on_supporting_gaps = (
            os.getenv("PDF_DETERMINISTIC_ON_SUPPORTING_GAPS", "false")
            .strip()
            .lower()
            in {"1", "true", "yes", "on"}
        )
        grounded_data_gap_threshold = 3
        should_use_grounded_report_for_data_gaps = (
            deterministic_on_supporting_gaps
            and not report_cache_hit
            and not missing_context
            and len(optional_context_gaps) >= grounded_data_gap_threshold
        )
        if should_use_grounded_report_for_data_gaps:
            if not deterministic_fallback_enabled:
                raise RuntimeError(
                    "Supporting PDF datasets are unavailable and deterministic fallbacks are disabled: "
                    + ", ".join(sorted(optional_context_gaps))
                )
            report_markdown_for_pdf = PDFService._build_deterministic_full_report(
                audit=audit,
                pagespeed_data=(
                    pagespeed_data if isinstance(pagespeed_data, dict) else {}
                ),
                keywords_data=(
                    keywords_data if isinstance(keywords_data, dict) else {}
                ),
                backlinks_data=(
                    backlinks_data if isinstance(backlinks_data, dict) else {}
                ),
                rank_tracking_data=(
                    rank_tracking_data if isinstance(rank_tracking_data, dict) else {}
                ),
                llm_visibility_data=llm_viz_for_report,
                ai_content_suggestions=ai_suggestions_for_report,
                fix_plan=fallback_fix_plan,
                reason="supporting_data_gap",
                data_gaps=optional_context_gaps,
            )
            audit.report_markdown = report_markdown_for_pdf
            audit.fix_plan = fallback_fix_plan
            db.commit()
            report_regenerated = True
            report_persisted = True
            generation_mode = "deterministic_grounded_supporting_data_gap"
            generation_warnings.append(
                "Supporting datasets were unavailable; generated a grounded deterministic report instead of invoking the LLM."
            )
            logger.warning(
                "Skipping LLM report regeneration because supporting datasets are unavailable: %s",
                ", ".join(sorted(optional_context_gaps)),
            )

        if not report_cache_hit and not should_use_grounded_report_for_data_gaps:
            try:
                if missing_context:
                    raise RuntimeError(
                        "Validated PDF context is incomplete: "
                        + ", ".join(sorted(missing_context))
                    )
                llm_function = get_llm_function()

                # Product Intelligence (ecommerce) - for LLM product positioning
                product_intelligence_data = {}
                try:
                    from dataclasses import asdict

                    from .product_intelligence_service import ProductIntelligenceService

                    # Build pages_data from audited pages
                    pages = AuditService.get_audited_pages(db, audit_id)
                    pages_data = []
                    for page in pages:
                        try:
                            page_data = (
                                json.loads(page.audit_data)
                                if isinstance(page.audit_data, str)
                                else page.audit_data or {}
                            )
                            schema_info = (
                                page_data.get("schema", {})
                                if isinstance(page_data, dict)
                                else {}
                            )
                            schemas = []

                            raw_jsonld_blocks = schema_info.get("raw_jsonld", [])
                            if isinstance(raw_jsonld_blocks, list):
                                for raw in raw_jsonld_blocks:
                                    try:
                                        parsed = (
                                            json.loads(raw)
                                            if isinstance(raw, str)
                                            else raw
                                        )
                                        if isinstance(parsed, list):
                                            for item in parsed:
                                                if isinstance(item, dict):
                                                    schemas.append(
                                                        {
                                                            "type": item.get("@type")
                                                            or item.get("type"),
                                                            "properties": item,
                                                        }
                                                    )
                                        elif isinstance(parsed, dict):
                                            schemas.append(
                                                {
                                                    "type": parsed.get("@type")
                                                    or parsed.get("type"),
                                                    "properties": parsed,
                                                }
                                            )
                                    except Exception:  # nosec B112
                                        continue

                            if not schemas:
                                schema_types = schema_info.get("schema_types", [])
                                if isinstance(schema_types, list):
                                    for t in schema_types:
                                        schemas.append({"type": t, "properties": {}})

                            title = ""
                            if isinstance(page_data, dict):
                                title = page_data.get("content", {}).get(
                                    "title"
                                ) or page_data.get("title", "")

                            pages_data.append(
                                {"url": page.url, "title": title, "schemas": schemas}
                            )
                        except Exception:
                            pages_data.append(
                                {"url": page.url, "title": "", "schemas": []}
                            )

                    product_service = ProductIntelligenceService(
                        llm_function=llm_function
                    )
                    product_result = await PDFService._run_stage_with_timeout(
                        stage_name="Product intelligence",
                        coroutine_factory=lambda: product_service.analyze(
                            audit_data=audit.target_audit or {},
                            pages_data=pages_data,
                            llm_visibility_data=llm_viz_for_report,
                            competitor_data=audit.competitor_audits or None,
                        ),
                        stage_timeout_seconds=product_intel_timeout_seconds,
                        started_at=started_at,
                        total_budget_seconds=total_budget_seconds,
                    )
                    if product_result is None:
                        raise TimeoutError("Product intelligence timed out")
                    product_intelligence_data = asdict(product_result)
                    logger.info(
                        f"âœ“ Product intelligence loaded (ecommerce={product_intelligence_data.get('is_ecommerce')})"
                    )
                except Exception as e:
                    logger.warning(f"Product intelligence generation failed: {e}")

                logger.info("  Using fresh data for report generation:")
                logger.info(
                    f"    - Keywords: {len(keywords_data.get('items', [])) if isinstance(keywords_data, dict) else 0}"
                )
                logger.info(
                    f"    - Backlinks: {len(backlinks_data.get('top_backlinks', [])) if isinstance(backlinks_data, dict) else 0}"
                )
                logger.info(
                    f"    - Rankings: {len(rank_tracking_data.get('rankings', [])) if isinstance(rank_tracking_data, dict) else 0}"
                )
                logger.info(f"    - LLM Visibility: {len(llm_viz_for_report)}")
                logger.info(
                    f"    - AI Content Suggestions: {len(ai_suggestions_for_report)}"
                )

                # Regenerate report with complete context (using FRESH data from GEO tools)
                report_generation_result = None
                report_generation_error: Optional[Exception] = None
                report_max_attempts = 1

                for attempt_idx in range(report_max_attempts):
                    attempt_no = attempt_idx + 1
                    attempt_keywords_data = keywords_data
                    attempt_backlinks_data = backlinks_data
                    attempt_rank_tracking_data = rank_tracking_data
                    attempt_llm_viz = llm_viz_for_report
                    attempt_ai_suggestions = ai_suggestions_for_report

                    if attempt_no > 1:
                        compact_inputs = PDFService._compact_report_inputs_for_retry(
                            keywords_data=keywords_data,
                            backlinks_data=backlinks_data,
                            rank_tracking_data=rank_tracking_data,
                            llm_visibility_data=llm_viz_for_report,
                            ai_content_suggestions=ai_suggestions_for_report,
                        )
                        attempt_keywords_data = compact_inputs["keywords_data"]
                        attempt_backlinks_data = compact_inputs["backlinks_data"]
                        attempt_rank_tracking_data = compact_inputs[
                            "rank_tracking_data"
                        ]
                        attempt_llm_viz = compact_inputs["llm_visibility_data"]
                        attempt_ai_suggestions = compact_inputs[
                            "ai_content_suggestions"
                        ]
                        logger.warning(
                            "Retrying report regeneration with compact context "
                            f"(attempt {attempt_no}/{report_max_attempts})."
                        )

                    try:
                        report_generation_result = await PDFService._run_stage_with_timeout(
                            stage_name=f"LLM report regeneration (attempt {attempt_no}/{report_max_attempts})",
                            coroutine_factory=lambda: PipelineService.generate_report(
                                target_audit=audit.target_audit or {},
                                external_intelligence=audit.external_intelligence or {},
                                search_results=audit.search_results or {},
                                competitor_audits=audit.competitor_audits or [],
                                pagespeed_data=pagespeed_data,
                                keywords_data=attempt_keywords_data,
                                backlinks_data=attempt_backlinks_data,
                                product_intelligence_data=product_intelligence_data,
                                rank_tracking_data=attempt_rank_tracking_data,
                                llm_visibility_data=attempt_llm_viz,
                                ai_content_suggestions=attempt_ai_suggestions,
                                llm_function=llm_function,
                            ),
                            stage_timeout_seconds=report_timeout_seconds,
                            started_at=started_at,
                            total_budget_seconds=total_budget_seconds,
                        )
                    except Exception as generation_attempt_error:
                        report_generation_error = generation_attempt_error
                        logger.warning(
                            f"Report regeneration attempt {attempt_no}/{report_max_attempts} failed: "
                            f"{generation_attempt_error}"
                        )
                        continue

                    if report_generation_result is not None:
                        break

                    report_generation_error = TimeoutError(
                        f"Report regeneration timed out on attempt {attempt_no}"
                    )

                if report_generation_result is None:
                    if report_generation_error:
                        raise report_generation_error
                    raise TimeoutError("Report regeneration timed out")
                markdown_report, fix_plan = report_generation_result

                # Update audit with new report (hard fail if regeneration failed)
                if not markdown_report or len(markdown_report.strip()) <= 100:
                    raise RuntimeError(
                        f"Report regeneration failed: content too short ({len(markdown_report or '')} chars)"
                    )

                audit.report_markdown = markdown_report
                logger.info(
                    f"âœ“ Markdown report regenerated with complete context ({len(markdown_report)} chars)"
                )

                # Ensure fix_plan is generated - NO FALLBACK for production
                if not fix_plan or len(fix_plan) == 0:
                    logger.warning(
                        "Fix plan is empty. No fallback used as per production requirements."
                    )
                    fix_plan = []

                audit.fix_plan = fix_plan
                db.commit()
                PDFService._save_report_signature(
                    audit_id, current_signature, db=db
                )
                db.commit()
                persisted_signature = PDFService._load_saved_report_signature(
                    audit_id, db=db
                )
                if persisted_signature != current_signature:
                    logger.warning(
                        "Report signature persistence mismatch after regeneration. "
                        f"audit_id={audit_id} current_sig={current_signature[:12]} "
                        f"persisted_sig={persisted_signature[:12] if persisted_signature else 'none'}"
                    )
                report_markdown_for_pdf = markdown_report
                report_regenerated = True
                report_persisted = True
                generation_mode = (
                    "full_regenerated" if always_full_mode else "report_regenerated"
                )

                logger.info(f"Fix plan length: {len(fix_plan) if fix_plan else 0}")
            except Exception as e:
                if missing_context:
                    logger.warning(
                        "Skipping LLM report regeneration because validated context is incomplete.",
                        exc_info=False,
                    )
                    if not deterministic_fallback_enabled:
                        raise RuntimeError(
                            "Validated PDF context is incomplete and deterministic fallback is disabled: "
                            + ", ".join(sorted(missing_context))
                        ) from e
                    report_markdown_for_pdf = PDFService._build_deterministic_full_report(
                        audit=audit,
                        pagespeed_data=(
                            pagespeed_data if isinstance(pagespeed_data, dict) else {}
                        ),
                        keywords_data=(
                            keywords_data if isinstance(keywords_data, dict) else {}
                        ),
                        backlinks_data=(
                            backlinks_data if isinstance(backlinks_data, dict) else {}
                        ),
                        rank_tracking_data=(
                            rank_tracking_data
                            if isinstance(rank_tracking_data, dict)
                            else {}
                        ),
                        llm_visibility_data=llm_viz_for_report,
                        ai_content_suggestions=ai_suggestions_for_report,
                        fix_plan=[],
                        reason="missing_context",
                        data_gaps=missing_context,
                    )
                    if (
                        not report_markdown_for_pdf
                        or len(report_markdown_for_pdf.strip()) <= 100
                    ):
                        raise RuntimeError(
                            "Validated context is incomplete and deterministic fallback report is too short."
                        ) from e
                    report_regenerated = True
                    generation_mode = "deterministic_missing_context"
                    generation_warnings.append(
                        "Generated a deterministic PDF report without persisting or caching it because validated context is incomplete."
                    )
                else:
                    if safe_cached_markdown_available:
                        logger.warning(
                            "LLM report regeneration failed; reusing persisted markdown report for this PDF.",
                            exc_info=True,
                        )
                        report_markdown_for_pdf = fallback_markdown_report
                        generation_mode = "report_cached_llm_failure"
                        generation_warnings.append(
                            "LLM report regeneration failed; reused the last persisted markdown report for this PDF."
                        )
                    else:
                        if has_valid_cached_markdown and not signature_match:
                            logger.warning(
                                "LLM report regeneration failed and the persisted markdown report was rejected because its context signature does not match the current audit context.",
                                exc_info=False,
                            )
                        logger.error(
                            "LLM report regeneration failed; switching to deterministic fallback report for this PDF only.",
                            exc_info=True,
                        )
                        if not deterministic_fallback_enabled:
                            raise RuntimeError(
                                "LLM report regeneration failed and deterministic fallbacks are disabled."
                            ) from e
                        report_markdown_for_pdf = PDFService._build_deterministic_full_report(
                            audit=audit,
                            pagespeed_data=(
                                pagespeed_data if isinstance(pagespeed_data, dict) else {}
                            ),
                            keywords_data=(
                                keywords_data if isinstance(keywords_data, dict) else {}
                            ),
                            backlinks_data=(
                                backlinks_data if isinstance(backlinks_data, dict) else {}
                            ),
                            rank_tracking_data=(
                                rank_tracking_data
                                if isinstance(rank_tracking_data, dict)
                                else {}
                            ),
                            llm_visibility_data=llm_viz_for_report,
                            ai_content_suggestions=ai_suggestions_for_report,
                            fix_plan=[],
                            reason="llm_failure",
                            data_gaps=optional_context_gaps,
                        )
                        if (
                            not report_markdown_for_pdf
                            or len(report_markdown_for_pdf.strip()) <= 100
                        ):
                            raise RuntimeError(
                                "Report regeneration failed and deterministic fallback report is too short."
                            ) from e

                        report_regenerated = True
                        generation_mode = "deterministic_fallback_transient"
                        generation_warnings.append(
                            "LLM report regeneration failed; generated a deterministic report for this PDF only without persisting or caching it."
                        )

        # 7. Get pages and competitors
        pages = AuditService.get_audited_pages(db, audit_id)
        from .audit_service import CompetitorService

        competitors = CompetitorService.get_competitors(db, audit_id)

        logger.info(f"âœ“ Loaded {len(pages)} pages and {len(competitors)} competitors")

        # 8. Generate PDF with complete context
        pdf_path = await PDFService.generate_comprehensive_pdf(
            audit=audit,
            pages=pages,
            competitors=competitors,
            pagespeed_data=pagespeed_data,
            keywords_data=keywords_data,
            backlinks_data=backlinks_data,
            rank_tracking_data=rank_tracking_data,
            llm_visibility_data=llm_visibility_data,
            report_markdown_override=report_markdown_for_pdf,
        )
        pdf_file_size = getattr(audit, "_generated_pdf_size_bytes", None)

        total_elapsed = time.monotonic() - started_at
        logger.info(
            f"PDF pipeline finished in {total_elapsed:.1f}s (mode={generation_mode})"
        )
        logger.info(f"=== PDF generation completed: {pdf_path} ===")
        if return_details:
            return {
                "pdf_path": pdf_path,
                "report_cache_hit": report_cache_hit,
                "report_regenerated": report_regenerated,
                "report_persisted": report_persisted,
                "generation_mode": generation_mode,
                "external_intel_refreshed": external_intel_refreshed,
                "external_intel_refresh_reason": external_intel_refresh_reason,
                "missing_context": missing_context,
                "generation_warnings": generation_warnings,
                "file_size": pdf_file_size,
            }
        return pdf_path

    @staticmethod
    async def generate_comprehensive_pdf(
        audit: Audit,
        pages: list,
        competitors: list,
        pagespeed_data: dict = None,
        keywords_data: dict = None,
        backlinks_data: dict = None,
        rank_tracking_data: dict = None,
        llm_visibility_data: list = None,
        report_markdown_override: Optional[str] = None,
    ) -> str:
        """
        Genera un PDF completo con todos los datos de la auditorÃ­a:
        - Datos de auditorÃ­a principal
        - PÃ¡ginas auditadas
        - Competidores
        - PageSpeed data
        - Keywords
        - Backlinks
        - Rank tracking
        - LLM Visibility

        Args:
            audit: La instancia del modelo Audit
            pages: Lista de pÃ¡ginas auditadas
            competitors: Lista de competidores
            pagespeed_data: Datos de PageSpeed (opcional)
            keywords_data: Datos de Keywords (opcional)
            backlinks_data: Datos de Backlinks (opcional)
            rank_tracking_data: Datos de Rank Tracking (opcional)
            llm_visibility_data: Datos de LLM Visibility (opcional)
            report_markdown_override: Markdown report a renderizar sin persistirlo

        Returns:
            La ruta completa al archivo PDF generado
        """
        if not PDF_GENERATOR_AVAILABLE:
            logger.error(
                "PDF generator no estÃ¡ disponible. Instalar fpdf2: pip install fpdf2"
            )
            raise ImportError("PDF generator not available")

        logger.info(
            f"Generando PDF completo para auditorÃ­a {audit.id} con todos los datos"
        )

        reports_dir = tempfile.mkdtemp(prefix=f"audit_{audit.id}_")
        try:
            os.makedirs(reports_dir, exist_ok=True)
            PDFService._clean_previous_pdf_artifacts(reports_dir)
            report_markdown_value = (
                report_markdown_override
                if report_markdown_override is not None
                else audit.report_markdown
            )
            report_markdown_value = PDFService._normalize_markdown_for_pdf_render(
                report_markdown_value
            )

            # 1. Guardar markdown report
            if report_markdown_value:
                md_file_path = os.path.join(reports_dir, "ag2_report.md")
                with open(md_file_path, "w", encoding="utf-8") as f:
                    f.write(report_markdown_value)

            # 2. Guardar fix_plan.json
            if audit.fix_plan:
                fix_plan_path = os.path.join(reports_dir, "fix_plan.json")
                try:
                    fix_plan_data = (
                        json.loads(audit.fix_plan)
                        if isinstance(audit.fix_plan, str)
                        else audit.fix_plan
                    )
                    with open(fix_plan_path, "w", encoding="utf-8") as f:
                        json.dump(fix_plan_data, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.warning(f"No se pudo guardar fix_plan.json: {e}")

            # 3. Guardar aggregated_summary.json (target audit)
            if audit.target_audit:
                agg_summary_path = os.path.join(reports_dir, "aggregated_summary.json")
                try:
                    target_audit_data = (
                        json.loads(audit.target_audit)
                        if isinstance(audit.target_audit, str)
                        else audit.target_audit
                    )
                    with open(agg_summary_path, "w", encoding="utf-8") as f:
                        json.dump(target_audit_data, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.warning(f"No se pudo guardar aggregated_summary.json: {e}")

            # 4. Guardar PageSpeed data
            if pagespeed_data:
                pagespeed_path = os.path.join(reports_dir, "pagespeed.json")
                try:
                    with open(pagespeed_path, "w", encoding="utf-8") as f:
                        json.dump(pagespeed_data, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.warning(f"No se pudo guardar pagespeed.json: {e}")

            # 4.1 Guardar Keywords data
            if keywords_data:
                keywords_path = os.path.join(reports_dir, "keywords.json")
                try:
                    # keywords_data can be a dict or a list
                    data_to_save = (
                        keywords_data.get("keywords", keywords_data)
                        if isinstance(keywords_data, dict)
                        else keywords_data
                    )
                    with open(keywords_path, "w", encoding="utf-8") as f:
                        json.dump(data_to_save, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.warning(f"No se pudo guardar keywords.json: {e}")

            # 4.2 Guardar Backlinks data
            if backlinks_data:
                backlinks_path = os.path.join(reports_dir, "backlinks.json")
                try:
                    # backlinks_data can be a dict or a list
                    data_to_save = (
                        backlinks_data.get("top_backlinks", backlinks_data)
                        if isinstance(backlinks_data, dict)
                        else backlinks_data
                    )
                    with open(backlinks_path, "w", encoding="utf-8") as f:
                        json.dump(data_to_save, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.warning(f"No se pudo guardar backlinks.json: {e}")

            # 4.3 Guardar Rankings data
            if rank_tracking_data:
                rankings_path = os.path.join(reports_dir, "rankings.json")
                try:
                    # rank_tracking_data can be a dict or a list
                    data_to_save = (
                        rank_tracking_data.get("rankings", rank_tracking_data)
                        if isinstance(rank_tracking_data, dict)
                        else rank_tracking_data
                    )
                    with open(rankings_path, "w", encoding="utf-8") as f:
                        json.dump(data_to_save, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.warning(f"No se pudo guardar rankings.json: {e}")

            # 4.4 Guardar LLM Visibility data
            if llm_visibility_data:
                visibility_path = os.path.join(reports_dir, "llm_visibility.json")
                try:
                    with open(visibility_path, "w", encoding="utf-8") as f:
                        json.dump(llm_visibility_data, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.warning(f"No se pudo guardar llm_visibility.json: {e}")

            # 5. Guardar datos de pÃ¡ginas
            if pages:
                pages_dir = os.path.join(reports_dir, "pages")
                os.makedirs(pages_dir, exist_ok=True)
                for page in pages:
                    try:
                        page_data = {
                            "url": page.url,
                            "path": page.path,
                            "overall_score": page.overall_score,
                            "h1_score": page.h1_score,
                            "structure_score": page.structure_score,
                            "content_score": page.content_score,
                            "eeat_score": page.eeat_score,
                            "schema_score": page.schema_score,
                            "critical_issues": page.critical_issues,
                            "high_issues": page.high_issues,
                            "medium_issues": page.medium_issues,
                            "low_issues": page.low_issues,
                            "audit_data": page.audit_data,
                        }
                        page_filename = f"page_{page.id}.json"
                        page_path = os.path.join(pages_dir, page_filename)
                        with open(page_path, "w", encoding="utf-8") as f:
                            json.dump(page_data, f, indent=2, ensure_ascii=False)
                    except Exception as e:
                        logger.warning(
                            f"No se pudo guardar datos de pÃ¡gina {page.id}: {e}"
                        )

            # 6. Guardar datos de competidores
            if competitors:
                competitors_dir = os.path.join(reports_dir, "competitors")
                os.makedirs(competitors_dir, exist_ok=True)
                for idx, comp in enumerate(competitors):
                    try:
                        comp_data = (
                            comp
                            if isinstance(comp, dict)
                            else {
                                "url": getattr(comp, "url", ""),
                                "geo_score": getattr(comp, "geo_score", 0),
                                "audit_data": getattr(comp, "audit_data", {}),
                            }
                        )
                        # Extract domain from URL if not present
                        if "domain" not in comp_data:
                            from urllib.parse import urlparse

                            url = comp_data.get("url", "")
                            if url:
                                domain = urlparse(url).netloc.replace("www.", "")
                            else:
                                domain = f"competitor_{idx + 1}"
                            comp_data["domain"] = domain
                        comp_filename = f"competitor_{idx + 1}.json"
                        comp_path = os.path.join(competitors_dir, comp_filename)
                        with open(comp_path, "w", encoding="utf-8") as f:
                            json.dump(comp_data, f, indent=2, ensure_ascii=False)
                    except Exception as e:
                        logger.warning(
                            f"No se pudo guardar datos de competidor {idx}: {e}"
                        )

            # 7. Generar PDF con create_comprehensive_pdf
            try:
                create_comprehensive_pdf(
                    reports_dir, metadata=PDFService._build_pdf_metadata(audit)
                )

                # Buscar el PDF generado
                import glob

                pdf_files = glob.glob(
                    os.path.join(reports_dir, "Reporte_Consolidado_*.pdf")
                )
                if pdf_files:
                    pdf_file_path = pdf_files[0]
                    logger.info(f"PDF completo generado en: {pdf_file_path}")
                    try:
                        supabase_path, pdf_size = PDFService._upload_pdf_to_supabase(
                            audit_id=audit.id, pdf_file_path=pdf_file_path
                        )
                        setattr(audit, "_generated_pdf_size_bytes", pdf_size)
                        logger.info(
                            f"storage_provider=supabase audit_id={audit.id} action=upload_pdf_ok size={pdf_size}"
                        )
                        return supabase_path
                    except Exception as upload_err:
                        logger.error(
                            f"storage_provider=supabase audit_id={audit.id} action=upload_pdf_failed error_code=supabase_upload_failed error={upload_err}"
                        )
                        raise RuntimeError(
                            "Error subiendo PDF a Supabase Storage."
                        ) from upload_err
                else:
                    logger.error(f"No se encontrÃ³ el PDF generado en {reports_dir}")
                    raise FileNotFoundError("PDF file not generated")
            except Exception as e:
                logger.error(
                    f"Error generando PDF con create_comprehensive_pdf: {e}",
                    exc_info=True,
                )
                raise
        finally:
            try:
                shutil.rmtree(reports_dir, ignore_errors=True)
            except Exception as cleanup_err:
                logger.warning(
                    f"Error limpiando temporales de PDF audit={audit.id}: {cleanup_err}"
                )
