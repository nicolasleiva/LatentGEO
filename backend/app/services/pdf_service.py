"""
Servicio para la generación de reportes en PDF.
"""

import asyncio
import hashlib
import json
import os
import time
from datetime import datetime
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
        f"No se pudo importar create_comprehensive_pdf: {e}. PDFs no estarán disponibles."
    )
    PDF_GENERATOR_AVAILABLE = False

    def create_comprehensive_pdf(report_folder_path, metadata=None):
        logger.error("create_comprehensive_pdf no está disponible")
        raise ImportError("create_pdf module not available")


class PDFService:
    """Encapsula la lógica para crear archivos PDF a partir de contenido."""

    REPORT_CONTEXT_PROMPT_VERSION = "report_generation_v2"

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
    def _reports_dir_for_audit(audit_id: int) -> str:
        return os.path.join(settings.REPORTS_BASE_DIR, f"audit_{audit_id}")

    @staticmethod
    def _report_context_signature_path(audit_id: int) -> str:
        return os.path.join(
            PDFService._reports_dir_for_audit(audit_id), "report_context.sha256"
        )

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
                [item for item in llm_rows if bool(item.get("is_visible"))]
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
    def _load_saved_report_signature(audit_id: int) -> str:
        signature_path = PDFService._report_context_signature_path(audit_id)
        if not os.path.exists(signature_path):
            return ""
        try:
            with open(signature_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as exc:
            logger.warning(f"Could not read report signature cache: {exc}")
            return ""

    @staticmethod
    def _save_report_signature(audit_id: int, signature: str) -> None:
        if not signature:
            return
        signature_path = PDFService._report_context_signature_path(audit_id)
        os.makedirs(os.path.dirname(signature_path), exist_ok=True)
        try:
            with open(signature_path, "w", encoding="utf-8") as f:
                f.write(signature)
        except Exception as exc:
            logger.warning(f"Could not persist report signature cache: {exc}")

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
    def _build_deterministic_full_report(
        *,
        audit: Audit,
        pagespeed_data: Dict[str, Any],
        keywords_data: Dict[str, Any],
        backlinks_data: Dict[str, Any],
        rank_tracking_data: Dict[str, Any],
        llm_visibility_data: List[Dict[str, Any]],
        ai_content_suggestions: List[Dict[str, Any]],
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

        target = audit.target_audit if isinstance(audit.target_audit, dict) else {}
        external = (
            audit.external_intelligence
            if isinstance(audit.external_intelligence, dict)
            else {}
        )
        competitors = (
            audit.competitor_audits if isinstance(audit.competitor_audits, list) else []
        )

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

        critical_issues = target.get("critical_issues_count", "not_available")
        high_issues = target.get("high_issues_count", "not_available")
        medium_issues = target.get("medium_issues_count", "not_available")
        low_issues = target.get("low_issues_count", "not_available")
        geo_score = target.get("geo_score", "not_available")
        structure_score = target.get("structure_score", "not_available")
        eeat_score = target.get("eeat_score", "not_available")

        report_lines = [
            "# GEO Audit Report",
            "",
            "## Generation Mode",
            "- Mode: full_deterministic_regenerated",
            "- Reason: LLM report regeneration timed out; deterministic report generated from collected data.",
            f"- Generated at (UTC): {datetime.utcnow().isoformat()}Z",
            "",
            "## Target",
            f"- URL: {getattr(audit, 'url', 'not_available')}",
            f"- Domain: {getattr(audit, 'domain', 'not_available')}",
            f"- Category: {external.get('category', 'not_available')}",
            f"- Subcategory: {external.get('subcategory', 'not_available')}",
            "",
            "## Executive Snapshot",
            f"- GEO score: {_safe_score(geo_score)}",
            f"- Structure score: {_safe_score(structure_score)}",
            f"- E-E-A-T score: {_safe_score(eeat_score)}",
            f"- Issues: critical={critical_issues}, high={high_issues}, medium={medium_issues}, low={low_issues}",
            f"- Competitors analyzed: {len(competitors)}",
            "",
            "## Performance Snapshot",
            f"- Mobile performance score: {_safe_score(mobile_perf)}",
            f"- Desktop performance score: {_safe_score(desktop_perf)}",
            f"- Mobile LCP: {_safe_score(mobile_lcp)}",
            "",
            "## GEO Tools Coverage",
            f"- Keywords collected: {len(keyword_items)}",
            f"- Backlinks collected: {len(backlink_items)}",
            f"- Rankings collected: {len(ranking_items)}",
            f"- LLM visibility entries: {len(llm_visibility_data) if isinstance(llm_visibility_data, list) else 0}",
            f"- AI content suggestions: {len(ai_content_suggestions) if isinstance(ai_content_suggestions, list) else 0}",
            "",
            "## Notes",
            "- This report contains only observed data from this run.",
            "- Any missing metric is marked as not_available and should be enriched in subsequent runs.",
            "",
        ]

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
    def _build_pdf_metadata(audit: Audit) -> Dict[str, str]:
        audit_url = str(getattr(audit, "url", "") or "").strip()
        if audit_url and "://" not in audit_url:
            audit_url = f"https://{audit_url}"
        parsed = urlparse(audit_url) if audit_url else None
        domain = (getattr(audit, "domain", "") or "").strip()
        if not domain and parsed:
            domain = (parsed.hostname or "").lower()
        domain = domain[4:] if domain.startswith("www.") else domain

        prepared_by = (
            getattr(audit, "user_email", None)
            or getattr(audit, "user_id", None)
            or "Auditor GEO"
        )
        footer_left = audit_url or "N/A"
        footer_right = domain or "Audit"

        return {
            "prepared_by": str(prepared_by),
            "footer_left": str(footer_left),
            "footer_right": str(footer_right),
            "report_title_prefix": "GEO Audit Report",
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
                    else k.search_volume
                    if hasattr(k, "search_volume")
                    else 0
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
                        "keyword": k.term
                        if hasattr(k, "term")
                        else k.keyword
                        if hasattr(k, "keyword")
                        else "",
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
            "total_backlinks": len(audit.backlinks)
            if hasattr(audit, "backlinks")
            else 0,
            "referring_domains": len(
                set(
                    b.source_url.split("/")[2] if "/" in b.source_url else b.source_url
                    for b in audit.backlinks
                )
            )
            if hasattr(audit, "backlinks")
            else 0,
            "top_backlinks": [],
        }
        if hasattr(audit, "backlinks"):
            for b in audit.backlinks[:20]:  # Top 20
                backlinks["top_backlinks"].append(
                    {
                        "source_url": b.source_url,
                        "target_url": b.target_url,
                        "anchor_text": b.anchor_text
                        if hasattr(b, "anchor_text")
                        else "",
                        "domain_authority": (
                            b.domain_authority if hasattr(b, "domain_authority") else 0
                        )
                        or 0,
                        "page_authority": getattr(b, "page_authority", 0) or 0,
                        "spam_score": getattr(b, "spam_score", 0) or 0,
                        "link_type": "dofollow"
                        if getattr(b, "is_dofollow", True)
                        else "nofollow",
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
                            (r.position or 100) - getattr(r, "previous_position", 0)
                        )
                        if getattr(r, "previous_position", None)
                        else 0,
                    }
                )

        llm_visibility = []
        if hasattr(audit, "llm_visibilities"):
            for visibility in audit.llm_visibilities:
                llm_visibility.append(
                    {
                        "query": visibility.query,
                        "llm_platform": visibility.llm_name
                        if hasattr(visibility, "llm_name")
                        else getattr(visibility, "llm_platform", ""),
                        "mentioned": visibility.is_visible
                        if hasattr(visibility, "is_visible")
                        else getattr(visibility, "mentioned", False),
                        "position": visibility.rank
                        if hasattr(visibility, "rank")
                        else getattr(visibility, "position", None),
                        "context": visibility.citation_text
                        if hasattr(visibility, "citation_text")
                        else getattr(visibility, "context", ""),
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
                        "title": a.topic
                        if hasattr(a, "topic")
                        else getattr(a, "title", ""),
                        "target_keyword": getattr(a, "target_keyword", ""),
                        "content_type": a.suggestion_type
                        if hasattr(a, "suggestion_type")
                        else getattr(a, "content_type", ""),
                        "priority": a.priority if hasattr(a, "priority") else "medium",
                        "estimated_traffic": getattr(a, "estimated_traffic", 0) or 0,
                        "difficulty": getattr(a, "difficulty", 0) or 0,
                        "outline": a.content_outline
                        if hasattr(a, "content_outline")
                        else getattr(a, "outline", {}),
                    }
                )
        else:
            # Generate on-demand when missing
            logger.info(
                f"AI content suggestions not found in DB for audit {audit_id}, generating on-demand"
            )
            try:
                from .ai_content_service import AIContentService

                # Generate suggestions based on keywords
                generated_suggestions = AIContentService.generate_content_suggestions(
                    keywords=keywords, url=str(audit.url)
                )

                # Convert to expected format
                for suggestion in generated_suggestions:
                    ai_content_suggestions.append(
                        {
                            "title": suggestion.get("title", ""),
                            "target_keyword": suggestion.get("target_keyword", ""),
                            "content_type": suggestion.get("content_type", ""),
                            "priority": suggestion.get("priority", "medium"),
                            "estimated_traffic": suggestion.get("estimated_traffic", 0),
                            "difficulty": suggestion.get("difficulty", 0),
                            "outline": suggestion.get("outline", {}),
                        }
                    )

                logger.info(
                    f"Generated {len(ai_content_suggestions)} AI content suggestions on-demand"
                )
            except Exception as e:
                logger.error(
                    f"Error generating AI content suggestions: {e}", exc_info=True
                )
                # Continue with empty list

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
                "average_difficulty": sum(k.get("difficulty", 0) for k in keywords)
                / len(keywords)
                if keywords
                else 0,
            },
            # Backlinks data
            "backlinks": backlinks,
            "backlinks_summary": {
                "total_backlinks": backlinks["total_backlinks"],
                "referring_domains": backlinks["referring_domains"],
                "average_domain_authority": sum(
                    b.get("domain_authority", 0) for b in backlinks["top_backlinks"]
                )
                / len(backlinks["top_backlinks"])
                if backlinks["top_backlinks"]
                else 0,
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
                "average_position": sum(r.get("position", 100) for r in rank_tracking)
                / len(rank_tracking)
                if rank_tracking
                else 0,
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
                "average_position": sum(
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
                else 0,
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
            f"Generated: {datetime.utcnow().isoformat()}Z",
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
        Crea un reporte PDF completo para una auditoría específica.
        Usa create_comprehensive_pdf para generar el PDF con índice y anexos.

        Args:
            audit: La instancia del modelo Audit.
            markdown_content: El contenido del reporte en formato Markdown.

        Returns:
            La ruta completa al archivo PDF generado.
        """
        if not PDF_GENERATOR_AVAILABLE:
            logger.error(
                "PDF generator no está disponible. Instalar fpdf2: pip install fpdf2"
            )
            raise ImportError("PDF generator not available")

        logger.info(f"Iniciando generación de PDF para auditoría {audit.id}")

        reports_dir = os.path.join(settings.REPORTS_BASE_DIR, f"audit_{audit.id}")
        os.makedirs(reports_dir, exist_ok=True)
        PDFService._clean_previous_pdf_artifacts(reports_dir)

        # Guardar el markdown en ag2_report.md (requerido por create_comprehensive_pdf)
        md_file_path = os.path.join(reports_dir, "ag2_report.md")
        with open(md_file_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        # Guardar fix_plan.json si existe en audit.fix_plan
        if hasattr(audit, "fix_plan") and audit.fix_plan:
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

        # Guardar aggregated_summary.json si existe en audit.target_audit
        if hasattr(audit, "target_audit") and audit.target_audit:
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

        # Guardar PageSpeed data
        if hasattr(audit, "pagespeed_data") and audit.pagespeed_data:
            pagespeed_path = os.path.join(reports_dir, "pagespeed.json")
            try:
                ps_data = (
                    json.loads(audit.pagespeed_data)
                    if isinstance(audit.pagespeed_data, str)
                    else audit.pagespeed_data
                )
                with open(pagespeed_path, "w", encoding="utf-8") as f:
                    json.dump(ps_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar pagespeed.json: {e}")

        # Guardar Keywords data
        if hasattr(audit, "keywords") and audit.keywords:
            keywords_path = os.path.join(reports_dir, "keywords.json")
            try:
                keywords_list = []
                for k in audit.keywords:
                    volume_value = k.volume or 0
                    difficulty_value = k.difficulty or 0
                    cpc_value = k.cpc or 0.0
                    metrics_source = (
                        "google_ads"
                        if (volume_value > 0 or difficulty_value > 0 or cpc_value > 0)
                        else "not_available"
                    )
                    keywords_list.append(
                        {
                            "term": k.term,
                            "volume": volume_value,
                            "difficulty": difficulty_value,
                            "cpc": cpc_value,
                            "intent": k.intent,
                            "metrics_source": metrics_source,
                        }
                    )
                with open(keywords_path, "w", encoding="utf-8") as f:
                    json.dump(keywords_list, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar keywords.json: {e}")

        # Guardar Backlinks data
        if hasattr(audit, "backlinks") and audit.backlinks:
            backlinks_path = os.path.join(reports_dir, "backlinks.json")
            try:
                backlinks_list = []
                for b in audit.backlinks:
                    backlinks_list.append(
                        {
                            "source_url": b.source_url,
                            "target_url": b.target_url,
                            "anchor_text": b.anchor_text,
                            "is_dofollow": b.is_dofollow,
                            "domain_authority": b.domain_authority,
                        }
                    )
                with open(backlinks_path, "w", encoding="utf-8") as f:
                    json.dump(backlinks_list, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar backlinks.json: {e}")

        # Guardar Rankings data
        if hasattr(audit, "rank_trackings") and audit.rank_trackings:
            rankings_path = os.path.join(reports_dir, "rankings.json")
            try:
                rankings_list = []
                for r in audit.rank_trackings:
                    rankings_list.append(
                        {
                            "keyword": r.keyword,
                            "position": r.position,
                            "url": r.url,
                            "device": r.device,
                            "location": r.location,
                            "top_results": r.top_results,
                        }
                    )
                with open(rankings_path, "w", encoding="utf-8") as f:
                    json.dump(rankings_list, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar rankings.json: {e}")

        # Guardar LLM Visibility data
        if hasattr(audit, "llm_visibilities") and audit.llm_visibilities:
            visibility_path = os.path.join(reports_dir, "llm_visibility.json")
            try:
                visibility_list = []
                for v in audit.llm_visibilities:
                    visibility_list.append(
                        {
                            "llm_name": v.llm_name,
                            "query": v.query,
                            "is_visible": v.is_visible,
                            "rank": v.rank,
                            "citation_text": v.citation_text,
                        }
                    )
                with open(visibility_path, "w", encoding="utf-8") as f:
                    json.dump(visibility_list, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"No se pudo guardar llm_visibility.json: {e}")

        # Guardar páginas individuales
        if hasattr(audit, "pages") and audit.pages:
            pages_dir = os.path.join(reports_dir, "pages")
            os.makedirs(pages_dir, exist_ok=True)
            for page in audit.pages:
                try:
                    # Crear nombre de archivo seguro
                    filename = (
                        page.url.replace("https://", "")
                        .replace("http://", "")
                        .replace("/", "_")
                        .replace("?", "_")
                        .replace("&", "_")
                    )
                    if not filename:
                        filename = "index"
                    page_path = os.path.join(pages_dir, f"report_{filename}.json")

                    page_data = (
                        json.loads(page.audit_data)
                        if isinstance(page.audit_data, str)
                        else page.audit_data
                    )
                    with open(page_path, "w", encoding="utf-8") as f:
                        json.dump(page_data, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.warning(f"No se pudo guardar página {page.url}: {e}")

        # Guardar competidores
        if hasattr(audit, "competitor_audits") and audit.competitor_audits:
            competitors_dir = os.path.join(reports_dir, "competitors")
            os.makedirs(competitors_dir, exist_ok=True)
            try:
                comp_list = (
                    json.loads(audit.competitor_audits)
                    if isinstance(audit.competitor_audits, str)
                    else audit.competitor_audits
                )
                if isinstance(comp_list, list):
                    for i, comp_data in enumerate(comp_list):
                        try:
                            domain = (
                                comp_data.get("domain")
                                or comp_data.get("url", "")
                                .replace("https://", "")
                                .replace("http://", "")
                                .split("/")[0]
                                or f"competitor_{i}"
                            )
                            comp_path = os.path.join(
                                competitors_dir, f"competitor_{domain}.json"
                            )
                            with open(comp_path, "w", encoding="utf-8") as f:
                                json.dump(comp_data, f, indent=2, ensure_ascii=False)
                        except Exception as e:
                            logger.warning(f"No se pudo guardar competidor {i}: {e}")
            except Exception as e:
                logger.warning(f"Error procesando competitor_audits: {e}")

        # Llamar a create_comprehensive_pdf (igual que ag2_pipeline.py)
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
                logger.info(f"Reporte PDF guardado en: {pdf_file_path}")
                return pdf_file_path
            else:
                logger.error(f"No se encontró el PDF generado en {reports_dir}")
                raise FileNotFoundError("PDF file not generated")
        except Exception as e:
            logger.error(
                f"Error generando PDF con create_comprehensive_pdf: {e}", exc_info=True
            )
            raise

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
            "PDF_ALWAYS_FULL_MODE", "true"
        ).strip().lower() in {"1", "true", "yes", "on"}

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
            f"geo_stage={timeout_geo_label}, "
            f"report={timeout_report_label}, "
            f"external_intel={timeout_external_intel_label}, "
            f"product_intel={timeout_product_intel_label}, "
            f"always_full_mode={always_full_mode}"
        )

        # 1. Load audit
        audit = AuditService.get_audit(db, audit_id)
        if not audit:
            raise ValueError(f"Audit {audit_id} not found")

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
                logger.info("✓ PageSpeed data collected and stored")
            except Exception as e:
                logger.error(f"PageSpeed collection failed: {e}")
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
            logger.info("✓ Using cached PageSpeed data (fresh)")

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
        keywords_data = (
            {
                "items": keywords_data_list,
                "keywords": keywords_data_list,
                "total": len(cached_keywords),
                "total_keywords": len(cached_keywords),
                "top_opportunities": sorted(
                    keywords_data_list,
                    key=_keyword_opportunity_score,
                    reverse=True,
                )[:10],
            }
            if keywords_data_list
            else {}
        )
        backlinks_top = (
            cached_backlinks.get("top_backlinks", [])
            if isinstance(cached_backlinks.get("top_backlinks", []), list)
            else []
        )
        has_cached_backlinks = bool(backlinks_top) or bool(
            cached_backlinks.get("total_backlinks")
        )
        backlinks_data = (
            {
                "items": backlinks_top[:20],
                "top_backlinks": backlinks_top[:20],
                "total": cached_backlinks.get("total_backlinks", len(backlinks_top)),
                "total_backlinks": cached_backlinks.get(
                    "total_backlinks", len(backlinks_top)
                ),
                "referring_domains": cached_backlinks.get("referring_domains", 0),
                "summary": cached_backlinks.get("summary", {}),
            }
            if has_cached_backlinks
            else {}
        )
        rankings_list = cached_rankings[:100]
        rank_tracking_data = (
            {
                "items": rankings_list,
                "rankings": rankings_list,
                "total": len(cached_rankings),
                "total_keywords": len(cached_rankings),
                "distribution": {
                    "top_3": len(
                        [
                            r
                            for r in rankings_list
                            if isinstance(r, dict)
                            and (r.get("position") or 100) <= 3
                            and (r.get("position") or 0) > 0
                        ]
                    ),
                    "top_10": len(
                        [
                            r
                            for r in rankings_list
                            if isinstance(r, dict)
                            and (r.get("position") or 100) <= 10
                            and (r.get("position") or 0) > 0
                        ]
                    ),
                    "top_20": len(
                        [
                            r
                            for r in rankings_list
                            if isinstance(r, dict)
                            and (r.get("position") or 100) <= 20
                            and (r.get("position") or 0) > 0
                        ]
                    ),
                    "beyond_20": len(
                        [
                            r
                            for r in rankings_list
                            if isinstance(r, dict)
                            and (
                                (r.get("position") or 100) > 20
                                or (r.get("position") or 0) == 0
                            )
                        ]
                    ),
                },
            }
            if rankings_list
            else {}
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
            should_refresh_keywords = force_fresh_geo
            should_refresh_backlinks = force_fresh_geo
            should_refresh_rankings = force_fresh_geo

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

            # 1. Keywords (fresh only when explicitly enabled)
            if should_refresh_keywords:
                try:
                    keyword_svc = KeywordService(db)
                    logger.info("  - Performing fresh keyword research for PDF...")
                    keywords_objs = await PDFService._run_stage_with_timeout(
                        stage_name="Keyword research",
                        coroutine_factory=lambda: keyword_svc.research_keywords(
                            audit_id, domain, seed_keywords=seed_keywords
                        ),
                        stage_timeout_seconds=geo_stage_timeout_seconds,
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

                    keywords_data = {
                        "items": keywords_data_list,
                        "keywords": keywords_data_list,
                        "total": len(keywords_data_list),
                        "total_keywords": len(keywords_data_list),
                        "top_opportunities": sorted(
                            keywords_data_list,
                            key=_keyword_opportunity_score,
                            reverse=True,
                        )[:10],
                    }
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
                        keywords_data = {
                            "items": keywords_data_list,
                            "keywords": keywords_data_list,
                            "total": len(keywords_data_list),
                            "total_keywords": len(keywords_data_list),
                            "top_opportunities": sorted(
                                keywords_data_list,
                                key=_keyword_opportunity_score,
                                reverse=True,
                            )[:10],
                        }
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
                        stage_timeout_seconds=geo_stage_timeout_seconds,
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

                    backlinks_data = {
                        "items": backlinks_list[:20],
                        "total": len(backlinks_list),
                        "total_backlinks": len(backlinks_list),
                        "referring_domains": len(
                            set(
                                urlparse(b["source_url"]).netloc
                                for b in backlinks_list
                                if "://" in b["source_url"]
                            )
                        ),
                        "top_backlinks": backlinks_list[:20],
                        "summary": {
                            "average_domain_authority": round(
                                sum(b["domain_authority"] for b in backlinks_list)
                                / len(backlinks_list),
                                1,
                            )
                            if backlinks_list
                            else 0,
                            "dofollow_count": len(
                                [b for b in backlinks_list if b["is_dofollow"]]
                            ),
                            "nofollow_count": len(
                                [b for b in backlinks_list if not b["is_dofollow"]]
                            ),
                        },
                    }
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

                        backlinks_data = {
                            "items": backlinks_list[:20],
                            "total": len(backlinks_list),
                            "total_backlinks": len(backlinks_list),
                            "referring_domains": len(
                                set(
                                    urlparse(b["source_url"]).netloc
                                    for b in backlinks_list
                                    if "://" in b["source_url"]
                                )
                            ),
                            "top_backlinks": backlinks_list[:20],
                            "summary": {
                                "average_domain_authority": round(
                                    sum(b["domain_authority"] for b in backlinks_list)
                                    / len(backlinks_list),
                                    1,
                                )
                                if backlinks_list
                                else 0,
                                "dofollow_count": len(
                                    [b for b in backlinks_list if b["is_dofollow"]]
                                ),
                                "nofollow_count": len(
                                    [b for b in backlinks_list if not b["is_dofollow"]]
                                ),
                            },
                        }
                except Exception as fb_err:
                    logger.error(f"Fallback for Backlinks failed: {fb_err}")

            # 3. Rankings (refresh when forced or cache is missing)
            if should_refresh_rankings:
                try:
                    rank_svc = RankTrackerService(db)
                    logger.info("  - Performing fresh rankings tracking for PDF...")
                    kw_terms = []
                    for item in keywords_data_list[:20]:
                        if isinstance(item, dict):
                            raw_term = item.get("keyword") or item.get("term")
                            if isinstance(raw_term, str) and raw_term.strip():
                                kw_terms.append(raw_term.strip())
                        elif isinstance(item, str) and item.strip():
                            kw_terms.append(item.strip())

                    if kw_terms:
                        rankings_objs = await PDFService._run_stage_with_timeout(
                            stage_name="Rankings tracking",
                            coroutine_factory=lambda: rank_svc.track_rankings(
                                audit_id, domain, kw_terms
                            ),
                            stage_timeout_seconds=geo_stage_timeout_seconds,
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

                    rank_tracking_data = {
                        "items": rankings_list,
                        "total": len(rankings_list),
                        "total_keywords": len(rankings_list),
                        "rankings": rankings_list,
                        "distribution": {
                            "top_3": len(
                                [
                                    r
                                    for r in rankings_list
                                    if r.get("position", 100) <= 3
                                    and r.get("position", 0) > 0
                                ]
                            ),
                            "top_10": len(
                                [
                                    r
                                    for r in rankings_list
                                    if r.get("position", 100) <= 10
                                    and r.get("position", 0) > 0
                                ]
                            ),
                            "top_20": len(
                                [
                                    r
                                    for r in rankings_list
                                    if r.get("position", 100) <= 20
                                    and r.get("position", 0) > 0
                                ]
                            ),
                            "beyond_20": len(
                                [
                                    r
                                    for r in rankings_list
                                    if r.get("position", 100) > 20
                                    or r.get("position", 0) == 0
                                ]
                            ),
                        },
                    }
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

                        rank_tracking_data = {
                            "rankings": rankings_list,
                            "total_keywords": len(rankings_list),
                            "distribution": {
                                "top_3": len(
                                    [
                                        r
                                        for r in rankings_list
                                        if r.get("position", 100) <= 3
                                        and r.get("position", 0) > 0
                                    ]
                                ),
                                "top_10": len(
                                    [
                                        r
                                        for r in rankings_list
                                        if r.get("position", 100) <= 10
                                        and r.get("position", 0) > 0
                                    ]
                                ),
                                "top_20": len(
                                    [
                                        r
                                        for r in rankings_list
                                        if r.get("position", 100) <= 20
                                        and r.get("position", 0) > 0
                                    ]
                                ),
                                "beyond_20": len(
                                    [
                                        r
                                        for r in rankings_list
                                        if r.get("position", 100) > 20
                                        or r.get("position", 0) == 0
                                    ]
                                ),
                            },
                        }
                except Exception as fb_err:
                    logger.error(f"Fallback for Rankings failed: {fb_err}")

            # 4. LLM Visibility (refresh when forced or missing cache)
            if force_fresh_geo:
                try:
                    if keywords_data_list:
                        refreshed_visibility = await PDFService._run_stage_with_timeout(
                            stage_name="LLM visibility analysis",
                            coroutine_factory=lambda: LLMVisibilityService.generate_llm_visibility(
                                keywords_data_list[:10], audit_url
                            ),
                            stage_timeout_seconds=geo_stage_timeout_seconds,
                            started_at=started_at,
                            total_budget_seconds=total_budget_seconds,
                        )
                        if refreshed_visibility is None:
                            raise TimeoutError("LLM visibility analysis timed out")
                        llm_visibility_data = refreshed_visibility
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
            if force_fresh_geo:
                try:
                    if keywords_data_list:
                        ai_content_suggestions_list = (
                            AIContentService.generate_content_suggestions(
                                keywords=keywords_data_list[:25], url=audit_url
                            )
                        )
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
                                {
                                    "topic": a.topic,
                                    "suggestion_type": a.suggestion_type,
                                    "content_outline": a.content_outline,
                                    "priority": a.priority,
                                    "page_url": a.page_url,
                                }
                                for a in audit.ai_content_suggestions
                            ]
                    except Exception:  # nosec B110
                        pass

            logger.info(
                f"✓ GEO Tools data ready: {len(keywords_data.get('items', []))} keywords, {len(backlinks_data.get('top_backlinks', []))} backlinks, {len(rank_tracking_data.get('rankings', []))} rankings"
            )

        except Exception as tool_error:
            logger.error(
                f"Critical error initializing GEO tools services: {tool_error}",
                exc_info=True,
            )
            # Fallback is handled by initialization values

        # 5. Load COMPLETE context from ALL features (refresh only if we ran fresh GEO)
        if force_fresh_geo:
            complete_context = PDFService._load_complete_audit_context(db, audit_id)
        logger.info(
            f"✓ Complete context loaded with {len(complete_context)} feature types"
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
                    logger.info("✓ External intelligence refreshed for PDF context")
            except Exception as external_err:
                logger.warning(
                    f"External intelligence full refresh failed. Continuing with persisted data: {external_err}"
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

        current_signature = PDFService._compute_report_context_signature(
            audit=audit,
            pagespeed_data=pagespeed_data if isinstance(pagespeed_data, dict) else {},
            keywords_data=keywords_data if isinstance(keywords_data, dict) else {},
            backlinks_data=backlinks_data if isinstance(backlinks_data, dict) else {},
            rank_tracking_data=(
                rank_tracking_data if isinstance(rank_tracking_data, dict) else {}
            ),
            llm_visibility_data=llm_viz_for_report,
            ai_content_suggestions=ai_suggestions_for_report,
        )
        cached_signature = PDFService._load_saved_report_signature(audit_id)
        has_valid_cached_markdown = len(fallback_markdown_report.strip()) > 100

        report_cache_hit = (
            (not force_report_refresh)
            and bool(current_signature)
            and current_signature == cached_signature
            and has_valid_cached_markdown
        )
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
            f"signature_match={bool(current_signature and current_signature == cached_signature)}, "
            f"current_sig={current_signature[:12] if current_signature else 'none'}, "
            f"cached_sig={cached_signature[:12] if cached_signature else 'none'}"
        )

        if report_cache_hit:
            logger.info(
                "✓ Report context signature matched. Reusing cached markdown report."
            )
            audit.report_markdown = fallback_markdown_report
            audit.fix_plan = fallback_fix_plan
            db.commit()

        if not report_cache_hit:
            try:
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
                        f"✓ Product intelligence loaded (ecommerce={product_intelligence_data.get('is_ecommerce')})"
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
                    f"✓ Markdown report regenerated with complete context ({len(markdown_report)} chars)"
                )

                # Ensure fix_plan is generated - NO FALLBACK for production
                if not fix_plan or len(fix_plan) == 0:
                    logger.warning(
                        "Fix plan is empty. No fallback used as per production requirements."
                    )
                    fix_plan = []

                audit.fix_plan = fix_plan
                db.commit()
                PDFService._save_report_signature(audit_id, current_signature)
                report_regenerated = True
                generation_mode = (
                    "full_regenerated" if always_full_mode else "report_regenerated"
                )

                logger.info(f"Fix plan length: {len(fix_plan) if fix_plan else 0}")
            except Exception as e:
                logger.error(
                    "LLM report regeneration failed; aborting PDF generation to avoid fallbacks.",
                    exc_info=True,
                )
                raise RuntimeError(
                    "Report regeneration failed and fallbacks are disabled."
                ) from e

        # 7. Get pages and competitors
        pages = AuditService.get_audited_pages(db, audit_id)
        from .audit_service import CompetitorService

        competitors = CompetitorService.get_competitors(db, audit_id)

        logger.info(f"✓ Loaded {len(pages)} pages and {len(competitors)} competitors")

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
        )

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
                "generation_mode": generation_mode,
                "external_intel_refreshed": external_intel_refreshed,
                "external_intel_refresh_reason": external_intel_refresh_reason,
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
    ) -> str:
        """
        Genera un PDF completo con todos los datos de la auditoría:
        - Datos de auditoría principal
        - Páginas auditadas
        - Competidores
        - PageSpeed data
        - Keywords
        - Backlinks
        - Rank tracking
        - LLM Visibility

        Args:
            audit: La instancia del modelo Audit
            pages: Lista de páginas auditadas
            competitors: Lista de competidores
            pagespeed_data: Datos de PageSpeed (opcional)
            keywords_data: Datos de Keywords (opcional)
            backlinks_data: Datos de Backlinks (opcional)
            rank_tracking_data: Datos de Rank Tracking (opcional)
            llm_visibility_data: Datos de LLM Visibility (opcional)

        Returns:
            La ruta completa al archivo PDF generado
        """
        if not PDF_GENERATOR_AVAILABLE:
            logger.error(
                "PDF generator no está disponible. Instalar fpdf2: pip install fpdf2"
            )
            raise ImportError("PDF generator not available")

        logger.info(
            f"Generando PDF completo para auditoría {audit.id} con todos los datos"
        )

        reports_dir = os.path.join(settings.REPORTS_BASE_DIR, f"audit_{audit.id}")
        os.makedirs(reports_dir, exist_ok=True)
        PDFService._clean_previous_pdf_artifacts(reports_dir)

        # 1. Guardar markdown report
        if audit.report_markdown:
            md_file_path = os.path.join(reports_dir, "ag2_report.md")
            with open(md_file_path, "w", encoding="utf-8") as f:
                f.write(audit.report_markdown)

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

        # 5. Guardar datos de páginas
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
                    logger.warning(f"No se pudo guardar datos de página {page.id}: {e}")

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
                    logger.warning(f"No se pudo guardar datos de competidor {idx}: {e}")

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
                return pdf_file_path
            else:
                logger.error(f"No se encontró el PDF generado en {reports_dir}")
                raise FileNotFoundError("PDF file not generated")
        except Exception as e:
            logger.error(
                f"Error generando PDF con create_comprehensive_pdf: {e}", exc_info=True
            )
            raise
