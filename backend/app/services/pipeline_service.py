#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_service.py - Servicio de Orquestación Pipeline (Agentes 1 y 2) v2.0

Integra la lógica de ag2_pipeline.py en servicios modulares reutilizables.
Utiliza PromptLoader para cargar prompts JSON v2.0 Enterprise.

Proporciona:
- Agente 1: Análisis de Inteligencia Externa
- Agente 2: Sintetizador de Reportes
- Orquestación completa del pipeline
- Búsqueda de competidores
- Auditoría de competidores
- Normalización de URLs
"""

import ast
import asyncio
import difflib
import inspect
import json
import logging
import math
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import aiohttp

from ..core.config import settings

# Importar PromptLoader
from .prompt_loader import get_prompt_loader

logger = logging.getLogger(__name__)


class PipelineService:
    """
    Servicio de Orquestación Pipeline v2.0.

    Coordina Agente 1, Agente 2, búsqueda de competidores,
    y generación de reportes completos utilizando prompts JSON Enterprise.
    """

    def __init__(self):
        """Inicializa el servicio con PromptLoader."""
        self.prompt_loader = get_prompt_loader()
        logger.info("PipelineService v2.0 initialized with PromptLoader")

    REPORT_SECTION_TITLES: Dict[int, str] = {
        1: "Executive Summary",
        2: "Competitive Intelligence Matrix",
        3: "Technical Performance & Financial Impact",
        4: "SEO Foundation",
        5: "Content Strategy & GEO Optimization",
        6: "Authority & Backlink Profile",
        7: "Keyword Strategy & Intent Mapping",
        8: "LLM Visibility & AI Mentions",
        9: "Product Intelligence",
        10: "90-Day Strategic Roadmap",
        11: "Appendices",
    }

    @staticmethod
    def normalize_url(url: str) -> str:
        """
        Normaliza una URL a formato completo.

        Convierte:
        - dominio.com → https://www.dominio.com
        - www.dominio.com → https://www.dominio.com
        - http://dominio.com → https://www.dominio.com

        Args:
            url: URL a normalizar

        Returns:
            URL normalizada con https:// y www.
        """
        if not url:
            return ""

        url = url.strip()

        parsed = urlparse(url)
        if not parsed.scheme:
            parsed = urlparse(f"https://{url}")

        scheme = (parsed.scheme or "https").lower()
        if scheme not in ("http", "https"):
            scheme = "https"

        netloc = (parsed.netloc or "").lower()
        path = parsed.path or ""

        normalized = parsed._replace(scheme=scheme, netloc=netloc).geturl()

        if not path:
            normalized = normalized.rstrip("/") + "/"

        logger.info(f"URL normalized: {normalized}")
        return normalized

    @staticmethod
    def now_iso() -> str:
        """Retorna timestamp ISO 8601 actual (timezone-aware)."""
        return (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

    @classmethod
    async def generate_pagespeed_analysis(
        cls, pagespeed_data: Dict[str, Any], llm_function: callable
    ) -> str:
        """
        Generates a markdown analysis of PageSpeed data using LLM.

        Args:
            pagespeed_data: Full PageSpeed data (mobile + desktop)
            llm_function: LLM call function

        Returns:
            Markdown string with the analysis
        """
        if not pagespeed_data:
            logger.warning("No PageSpeed data provided for analysis")
            return ""

        service = get_pipeline_service()

        try:

            def to_sec(ms):
                try:
                    return f"{float(ms) / 1000:.2f}s"
                except Exception:
                    return "0.00s"

            # Prepare simplified data for LLM to save tokens
            lite_data = {
                "mobile": {
                    "score": pagespeed_data.get("mobile", {}).get(
                        "performance_score", 0
                    ),
                    "metrics": {
                        "LCP": to_sec(
                            pagespeed_data.get("mobile", {})
                            .get("core_web_vitals", {})
                            .get("lcp", 0)
                        ),
                        "FID": f"{pagespeed_data.get('mobile', {}).get('core_web_vitals', {}).get('fid', 0):.0f}ms",
                        "CLS": f"{pagespeed_data.get('mobile', {}).get('core_web_vitals', {}).get('cls', 0):.3f}",
                        "FCP": to_sec(
                            pagespeed_data.get("mobile", {})
                            .get("core_web_vitals", {})
                            .get("fcp", 0)
                        ),
                        "TTFB": f"{pagespeed_data.get('mobile', {}).get('core_web_vitals', {}).get('ttfb', 0):.0f}ms",
                    },
                    "top_opportunities": service._extract_top_opportunities(
                        pagespeed_data.get("mobile", {}).get("opportunities", {}),
                        limit=3,
                    ),
                },
                "desktop": {
                    "score": pagespeed_data.get("desktop", {}).get(
                        "performance_score", 0
                    ),
                    "metrics": {
                        "LCP": to_sec(
                            pagespeed_data.get("desktop", {})
                            .get("core_web_vitals", {})
                            .get("lcp", 0)
                        ),
                        "FID": f"{pagespeed_data.get('desktop', {}).get('core_web_vitals', {}).get('fid', 0):.0f}ms",
                        "CLS": f"{pagespeed_data.get('desktop', {}).get('core_web_vitals', {}).get('cls', 0):.3f}",
                        "FCP": to_sec(
                            pagespeed_data.get("desktop", {})
                            .get("core_web_vitals", {})
                            .get("fcp", 0)
                        ),
                        "TTFB": f"{pagespeed_data.get('desktop', {}).get('core_web_vitals', {}).get('ttfb', 0):.0f}ms",
                    },
                    "top_opportunities": service._extract_top_opportunities(
                        pagespeed_data.get("desktop", {}).get("opportunities", {}),
                        limit=3,
                    ),
                },
            }

            # Cargar prompt desde JSON v2.0
            prompt_data = service.prompt_loader.load_prompt("pagespeed_analysis")
            system_prompt = prompt_data.get("system_prompt", "")
            user_template = prompt_data.get("user_template", "")

            # Preparar user prompt con los datos
            user_input = json.dumps(lite_data, ensure_ascii=False)
            user_prompt = user_template.replace("{pagespeed_data}", user_input)

            logger.info("Calling LLM for PageSpeed analysis with v2.0 prompt...")
            analysis = await llm_function(
                system_prompt=system_prompt, user_prompt=user_prompt
            )

            return analysis
        except Exception as e:
            logger.error(f"Error generating PageSpeed analysis: {e}", exc_info=True)
            return ""

    @staticmethod
    def _normalize_items(
        data: Any, list_keys: List[str], total_keys: List[str]
    ) -> Dict[str, Any]:
        """
        Normalize list-like structures to a {items: [...], total: N} shape.
        """
        if data is None:
            return {"items": [], "total": 0}

        if isinstance(data, dict):
            if "items" in data:
                items = data.get("items") or []
                total = data.get("total", len(items))
                return {"items": items, "total": total}

            for key in list_keys:
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    total = None
                    for total_key in total_keys:
                        if total_key in data:
                            total = data.get(total_key)
                            break
                    if total is None:
                        total = len(items)
                    return {"items": items, "total": total}

        if isinstance(data, list):
            return {"items": data, "total": len(data)}

        return {"items": [], "total": 0}

    @staticmethod
    def _sanitize_backlink_items(items: List[Any]) -> List[Dict[str, Any]]:
        sanitized: List[Dict[str, Any]] = []
        if not isinstance(items, list):
            return sanitized

        irrelevant_markers = (
            "unrelated",
            "irrelevant",
            "not related",
            "no relation",
            "no relacionado",
            "sin relación",
            "excluir del monitoreo",
            "exclude from brand monitoring",
        )

        for raw in items:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            anchor = item.get("anchor_text")

            if isinstance(anchor, str):
                stripped = anchor.strip()
                if stripped.startswith("{") and stripped.endswith("}"):
                    try:
                        parsed = json.loads(stripped)
                    except Exception:
                        parsed = None

                    if isinstance(parsed, dict):
                        summary = str(parsed.get("summary", "")).strip()
                        recommendation = str(parsed.get("recommendation", "")).strip()
                        topic = str(parsed.get("topic", "")).strip()
                        blob = f"{summary} {recommendation}".lower()

                        if any(marker in blob for marker in irrelevant_markers):
                            # Drop legacy irrelevant brand mentions leaked in anchor_text JSON.
                            continue

                        if summary:
                            anchor = f"{topic}: {summary}" if topic else summary
                        elif topic:
                            anchor = topic
                        else:
                            anchor = item.get("target_url", "") or "Brand mention"

                item["anchor_text"] = str(anchor)[:500] if anchor is not None else ""

            sanitized.append(item)

        return sanitized

    @staticmethod
    def _split_report_sections(
        report_markdown: str,
    ) -> Tuple[str, Dict[int, Dict[str, str]]]:
        header_re = re.compile(r"^##\s+(\d+)\.\s*(.*)$", re.MULTILINE)
        text = report_markdown or ""
        matches = list(header_re.finditer(text))
        if not matches:
            return text.strip(), {}

        preamble = text[: matches[0].start()].strip()
        sections: Dict[int, Dict[str, str]] = {}
        for idx, match in enumerate(matches):
            start = match.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            try:
                number = int(match.group(1))
            except Exception:  # nosec B112
                continue
            title = (match.group(2) or "").strip()
            body = text[start:end].strip()
            sections[number] = {"title": title, "body": body}
        return preamble, sections

    @staticmethod
    def _merge_report_sections(
        preamble: str, sections: Dict[int, Dict[str, str]]
    ) -> str:
        parts: List[str] = []
        if preamble:
            parts.append(preamble.strip())
        for section_number in range(1, 12):
            body = sections.get(section_number, {}).get("body", "")
            if body:
                parts.append(body.strip())
        return "\n\n".join(parts).strip()

    @staticmethod
    def _extract_section_from_text(text: str, section_number: int) -> str:
        if not text:
            return ""
        header_re = re.compile(rf"^##\s+{section_number}\.\s.*$", re.MULTILINE)
        match = header_re.search(text)
        if not match:
            return text.strip()
        start = match.start()
        next_match = re.search(r"^##\s+\d+\.\s", text[match.end() :], re.MULTILINE)
        end = match.end() + next_match.start() if next_match else len(text)
        return text[start:end].strip()

    async def _expand_report_sections(
        self,
        report_markdown: str,
        context: Dict[str, Any],
        llm_function: callable,
        min_total_words: int,
        min_section_words: int,
        min_exec_words: int,
        max_tokens: Optional[int],
    ) -> str:
        preamble, sections = self._split_report_sections(report_markdown)
        if not sections and (report_markdown or "").strip():
            sections = {
                1: {
                    "title": self.REPORT_SECTION_TITLES.get(1, "Executive Summary"),
                    "body": f"## 1. {self.REPORT_SECTION_TITLES.get(1, 'Executive Summary')}\n\n{report_markdown.strip()}",
                }
            }

        def _word_count(text: str) -> int:
            return len(re.findall(r"\b\w+\b", text or ""))

        target_per_section = max(
            min_section_words, int(math.ceil(min_total_words / 11.0))
        )
        target_exec = max(min_exec_words, target_per_section)

        section_system_prompt = (
            "You are a senior consulting lead expanding a single section of a "
            "board-ready digital audit report. Zero fabrication: do not invent "
            "metrics, competitors, or claims. Use only the provided context and "
            "include inline citations in the format [Source: <audited_url_or_page>] "
            "when referencing audited pages. If data is missing, explicitly label "
            "it as 'Insufficient data' and expand with methodology, implications, "
            "decision criteria, and implementation steps without adding new facts. "
            "Write in professional English."
        )

        section_max_tokens = min(int(max_tokens or 4000), 6000)

        section_context_keys = {
            1: [
                "target_audit",
                "external_intelligence",
                "data_quality",
                "score_definitions",
            ],
            2: [
                "competitor_audits",
                "search_results",
                "competitor_query_coverage",
                "target_audit",
                "data_quality",
                "score_definitions",
            ],
            3: ["pagespeed", "target_audit", "data_quality", "score_definitions"],
            4: ["target_audit", "pagespeed", "data_quality", "score_definitions"],
            5: [
                "target_audit",
                "ai_content_suggestions",
                "llm_visibility",
                "data_quality",
                "score_definitions",
            ],
            6: ["backlinks", "target_audit", "data_quality", "score_definitions"],
            7: [
                "keywords",
                "rank_tracking",
                "search_results",
                "target_audit",
                "data_quality",
                "score_definitions",
            ],
            8: [
                "llm_visibility",
                "ai_content_suggestions",
                "target_audit",
                "data_quality",
                "score_definitions",
            ],
            9: [
                "product_intelligence",
                "target_audit",
                "data_quality",
                "score_definitions",
            ],
            10: ["target_audit", "data_quality", "score_definitions"],
            11: ["data_quality", "score_definitions"],
        }

        for section_number in range(1, 12):
            current = sections.get(section_number, {})
            title = (
                current.get("title")
                or self.REPORT_SECTION_TITLES.get(section_number)
                or f"Section {section_number}"
            )
            current_body = current.get("body", "")
            target_words = target_exec if section_number == 1 else target_per_section
            if _word_count(current_body) >= target_words:
                if not current_body.strip().startswith(f"## {section_number}."):
                    sections[section_number] = {
                        "title": title,
                        "body": f"## {section_number}. {title}\n\n{current_body.strip()}",
                    }
                continue

            context_subset = {}
            for key in section_context_keys.get(section_number, []):
                if key in (context or {}):
                    context_subset[key] = context.get(key)
            if not context_subset:
                context_subset = context or {}
            context_json = json.dumps(context_subset, ensure_ascii=False, default=str)

            base_prompt = (
                f"Expand Section {section_number} to at least {target_words} words.\n"
                f"Return only this section in markdown starting with "
                f'"## {section_number}. {title}".\n\n'
                "Structure guidance: include at least 4 subsections with clear headings "
                "and 2-3 paragraphs each. If data is missing, add a 'Data Gaps' subsection "
                "and expand with methodology, implications, KPIs, and implementation steps "
                "without inventing facts.\n\n"
                "Existing section (if any):\n"
                "```markdown\n"
                f"{current_body.strip()}\n"
                "```\n\n"
                "Context JSON:\n"
                "```json\n"
                f"{context_json}\n"
                "```\n"
            )

            new_body = ""
            for attempt in range(2):
                attempt_prompt = base_prompt
                if attempt == 1:
                    attempt_prompt += (
                        "\nIMPORTANT: meet the minimum word count while respecting "
                        "zero-fabrication constraints.\n"
                    )
                try:
                    response = await llm_function(
                        system_prompt=section_system_prompt,
                        user_prompt=attempt_prompt,
                        max_tokens=section_max_tokens,
                    )
                except TypeError:
                    response = await llm_function(
                        system_prompt=section_system_prompt,
                        user_prompt=attempt_prompt,
                    )

                extracted = self._extract_section_from_text(
                    response or "", section_number
                )
                if not extracted.strip().startswith(f"## {section_number}."):
                    extracted = f"## {section_number}. {title}\n\n{extracted.strip()}"
                new_body = extracted.strip()
                if _word_count(new_body) >= target_words:
                    break

            if new_body:
                sections[section_number] = {"title": title, "body": new_body}

        return self._merge_report_sections(preamble, sections)

    async def _generate_report_impl(
        self,
        target_audit: Dict[str, Any],
        external_intelligence: Dict[str, Any],
        search_results: Dict[str, Any],
        competitor_audits: List[Dict[str, Any]],
        pagespeed_data: Optional[Dict] = None,
        keywords_data: Optional[Dict] = None,
        backlinks_data: Optional[Dict] = None,
        product_intelligence_data: Optional[Dict] = None,
        rank_tracking_data: Optional[Dict] = None,
        llm_visibility_data: Optional[Any] = None,
        ai_content_suggestions: Optional[Any] = None,
        llm_function: Optional[callable] = None,
    ) -> Tuple[str, List[Dict]]:
        """
        Generate report markdown and fix plan using the complete GEO context.
        """
        if llm_function is None:
            raise ValueError("LLM function is required for report generation")

        # Normalize core inputs
        target_audit = self._ensure_dict(target_audit)
        external_intelligence = self._ensure_dict(external_intelligence)
        search_results = self._ensure_dict(search_results)
        competitor_audits = competitor_audits or []
        competitor_audits = self._normalize_competitor_scores(competitor_audits)

        # Normalize optional GEO tools data
        keywords_norm = self._normalize_items(
            keywords_data,
            list_keys=["keywords"],
            total_keys=["total_keywords", "total"],
        )
        backlinks_norm = self._normalize_items(
            backlinks_data,
            list_keys=["top_backlinks", "backlinks"],
            total_keys=["total_backlinks", "total"],
        )
        backlinks_norm["items"] = self._sanitize_backlink_items(
            backlinks_norm.get("items", [])
        )
        backlinks_norm["total"] = len(backlinks_norm["items"])
        rank_norm = self._normalize_items(
            rank_tracking_data,
            list_keys=["rankings", "rank_tracking"],
            total_keys=["total_keywords", "total_rankings", "total"],
        )
        llm_visibility_norm = self._normalize_items(
            llm_visibility_data,
            list_keys=["items", "llm_visibility"],
            total_keys=["total", "total_queries", "total_items"],
        )
        ai_content_norm = self._normalize_items(
            ai_content_suggestions,
            list_keys=["items", "ai_content_suggestions"],
            total_keys=["total", "total_suggestions"],
        )

        competitor_audits = self._normalize_competitor_scores(competitor_audits or [])
        competitor_query_coverage: Dict[str, Any] = {}
        try:
            from app.services.competitive_intel_service import CompetitiveIntelService

            competitor_query_coverage = (
                CompetitiveIntelService.build_competitor_query_coverage(
                    search_results or {}, competitor_audits, target_audit=target_audit
                )
            )
        except Exception as e:
            logger.warning(f"Competitive intel coverage build failed: {e}")

        score_definitions = self._build_score_definitions()
        data_quality = self._build_data_quality(
            target_audit=target_audit,
            search_results=search_results or {},
            competitor_audits=competitor_audits,
            pagespeed_data=pagespeed_data or {},
            keywords_data=keywords_norm,
            backlinks_data=backlinks_norm,
            rank_tracking_data=rank_norm,
            llm_visibility_data=llm_visibility_norm,
            competitor_query_coverage=competitor_query_coverage,
        )

        context = {
            "target_audit": target_audit,
            "external_intelligence": external_intelligence,
            "search_results": search_results,
            "competitor_audits": competitor_audits,
            "competitor_query_coverage": competitor_query_coverage,
            "pagespeed": pagespeed_data or {},
            "keywords": keywords_norm,
            "backlinks": backlinks_norm,
            "rank_tracking": rank_norm,
            "llm_visibility": llm_visibility_norm,
            "ai_content_suggestions": ai_content_norm,
            "product_intelligence": product_intelligence_data or {},
            "data_quality": data_quality,
            "score_definitions": score_definitions,
        }

        prompt_data = {}
        try:
            prompt_data = self.prompt_loader.load_prompt("report_generation")
        except Exception as e:
            logger.warning(f"Could not load report_generation prompt: {e}")

        system_prompt = prompt_data.get("system_prompt", "")
        # Ensure system prompt references required keys for tests and clarity
        if "ai_content_suggestions" not in system_prompt:
            system_prompt += "\nContext includes ai_content_suggestions."
        if "PageSpeed" not in system_prompt and "pagespeed" not in system_prompt:
            system_prompt += "\nContext includes PageSpeed data."

        minimized_context, user_prompt = self._shrink_context_to_budget(
            context, system_prompt
        )

        report_max_tokens = None
        try:
            from app.core.config import settings

            report_max_tokens = getattr(settings, "NV_MAX_TOKENS_REPORT", None)
        except Exception:
            report_max_tokens = None

        from app.core.config import settings

        def _word_count(text: str) -> int:
            return len(re.findall(r"\b\w+\b", text or ""))

        def _section_word_counts(text: str) -> Dict[int, int]:
            pattern = re.compile(r"^##\s+(\d+)\.", re.MULTILINE)
            matches = list(pattern.finditer(text or ""))
            if not matches:
                return {}
            counts: Dict[int, int] = {}
            for idx, match in enumerate(matches):
                start = match.start()
                end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
                section_text = (text or "")[start:end]
                try:
                    section_number = int(match.group(1))
                except Exception:  # nosec B112
                    continue
                counts[section_number] = _word_count(section_text)
            return counts

        report_length_strict = bool(getattr(settings, "REPORT_LENGTH_STRICT", True))
        if report_length_strict:
            min_total_words = max(
                1000, int(getattr(settings, "REPORT_MIN_WORDS", 8000))
            )
            min_section_words = max(
                200, int(getattr(settings, "REPORT_MIN_SECTION_WORDS", 400))
            )
            min_exec_words = max(
                300, int(getattr(settings, "REPORT_MIN_EXEC_SUMMARY_WORDS", 800))
            )
        else:
            min_total_words = 0
            min_section_words = 0
            min_exec_words = 0

        def _meets_length_requirements(text: str) -> Tuple[bool, str]:
            if not report_length_strict:
                return (True, "")
            total_words = _word_count(text)
            if total_words < min_total_words:
                return (
                    False,
                    f"Total words {total_words} < min {min_total_words}",
                )
            required_sections = [f"## {i}." for i in range(1, 12)]
            missing = [s for s in required_sections if s not in text]
            if missing:
                return (False, f"Missing sections: {', '.join(missing)}")
            section_counts = _section_word_counts(text)
            if section_counts:
                if section_counts.get(1, 0) < min_exec_words:
                    return (
                        False,
                        f"Section 1 words {section_counts.get(1, 0)} < min {min_exec_words}",
                    )
                for sec in range(2, 11):
                    if section_counts.get(sec, 0) < min_section_words:
                        return (
                            False,
                            f"Section {sec} words {section_counts.get(sec, 0)} < min {min_section_words}",
                        )
                if section_counts.get(11, 0) < min_section_words:
                    return (
                        False,
                        f"Section 11 words {section_counts.get(11, 0)} < min {min_section_words}",
                    )
            return (True, "")

        delimiter = self.prompt_loader.get_delimiter()
        report_markdown = ""
        fix_plan: List[Dict] = []
        last_reason = ""

        for attempt in range(2):
            attempt_system_prompt = system_prompt
            if attempt == 1 and report_length_strict:
                attempt_system_prompt += (
                    "\n\nIMPORTANT LENGTH REQUIREMENTS:\n"
                    f"- Total words >= {min_total_words}\n"
                    f"- Section 1 >= {min_exec_words} words\n"
                    f"- Sections 2-10 >= {min_section_words} words each\n"
                    f"- Section 11 >= {min_section_words} words\n"
                    "Expand each section with deeper analysis grounded in the provided data. "
                    "Do NOT invent metrics. If data is missing, explicitly label it as "
                    "'Insufficient data' and expand with methodology, implications, and "
                    "implementation detail. Return the full report and fix plan using the "
                    "standard delimiter.\n"
                )
            try:
                response = await llm_function(
                    system_prompt=attempt_system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=report_max_tokens,
                )
            except TypeError:
                response = await llm_function(
                    system_prompt=attempt_system_prompt, user_prompt=user_prompt
                )

            parts = response.split(delimiter)
            if len(parts) >= 2:
                report_markdown = parts[0].strip()
                fix_plan_text = parts[1].strip()
                try:
                    fix_plan = json.loads(fix_plan_text)
                    if not isinstance(fix_plan, list):
                        fix_plan = []
                except json.JSONDecodeError:
                    fix_plan = []
            else:
                report_markdown = response.strip()
                fix_plan = []

            ok, reason = _meets_length_requirements(report_markdown)
            last_reason = reason
            if ok:
                break

            logger.warning(
                f"Report length requirements not met (attempt {attempt + 1}/2): {reason}"
            )

        if not report_markdown:
            raise RuntimeError("Report generation failed: empty response")
        ok, reason = _meets_length_requirements(report_markdown)
        if not ok:
            logger.warning(
                f"Report too short after initial attempts ({last_reason or reason}). "
                "Starting section expansion pass."
            )
            try:
                report_markdown = await self._expand_report_sections(
                    report_markdown=report_markdown,
                    context=minimized_context,
                    llm_function=llm_function,
                    min_total_words=min_total_words,
                    min_section_words=min_section_words,
                    min_exec_words=min_exec_words,
                    max_tokens=report_max_tokens,
                )
            except Exception as expand_err:
                logger.error(
                    f"Report expansion pass failed: {expand_err}", exc_info=True
                )

            ok, reason = _meets_length_requirements(report_markdown)
            if not ok:
                raise RuntimeError(
                    "Report generation failed to meet minimum length requirements: "
                    f"{last_reason or reason}"
                )

        report_markdown = self._sanitize_report_sources(report_markdown, target_audit)

        enriched_fix_plan = self._enrich_fix_plan_with_audit_issues(
            fix_plan,
            target_audit,
            pagespeed_data=pagespeed_data,
            product_intelligence_data=product_intelligence_data,
        )
        return report_markdown, enriched_fix_plan

    @classmethod
    async def generate_report(
        cls,
        target_audit: Dict[str, Any],
        external_intelligence: Dict[str, Any],
        search_results: Dict[str, Any],
        competitor_audits: List[Dict[str, Any]],
        pagespeed_data: Optional[Dict] = None,
        keywords_data: Optional[Dict] = None,
        backlinks_data: Optional[Dict] = None,
        product_intelligence_data: Optional[Dict] = None,
        rank_tracking_data: Optional[Dict] = None,
        llm_visibility_data: Optional[Any] = None,
        ai_content_suggestions: Optional[Any] = None,
        llm_function: Optional[callable] = None,
    ) -> Tuple[str, List[Dict]]:
        service = get_pipeline_service()
        return await service._generate_report_impl(
            target_audit=target_audit,
            external_intelligence=external_intelligence,
            search_results=search_results,
            competitor_audits=competitor_audits,
            pagespeed_data=pagespeed_data,
            keywords_data=keywords_data,
            backlinks_data=backlinks_data,
            product_intelligence_data=product_intelligence_data,
            rank_tracking_data=rank_tracking_data,
            llm_visibility_data=llm_visibility_data,
            ai_content_suggestions=ai_content_suggestions,
            llm_function=llm_function,
        )

    @staticmethod
    def _extract_top_opportunities(opportunities_dict: dict, limit: int = 3) -> list:
        """
        Extract top opportunities from PageSpeed opportunities dictionary.

        Safely converts the opportunities dictionary to a sorted list of the most
        impactful optimizations based on potential time savings.

        Args:
            opportunities_dict: Dictionary of opportunity audits from PageSpeed API
            limit: Maximum number of opportunities to return (default: 3)

        Returns:
            List of top opportunities sorted by potential savings (descending)
        """
        if not opportunities_dict or not isinstance(opportunities_dict, dict):
            logger.warning(
                f"PageSpeed opportunities is not a valid dict: {type(opportunities_dict)}"
            )
            return []

        try:
            opportunities_list = []
            for key, opp_data in opportunities_dict.items():
                if not isinstance(opp_data, dict):
                    continue

                numeric_value = opp_data.get("numericValue", 0)
                if numeric_value is None:
                    numeric_value = 0

                if not isinstance(numeric_value, (int, float)):
                    numeric_value = 0

                if numeric_value > 0:
                    opportunities_list.append(
                        {
                            "id": key,
                            "title": opp_data.get(
                                "title", key.replace("_", " ").title()
                            ),
                            "description": opp_data.get("description", ""),
                            "savings_ms": numeric_value,
                            "score": opp_data.get("score", 0),
                            "display_value": opp_data.get("displayValue", ""),
                        }
                    )

            opportunities_list.sort(key=lambda x: x["savings_ms"], reverse=True)
            result = opportunities_list[:limit]

            logger.info(
                f"Extracted {len(result)} PageSpeed opportunities from {len(opportunities_dict)} total (top {limit})"
            )
            return result

        except Exception as e:
            logger.error(
                f"Error extracting PageSpeed opportunities: {e}", exc_info=True
            )
            return []

    @staticmethod
    def _aggregate_summaries(summaries: List[Dict], base_url: str) -> Dict[str, Any]:
        """Agrega múltiples auditorías en un resumen consolidado."""
        if not summaries:
            return {"error": "No summaries provided"}

        def get_path_from_url(url_str, base_url_str):
            if not url_str:
                return "/"

            raw = str(url_str).strip()
            if not raw:
                return "/"

            def _canonical_host(value: str) -> str:
                if not value:
                    return ""
                try:
                    parsed_value = urlparse(
                        value if "://" in value else f"https://{value}"
                    )
                except Exception:
                    return ""
                host_value = (parsed_value.hostname or "").lower()
                if host_value.startswith("www."):
                    host_value = host_value[4:]
                return host_value

            base_host = _canonical_host(str(base_url_str or "").strip())
            path = ""

            if raw.startswith("/"):
                path = raw
            else:
                try:
                    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
                except Exception:
                    parsed = None

                parsed_host = ""
                if parsed is not None:
                    parsed_host = (parsed.hostname or "").lower()
                    if parsed_host.startswith("www."):
                        parsed_host = parsed_host[4:]
                    path = parsed.path or ""

                # Valores malformados como "root-house./services" deben conservar
                # solo la parte de ruta, nunca el host residual.
                if (
                    base_host
                    and parsed_host
                    and parsed_host != base_host
                    and "://" not in raw
                    and "/" in raw
                ):
                    path = f"/{raw.split('/', 1)[1]}"

            if not path:
                if raw.startswith("/"):
                    path = raw
                elif "://" not in raw and "/" in raw:
                    path = f"/{raw.split('/', 1)[1]}"
                else:
                    path = "/"

            path = path.split("?", 1)[0].split("#", 1)[0].strip() or "/"
            if not path.startswith("/"):
                path = f"/{path}"
            path = re.sub(r"/{2,}", "/", path)
            return path or "/"

        if len(summaries) == 1:
            s = summaries[0]
            s["audited_page_paths"] = [get_path_from_url(s["url"], base_url)]
            return s

        logger.info(f"Agregando {len(summaries)} resúmenes de auditoría...")

        pages_with_h1_pass = [
            get_path_from_url(s["url"], base_url)
            for s in summaries
            if s["structure"]["h1_check"]["status"] == "pass"
        ]
        pages_missing_h1 = [
            get_path_from_url(s["url"], base_url)
            for s in summaries
            if s["structure"]["h1_check"]["status"] != "pass"
        ]
        pages_with_author = [
            get_path_from_url(s["url"], base_url)
            for s in summaries
            if s["eeat"]["author_presence"]["status"] == "pass"
        ]
        pages_with_schema = [
            get_path_from_url(s["url"], base_url)
            for s in summaries
            if s["schema"]["schema_presence"]["status"] == "present"
        ]
        pages_with_faqs = [
            get_path_from_url(s["url"], base_url)
            for s in summaries
            if s["content"]["question_targeting"]["status"] == "pass"
        ]

        header_hierarchy_issues = []
        long_paragraph_issues = [
            get_path_from_url(s["url"], base_url)
            for s in summaries
            if "long_paragraphs=" in s["content"]["fragment_clarity"]["details"]
            and int(s["content"]["fragment_clarity"]["details"].split("=")[-1]) > 0
        ]
        author_missing_issues = [
            get_path_from_url(s["url"], base_url)
            for s in summaries
            if s["eeat"]["author_presence"]["status"] != "pass"
        ]
        freshness_missing_issues = [
            get_path_from_url(s["url"], base_url)
            for s in summaries
            if not s["eeat"]["content_freshness"]["dates_found"]
        ]
        no_authoritative_links = [
            get_path_from_url(s["url"], base_url)
            for s in summaries
            if s["eeat"]["citations_and_sources"]["authoritative_links"] == 0
        ]

        all_schema_types = set()
        all_raw_jsonld = []
        all_h1s = []
        homepage_h1_status = None
        homepage_h1_example = None
        homepage_h1_count = None
        all_meta_robots = set()
        total_external = 0
        total_authoritative = 0
        total_lists = 0
        total_tables = 0

        for s in summaries:
            path = get_path_from_url(s["url"], base_url)
            all_schema_types.update(s["schema"]["schema_types"])
            if s["schema"].get("raw_jsonld"):
                all_raw_jsonld.append(
                    {
                        "page_path": path,
                        "raw_json": (
                            s["schema"]["raw_jsonld"][0]
                            if s["schema"]["raw_jsonld"]
                            else "{}"
                        ),
                    }
                )

            h1_details = s["structure"]["h1_check"].get("details", {})
            if h1_details:
                all_h1s.append(
                    f"[{path}] -> H1: {h1_details.get('example', 'N/A')} (Count: {h1_details.get('count', 0)})"
                )
            if path == "/":
                homepage_h1_status = s["structure"]["h1_check"].get("status")
                homepage_h1_example = h1_details.get("example") if h1_details else None
                homepage_h1_count = h1_details.get("count") if h1_details else None
            if s.get("meta_robots"):
                all_meta_robots.add(s["meta_robots"])

            total_external += s["eeat"]["citations_and_sources"]["external_links"]
            total_authoritative += s["eeat"]["citations_and_sources"][
                "authoritative_links"
            ]
            total_lists += s["structure"]["list_usage"]["count"]
            total_tables += s["structure"]["table_usage"]["count"]

            if s["structure"]["header_hierarchy"]["issues"]:
                first_issue = s["structure"]["header_hierarchy"]["issues"][0]
                header_hierarchy_issues.append(
                    {
                        "page_path": path,
                        "prev_tag_html": first_issue.get("prev_tag_html"),
                        "current_tag_html": first_issue.get("current_tag_html"),
                    }
                )

        avg_semantic_score = round(
            sum(s["structure"]["semantic_html"]["score_percent"] for s in summaries)
            / len(summaries),
            1,
        )
        avg_conversational = round(
            sum(s["content"]["conversational_tone"]["score"] for s in summaries)
            / len(summaries),
            1,
        )

        h1_status = "pass" if len(pages_with_h1_pass) == len(summaries) else "warn"
        if homepage_h1_status and homepage_h1_status != "pass":
            h1_status = "fail"

        aggregated = {
            "url": f"SITE-WIDE AGGREGATE: {base_url}",
            "status": 200,
            "content_type": "aggregate/json",
            "generated_at": summaries[0]["generated_at"],
            "audited_pages_count": len(summaries),
            "audited_page_paths": [
                get_path_from_url(s["url"], base_url) for s in summaries
            ],
            "structure": {
                "h1_check": {
                    "status": h1_status,
                    "details": f"{len(pages_with_h1_pass)}/{len(summaries)} pages have a valid H1.",
                    "pages_pass": pages_with_h1_pass,
                    "pages_missing": pages_missing_h1,
                    "homepage_status": homepage_h1_status,
                    "homepage_example": homepage_h1_example,
                    "homepage_count": homepage_h1_count,
                    "examples": all_h1s,
                },
                "header_hierarchy": {
                    "issues_found_on_pages": len(header_hierarchy_issues),
                    "pages_with_issues": [
                        issue["page_path"] for issue in header_hierarchy_issues
                    ],
                    "issue_examples": header_hierarchy_issues,
                },
                "semantic_html": {"score_percent": avg_semantic_score},
                "list_usage": {"count": total_lists},
                "table_usage": {"count": total_tables},
            },
            "content": {
                "fragment_clarity": {
                    "long_paragraphs_found_on_pages": len(long_paragraph_issues),
                    "pages_with_issues": long_paragraph_issues,
                },
                "conversational_tone": {"score": avg_conversational},
                "question_targeting": {
                    "status": "pass" if pages_with_faqs else "warn",
                    "details": f"FAQs detected on {len(pages_with_faqs)} pages.",
                    "pages_with_faqs": pages_with_faqs,
                },
            },
            "eeat": {
                "author_presence": {
                    "status": (
                        "warn" if len(pages_with_author) < len(summaries) else "pass"
                    ),
                    "details": f"Author found on {len(pages_with_author)}/{len(summaries)} pages.",
                    "pages_with_author": pages_with_author,
                    "pages_missing_author": author_missing_issues,
                },
                "citations_and_sources": {
                    "total_external_links": total_external,
                    "total_authoritative_links": total_authoritative,
                    "pages_missing_authoritative_links": no_authoritative_links,
                },
                "content_freshness": {
                    "dates_found_on_pages": len(summaries)
                    - len(freshness_missing_issues),
                    "pages_missing_dates": freshness_missing_issues,
                },
            },
            "schema": {
                "schema_presence": {
                    "status": (
                        "warn" if len(pages_with_schema) < len(summaries) else "pass"
                    ),
                    "details": f"JSON-LD Schema found on {len(pages_with_schema)}/{len(summaries)} pages.",
                    "pages_with_schema": pages_with_schema,
                },
                "schema_types": list(all_schema_types),
                "raw_jsonld_found": all_raw_jsonld,
            },
            "meta_robots": list(all_meta_robots),
        }
        return aggregated

    @staticmethod
    def _compute_site_metrics(page_summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not page_summaries:
            return {}

        total_pages = len(page_summaries)
        h1_missing = 0
        schema_present = 0
        faq_pages = 0
        semantic_scores: List[float] = []
        product_pages = 0
        category_pages = 0
        meta_desc_pages = 0
        meta_kw_pages = 0
        product_schema_pages = 0
        faq_schema_pages = 0
        offer_schema_pages = 0
        review_schema_pages = 0
        text_lengths: List[int] = []
        price_samples: List[float] = []
        price_currency = None
        pages_with_price = 0
        total_images = 0
        missing_alt = 0
        total_videos = 0
        header_hierarchy_issue_pages = 0
        homepage_h1_status = None

        product_url_patterns = [
            "/p/",
            "/producto",
            "/product/",
            "/products/",
            "/sku/",
            "/item/",
        ]
        category_url_patterns = [
            "/category/",
            "/categories/",
            "/collection/",
            "/collections/",
            "/c/",
            "/shop/",
            "/store/",
            "/department/",
        ]
        product_schema_types = {"Product"}
        offer_schema_types = {"Offer", "AggregateOffer"}
        review_schema_types = {"Review", "AggregateRating"}
        faq_schema_types = {"FAQPage"}

        for summary in page_summaries:
            if not isinstance(summary, dict):
                continue
            structure = (
                summary.get("structure", {})
                if isinstance(summary.get("structure"), dict)
                else {}
            )
            content = (
                summary.get("content", {})
                if isinstance(summary.get("content"), dict)
                else {}
            )
            schema = (
                summary.get("schema", {})
                if isinstance(summary.get("schema"), dict)
                else {}
            )

            h1_status = structure.get("h1_check", {}).get("status")
            if h1_status != "pass":
                h1_missing += 1

            if schema.get("schema_presence", {}).get("status") == "present":
                schema_present += 1

            if content.get("question_targeting", {}).get("status") == "pass":
                faq_pages += 1

            if content.get("meta_description"):
                meta_desc_pages += 1
            if content.get("meta_keywords"):
                meta_kw_pages += 1

            semantic_score = structure.get("semantic_html", {}).get("score_percent")
            if isinstance(semantic_score, (int, float)):
                semantic_scores.append(float(semantic_score))

            url_value = summary.get("url", "") or ""
            url_path = urlparse(url_value).path.lower() if url_value else ""
            if url_path in ("", "/") and homepage_h1_status is None:
                homepage_h1_status = h1_status
            schema_types = schema.get("schema_types") or []
            if any(p in url_path for p in product_url_patterns) or any(
                t in ["Product", "Offer", "AggregateOffer"] for t in schema_types
            ):
                product_pages += 1
            if any(p in url_path for p in category_url_patterns):
                category_pages += 1

            for t in schema_types:
                if t in product_schema_types:
                    product_schema_pages += 1
                if t in offer_schema_types:
                    offer_schema_pages += 1
                if t in review_schema_types:
                    review_schema_pages += 1
                if t in faq_schema_types:
                    faq_schema_pages += 1

            media = (
                content.get("media", {})
                if isinstance(content.get("media"), dict)
                else {}
            )
            img_count = media.get("image_count")
            if isinstance(img_count, int):
                total_images += img_count
            alt_missing = media.get("images_missing_alt")
            if isinstance(alt_missing, int):
                missing_alt += alt_missing
            vid_count = media.get("video_count")
            if isinstance(vid_count, int):
                total_videos += vid_count

            header_issues = structure.get("header_hierarchy", {}).get("issues") or []
            if header_issues:
                header_hierarchy_issue_pages += 1

            raw_jsonld = schema.get("raw_jsonld") or []
            page_has_price = False
            for block in raw_jsonld[:5]:
                try:
                    parsed = json.loads(block)
                except Exception:  # nosec B112
                    continue

                def _collect_from_obj(obj: Any):
                    nonlocal price_currency, page_has_price
                    if isinstance(obj, dict):
                        offers = obj.get("offers")
                        if offers:
                            _collect_from_obj(offers)
                        price_val = obj.get("price")
                        currency_val = obj.get("priceCurrency") or obj.get(
                            "pricecurrency"
                        )
                        if currency_val and not price_currency:
                            price_currency = str(currency_val)
                        if price_val is not None:
                            if isinstance(price_val, (int, float)):
                                price_samples.append(float(price_val))
                                page_has_price = True
                            elif isinstance(price_val, str):
                                match = re.search(r"[0-9]+(?:[\\.,][0-9]+)?", price_val)
                                if match:
                                    try:
                                        price_samples.append(
                                            float(match.group(0).replace(",", "."))
                                        )
                                        page_has_price = True
                                    except Exception:  # nosec B110
                                        pass
                        for v in obj.values():
                            _collect_from_obj(v)
                    elif isinstance(obj, list):
                        for it in obj:
                            _collect_from_obj(it)

                _collect_from_obj(parsed)

            if page_has_price:
                pages_with_price += 1

            text_sample = content.get("text_sample", "") or ""
            text_lengths.append(len(text_sample))

        avg_semantic = (
            round(sum(semantic_scores) / len(semantic_scores), 1)
            if semantic_scores
            else 0.0
        )
        avg_text_len = (
            round(sum(text_lengths) / len(text_lengths), 1) if text_lengths else 0.0
        )
        schema_coverage = round((schema_present / max(1, total_pages)) * 100, 1)
        h1_coverage = round(((total_pages - h1_missing) / max(1, total_pages)) * 100, 1)
        header_hierarchy_coverage = round(
            ((total_pages - header_hierarchy_issue_pages) / max(1, total_pages)) * 100,
            1,
        )
        structure_score = round(
            (avg_semantic + h1_coverage + header_hierarchy_coverage) / 3, 1
        )

        price_samples = [p for p in price_samples if p > 0][:50]
        avg_price = (
            round(sum(price_samples) / len(price_samples), 2) if price_samples else None
        )
        min_price = round(min(price_samples), 2) if price_samples else None
        max_price = round(max(price_samples), 2) if price_samples else None
        avg_images = round(total_images / max(1, total_pages), 1)
        image_alt_coverage = (
            round((total_images - missing_alt) / max(1, total_images) * 100, 1)
            if total_images
            else None
        )

        return {
            "pages_analyzed": total_pages,
            "schema_coverage_percent": schema_coverage,
            "h1_coverage_percent": h1_coverage,
            "header_hierarchy_issue_pages": header_hierarchy_issue_pages,
            "header_hierarchy_coverage_percent": header_hierarchy_coverage,
            "structure_score_percent": structure_score,
            "homepage_h1_status": homepage_h1_status,
            "faq_page_count": faq_pages,
            "product_page_count": product_pages,
            "category_page_count": category_pages,
            "avg_semantic_score_percent": avg_semantic,
            "avg_text_sample_length": avg_text_len,
            "meta_description_coverage_percent": round(
                (meta_desc_pages / max(1, total_pages)) * 100, 1
            ),
            "meta_keywords_coverage_percent": round(
                (meta_kw_pages / max(1, total_pages)) * 100, 1
            ),
            "product_schema_pages": product_schema_pages,
            "offer_schema_pages": offer_schema_pages,
            "review_schema_pages": review_schema_pages,
            "faq_schema_pages": faq_schema_pages,
            "price_samples_count": len(price_samples),
            "avg_price": avg_price,
            "min_price": min_price,
            "max_price": max_price,
            "price_currency": price_currency,
            "pages_with_price": pages_with_price,
            "avg_images_per_page": avg_images,
            "image_alt_coverage_percent": image_alt_coverage,
            "video_count_total": total_videos,
        }

    @staticmethod
    def _build_score_definitions() -> Dict[str, Any]:
        return {
            "structure_score_percent": {
                "definition": "Composite structural quality score (semantic HTML + H1 coverage + header hierarchy health).",
                "formula": "(semantic_html_score + h1_coverage_percent + header_hierarchy_coverage_percent) / 3",
                "scale": "0-100 (higher is better)",
            },
            "conversational_tone_score": {
                "definition": "Share of H2/H3 headings phrased as questions (Q&A orientation).",
                "formula": "(question_headings / total_headings) * 10",
                "scale": "0-10 (higher is more conversational)",
            },
        }

    @staticmethod
    def _build_data_quality(
        target_audit: Dict[str, Any],
        search_results: Dict[str, Any],
        competitor_audits: List[Dict[str, Any]],
        pagespeed_data: Optional[Dict[str, Any]],
        keywords_data: Optional[Dict[str, Any]],
        backlinks_data: Optional[Dict[str, Any]],
        rank_tracking_data: Optional[Dict[str, Any]] = None,
        llm_visibility_data: Optional[Any] = None,
        competitor_query_coverage: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        insufficient: List[str] = []
        if not search_results:
            insufficient.append("competitor_search_results")
        if not competitor_audits:
            insufficient.append("competitor_audits")
        if not pagespeed_data:
            insufficient.append("pagespeed")
        if not keywords_data or not (
            keywords_data.get("items") if isinstance(keywords_data, dict) else None
        ):
            insufficient.append("keywords")
        if not backlinks_data or not (
            backlinks_data.get("items") if isinstance(backlinks_data, dict) else None
        ):
            insufficient.append("backlinks")
        if rank_tracking_data is None or (
            isinstance(rank_tracking_data, dict) and not rank_tracking_data.get("items")
        ):
            insufficient.append("rank_tracking")
        if llm_visibility_data is None or (
            isinstance(llm_visibility_data, dict)
            and not llm_visibility_data.get("items")
        ):
            insufficient.append("llm_visibility")
        if competitor_query_coverage and isinstance(competitor_query_coverage, dict):
            if competitor_query_coverage.get("status") == "insufficient_data":
                insufficient.append("competitor_query_coverage")

        pages_analyzed = None
        if isinstance(target_audit, dict):
            site_metrics = target_audit.get("site_metrics", {})
            if isinstance(site_metrics, dict):
                pages_analyzed = site_metrics.get("pages_analyzed")
        if pages_analyzed is not None and pages_analyzed < 3:
            insufficient.append("pages_analyzed_low_sample")

        assumptions = [
            "Financial projections require confirmed traffic/conversion baselines; treat as scenario estimates unless provided."
        ]
        notes = [
            "Competitor keyword capture uses Serper query results as a proxy; it is not a true ranking dataset.",
        ]
        return {
            "insufficient_data": sorted(set(insufficient)),
            "assumptions": assumptions,
            "notes": notes,
        }

    @staticmethod
    def _normalize_competitor_scores(
        competitor_audits: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Garantiza geo_score/benchmark consistentes en competidores."""
        if not isinstance(competitor_audits, list) or not competitor_audits:
            return competitor_audits or []
        try:
            from app.services.audit_service import CompetitorService
        except Exception:
            CompetitorService = None

        for comp in competitor_audits:
            if not isinstance(comp, dict):
                continue
            geo_score = comp.get("geo_score")
            if not isinstance(geo_score, (int, float)) or geo_score <= 0:
                if CompetitorService is not None:
                    comp["geo_score"] = CompetitorService._calculate_geo_score(comp)
            if CompetitorService is not None and comp.get("status", 200) == 200:
                comp["benchmark"] = CompetitorService._format_competitor_data(
                    comp, comp.get("geo_score", 0.0), comp.get("url")
                )
            # Sanitize any legacy benchmark payloads to avoid circular references
            if isinstance(comp.get("benchmark"), dict):
                comp["benchmark"].pop("audit_data", None)
        return competitor_audits

    @staticmethod
    def _sanitize_report_sources(
        report_markdown: str, target_audit: Dict[str, Any]
    ) -> str:
        if not report_markdown:
            return report_markdown

        base_url = ""
        if isinstance(target_audit, dict):
            base_url = target_audit.get("url") or ""
        if base_url and not urlparse(base_url).scheme:
            base_url = f"https://{base_url}"
        base_url = base_url.rstrip("/")
        base_domain = urlparse(base_url).netloc if base_url else ""

        internal_markers = [
            "structure/",
            "content/",
            "schema/",
            "eeat/",
            "site_metrics",
            "structure_score",
            "schema_presence",
            "product_schema",
            "pagespeed",
            "keywords",
            "backlinks",
            "rank_tracking",
            "llm_visibility",
            "ai_content",
            "h1_check",
            "header_hierarchy",
            "semantic_html",
            "conversational_tone",
            "question_targeting",
            "citations_and_sources",
            "content_freshness",
            "author_presence",
            "list_usage",
            "table_usage",
            "fragment_clarity",
        ]
        placeholder_sources = {
            "score_definitions": "Internal audit - score definitions",
            "data_quality": "Internal audit - data quality notes",
            "competitor_query_coverage": "Internal audit - competitor query coverage",
            "product_intelligence": "Internal audit - product intelligence",
            "rank_tracking": "Internal audit - rank tracking",
            "keywords": "Internal audit - keyword research",
            "backlinks": "Internal audit - backlink analysis",
            "llm_visibility": "Internal audit - llm visibility",
            "pagespeed_data": "Internal audit - pagespeed data",
        }

        def normalize_source(raw: str) -> str:
            src = (raw or "").strip()
            lower = src.lower()
            if not src:
                return "Internal audit"
            if lower in placeholder_sources:
                return placeholder_sources[lower]
            if any(marker in lower for marker in internal_markers):
                tail = src.split("/")[-1] if "/" in src else src
                return f"Internal audit - {tail}"
            if src.startswith("/") and base_url:
                return f"{base_url}{src}"
            if "://" not in src and base_domain:
                if src.startswith(base_domain):
                    return f"https://{src}"
            return src

        pattern = re.compile(r"\[Source:\s*([^\]]+)\]")

        def repl(match: re.Match) -> str:
            return f"[Source: {normalize_source(match.group(1))}]"

        return pattern.sub(repl, report_markdown)

    @staticmethod
    def _build_initial_baseline_report(
        target_audit: Dict[str, Any],
        external_intelligence: Dict[str, Any],
        competitor_count: int,
    ) -> str:
        """
        Genera un reporte baseline persistente (no-LLM) para el flujo inicial.
        Solo usa datos reales ya recolectados, sin inventar métricas.
        """
        target = target_audit if isinstance(target_audit, dict) else {}
        external = (
            external_intelligence if isinstance(external_intelligence, dict) else {}
        )
        url_value = target.get("url") or "N/A"
        pages_count = target.get("audited_pages_count") or target.get(
            "site_metrics", {}
        ).get("pages_analyzed", 0)
        category_value = (
            external.get("category") or target.get("category") or "Unclassified"
        )
        market_value = external.get("market") or target.get("market") or "Unknown"
        is_ymyl = bool(external.get("is_ymyl", False))

        lines = [
            "# Initial GEO Audit Snapshot",
            "",
            f"- Target URL: {url_value}",
            f"- Audited pages: {pages_count}",
            f"- Category: {category_value}",
            f"- Market: {market_value}",
            f"- YMYL: {is_ymyl}",
            f"- Competitors audited: {int(competitor_count or 0)}",
            "",
            "This baseline report is generated from collected audit data only. "
            "A full strategic report will be generated during PDF creation.",
        ]
        return "\n".join(lines)

    @staticmethod
    def _ensure_dict(obj: Any) -> Dict[str, Any]:
        """Normaliza: si obj es tuple/list devuelve su primer elemento, si es dict lo devuelve, si None devuelve {}."""
        if obj is None:
            return {}
        if isinstance(obj, (tuple, list)) and len(obj) > 0:
            maybe = obj[0]
            return maybe if isinstance(maybe, dict) else {}
        if isinstance(obj, dict):
            return obj
        return {}

    @staticmethod
    def filter_competitor_urls(
        search_items: List[Dict],
        target_domain: str,
        limit: int = 5,
        core_terms: Optional[List[str]] = None,
        anchor_terms: Optional[List[str]] = None,
        vertical_hint: Optional[str] = None,
    ) -> List[str]:
        """
        Filtra una lista de resultados de Google Search y devuelve URLs limpias (Home Pages) de competidores reales.

        Reglas:
        1. Excluye el dominio objetivo.
        2. Excluye directorios, redes sociales y sitios de "listas".
        3. Excluye subdominios irrelevantes (blog, help, forums).
        4. Normaliza a la URL raíz (Home Page).
        5. Devuelve solo un dominio único por competidor.
        6. Requiere match con core_terms derivados del contenido del sitio (sin hardcode de industria).

        Args:
            search_items: Lista de items de Google Search API
            target_domain: Dominio objetivo (para excluir)
            core_terms: Lista de términos clave del negocio (sin marca)

        Returns:
            Lista de URLs filtradas y únicas (Home Pages)
        """
        if not search_items:
            return []

        core_terms = [
            t.strip().lower()
            for t in (core_terms or [])
            if isinstance(t, str) and t.strip()
        ]
        anchor_terms = [
            t.strip().lower()
            for t in (anchor_terms or [])
            if isinstance(t, str) and t.strip()
        ]
        if core_terms:
            generic_terms = PipelineService._generic_business_terms()
            core_terms = [t for t in core_terms if t not in generic_terms]
        if anchor_terms:
            generic_terms = PipelineService._generic_business_terms()
            anchor_terms = [t for t in anchor_terms if t not in generic_terms]
        if not core_terms:
            logger.info(
                "PIPELINE: Sin core terms; no se intentará detectar competidores para evitar falsos."
            )
            return []

        bad_patterns = [
            "linkedin.com",
            "facebook.com",
            "twitter.com",
            "x.com",
            "youtube.com",
            "instagram.com",
            "pinterest.com",
            "tiktok.com",
            ".gov",
            ".edu",
            "wikipedia.org",
            "medium.com",
            "reddit.com",
            "quora.com",
            ".science",
            "g.page",
            "goo.gl",
            "maps.google.com",
            "github.com",
            "gob.ar",
            ".gob.",
            "gob.",
            "gouv.",
            "gov.",
            "ac.uk",
            ".ac.",
            ".edu.",
            ".gov.",
            ".mil",
            ".int",
            "europa.eu",
            "zoom.info",
            "crunchbase.com",
            "zoominfo.com",
            "similarweb.com",
            "brandfetch.com",
            "builtwith.com",
            "wappalyzer.com",
            "semrush.com",
            "ahrefs.com",
            "moz.com",
            "spyfu.com",
            "seranking.com",
            "sistrix.com",
            "majestic.com",
            "owler.com",
            "cbinsights.com",
            "apollo.io",
            "craft.co",
            "opencorporates.com",
            "amazon.com",
            "ebay.com",
            "mercadolibre.com",
            "clarin.com",
            "lanacion.com",
            "foxbusiness.com",
            "foxnews.com",
            "reuters.com",
            "bloomberg.com",
            "forbes.com",
            "nytimes.com",
            "cnn.com",
            "bbc.co",
            "theguardian.com",
            "stackoverflow.com",
            "developers.google.com",
            "imdb.com",
            "warnerbros.com",
            "merriam-webster.com",
            "britannica.com",
            "dictionary.com",
            "thefreedictionary.com",
            "medicalnewstoday.com",
            "mayoclinic.org",
            "webmd.com",
            "healthline.com",
            # Software Directories and Comparators
            "sourceforge.net",
            "capterra.com",
            "g2.com",
            "getapp.com",
            "softwareadvice.com",
            "trustradius.com",
            "alternativeto.net",
            "openalternative.co",
            "tracxn.com",
            "pitchbook.com",
            "producthunt.com",
            "appsumo.com",
            "slashdot.org",
            "clutch.co",
            "themanifest.com",
            "sortlist.com",
            "techbehemoths.com",
            "goodfirms.co",
            "superbcompanies.com",
            "techradar.com",
            "pcmag.com",
            "zapier.com",
            "dev.to",
            "hashnode.com",
            "softpedia.com",
            "uptodown.com",
            "softonic.com",
            target_domain,  # Excluir self
        ]

        bad_subdomains = {
            "blog",
            "blogs",
            "forum",
            "forums",
            "community",
            "help",
            "support",
            "docs",
            "status",
            "dev",
            "developer",
            "developers",
            "learn",
            "academy",
            "science",
            "journal",
            "journals",
            "research",
            "news",
            "press",
            "investors",
            "careers",
            "jobs",
        }

        bad_title_words = [
            "review",
            "reviews",
            "alternativa",
            "alternative",
            "alternativas",
            "alternatives",
            "comparativa",
            "comparacion",
            "comparación",
            " vs ",
            " versus ",
            "top 10",
            "top 5",
            "top 20",
            "best of",
            "list of",
            "forum",
            "news",
            "press",
            "press release",
            "report",
            "charged",
            "sanctions",
            "investigation",
            "lawsuit",
            "court",
            "treasury",
            "justice",
            "dea",
            "asociacion",
            "asociación",
            "camara",
            "cámara",
            "federacion",
            "federación",
            "fundacion",
            "fundación",
            "instituto",
            "ministerio",
            "gobierno",
            "government",
            "agency",
            "embassy",
            "consulate",
            "association",
            "federation",
            "chamber",
            "b2b",
            "supplier",
            "manufacturing",
            "ingredients",
        ]

        bad_snippet_words = [
            "asociacion",
            "asociación",
            "camara",
            "cámara",
            "federacion",
            "federación",
            "fundacion",
            "fundación",
            "instituto",
            "ministerio",
            "gobierno",
            "government",
            "agency",
            "embassy",
            "consulate",
            "association",
            "federation",
            "chamber",
            "b2b",
            "supplier",
            "manufacturing",
            "ingredients",
            "news",
            "press",
            "press release",
            "report",
            "charged",
            "sanctions",
            "investigation",
            "lawsuit",
            "court",
            "treasury",
            "justice",
            "dea",
        ]

        bad_url_keywords = [
            "/competitors",
            "/competitor",
            "/alternatives",
            "/alternative",
            "/compare",
            "/comparison",
            "/similar",
            "/reviews",
            "/research",
            "/reports",
            "/report",
            "/insight",
            "/insights",
            "/blog",
            "/blogs",
            "/news",
            "/article",
            "/articles",
        ]

        unique_domains = set()
        local_urls: List[str] = []
        global_urls: List[str] = []
        country_hint = PipelineService._infer_country_tld(target_domain)

        logger.info(
            f"PIPELINE: Filtrando {len(search_items)} resultados de búsqueda para encontrar competidores."
        )

        def _text_roots(text: str) -> set:
            roots = set()
            for token in re.findall(r"[a-z0-9áéíóúñ]{2,}", str(text or "").lower()):
                root = PipelineService._normalize_token_root(token)
                if root:
                    roots.add(root)
            return roots

        def _roots_match(term_root: str, roots: set) -> bool:
            if not term_root or not roots:
                return False
            if term_root in roots:
                return True
            if len(term_root) < 5:
                return False
            for root in roots:
                if len(root) < 5:
                    continue
                prefix_len = min(7, len(term_root), len(root))
                if (
                    prefix_len >= 5
                    and term_root[:prefix_len] == root[:prefix_len]
                ):
                    return True
            return False

        def _count_core_term_matches(text: str) -> int:
            if not core_terms:
                return 0
            roots = _text_roots(text)
            matches = 0
            matched_roots = set()
            for term in core_terms:
                root = PipelineService._normalize_token_root(term)
                if not root or root in matched_roots:
                    continue
                if _roots_match(root, roots):
                    matches += 1
                    matched_roots.add(root)
            return matches

        def matches_core_terms(text: str, minimum: int) -> bool:
            return _count_core_term_matches(text) >= minimum

        def _count_anchor_term_matches(text: str) -> int:
            if not anchor_terms:
                return 0
            roots = _text_roots(text)
            matches = 0
            matched_roots = set()
            for term in anchor_terms:
                root = PipelineService._normalize_token_root(term)
                if not root or root in matched_roots:
                    continue
                if _roots_match(root, roots):
                    matches += 1
                    matched_roots.add(root)
            return matches

        def _contains_banned_term(text: str, term: str) -> bool:
            hay = (text or "").lower()
            needle = (term or "").strip().lower()
            if not hay or not needle:
                return False
            if " " in needle:
                return needle in hay
            if re.fullmatch(r"[a-z0-9]+", needle):
                return (
                    re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", hay)
                    is not None
                )
            return needle in hay

        def evaluate_item(item: Dict[str, Any], relaxed: bool) -> Optional[str]:
            url = item.get("link") if isinstance(item, dict) else None
            title = item.get("title", "").lower() if isinstance(item, dict) else ""
            snippet = item.get("snippet", "").lower() if isinstance(item, dict) else ""

            if not url:
                return None

            parsed_url = urlparse(url)
            netloc = parsed_url.netloc.lower()
            path = parsed_url.path.lower()
            tld = netloc.split(".")[-1] if "." in netloc else ""

            domain_clean = netloc[4:] if netloc.startswith("www.") else netloc

            if domain_clean in unique_domains:
                return None

            domain_parts = netloc.split(".")
            subdomain = ""
            if len(domain_parts) >= 3 and domain_parts[0] != "www":
                subdomain = domain_parts[0]

            if subdomain in bad_subdomains:
                logger.info(
                    f"PIPELINE: Excluyendo {url} (subdominio irrelevante: {subdomain})"
                )
                return None

            if any(keyword in path for keyword in bad_url_keywords):
                logger.info(f"PIPELINE: Excluyendo {url} (ruta no competitiva: {path})")
                return None

            for pattern in bad_patterns:
                if pattern in domain_clean:
                    logger.info(
                        f"PIPELINE: Excluyendo {url} (patrón prohibido: {pattern})"
                    )
                    return None

            bad_word = next(
                (
                    word
                    for word in bad_title_words
                    if _contains_banned_term(title, word)
                ),
                None,
            )
            if bad_word:
                logger.info(
                    f"PIPELINE: Excluyendo {url} (palabra prohibida en título: {bad_word})"
                )
                return None

            bad_snippet = next(
                (
                    word
                    for word in bad_snippet_words
                    if _contains_banned_term(snippet, word)
                ),
                None,
            )
            if bad_snippet:
                logger.info(
                    f"PIPELINE: Excluyendo {url} (palabra prohibida en snippet: {bad_snippet})"
                )
                return None

            if str(vertical_hint or "").lower() in {"ecommerce", "retail"} and tld in {
                "org",
                "edu",
                "gov",
            }:
                logger.info(
                    f"PIPELINE: Excluyendo {url} (TLD no comercial para ecommerce: .{tld})"
                )
                return None

            title_matches = _count_core_term_matches(title)
            snippet_matches = _count_core_term_matches(snippet)
            domain_matches = _count_core_term_matches(domain_clean.replace("-", " "))
            total_matches = title_matches + snippet_matches
            min_matches = 2 if len(core_terms) >= 2 else 1

            if relaxed:
                # En modo relajado exigimos señal fuerte en título o dominio
                # para evitar falsos positivos basados solo en snippets genéricos.
                if (title_matches + domain_matches) < 1:
                    logger.info(
                        f"PIPELINE: Excluyendo {url} (sin match fuerte en title/domain)"
                    )
                    return None
            else:
                # En modo estricto también exigimos al menos un match fuerte en
                # título o dominio para evitar ruido de snippets ambiguos.
                if (title_matches + domain_matches) < 1:
                    logger.info(
                        f"PIPELINE: Excluyendo {url} (sin match fuerte en title/domain)"
                    )
                    return None
                if total_matches < min_matches:
                    logger.info(f"PIPELINE: Excluyendo {url} (sin match de core terms)")
                    return None

            if anchor_terms:
                anchor_title = _count_anchor_term_matches(title)
                anchor_domain = _count_anchor_term_matches(
                    domain_clean.replace("-", " ")
                )
                anchor_snippet = _count_anchor_term_matches(snippet)
                if (anchor_title + anchor_domain + anchor_snippet) < 1:
                    logger.info(
                        f"PIPELINE: Excluyendo {url} (sin match de anchor terms)"
                    )
                    return None

            home_url = f"{parsed_url.scheme}://{netloc}/"
            return home_url

        for item in search_items:
            if country_hint:
                if len(local_urls) >= max(1, int(limit)):
                    break
            else:
                if (len(local_urls) + len(global_urls)) >= max(1, int(limit)):
                    break
            try:
                home_url = evaluate_item(item, relaxed=False)
                if not home_url:
                    continue
                domain_clean = urlparse(home_url).netloc.lower().replace("www.", "")
                logger.info(f"PIPELINE: Competidor detectado: {home_url}")
                unique_domains.add(domain_clean)
                if country_hint and domain_clean.endswith(country_hint):
                    local_urls.append(home_url)
                else:
                    global_urls.append(home_url)
            except Exception as e:
                logger.error(f"PIPELINE: Error procesando URL {item}: {e}")
                continue

        # Second pass (relaxed) is disabled by default to avoid false positives.
        enable_relaxed_pass = bool(
            getattr(settings, "COMPETITOR_RELAXED_PASS", False)
        )
        if enable_relaxed_pass and (len(local_urls) + len(global_urls)) < max(
            2, int(limit // 2)
        ):
            for item in search_items:
                if (len(local_urls) + len(global_urls)) >= max(1, int(limit)):
                    break
                try:
                    home_url = evaluate_item(item, relaxed=True)
                    if not home_url:
                        continue
                    domain_clean = urlparse(home_url).netloc.lower().replace("www.", "")
                    if domain_clean in unique_domains:
                        continue
                    logger.info(f"PIPELINE: Competidor detectado (relaxed): {home_url}")
                    unique_domains.add(domain_clean)
                    if country_hint and domain_clean.endswith(country_hint):
                        local_urls.append(home_url)
                    else:
                        global_urls.append(home_url)
                except Exception as e:
                    logger.error(f"PIPELINE: Error procesando URL {item}: {e}")
                    continue
        elif not enable_relaxed_pass:
            logger.info(
                "PIPELINE: relaxed competitor pass disabled (precision-first mode)."
            )

        ordered_urls = local_urls + global_urls
        filtered_urls = ordered_urls[: max(1, int(limit))]
        logger.info(
            f"PIPELINE: Total {len(filtered_urls)} competidores únicos encontrados."
        )
        return filtered_urls

    @staticmethod
    def normalize_competitor_list(
        competitors: List[str], target_domain: str
    ) -> List[str]:
        if not competitors:
            return []
        normalized: List[str] = []
        seen = set()
        for raw in competitors:
            if not raw:
                continue
            url = PipelineService.normalize_url(str(raw))
            parsed = urlparse(url)
            if not parsed.netloc:
                continue
            domain_clean = parsed.netloc.lower().replace("www.", "")
            if not domain_clean or domain_clean == target_domain:
                continue
            if domain_clean in seen:
                continue
            seen.add(domain_clean)
            normalized.append(f"{parsed.scheme}://{parsed.netloc}/")
        return normalized

    @staticmethod
    def _extract_competitor_urls_from_search(
        search_results: Dict[str, Any],
        target_domain: str,
        target_audit: Dict[str, Any],
        external_intelligence: Optional[Dict[str, Any]] = None,
        core_profile: Optional[Dict[str, Any]] = None,
        limit: int = 5,
    ) -> List[str]:
        if not isinstance(search_results, dict):
            return []

        all_items: List[Dict[str, Any]] = []
        for query_text, res in search_results.items():
            if isinstance(res, dict):
                items = res.get("items", [])
                if isinstance(items, list):
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        enriched = dict(item)
                        enriched["_query"] = str(query_text or "")
                        all_items.append(enriched)
        if not all_items:
            return []

        effective_core_profile = (
            core_profile
            if isinstance(core_profile, dict)
            else PipelineService._build_core_business_profile(target_audit, max_terms=6)
        )
        core_terms_all = [
            str(term).strip().lower()
            for term in (effective_core_profile.get("core_terms") or [])
            if str(term).strip()
        ]
        noisy_core_terms = {
            "insight",
            "insights",
            "webinar",
            "webinars",
            "newsroom",
            "overview",
            "news",
            "blog",
            "blogs",
            "article",
            "articles",
            "evento",
            "eventos",
            "event",
            "events",
            "que",
            "no",
        }
        core_terms_all = [
            term
            for term in core_terms_all
            if len(term) >= 3 and term not in noisy_core_terms
        ]
        if not core_terms_all:
            core_terms_all = PipelineService._extract_core_terms_from_target(
                target_audit, max_terms=3, include_generic=True
            )
        generic_terms = PipelineService._generic_business_terms()
        core_terms_strong = [
            term for term in core_terms_all if term not in generic_terms
        ]
        if not core_terms_strong:
            core_terms_strong = PipelineService._extract_core_terms_from_target(
                target_audit, max_terms=3, include_generic=False
            )
        if not core_terms_strong:
            logger.info(
                "PIPELINE: Sin core terms fuertes; no se intentará detectar competidores para evitar falsos."
            )
            return []

        external = (
            external_intelligence if isinstance(external_intelligence, dict) else {}
        )
        primary_query = str(external.get("primary_query") or "").strip().lower()
        anchor_terms = PipelineService._extract_anchor_terms_from_queries(
            external.get("queries_to_run", []),
            external.get("market") or target_audit.get("market"),
        )
        market_tokens = set(
            re.findall(
                r"[a-z0-9]+",
                str(external.get("market") or target_audit.get("market") or "").lower(),
            )
        )

        def _score_item(item: Dict[str, Any]) -> float:
            title = str(item.get("title") or "").lower()
            snippet = str(item.get("snippet") or "").lower()
            domain = (
                urlparse(str(item.get("link") or "")).netloc.replace("www.", "").lower()
            )
            source_query = str(item.get("_query") or "").strip().lower()
            text = f"{title} {snippet} {domain}"
            score = 0.0
            if primary_query and source_query == primary_query:
                score += 10.0
            for term in core_terms_strong:
                token = str(term or "").strip().lower()
                if token and token in text:
                    score += 2.0
            for term in anchor_terms:
                token = str(term or "").strip().lower()
                if token and token in text:
                    score += 1.0
            for token in market_tokens:
                if len(token) >= 3 and token in text:
                    score += 0.5
            return score

        ranked_items = sorted(all_items, key=_score_item, reverse=True)

        logger.info(f"PIPELINE: Core terms para competidores: {core_terms_strong}")
        competitor_urls = PipelineService.filter_competitor_urls(
            ranked_items,
            target_domain,
            limit=limit,
            core_terms=core_terms_strong,
            anchor_terms=anchor_terms,
            vertical_hint=effective_core_profile.get("vertical_hint"),
        )
        if competitor_urls:
            return competitor_urls

        if anchor_terms:
            fallback_core = [
                term for term in anchor_terms[:3] if term and term not in generic_terms
            ]
            if fallback_core:
                logger.info(
                    "PIPELINE: Sin competidores con core terms. Reintentando con anchor terms."
                )
                competitor_urls = PipelineService.filter_competitor_urls(
                    ranked_items,
                    target_domain,
                    limit=limit,
                    core_terms=fallback_core,
                    anchor_terms=anchor_terms,
                    vertical_hint=effective_core_profile.get("vertical_hint"),
                )
                if competitor_urls:
                    return competitor_urls

        topic_hint = " ".join(
            str(v or "")
            for v in [
                target_audit.get("subcategory"),
                target_audit.get("category"),
            ]
        ).strip()
        if topic_hint:
            topic_terms_raw = PipelineService._extract_core_terms(
                topic_hint, max_terms=4
            )
            topic_terms = [
                term
                for term in topic_terms_raw.split()
                if term and term not in generic_terms
            ][:3]
            if topic_terms:
                logger.info(
                    "PIPELINE: Sin competidores con core/anchor terms. Reintentando con category/subcategory."
                )
                return PipelineService.filter_competitor_urls(
                    ranked_items,
                    target_domain,
                    limit=limit,
                    core_terms=topic_terms,
                    anchor_terms=anchor_terms or topic_terms,
                    vertical_hint=effective_core_profile.get("vertical_hint"),
                )

        return []

    @staticmethod
    def _extract_internal_urls_from_search(
        search_items: List[Dict[str, Any]], target_domain: str, limit: int = 50
    ) -> List[str]:
        if not search_items or not target_domain:
            return []
        target_domain = target_domain.replace("www.", "").lower()
        urls: List[str] = []
        seen = set()
        for item in search_items:
            if not isinstance(item, dict):
                continue
            link = item.get("link")
            if not link:
                continue
            try:
                parsed = urlparse(link)
            except Exception:  # nosec B112
                continue
            if parsed.scheme not in {"http", "https"}:
                continue
            host = (parsed.hostname or "").lower()
            host = host[4:] if host.startswith("www.") else host
            if not host:
                continue
            if not re.fullmatch(r"[a-z0-9.-]+", host):
                continue
            if host.startswith(".") or host.endswith(".") or ".." in host:
                continue
            if host != target_domain:
                continue
            if any(
                parsed.path.lower().endswith(ext)
                for ext in [".pdf", ".jpg", ".png", ".svg", ".zip", ".mp4"]
            ):
                continue
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path or '/'}"
            key = normalized.rstrip("/").lower()
            if key in seen:
                continue
            seen.add(key)
            urls.append(normalized)
            if len(urls) >= limit:
                break
        return urls

    @staticmethod
    def parse_agent_json_or_raw(text: str, default_key: str = "raw") -> Dict[str, Any]:
        """
        Parsea JSON de la respuesta del agente.

        Maneja:
        - Bloques ```json ... ```
        - Bloques ~~~json ... ~~~
        - Trailing commas (error común en LLMs)

        Args:
            text: Texto a parsear
            default_key: Clave por defecto si falla el parseo

        Returns:
            Diccionario parseado o con fallback
        """
        text = (text or "").strip()
        if not text:
            return {default_key: ""}
        max_chars = int(settings.PIPELINE_JSON_PARSE_MAX_CHARS)
        if max_chars <= 0:
            max_chars = 200000
        if len(text) > max_chars:
            logger.warning(
                f"parse_agent_json_or_raw: payload exceeds limit ({len(text)} > {max_chars}), returning truncated raw."
            )
            return {default_key: text[:max_chars]}

        # Remover bloques de código
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("~~~json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.startswith("~~~"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        if text.endswith("~~~"):
            text = text[:-3]
        text = text.strip()

        try:
            first_brace = text.find("{")
            first_bracket = text.find("[")

            start = -1
            end_char = "}"

            if first_brace == -1 and first_bracket == -1:
                return {default_key: text}

            if first_brace != -1 and (
                first_bracket == -1 or first_brace < first_bracket
            ):
                start = first_brace
                end_char = "}"
            else:
                start = first_bracket
                end_char = "]"

            end = text.rfind(end_char)
            if end == -1:
                return {default_key: text}

            candidate = text[start : end + 1]
            if len(candidate) > max_chars:
                logger.warning(
                    f"parse_agent_json_or_raw: candidate exceeds limit ({len(candidate)} > {max_chars}), returning raw."
                )
                return {default_key: text[:max_chars]}

            # Try strict JSON first.
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, (dict, list)):
                    return parsed
            except json.JSONDecodeError:
                pass

            # Limpiar trailing commas
            candidate_cleaned = re.sub(r",\s*([}\]])", r"\1", candidate)

            # Limpiar comentarios estilo JS
            candidate_cleaned = re.sub(r"//.*?\n", "\n", candidate_cleaned)
            candidate_cleaned = re.sub(
                r"/\*.*?\*/", "", candidate_cleaned, flags=re.DOTALL
            )
            if len(candidate_cleaned) > max_chars:
                logger.warning(
                    f"parse_agent_json_or_raw: cleaned candidate exceeds limit ({len(candidate_cleaned)} > {max_chars}), returning raw."
                )
                return {default_key: text[:max_chars]}

            try:
                parsed = json.loads(candidate_cleaned)
                if isinstance(parsed, (dict, list)):
                    return parsed
            except json.JSONDecodeError:
                # Fallback: intentar parseo tipo Python dict (comillas simples, True/False)
                try:
                    parsed = ast.literal_eval(candidate_cleaned)
                    if isinstance(parsed, (dict, list)):
                        return parsed
                except Exception:  # nosec B110
                    pass
                return {default_key: text}

        except Exception as e:
            logger.warning(f"Fallo parsear JSON: {e}. Raw: {text[:200]}...")
            return {default_key: text}

    @staticmethod
    @staticmethod
    def _looks_like_ecommerce(
        domain: str, title: str, snippet: str, relaxed: bool = False
    ) -> bool:
        """
        Heurística genérica (sin hardcode de industria) para señales comerciales básicas.
        """
        combined = f"{domain} {title} {snippet}".lower()
        commerce_signals = [
            "pricing",
            "plans",
            "plan",
            "subscribe",
            "signup",
            "sign up",
            "apply",
            "enroll",
            "book",
            "booking",
            "checkout",
            "cart",
            "buy",
            "shop",
            "store",
            "services",
            "solutions",
            "platform",
            "product",
            "products",
            "software",
            "saas",
        ]
        has_signal = any(sig in combined for sig in commerce_signals)
        return has_signal

    @staticmethod
    def _infer_country_tld(domain: str) -> str:
        """
        Devuelve un TLD país (ej: .com.ar, .com.mx, .ar) si se puede inferir.
        Útil para priorizar competidores locales.
        """
        if not domain:
            return ""
        domain = domain.lower().strip()
        regional_tlds = [
            ".com.ar",
            ".com.mx",
            ".com.co",
            ".com.uy",
            ".com.cl",
            ".com.pe",
            ".com.ec",
            ".com.bo",
            ".com.py",
            ".com.ve",
            ".com.do",
            ".com.gt",
            ".com.hn",
            ".com.ni",
            ".com.pa",
            ".com.sv",
            ".com.cr",
            ".com.br",
        ]
        for tld in regional_tlds:
            if domain.endswith(tld):
                return tld
        parts = domain.split(".")
        if len(parts) >= 2:
            cc = parts[-1]
            if len(cc) == 2:
                return f".{cc}"
        return ""

    @staticmethod
    def _extract_agent_payload(agent_json: Any) -> Dict[str, Any]:
        """Extrae y normaliza el payload real del Agente 1."""
        if not isinstance(agent_json, dict):
            return {}

        required_keys = {
            "category",
            "queries_to_run",
            "business_type",
            "business_model",
            "market_maturity",
        }
        alias_keys = {
            "classification",
            "strategic_queries",
            "ymyl_status",
            "market_country",
            "industry_context",
        }

        def _to_bool(value: Any) -> Optional[bool]:
            if value is None:
                return None
            if isinstance(value, bool):
                return value
            raw = str(value).strip().lower()
            if raw in {"true", "yes", "y", "1", "ymyl", "high"}:
                return True
            if raw in {"false", "no", "n", "0", "non-ymyl", "low"}:
                return False
            return None

        def _normalize_payload(payload: Any) -> Dict[str, Any]:
            if not isinstance(payload, dict):
                return {}
            normalized = dict(payload)

            classification = payload.get("classification")
            if isinstance(classification, dict):
                if classification.get("category") and not normalized.get("category"):
                    normalized["category"] = classification.get("category")
                if classification.get("subcategory") and not normalized.get(
                    "subcategory"
                ):
                    normalized["subcategory"] = classification.get("subcategory")
                if classification.get("business_type") and not normalized.get(
                    "business_type"
                ):
                    normalized["business_type"] = classification.get("business_type")
            elif isinstance(classification, str) and not normalized.get("category"):
                normalized["category"] = classification

            strategic_queries = payload.get("strategic_queries")
            if strategic_queries and not normalized.get("queries_to_run"):
                normalized["queries_to_run"] = strategic_queries

            strategic_search_queries = payload.get("strategic_search_queries")
            if strategic_search_queries and not normalized.get("queries_to_run"):
                normalized["queries_to_run"] = strategic_search_queries

            competitor_queries = payload.get("competitor_queries")
            if competitor_queries and not normalized.get("queries_to_run"):
                normalized["queries_to_run"] = competitor_queries

            competitive_intel_queries = payload.get("competitive_intelligence_queries")
            if competitive_intel_queries and not normalized.get("queries_to_run"):
                normalized["queries_to_run"] = competitive_intel_queries

            ymyl_status = payload.get("ymyl_status")
            if "is_ymyl" not in normalized and ymyl_status is not None:
                ymyl_bool = _to_bool(ymyl_status)
                if ymyl_bool is not None:
                    normalized["is_ymyl"] = ymyl_bool

            ymyl_block = payload.get("yMYL_classification") or payload.get(
                "ymyl_classification"
            )
            if isinstance(ymyl_block, dict):
                if "is_ymyl" not in normalized:
                    ymyl_bool = _to_bool(
                        ymyl_block.get("is_ymyl")
                        or ymyl_block.get("status")
                        or ymyl_block.get("label")
                    )
                    if ymyl_bool is not None:
                        normalized["is_ymyl"] = ymyl_bool
                if "ymyl_confidence_score" not in normalized:
                    score = (
                        ymyl_block.get("confidence")
                        or ymyl_block.get("confidence_score")
                        or ymyl_block.get("score")
                    )
                    try:
                        if score is not None:
                            normalized["ymyl_confidence_score"] = float(score)
                    except Exception:  # nosec B110
                        pass
            elif ymyl_block is not None and "is_ymyl" not in normalized:
                ymyl_bool = _to_bool(ymyl_block)
                if ymyl_bool is not None:
                    normalized["is_ymyl"] = ymyl_bool

            if not normalized.get("market") and payload.get("market_country"):
                normalized["market"] = payload.get("market_country")

            if not normalized.get("subcategory") and payload.get("subindustry"):
                normalized["subcategory"] = payload.get("subindustry")

            if not normalized.get("strategic_insights") and payload.get(
                "actionable_insights"
            ):
                normalized["strategic_insights"] = payload.get("actionable_insights")

            if not normalized.get("category") and payload.get("industry_context"):
                normalized["category"] = payload.get("industry_context")

            if not normalized.get("queries_to_run"):
                # Heurística: busca listas con "query" o "search" en el nombre.
                for key, value in payload.items():
                    if not isinstance(value, list):
                        continue
                    key_lower = str(key).lower()
                    if "query" in key_lower or "search" in key_lower:
                        normalized["queries_to_run"] = value
                        break

            if not normalized.get("queries_to_run"):
                # Heurística: intenta dentro de bloques conocidos
                for key in [
                    "competitive_intelligence",
                    "strategic_insights",
                    "analysis",
                ]:
                    block = payload.get(key)
                    if not isinstance(block, dict):
                        continue
                    for subkey, subval in block.items():
                        if not isinstance(subval, list):
                            continue
                        subkey_lower = str(subkey).lower()
                        if "query" in subkey_lower or "search" in subkey_lower:
                            normalized["queries_to_run"] = subval
                            break
                    if normalized.get("queries_to_run"):
                        break

            return normalized

        def _is_candidate(payload: Any) -> bool:
            if not isinstance(payload, dict):
                return False
            return any(k in payload for k in required_keys.union(alias_keys))

        normalized_root = _normalize_payload(agent_json)
        if _is_candidate(normalized_root):
            return normalized_root

        for key in ["data", "result", "output", "analysis", "payload", "response"]:
            value = agent_json.get(key)
            normalized_value = _normalize_payload(value)
            if _is_candidate(normalized_value):
                return normalized_value

        dict_values = [v for v in agent_json.values() if isinstance(v, dict)]
        if len(dict_values) == 1:
            normalized_single = _normalize_payload(dict_values[0])
            if normalized_single:
                return normalized_single

        return normalized_root or agent_json

    @staticmethod
    def _is_unknown_category(category_value: Optional[str]) -> bool:
        if category_value is None:
            return True
        raw = str(category_value).strip().lower()
        if not raw:
            return True
        return raw in {
            "unknown",
            "unknown category",
            "n/a",
            "none",
            "unspecified",
            "other",
        }

    @staticmethod
    def _build_agent_retry_input(
        target_audit: Dict[str, Any],
        market_hint: Optional[str],
        language_hint: Optional[str],
    ) -> Dict[str, Any]:
        if not isinstance(target_audit, dict):
            return {"market": market_hint, "language": language_hint}

        url_value = target_audit.get("url", "")
        domain_value = target_audit.get("domain") or urlparse(url_value).netloc.replace(
            "www.", ""
        )
        content_block = (
            target_audit.get("content", {})
            if isinstance(target_audit.get("content"), dict)
            else {}
        )
        structure_block = (
            target_audit.get("structure", {})
            if isinstance(target_audit.get("structure"), dict)
            else {}
        )
        schema_block = (
            target_audit.get("schema", {})
            if isinstance(target_audit.get("schema"), dict)
            else {}
        )
        h1_block = (
            structure_block.get("h1_check", {})
            if isinstance(structure_block.get("h1_check"), dict)
            else {}
        )
        h1_details = (
            h1_block.get("details", {})
            if isinstance(h1_block.get("details"), dict)
            else {}
        )
        h1_example = h1_details.get("example", "")

        retry_input = {
            "url": url_value,
            "domain": domain_value,
            "market": market_hint or target_audit.get("market"),
            "language": language_hint or target_audit.get("language"),
            "title": content_block.get("title", ""),
            "meta_description": content_block.get("meta_description")
            or content_block.get("description", ""),
            "h1_example": h1_example,
            "text_sample": content_block.get("text_sample", ""),
            "schema_types": schema_block.get("schema_types")
            or schema_block.get("types")
            or [],
        }

        return PipelineService._truncate_long_strings(retry_input, 800)

    @staticmethod
    def _needs_agent_retry(
        category_value: Optional[str],
        raw_queries: List[Dict[str, str]],
        pruned_queries: List[Dict[str, str]],
    ) -> bool:
        if PipelineService._is_unknown_category(category_value):
            return True
        if not raw_queries:
            return True
        if raw_queries and not pruned_queries:
            return True
        if pruned_queries and len(pruned_queries) < 2:
            return True
        return False

    async def _retry_external_intelligence(
        self,
        target_audit: Dict[str, Any],
        market_hint: Optional[str],
        language_hint: Optional[str],
        system_prompt: str,
        llm_function: callable,
        timeout_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        retry_input = self._build_agent_retry_input(
            target_audit, market_hint, language_hint
        )
        retry_system_prompt = (
            system_prompt
            + "\n\nRETRY RULES: The previous output was invalid or missing required fields."
            " Return ONLY valid JSON matching the schema, including 2-5 queries in the site's language."
            " Avoid 'alternative(s)' and avoid generic 'tienda online' without category context."
        )
        retry_user_prompt = (
            "RETRY: Return ONLY valid JSON matching the schema keys.\n"
            "Required keys: is_ymyl, ymyl_confidence_score, business_type, business_model, "
            "category, subcategory, market, market_maturity, queries_to_run, strategic_insights.\n"
            "Ensure queries_to_run has 2-5 items with query + purpose, includes the market, "
            "and uses category + market phrasing (e.g., 'online {core_business} {market}').\n"
            "Avoid policy/support terms and avoid 'alternatives'.\n\n"
            f"Signals:\n```json\n{json.dumps(retry_input, ensure_ascii=True)}\n```"
        )
        try:
            retry_call = llm_function(
                system_prompt=retry_system_prompt, user_prompt=retry_user_prompt
            )
            if timeout_seconds is not None and timeout_seconds > 0:
                retry_text = await asyncio.wait_for(retry_call, timeout=timeout_seconds)
            else:
                retry_text = await retry_call
            logger.info(
                f"Respuesta recibida del Agente 1 (retry). Tamaño: {len(retry_text)} caracteres."
            )
            retry_json = self.parse_agent_json_or_raw(retry_text)
            return self._extract_agent_payload(retry_json)
        except Exception as retry_err:
            logger.warning(f"Retry Agente 1 falló: {retry_err}")
            return {}

    @staticmethod
    def _normalize_queries(raw_queries: Any) -> List[Dict[str, str]]:
        """Normaliza queries en formato [{id, query, purpose}]"""
        queries: List[Dict[str, str]] = []

        def add_query(query_text: str, idx: int, purpose: str = "Competitor discovery"):
            qt = (query_text or "").strip()
            if not qt:
                return
            queries.append(
                {
                    "id": f"q{idx}",
                    "query": qt,
                    "purpose": purpose,
                }
            )

        if isinstance(raw_queries, list):
            for idx, item in enumerate(raw_queries, start=1):
                if isinstance(item, dict):
                    query_text = item.get("query") or item.get("text") or item.get("q")
                    purpose = item.get("purpose") or "Competitor discovery"
                    if query_text:
                        queries.append(
                            {
                                "id": item.get("id", f"q{idx}"),
                                "query": str(query_text).strip(),
                                "purpose": purpose,
                            }
                        )
                elif isinstance(item, str):
                    add_query(item, idx)
        elif isinstance(raw_queries, str):
            # Split por líneas o comas
            parts = [p.strip() for p in re.split(r"[\n,]+", raw_queries) if p.strip()]
            for idx, part in enumerate(parts, start=1):
                add_query(part, idx)

        return queries

    @staticmethod
    def _prune_competitor_queries(
        queries: List[Dict[str, str]],
        target_audit: Dict[str, Any],
        llm_category: Optional[str] = None,
        llm_subcategory: Optional[str] = None,
        market_hint: Optional[str] = None,
        core_profile: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, str]]:
        """
        Filtra queries irrelevantes (alternativas, demasiado genéricas, no retail).

        Args:
            queries: Lista de queries del LLM
            target_audit: Datos de auditoría del sitio
            llm_category: Categoría detectada por el LLM
            llm_subcategory: Subcategoría detectada por el LLM
            market_hint: Mercado objetivo

        Returns:
            Lista de queries filtradas o fallback queries si ninguna es válida
        """
        if not queries:
            logger.debug("_prune_competitor_queries: No se recibieron queries del LLM")
            return []
        if not isinstance(target_audit, dict):
            logger.debug("_prune_competitor_queries: target_audit no es un diccionario")
            return queries

        url = target_audit.get("url", "")
        domain = urlparse(url).netloc.replace("www.", "") if url else ""
        brand_hint = (
            PipelineService._extract_brand_from_domain(domain) if domain else ""
        )

        content_block = (
            target_audit.get("content", {})
            if isinstance(target_audit.get("content"), dict)
            else {}
        )
        structure_block = (
            target_audit.get("structure", {})
            if isinstance(target_audit.get("structure"), dict)
            else {}
        )
        h1_block = (
            structure_block.get("h1_check", {})
            if isinstance(structure_block.get("h1_check"), dict)
            else {}
        )
        h1_details = (
            h1_block.get("details", {})
            if isinstance(h1_block.get("details"), dict)
            else {}
        )
        h1_example = h1_details.get("example", "")
        title = content_block.get("title", "")
        meta_description = content_block.get("meta_description") or content_block.get(
            "description", ""
        )
        text_sample = content_block.get("text_sample", "")

        language = target_audit.get("language", "")
        is_spanish = str(language).lower().startswith("es")

        market_tokens: List[str] = []
        if market_hint:
            market_lower = str(market_hint).strip().lower()
            if market_lower:
                market_tokens.append(market_lower)
                market_tokens.extend(
                    [
                        token
                        for token in re.findall(r"\b\w{3,}\b", market_lower)
                        if token
                    ]
                )

        text_for_industry = " ".join(
            str(v)
            for v in [
                title,
                meta_description,
                h1_example,
                text_sample,
                brand_hint,
                domain,
            ]
            if v
        )
        industry_terms = PipelineService._detect_industry_terms(
            text_for_industry, is_spanish=is_spanish
        )

        # Construir tokens de industria desde el sitio auditado
        industry_tokens = set()
        for term in industry_terms:
            for token in re.split(r"\W+", term.lower()):
                if token and len(token) > 2:  # Ignorar tokens muy cortos
                    industry_tokens.add(token)

        dynamic_core = PipelineService._extract_core_terms(
            text_for_industry, brand_hint=brand_hint
        )
        for token in re.split(r"\W+", (dynamic_core or "").lower()):
            if token and len(token) > 2:
                industry_tokens.add(token)

        # Añadir tokens desde la categoría del LLM (tokens individuales y bigramas)
        llm_category_tokens = set()
        if llm_category:
            cat_lower = llm_category.lower()
            # Limpiar y separar por espacios y símbolos
            words = re.findall(r"\b\w+\b", cat_lower)
            for word in words:
                if len(word) > 2:
                    llm_category_tokens.add(word)
            # Bigramas (pares de palabras consecutivas)
            for i in range(len(words) - 1):
                bigram = f"{words[i]} {words[i + 1]}"
                llm_category_tokens.add(bigram)
            # Trigramas (triplets) para categorías largas
            for i in range(len(words) - 2):
                trigram = f"{words[i]} {words[i + 1]} {words[i + 2]}"
                llm_category_tokens.add(trigram)

        if llm_subcategory:
            sub_words = re.findall(r"\b\w+\b", llm_subcategory.lower())
            for word in sub_words:
                if len(word) > 2:
                    llm_category_tokens.add(word)

        # Combinar todos los tokens
        all_valid_tokens = industry_tokens.union(llm_category_tokens)

        def _token_looks_like_category(token: str) -> bool:
            token_root = token.lower().rstrip("s")
            for candidate in all_valid_tokens:
                cand = str(candidate).lower().strip()
                if not cand:
                    continue
                for cand_part in re.findall(r"\b\w+\b", cand):
                    cand_root = cand_part.rstrip("s")
                    if not cand_root:
                        continue
                    if token_root == cand_root:
                        return True
                    if token_root in cand_root or cand_root in token_root:
                        return True
            return False

        brand_tokens = {
            token
            for token in re.findall(r"\b\w+\b", (brand_hint or "").lower())
            if len(token) > 2
        }
        profile_core_terms = {
            PipelineService._normalize_token_root(term)
            for term in (core_profile or {}).get("core_terms", [])
            if term
        }
        profile_outlier_terms = {
            PipelineService._normalize_token_root(term)
            for term in (core_profile or {}).get("outlier_terms", [])
            if term
        }
        profile_core_terms = {term for term in profile_core_terms if term}
        profile_outlier_terms = {term for term in profile_outlier_terms if term}

        def _query_token_roots(text: str) -> set:
            return {
                PipelineService._normalize_token_root(token)
                for token in re.findall(r"[a-z0-9áéíóúñ]{2,}", str(text or "").lower())
                if token
            }

        # Avoid rejecting generic category words that happen to match the domain token
        # (e.g., robot.com -> "robot" is both brand token and industry term).
        brand_tokens_for_block = {
            token
            for token in brand_tokens
            if token not in industry_tokens
            and token not in llm_category_tokens
            and not _token_looks_like_category(token)
        }

        logger.debug(
            f"_prune_competitor_queries: Industry tokens={len(industry_tokens)}, "
            f"LLM category tokens={len(llm_category_tokens)}, "
            f"Brand hint={brand_hint}"
        )

        blocked_words = ["alternativa", "alternativas", "alternative", "alternatives"]
        blocked_phrases = [
            "tienda online competidores",
            "online store competitors",
            "tienda online competitor",
            "online store competitor",
        ]
        competitor_markers = [
            "competidor",
            "competidores",
            "competitor",
            "competitors",
            "vs",
            "versus",
            "comparar",
            "compare",
            "comparativa",
            "comparison",
            "similar",
            "similares",
            "rival",
            "rivales",
            "competencia",
        ]
        commerce_query_terms = [
            "online",
            "tienda",
            "store",
            "ecommerce",
            "e-commerce",
            "shop",
            "comprar",
            "venta",
            "retail",
            "mejores",
            "top",
            "best",
            "pricing",
            "price",
            "plans",
            "plan",
            "subscription",
            "subscriptions",
            "subscript",
            "leasing",
            "lease",
            "raas",
            "service",
            "services",
            "solutions",
            "platform",
            "product",
            "products",
            "bootcamp",
            "bootcamps",
            "curso",
            "cursos",
            "course",
            "courses",
            "training",
            "program",
            "programa",
            "academy",
            "academia",
        ]
        generic_market_terms = {
            "argentina",
            "buenos aires",
            "latam",
            "latin america",
            "mexico",
            "chile",
            "colombia",
            "peru",
            "uruguay",
            "paraguay",
            "bolivia",
            "ecuador",
            "brazil",
            "brasil",
            "spain",
            "españa",
            "united states",
            "usa",
            "canada",
            "europe",
        }
        non_competitor_terms = [
            "politicas",
            "políticas",
            "politica",
            "policy",
            "policies",
            "reclamos",
            "trabajo",
            "empleo",
            "sucursales",
            "horarios",
            "ubicacion",
            "ubicación",
            "direccion",
            "dirección",
            "telefono",
            "teléfono",
            "diferencias",
            "difference",
            "differences",
        ]

        # Strict by default to preserve category/subcategory relevance in competitor discovery.
        # Can be relaxed via AGENT1_RELAXED_QUERY_FILTER=true for debugging.
        relaxed_mode = bool(settings.AGENT1_RELAXED_QUERY_FILTER)

        filtered: List[Dict[str, str]] = []
        rejected_reasons = []

        for idx, q in enumerate(queries):
            qtext = (q.get("query") or "").strip()
            if not qtext:
                rejected_reasons.append(f"Query {idx}: vacía")
                continue
            ql = qtext.lower()
            query_tokens = set(re.findall(r"\b\w+\b", ql))
            query_token_roots = _query_token_roots(ql)

            has_blocking_brand = bool(
                brand_tokens_for_block
                and any(token in query_tokens for token in brand_tokens_for_block)
            )
            if not relaxed_mode and has_blocking_brand:
                rejected_reasons.append(f"Query {idx}: contiene marca - '{qtext[:50]}'")
                continue

            # Rechazar queries con palabras bloqueadas
            if any(bad in ql for bad in blocked_words):
                rejected_reasons.append(
                    f"Query {idx}: contiene palabra bloqueada - '{qtext[:50]}'"
                )
                continue
            if any(phrase in ql for phrase in blocked_phrases):
                rejected_reasons.append(
                    f"Query {idx}: contiene frase bloqueada - '{qtext[:50]}'"
                )
                continue
            if any(term in ql for term in non_competitor_terms):
                rejected_reasons.append(
                    f"Query {idx}: contiene término no-competidor - '{qtext[:50]}'"
                )
                continue

            if relaxed_mode:
                filtered.append(q)
                logger.debug("Query aceptada: modo relajado (pass-through)")
                continue

            # Verificar si tiene marcadores de competidor o términos de comercio
            has_competitor_marker = any(marker in ql for marker in competitor_markers)
            has_commerce_term = any(term in ql for term in commerce_query_terms)
            has_market_hint_term = (
                any(token in ql for token in market_tokens) if market_tokens else False
            )
            has_geo_market_term = any(term in ql for term in generic_market_terms)
            has_market_term = has_market_hint_term or has_geo_market_term

            # Verificar si tiene términos de categoría (desde sitio o LLM)
            has_industry_term = any(tok in ql for tok in industry_tokens)
            has_llm_category_term = any(tok in ql for tok in llm_category_tokens)
            has_category_term = has_industry_term or has_llm_category_term
            has_profile_core_term = bool(
                profile_core_terms
                and profile_core_terms.intersection(query_token_roots)
            )
            has_profile_outlier_term = bool(
                profile_outlier_terms
                and profile_outlier_terms.intersection(query_token_roots)
            )
            uses_only_outlier = bool(
                has_profile_outlier_term and not has_profile_core_term
            )

            # Verificar si tiene marca
            has_brand = bool(
                brand_tokens and any(token in query_tokens for token in brand_tokens)
            )

            if uses_only_outlier:
                rejected_reasons.append(
                    f"Query {idx}: usa solo términos outlier - '{qtext[:60]}'"
                )
                continue

            # Verificar si la query contiene palabras clave de la categoría LLM de forma flexible
            # Busca coincidencias parciales entre palabras de la query y la categoría
            has_flexible_category_match = False
            if llm_category and not has_llm_category_term:
                cat_words = set(re.findall(r"\b\w{3,}\b", llm_category.lower()))
                query_words = set(re.findall(r"\b\w{3,}\b", ql))
                matching_words = cat_words.intersection(query_words)
                if len(matching_words) >= 1:  # Al menos 1 palabra en común
                    has_flexible_category_match = True
                    logger.debug(
                        f"Query '{qtext[:50]}': match flexible con categoría: {matching_words}"
                    )

            # Logging detallado de la decisión
            logger.debug(
                f"Query '{qtext[:60]}': brand={has_brand}, category={has_category_term} "
                f"(industry={has_industry_term}, llm={has_llm_category_term}, flexible={has_flexible_category_match}), "
                f"commerce={has_commerce_term}, competitor_marker={has_competitor_marker}"
            )

            # Validación profesional y flexible:

            # 1. Query usa categoría del LLM (exacta o flexible) + término de comercio
            if (
                has_llm_category_term or has_flexible_category_match
            ) and has_commerce_term:
                filtered.append(q)
                logger.debug("Query aceptada: categoría LLM + comercio")
                continue

            # 2. Marca + término de comercio
            if has_brand and has_commerce_term:
                filtered.append(q)
                logger.debug("Query aceptada: marca + comercio")
                continue

            # 3. Categoría + marcador de competidor
            if has_category_term and has_competitor_marker:
                filtered.append(q)
                logger.debug("Query aceptada: categoría + competidor")
                continue

            # 3.5 Categoría + mercado (query recomendada por prompt)
            if has_market_term and (has_category_term or has_flexible_category_match):
                filtered.append(q)
                logger.debug("Query aceptada: categoría + mercado")
                continue

            # 3.6 Query alineada al core real + señal de intención (sin requerir marcador rígido)
            if has_profile_core_term and (
                has_commerce_term or has_market_term or has_competitor_marker
            ):
                filtered.append(q)
                logger.debug("Query aceptada: core profile + intención")
                continue

            # 3.7 Comercio + mercado (fallback robusto para e-commerce/local intent)
            if has_commerce_term and has_market_term:
                filtered.append(q)
                logger.debug("Query aceptada: comercio + mercado")
                continue

            # 4. Tiene comercio + match flexible con categoría (fallback)
            if has_commerce_term and has_flexible_category_match:
                filtered.append(q)
                logger.debug("Query aceptada: comercio + match flexible categoría")
                continue

            # 5. Score-based: al menos 2 características positivas
            effective_category = has_category_term or has_flexible_category_match
            score = sum(
                [
                    has_brand,
                    effective_category,
                    has_commerce_term,
                    has_competitor_marker,
                    has_market_term,
                    has_profile_core_term,
                ]
            )
            if score >= 2 and not uses_only_outlier:
                filtered.append(q)
                logger.debug(f"Query aceptada: score-based ({score}/6)")
                continue

            # Query rechazada - loggear razón detallada
            rejection_reason = (
                f"Query {idx} rechazada: '{qtext[:60]}' - "
                f"brand={has_brand}, category_exact={has_llm_category_term}, "
                f"category_flexible={has_flexible_category_match}, "
                f"commerce={has_commerce_term}, competitor={has_competitor_marker}, "
                f"score={score}"
            )
            rejected_reasons.append(rejection_reason)
            logger.debug(rejection_reason)

        # Log detallado si no hay queries válidas
        if not filtered:
            logger.error(
                f"[AGENTE 1 FALLÓ] Ninguna query válida después del filtrado. "
                f"Total queries recibidas: {len(queries)}. "
                f"Categoría LLM: '{llm_category}', Subcategoría: '{llm_subcategory}', "
                f"Mercado: '{market_hint}'"
            )
            if rejected_reasons:
                logger.error(
                    f"[AGENTE 1 FALLÓ] Razones de rechazo ({len(rejected_reasons)} total):"
                )
                for reason in rejected_reasons:
                    logger.error(f"  - {reason}")

            # Log de diagnóstico de tokens
            logger.error(
                f"[AGENTE 1 DIAGNÓSTICO] Tokens de industria detectados: {list(industry_tokens)[:10]}..."
            )
            logger.error(
                f"[AGENTE 1 DIAGNÓSTICO] Tokens de categoría LLM: {list(llm_category_tokens)[:10]}..."
            )
            logger.error(f"[AGENTE 1 DIAGNÓSTICO] Brand hint: '{brand_hint}'")
            # Mostrar palabras de categoría para debug de match flexible
            if llm_category:
                cat_words = set(re.findall(r"\b\w{3,}\b", llm_category.lower()))
                logger.error(
                    f"[AGENTE 1 DIAGNÓSTICO] Palabras de categoría LLM: {cat_words}"
                )

        if rejected_reasons:
            logger.debug(
                f"_prune_competitor_queries: {len(rejected_reasons)} queries rechazadas. "
                f"Razones: {rejected_reasons[:3]}"
            )  # Mostrar solo las primeras 3

        logger.info(
            f"_prune_competitor_queries: {len(queries)} queries recibidas, "
            f"{len(filtered)} válidas después de filtrado"
        )

        return filtered[:5] if filtered else []

    @staticmethod
    def _normalize_market_value(value: Optional[Any]) -> Optional[str]:
        if not value:
            return None
        if isinstance(value, dict):
            for key in ("country", "market", "name", "label", "country_name"):
                candidate = value.get(key)
                if candidate:
                    value = candidate
                    break
            else:
                return None
        elif isinstance(value, list):
            candidate = next(
                (item for item in value if isinstance(item, str) and item.strip()), None
            )
            if not candidate:
                return None
            value = candidate
        raw = str(value).strip().lower()
        if not raw:
            return None
        invalid_values = {
            "nuestro",
            "nuestra",
            "nuestros",
            "nuestras",
            "our",
            "my",
            "your",
            "mercado",
            "market",
            "local",
            "global",
            "no",
            "none",
            "n/a",
        }
        if raw in invalid_values:
            return None
        canonical = {
            "uy": "Uruguay",
            "uruguay": "Uruguay",
            "ar": "Argentina",
            "argentina": "Argentina",
            "cl": "Chile",
            "chile": "Chile",
            "co": "Colombia",
            "colombia": "Colombia",
            "mx": "Mexico",
            "mexico": "Mexico",
            "es": "Spain",
            "spain": "Spain",
            "us": "United States",
            "usa": "United States",
            "united states": "United States",
            "uk": "United Kingdom",
            "united kingdom": "United Kingdom",
            "br": "Brazil",
            "brazil": "Brazil",
            "pe": "Peru",
            "peru": "Peru",
            "ec": "Ecuador",
            "ecuador": "Ecuador",
            "bo": "Bolivia",
            "bolivia": "Bolivia",
            "py": "Paraguay",
            "paraguay": "Paraguay",
            "ve": "Venezuela",
            "venezuela": "Venezuela",
            "do": "Dominican Republic",
            "dominican republic": "Dominican Republic",
            "cr": "Costa Rica",
            "costa rica": "Costa Rica",
            "gt": "Guatemala",
            "guatemala": "Guatemala",
            "hn": "Honduras",
            "honduras": "Honduras",
            "ni": "Nicaragua",
            "nicaragua": "Nicaragua",
            "pa": "Panama",
            "panama": "Panama",
            "sv": "El Salvador",
            "el salvador": "El Salvador",
            "latam": "Latin America",
            "latin america": "Latin America",
            "eu": "Europe",
            "europe": "Europe",
        }
        if raw in canonical:
            normalized = canonical[raw]
            return normalized[:50].rstrip() if len(normalized) > 50 else normalized

        tokens = [t for t in re.findall(r"[a-z0-9]+", raw) if t]
        invalid_tokens = invalid_values | {"de", "del", "la", "el", "our", "market"}
        if tokens and all(token in invalid_tokens for token in tokens):
            return None

        normalized = str(value).strip()
        return normalized[:50].rstrip() if len(normalized) > 50 else normalized

    @staticmethod
    def _sanitize_context_label(
        value: Optional[str], *, fallback: Optional[str] = None
    ) -> Optional[str]:
        if value is None:
            return fallback

        text = str(value).strip()
        if not text:
            return fallback

        removable_tokens = {
            "nuestro",
            "nuestra",
            "nuestros",
            "nuestras",
            "our",
            "my",
            "your",
            "su",
            "sus",
        }

        words = re.findall(r"[A-Za-zÀ-ÿ0-9&+\-]+", text)
        filtered_words = [w for w in words if w.lower() not in removable_tokens]
        if not filtered_words:
            return fallback

        cleaned = " ".join(filtered_words).strip()
        return cleaned or fallback

    @staticmethod
    def _normalize_category_fields(
        category_value: Optional[str], subcategory_value: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Normaliza salidas del LLM cuando category/subcategory llegan en formatos mixtos.
        Ejemplo soportado:
        "primary Industrial Technology subcategory Autonomous Mobile Robots confidence 100"
        """
        raw_category = str(category_value or "").strip()
        raw_subcategory = str(subcategory_value or "").strip() or None
        if not raw_category:
            return None, raw_subcategory

        compact = re.sub(r"\s+", " ", raw_category).strip()
        category_out = compact
        sub_out = raw_subcategory

        marker_pattern = re.compile(r"\bsub[\s_-]?category\b", flags=re.IGNORECASE)
        marker_match = marker_pattern.search(compact)
        if marker_match:
            left = compact[: marker_match.start()].strip(" :-,")
            right = compact[marker_match.end() :].strip(" :-,")
            if left:
                category_out = left
            if right and not sub_out:
                sub_out = right

        category_out = re.sub(
            r"^\s*primary\s*[:\-]?\s*", "", category_out, flags=re.IGNORECASE
        ).strip(" :-,")
        category_out = re.sub(
            r"\s+confidence\s*[:\-]?\s*\d+(\.\d+)?\s*$",
            "",
            category_out,
            flags=re.IGNORECASE,
        ).strip(" :-,")

        if sub_out:
            sub_out = re.sub(
                r"\s+confidence\s*[:\-]?\s*\d+(\.\d+)?\s*$",
                "",
                sub_out,
                flags=re.IGNORECASE,
            ).strip(" :-,")
            sub_out = re.sub(
                r"^\s*confidence\s*[:\-]?\s*", "", sub_out, flags=re.IGNORECASE
            ).strip(" :-,")
            if not sub_out:
                sub_out = None

        return category_out or None, sub_out

    @staticmethod
    def _infer_category_from_site_signals(
        target_audit: Dict[str, Any],
    ) -> Tuple[str, Optional[str], str]:
        """
        Infiere categoría/subcategoría desde señales onsite cuando el LLM no resuelve.
        No inventa datos: usa términos extraídos de title/H1/meta/text_sample.
        """
        if not isinstance(target_audit, dict):
            return "Unknown Category", None, "unresolved"

        strict_terms = PipelineService._extract_core_terms_from_target(
            target_audit, max_terms=4, include_generic=False
        )
        loose_terms = PipelineService._extract_core_terms_from_target(
            target_audit, max_terms=4, include_generic=True
        )
        terms = [t for t in (strict_terms or loose_terms) if t]
        if not terms:
            return "Unknown Category", None, "unresolved"

        category = " ".join(terms[:2]).strip().title()
        if not category:
            category = terms[0].strip().title()
        subcategory = terms[2].strip().title() if len(terms) > 2 else None
        return category or "Unknown Category", subcategory, "onsite_inference"

    @staticmethod
    def _resolve_external_intel_error(exc: Exception) -> Tuple[str, str]:
        if exc is None:
            return (
                "AGENT1_UNAVAILABLE",
                "Agent 1 external intelligence is unavailable.",
            )

        chain: List[BaseException] = []
        visited_ids = set()
        cursor: Optional[BaseException] = exc
        while cursor is not None and id(cursor) not in visited_ids:
            chain.append(cursor)
            visited_ids.add(id(cursor))
            cursor = (
                cursor.__cause__ if cursor.__cause__ is not None else cursor.__context__
            )

        for item in chain:
            if isinstance(item, (asyncio.TimeoutError, TimeoutError)):
                return (
                    "AGENT1_LLM_TIMEOUT",
                    "Agent 1 timed out while waiting for provider response.",
                )

            raw = str(item or "").strip()
            lowered = raw.lower()
            if "agent1_core_query_empty" in lowered:
                return ("AGENT1_CORE_QUERY_EMPTY", raw)
            if "kimi_timeout" in lowered or "timeout" in lowered:
                return (
                    "AGENT1_LLM_TIMEOUT",
                    "Agent 1 timed out while waiting for provider response.",
                )
            if "cancelled" in lowered or "canceled" in lowered:
                return (
                    "AGENT1_LLM_TIMEOUT",
                    "Agent 1 request was cancelled before completing.",
                )
            if any(
                token in lowered
                for token in [
                    "network",
                    "connection",
                    "connect",
                    "transport",
                    "dns",
                    "socket",
                    "kimi_network_error",
                ]
            ):
                return (
                    "AGENT1_LLM_NETWORK",
                    "Agent 1 failed due to provider network transport issues.",
                )

        message = str(exc).strip() or "Agent 1 external intelligence is unavailable."
        return ("AGENT1_UNAVAILABLE", message)

    @staticmethod
    def _build_unavailable_external_intelligence(
        target_audit: Dict[str, Any],
        *,
        error_code: str,
        error_message: str,
        analysis_mode: str,
    ) -> Dict[str, Any]:
        normalized_target = target_audit if isinstance(target_audit, dict) else {}
        normalized_mode = str(analysis_mode or "full").strip().lower()
        if normalized_mode not in {"fast", "full"}:
            normalized_mode = "full"

        category_value = PipelineService._sanitize_context_label(
            normalized_target.get("category"), fallback="Unknown Category"
        )
        subcategory_value = PipelineService._sanitize_context_label(
            normalized_target.get("subcategory"), fallback=None
        )
        category_value, subcategory_value = PipelineService._normalize_category_fields(
            category_value, subcategory_value
        )
        category_value = PipelineService._sanitize_context_label(
            category_value, fallback="Unknown Category"
        )
        subcategory_value = PipelineService._sanitize_context_label(
            subcategory_value, fallback=None
        )

        category_source = "unresolved"
        if PipelineService._is_unknown_category(category_value):
            (
                inferred_category,
                inferred_subcategory,
                inference_source,
            ) = PipelineService._infer_category_from_site_signals(normalized_target)
            if inferred_category and not PipelineService._is_unknown_category(
                inferred_category
            ):
                category_value = inferred_category
                if not subcategory_value and inferred_subcategory:
                    subcategory_value = inferred_subcategory
                category_source = inference_source
        else:
            category_source = "onsite_inference"

        market_value = PipelineService._normalize_market_value(
            normalized_target.get("market")
        ) or PipelineService._infer_market_from_url(
            str(normalized_target.get("url", "")).strip()
        )

        sanitized_error_code = str(error_code or "AGENT1_UNAVAILABLE").strip()
        sanitized_error_message = (
            str(error_message or "Agent 1 external intelligence is unavailable.")
            .strip()
            .replace("\n", " ")
        )
        if len(sanitized_error_message) > 300:
            sanitized_error_message = sanitized_error_message[:300].rstrip()

        return {
            "status": "unavailable",
            "error_code": sanitized_error_code,
            "error_message": sanitized_error_message,
            "is_ymyl": False,
            "category": category_value,
            "subcategory": subcategory_value,
            "business_type": "OTHER",
            "business_model": {},
            "market_maturity": "unknown",
            "strategic_insights": {},
            "market": market_value,
            "category_source": category_source,
            "analysis_mode": normalized_mode,
            "queries_to_run": [],
            "query_source": "none",
        }

    @staticmethod
    def _generic_business_terms() -> set:
        return {
            "digital",
            "online",
            "platform",
            "service",
            "services",
            "solutions",
            "company",
            "companies",
            "empresa",
            "empresas",
            "official",
            "site",
            "website",
            "store",
            "shop",
            "product",
            "products",
            "business",
            "producto",
            "productos",
            "mas",
            "más",
            "gratis",
            "free",
            "ars",
            "usd",
            "mxn",
            "clp",
            "brl",
            "superando",
            "supera",
            "superar",
            "insight",
            "insights",
            "webinar",
            "webinars",
            "newsroom",
            "overview",
            "blog",
            "news",
            "event",
            "events",
            "research",
            "report",
            "reports",
            "que",
            "no",
            "servicio",
            "servicios",
            "consultora",
            "consultoras",
            "nuestra",
            "nuestro",
            "nuestras",
            "nuestros",
            "sobre",
            "contacto",
            "somos",
            "somo",
            "global",
        }

    @staticmethod
    def _normalize_token_root(token: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(token or "").lower())
        ascii_folded = "".join(
            ch for ch in normalized if not unicodedata.combining(ch)
        )
        raw = re.sub(r"[^a-z0-9]+", "", ascii_folded)
        if not raw:
            return ""
        if raw.endswith("es") and len(raw) > 5:
            return raw[:-2]
        if raw.endswith("s") and len(raw) > 4:
            return raw[:-1]
        return raw

    @staticmethod
    def _pluralize_spanish(token: str) -> str:
        value = str(token or "").strip().lower()
        if not value:
            return ""
        if value.endswith(("a", "e", "i", "o", "u", "á", "é", "í", "ó", "ú")):
            return f"{value}s"
        if value.endswith("z"):
            return f"{value[:-1]}ces"
        if value.endswith("s"):
            return value
        return f"{value}es"

    @staticmethod
    def _singularize_english(token: str) -> str:
        value = str(token or "").strip().lower()
        if not value:
            return ""
        if value.endswith("ies") and len(value) > 4:
            return f"{value[:-3]}y"
        if value.endswith("ses") and len(value) > 4:
            return value[:-2]
        if value.endswith("s") and len(value) > 4:
            return value[:-1]
        return value

    @staticmethod
    def _build_core_business_profile(
        target_audit: Dict[str, Any], max_terms: int = 6
    ) -> Dict[str, Any]:
        if not isinstance(target_audit, dict):
            return {
                "core_terms": [],
                "outlier_terms": [],
                "confidence": 0.0,
                "vertical_hint": "other",
                "market_terms": [],
                "source_support": {},
            }

        url = (target_audit or {}).get("url", "")
        content_block = (
            target_audit.get("content", {})
            if isinstance(target_audit.get("content"), dict)
            else {}
        )
        structure_block = (
            target_audit.get("structure", {})
            if isinstance(target_audit.get("structure"), dict)
            else {}
        )
        h1_block = (
            structure_block.get("h1_check", {})
            if isinstance(structure_block.get("h1_check"), dict)
            else {}
        )
        h1_details = (
            h1_block.get("details", {})
            if isinstance(h1_block.get("details"), dict)
            else {}
        )
        h1_example = h1_details.get("example", "")
        title = content_block.get("title", "")
        meta_description = content_block.get("meta_description") or content_block.get(
            "description", ""
        )
        nav_items = content_block.get("nav_items", [])
        nav_text = content_block.get("nav_text", "")
        text_sample = content_block.get("text_sample", "")
        category_hint = str(target_audit.get("category") or "")
        subcategory_hint = str(target_audit.get("subcategory") or "")

        page_paths = target_audit.get("audited_page_paths", [])
        if not isinstance(page_paths, list):
            page_paths = []

        domain = urlparse(url).netloc.replace("www.", "") if url else ""
        root = domain.split(".")[0] if domain else ""
        brand_tokens: set = set()
        if root:
            brand_tokens.add(root.lower())
            root_tokens = [t for t in re.findall(r"[a-z0-9]+", root.lower()) if t]
            if len(root_tokens) <= 1:
                for token in root_tokens:
                    brand_tokens.add(token)
            else:
                # Multi-token domains often include generic business words (e.g. guitar-store),
                # keep only short/id-like tokens as strict brand blockers.
                for token in root_tokens:
                    if len(token) <= 3 or any(ch.isdigit() for ch in token):
                        brand_tokens.add(token)
        brand_hint = (
            PipelineService._extract_brand_from_domain(domain) if domain else ""
        )
        if brand_hint:
            for token in re.findall(r"[a-z0-9]+", brand_hint.lower()):
                if token and (len(token) <= 3 or any(ch.isdigit() for ch in token)):
                    brand_tokens.add(token)

        nav_joined = ""
        if isinstance(nav_items, list):
            nav_joined = " ".join(str(item) for item in nav_items if item)

        path_text = " ".join(
            (urlparse(str(path)).path or str(path)).replace("/", " ")
            for path in page_paths[:50]
            if path
        )

        signals_text = " ".join(
            str(v)
            for v in [
                category_hint,
                subcategory_hint,
                h1_example,
                nav_joined,
                nav_text,
                text_sample,
            ]
            if v
        ).lower()
        ecommerce_tokens = {
            "shop",
            "store",
            "tienda",
            "ecommerce",
            "e-commerce",
            "producto",
            "productos",
            "product",
            "products",
            "buy",
            "comprar",
            "precio",
            "price",
            "stock",
            "disponible",
            "shipping",
            "envio",
            "envío",
            "delivery",
            "checkout",
            "cart",
            "sku",
        }
        services_tokens = {
            "consulting",
            "consultoria",
            "consultoría",
            "agency",
            "agencia",
            "services",
            "servicios",
            "solutions",
            "soluciones",
            "transformation",
            "transformación",
            "software",
            "development",
            "desarrollo",
        }
        software_tokens = {
            "saas",
            "platform",
            "api",
            "developer",
            "cloud",
            "app",
            "dashboard",
        }
        education_tokens = {
            "bootcamp",
            "course",
            "courses",
            "curso",
            "cursos",
            "academy",
            "training",
            "program",
            "programa",
        }

        ecommerce_score = sum(1 for token in ecommerce_tokens if token in signals_text)
        services_score = sum(1 for token in services_tokens if token in signals_text)
        software_score = sum(1 for token in software_tokens if token in signals_text)
        education_score = sum(1 for token in education_tokens if token in signals_text)

        if (
            "e-commerce" in category_hint.lower()
            or "ecommerce" in category_hint.lower()
        ):
            ecommerce_score += 3
        if "retail" in category_hint.lower():
            ecommerce_score += 2

        vertical_hint = "other"
        vertical_score = max(
            ecommerce_score, services_score, software_score, education_score
        )
        if vertical_score > 0:
            if ecommerce_score == vertical_score:
                vertical_hint = "ecommerce"
            elif services_score == vertical_score:
                vertical_hint = "services"
            elif software_score == vertical_score:
                vertical_hint = "software"
            elif education_score == vertical_score:
                vertical_hint = "education"

        sources = [
            ("category", category_hint, 4.0, True),
            ("subcategory", subcategory_hint, 4.2, True),
            ("h1", h1_example, 5.0, True),
            ("nav_items", nav_joined, 4.2, True),
            ("nav_text", nav_text, 3.8, True),
            ("text_sample", text_sample, 4.5, True),
            ("paths", path_text, 2.8, True),
            ("title", title, 1.8, False),
            ("meta", meta_description, 1.4, False),
        ]

        market_hint = PipelineService._normalize_market_value(
            target_audit.get("market")
        ) or PipelineService._infer_market_from_url(url)
        market_terms = re.findall(r"[a-z0-9]+", (market_hint or "").lower())

        stopwords = {
            "de",
            "la",
            "el",
            "los",
            "las",
            "y",
            "o",
            "a",
            "en",
            "para",
            "por",
            "con",
            "sin",
            "del",
            "un",
            "una",
            "the",
            "and",
            "or",
            "for",
            "with",
            "to",
            "in",
            "of",
            "on",
            "at",
            "from",
            "by",
            "is",
            "are",
            "your",
            "our",
            "site",
            "website",
            "official",
            "page",
            "home",
            "www",
            "about",
            "contact",
            "privacy",
            "terms",
            "news",
            "blog",
            "error",
            "errors",
            "unavailable",
            "forbidden",
            "access",
            "denied",
            "temporarily",
            "temporary",
            "stopped",
            "app",
            "apps",
            "find",
            "sound",
            "boost",
            "traffic",
            "premium",
            "collection",
            "legendary",
            "modern",
            "classic",
            "classics",
        }
        stopwords.update(PipelineService._generic_business_terms())
        stopwords.update(market_terms)

        score_by_term: Dict[str, float] = {}
        source_support: Dict[str, set] = {}
        strong_support: Dict[str, int] = {}
        weak_support: Dict[str, int] = {}
        first_pos: Dict[str, int] = {}
        cursor = 0

        def tokenize(text: str) -> List[str]:
            if not text:
                return []
            tokens: List[str] = []
            for token in re.findall(r"[a-z0-9áéíóúñ]{2,}", str(text).lower()):
                root_token = PipelineService._normalize_token_root(token)
                if not root_token or root_token in stopwords:
                    continue
                if root_token.isdigit():
                    continue
                if root_token in brand_tokens:
                    continue
                tokens.append(root_token)
            return tokens

        for source_name, text, weight, is_strong in sources:
            if not text:
                continue
            for term in tokenize(text):
                score_by_term[term] = score_by_term.get(term, 0.0) + weight
                if term not in source_support:
                    source_support[term] = set()
                source_support[term].add(source_name)
                if is_strong:
                    strong_support[term] = strong_support.get(term, 0) + 1
                else:
                    weak_support[term] = weak_support.get(term, 0) + 1
                if term not in first_pos:
                    first_pos[term] = cursor
                cursor += 1

        if not score_by_term:
            return {
                "core_terms": [],
                "outlier_terms": [],
                "confidence": 0.0,
                "vertical_hint": vertical_hint,
                "market_terms": market_terms,
                "source_support": {},
            }

        outlier_terms = sorted(
            [
                term
                for term in score_by_term
                if strong_support.get(term, 0) == 0 and weak_support.get(term, 0) > 0
            ]
        )

        ordered_terms = sorted(
            score_by_term.keys(),
            key=lambda term: (
                -(
                    score_by_term.get(term, 0.0)
                    + 0.6 * len(source_support.get(term, set()))
                ),
                first_pos.get(term, 0),
            ),
        )

        core_terms: List[str] = []
        for term in ordered_terms:
            has_strong = strong_support.get(term, 0) > 0
            sources_count = len(source_support.get(term, set()))
            if not has_strong and sources_count < 2:
                continue
            if term in outlier_terms and not has_strong:
                continue
            core_terms.append(term)
            if len(core_terms) >= max(1, max_terms):
                break

        if not core_terms:
            core_terms = [term for term in ordered_terms if term not in outlier_terms][
                : max(1, max_terms)
            ]

        confidence_numerator = sum(
            1.0
            for term in core_terms
            if strong_support.get(term, 0) > 0
            and len(source_support.get(term, set())) >= 2
        )
        confidence = min(
            1.0,
            confidence_numerator / max(1.0, float(len(core_terms))),
        )

        source_support_export = {
            term: sorted(list(source_support.get(term, set())))
            for term in core_terms[: max(1, max_terms)]
        }

        return {
            "core_terms": core_terms[: max(1, max_terms)],
            "outlier_terms": outlier_terms[: max(1, max_terms * 2)],
            "confidence": round(float(confidence), 3),
            "vertical_hint": vertical_hint,
            "market_terms": market_terms,
            "source_support": source_support_export,
        }

    @staticmethod
    def _build_primary_business_query(
        core_profile: Dict[str, Any],
        market_hint: Optional[str],
        language: Optional[str],
    ) -> Optional[str]:
        if not isinstance(core_profile, dict):
            return None

        core_terms = [
            str(term).strip().lower()
            for term in (core_profile.get("core_terms") or [])
            if str(term).strip()
        ]
        if not core_terms:
            return None

        generic_terms = PipelineService._generic_business_terms()
        intent_terms = {
            "online",
            "store",
            "shop",
            "tienda",
            "price",
            "precio",
            "shipping",
            "envio",
            "envío",
            "stock",
            "buy",
            "comprar",
            "delivery",
            "find",
            "sound",
            "premium",
            "collection",
            "handcrafted",
            "legendary",
            "modern",
            "cutting",
            "edge",
            "electric",
            "acoustic",
            "musician",
            "fender",
            "gibson",
            "commerce",
            "musical",
            "instrument",
        }
        source_support = (
            core_profile.get("source_support")
            if isinstance(core_profile.get("source_support"), dict)
            else {}
        )
        preferred_sources = {
            "text_sample",
            "nav_items",
            "nav_text",
            "subcategory",
            "category",
            "paths",
        }
        product_term = ""
        scored_candidates: List[Tuple[int, str]] = []
        for term in core_terms:
            if term in generic_terms or term in intent_terms:
                continue
            if len(term) < 3:
                continue
            support = source_support.get(term, [])
            support_score = sum(1 for src in support if src in preferred_sources)
            scored_candidates.append((support_score, term))
        if scored_candidates:
            scored_candidates.sort(key=lambda row: (-row[0], core_terms.index(row[1])))
            product_term = scored_candidates[0][1]
        if not product_term:
            return None

        vertical_hint = str(core_profile.get("vertical_hint") or "other").lower()
        market_value = (
            PipelineService._normalize_market_value(market_hint)
            or str(market_hint or "").strip()
        )
        lang = str(language or "").lower()
        is_spanish = lang.startswith("es")
        education_markers = {
            "bootcamp",
            "curso",
            "cursos",
            "course",
            "courses",
            "academy",
            "training",
            "program",
            "programa",
        }
        education_term = next(
            (term for term in core_terms if term in education_markers), ""
        )

        if vertical_hint == "ecommerce":
            if is_spanish:
                product_plural = PipelineService._pluralize_spanish(product_term)
                query = f"tienda de {product_plural} online".strip()
            else:
                singular = PipelineService._singularize_english(product_term)
                query = f"online {singular} store".strip()
        elif vertical_hint == "education":
            edu = education_term or ("bootcamp" if is_spanish else "course")
            if is_spanish:
                if product_term == edu:
                    query = f"{edu} online".strip()
                else:
                    query = f"{edu} de {product_term}".strip()
            else:
                if product_term == edu:
                    query = f"online {edu}".strip()
                else:
                    query = f"{product_term} {edu}".strip()
        else:
            if is_spanish:
                query = f"servicios de {product_term}".strip()
            else:
                query = f"{product_term} services".strip()

        if market_value:
            query = f"{query} {market_value}".strip()
        return re.sub(r"\s+", " ", query).strip()

    @staticmethod
    def _query_matches_core_profile(
        query: str, core_profile: Optional[Dict[str, Any]]
    ) -> bool:
        if not query or not isinstance(core_profile, dict):
            return False
        core_terms = {
            PipelineService._normalize_token_root(term)
            for term in (core_profile.get("core_terms") or [])
            if term
        }
        if not core_terms:
            return False
        query_terms = {
            PipelineService._normalize_token_root(term)
            for term in re.findall(r"[a-z0-9áéíóúñ]{2,}", str(query).lower())
            if term
        }
        return bool(core_terms.intersection(query_terms))

    @staticmethod
    def _query_uses_only_outlier_terms(
        query: str, core_profile: Optional[Dict[str, Any]]
    ) -> bool:
        if not query or not isinstance(core_profile, dict):
            return False
        outliers = {
            PipelineService._normalize_token_root(term)
            for term in (core_profile.get("outlier_terms") or [])
            if term
        }
        if not outliers:
            return False
        core_terms = {
            PipelineService._normalize_token_root(term)
            for term in (core_profile.get("core_terms") or [])
            if term
        }
        query_terms = {
            PipelineService._normalize_token_root(term)
            for term in re.findall(r"[a-z0-9áéíóúñ]{2,}", str(query).lower())
            if term
        }
        if not query_terms:
            return False
        if not query_terms.intersection(outliers):
            return False
        return not bool(query_terms.intersection(core_terms))

    @staticmethod
    def _recover_queries_from_core_profile(
        core_profile: Dict[str, Any],
        market_hint: Optional[str],
        language: Optional[str],
        max_queries: int = 5,
    ) -> List[Dict[str, str]]:
        primary_query = PipelineService._build_primary_business_query(
            core_profile, market_hint, language
        )
        if not primary_query:
            return []

        market_value = (
            PipelineService._normalize_market_value(market_hint)
            or str(market_hint or "").strip()
        )
        lang = str(language or "").lower()
        is_spanish = lang.startswith("es")
        vertical_hint = str(core_profile.get("vertical_hint") or "other").lower()
        core_terms = [
            str(term).strip().lower()
            for term in (core_profile.get("core_terms") or [])
            if str(term).strip()
        ]
        anchor_term = core_terms[0] if core_terms else ""
        if vertical_hint == "ecommerce":
            if is_spanish:
                product = PipelineService._pluralize_spanish(anchor_term or "productos")
                templates = [
                    f"comprar {product} online",
                    f"{product} precio",
                    f"{product} envio",
                    f"{product} stock disponible",
                    f"{product} tienda online",
                ]
            else:
                singular = PipelineService._singularize_english(
                    anchor_term or "products"
                )
                templates = [
                    f"buy {singular} online",
                    f"{singular} price",
                    f"{singular} shipping",
                    f"{singular} in stock",
                    f"{singular} online store",
                ]
        elif vertical_hint == "education":
            if is_spanish:
                templates = [
                    f"bootcamp {anchor_term}",
                    f"curso {anchor_term} online",
                    f"programa {anchor_term} precio",
                    f"bootcamp {anchor_term} argentina",
                ]
            else:
                templates = [
                    f"{anchor_term} bootcamp",
                    f"{anchor_term} online course",
                    f"{anchor_term} training program price",
                    f"best {anchor_term} bootcamp",
                ]
        else:
            if is_spanish:
                templates = [
                    f"servicios {anchor_term}",
                    f"{anchor_term} consultoria",
                    f"{anchor_term} empresas",
                ]
            else:
                templates = [
                    f"{anchor_term} services",
                    f"{anchor_term} consulting",
                    f"{anchor_term} companies",
                ]

        queries: List[Dict[str, str]] = []
        seen = set()

        def add_query(q: str, purpose: str) -> None:
            query_text = re.sub(r"\s+", " ", str(q or "").strip())
            if not query_text:
                return
            if market_value and market_value.lower() not in query_text.lower():
                query_text = f"{query_text} {market_value}".strip()
            key = query_text.lower()
            if key in seen:
                return
            seen.add(key)
            queries.append(
                {
                    "id": f"q{len(queries) + 1}",
                    "query": query_text,
                    "purpose": purpose,
                }
            )

        add_query(primary_query, "Primary core business query")
        for template in templates:
            if len(queries) >= max(2, int(max_queries)):
                break
            add_query(template, "Core competitor discovery")

        return queries[: max(1, int(max_queries))]

    @staticmethod
    def _infer_market_from_url(url: str) -> Optional[str]:
        if not url:
            return None
        hostname = urlparse(url).hostname or ""
        if not hostname:
            return None
        tld = hostname.split(".")[-1].lower()
        tld_map = {
            "uy": "Uruguay",
            "ar": "Argentina",
            "cl": "Chile",
            "co": "Colombia",
            "mx": "Mexico",
            "es": "Spain",
            "us": "United States",
            "uk": "United Kingdom",
            "br": "Brazil",
            "pe": "Peru",
            "ec": "Ecuador",
            "bo": "Bolivia",
            "py": "Paraguay",
            "ve": "Venezuela",
            "do": "Dominican Republic",
            "cr": "Costa Rica",
            "gt": "Guatemala",
            "hn": "Honduras",
            "ni": "Nicaragua",
            "pa": "Panama",
            "sv": "El Salvador",
        }
        return tld_map.get(tld)

    @staticmethod
    def _extract_brand_from_domain(domain: str) -> str:
        """Deriva un nombre de marca simple desde el dominio."""
        if not domain:
            return ""
        raw = str(domain).split(":")[0].strip().lower()
        if not raw:
            return ""
        parts = raw.split(".")
        root = parts[0] if parts else raw
        cleaned = re.sub(r"[^a-z0-9]+", " ", root, flags=re.IGNORECASE).strip()
        return cleaned.title() if cleaned else ""

    @staticmethod
    def _extract_core_terms(text: str, brand_hint: str = "", max_terms: int = 3) -> str:
        """Extrae términos clave simples desde un texto breve."""
        if not text:
            return ""
        cleaned = str(text)
        if brand_hint:
            cleaned = re.sub(re.escape(brand_hint), " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"[|/–—-]", " ", cleaned)

        stopwords = {
            "de",
            "la",
            "el",
            "los",
            "las",
            "y",
            "o",
            "a",
            "en",
            "para",
            "por",
            "con",
            "sin",
            "del",
            "un",
            "una",
            "unos",
            "unas",
            "the",
            "and",
            "or",
            "for",
            "with",
            "to",
            "in",
            "of",
            "on",
            "at",
            "from",
            "by",
            "is",
            "are",
            "your",
            "our",
            "nuestro",
            "nuestra",
            "nuestros",
            "nuestras",
            "mi",
            "mis",
            "tu",
            "tus",
            "su",
            "sus",
            "home",
            "inicio",
            "sitio",
            "web",
            "oficial",
            "official",
            "page",
            "pagina",
            "site",
            "www",
            "cuotas",
            "cuota",
            "interes",
            "interés",
            "descuento",
            "descuentos",
            "oferta",
            "ofertas",
            "gratis",
            "envio",
            "envíos",
            "shipping",
            "sale",
            "promocion",
            "promoción",
            "promo",
            "hoy",
            "ahora",
            "dia",
            "día",
            "que",
            "no",
            "insight",
            "insights",
            "webinar",
            "webinars",
            "newsroom",
            "overview",
            "evento",
            "eventos",
            "event",
            "events",
            "research",
            "report",
            "reports",
        }

        terms = []
        for word in re.split(r"\s+", cleaned.lower()):
            token = re.sub(r"[^\w]+", "", word, flags=re.UNICODE).strip("_")
            if not token or len(token) < 3:
                continue
            if token.isdigit():
                continue
            if token in stopwords:
                continue
            if token in terms:
                continue
            terms.append(token)
            if len(terms) >= max_terms:
                break
        return " ".join(terms)

    @staticmethod
    def _extract_core_terms_from_target(
        target_audit: Dict[str, Any], max_terms: int = 3, include_generic: bool = False
    ) -> List[str]:
        """Extrae términos core desde señales reales del sitio (sin brand)."""
        if not isinstance(target_audit, dict):
            return []

        core_profile = PipelineService._build_core_business_profile(
            target_audit, max_terms=max(3, int(max_terms) * 2)
        )
        profile_terms = [
            str(term).strip().lower()
            for term in (core_profile.get("core_terms") or [])
            if str(term).strip()
        ]
        if profile_terms:
            if include_generic:
                return profile_terms[: max(1, int(max_terms))]
            generic_terms = PipelineService._generic_business_terms()
            filtered = [term for term in profile_terms if term not in generic_terms]
            if filtered:
                return filtered[: max(1, int(max_terms))]
            return profile_terms[: max(1, int(max_terms))]

        url = (target_audit or {}).get("url", "")
        content_block = (
            target_audit.get("content", {})
            if isinstance(target_audit.get("content"), dict)
            else {}
        )
        content_block = (
            target_audit.get("content", {})
            if isinstance(target_audit.get("content"), dict)
            else {}
        )
        domain = urlparse(url).netloc.replace("www.", "") if url else ""
        root = domain.split(".")[0] if domain else ""
        brand_tokens = set()
        if root:
            brand_tokens.add(root.lower())
            for token in re.findall(r"[a-z0-9]+", root.lower()):
                if token:
                    brand_tokens.add(token)
        brand_hint = (
            PipelineService._extract_brand_from_domain(domain) if domain else ""
        )
        if brand_hint:
            for token in re.findall(r"[a-z0-9]+", brand_hint.lower()):
                if token:
                    brand_tokens.add(token)

        content_block = (
            target_audit.get("content", {})
            if isinstance(target_audit.get("content"), dict)
            else {}
        )
        structure_block = (
            target_audit.get("structure", {})
            if isinstance(target_audit.get("structure"), dict)
            else {}
        )
        h1_block = (
            structure_block.get("h1_check", {})
            if isinstance(structure_block.get("h1_check"), dict)
            else {}
        )
        h1_details = (
            h1_block.get("details", {})
            if isinstance(h1_block.get("details"), dict)
            else {}
        )

        title = content_block.get("title", "")
        meta_description = content_block.get("meta_description") or content_block.get(
            "description", ""
        )
        nav_text = content_block.get("nav_text", "")
        h1_example = h1_details.get("example", "")
        text_sample = content_block.get("text_sample", "")
        category_hint = target_audit.get("category", "")
        subcategory_hint = target_audit.get("subcategory", "")
        page_paths = target_audit.get("audited_page_paths", [])
        if not isinstance(page_paths, list):
            page_paths = []

        # Heurística: tratar el primer segmento del title como brand si coincide con el dominio.
        if title:
            first_segment = re.split(r"[|–—:-]", str(title))[0].strip()
            if first_segment:
                root_alpha = re.sub(r"[^a-z]+", "", root.lower())
                seg_alpha = re.sub(r"[^a-z]+", "", first_segment.lower())
                if root_alpha and seg_alpha:
                    overlap = root_alpha in seg_alpha or seg_alpha in root_alpha
                    prefix_len = min(len(root_alpha), len(seg_alpha), 6)
                    prefix_match = (
                        prefix_len >= 4
                        and root_alpha[:prefix_len] == seg_alpha[:prefix_len]
                    )
                    similarity = difflib.SequenceMatcher(
                        None, root_alpha, seg_alpha
                    ).ratio()
                    if overlap or prefix_match or similarity >= 0.75:
                        for token in re.findall(r"[a-z0-9]+", first_segment.lower()):
                            if token:
                                brand_tokens.add(token)

        def _path_segments(paths: List[str]) -> str:
            segments: List[str] = []
            for raw_path in paths[:50]:
                if not raw_path:
                    continue
                try:
                    parsed_path = urlparse(str(raw_path)).path or str(raw_path)
                except Exception:
                    parsed_path = str(raw_path)
                parts = [p for p in parsed_path.strip("/").split("/") if p]
                if not parts:
                    continue
                # Consider top-level and second-level segments only, skip product-like slugs.
                for idx, seg in enumerate(parts[:2]):
                    if not seg:
                        continue
                    next_seg = parts[idx + 1] if idx + 1 < len(parts) else ""
                    slug_hyphens = seg.count("-")
                    if next_seg.lower() in {"p", "product", "sku", "item"}:
                        continue
                    if slug_hyphens >= 3:
                        continue
                    if any(ch.isdigit() for ch in seg):
                        continue
                    if len(seg) > 32:
                        continue
                    if seg.lower() in brand_tokens:
                        continue
                    segments.append(seg)
            return " ".join(segments)

        sources = [
            ("category", category_hint, 3.5),
            ("subcategory", subcategory_hint, 3.0),
            ("title", title, 4.0),
            ("meta", meta_description, 3.0),
            ("h1", h1_example, 3.0),
            ("nav", nav_text, 3.5),
            ("paths", _path_segments(page_paths), 1.5),
            ("text", text_sample, 0.2),
        ]

        # Permitir tokens de marca cuando parecen términos de industria
        # (p. ej., "robot" en robot.com si también aparece como "robots/robotics").
        combined_text = " ".join(src[1] for src in sources if src[1])
        content_tokens_set = set(re.findall(r"[a-z0-9]+", combined_text.lower()))
        brand_allowlist = set()
        for token in brand_tokens:
            if len(token) < 4:
                continue
            if token not in content_tokens_set:
                continue
            for other in content_tokens_set:
                if other == token:
                    continue
                if other.startswith(token) or token.startswith(other):
                    brand_allowlist.add(token)
                    break

        market_hint = PipelineService._normalize_market_value(
            target_audit.get("market")
        ) or PipelineService._infer_market_from_url(url)
        market_tokens = set(re.findall(r"[a-z0-9]+", (market_hint or "").lower()))

        stopwords = {
            "de",
            "la",
            "el",
            "los",
            "las",
            "y",
            "o",
            "a",
            "en",
            "para",
            "por",
            "con",
            "sin",
            "del",
            "un",
            "una",
            "unos",
            "unas",
            "the",
            "and",
            "or",
            "for",
            "with",
            "to",
            "in",
            "of",
            "on",
            "at",
            "from",
            "by",
            "is",
            "are",
            "your",
            "our",
            "nuestro",
            "nuestra",
            "nuestros",
            "nuestras",
            "mi",
            "mis",
            "tu",
            "tus",
            "su",
            "sus",
            "home",
            "inicio",
            "sitio",
            "web",
            "oficial",
            "official",
            "page",
            "pagina",
            "site",
            "www",
            "online",
            "website",
            "blog",
            "news",
            "press",
            "about",
            "contact",
            "privacy",
            "terms",
            "help",
            "support",
            "career",
            "careers",
            "job",
            "jobs",
            "empleo",
            "trabajo",
            "vacantes",
            "competitor",
            "competitors",
            "hasta",
            "todos",
            "todas",
            "todo",
            "toda",
            "dia",
            "día",
            "dias",
            "días",
            "cada",
            "ayuda",
            "preguntas",
            "frecuentes",
            "terminos",
            "términos",
            "condiciones",
            "politicas",
            "políticas",
            "privacidad",
            "promociones",
            "ofertas",
            "sucursales",
            "institucional",
            "nosotros",
            "contacto",
            "sobre",
            "faq",
            "blog",
            "news",
            "press",
            "login",
            "signup",
            "register",
            "carrito",
            "checkout",
            "delivery",
            "envio",
            "envíos",
            "envío",
            "shipping",
            "cuota",
            "cuotas",
            "interes",
            "interés",
            "descuento",
            "descuentos",
            "marca",
            "marcas",
            "promocion",
            "promoción",
            "promo",
            "promos",
            "comprar",
            "compra",
            "comprá",
            "original",
            "originales",
            "producto",
            "productos",
            "mas",
            "más",
            "gratis",
            "free",
            "ars",
            "usd",
            "mxn",
            "clp",
            "brl",
            "superando",
            "supera",
            "superar",
            "error",
            "errors",
            "unavailable",
            "forbidden",
            "access",
            "denied",
            "temporarily",
            "temporary",
            "stopped",
            "stop",
            "app",
            "apps",
            "que",
            "no",
            "insight",
            "insights",
            "webinar",
            "webinars",
            "newsroom",
            "overview",
            "evento",
            "eventos",
            "event",
            "events",
            "research",
            "report",
            "reports",
        }
        stopwords.update(market_tokens)

        generic_terms = PipelineService._generic_business_terms()

        scores: Dict[str, float] = {}
        source_hits: Dict[str, set] = {}
        first_pos: Dict[str, int] = {}
        position = 0

        def tokenize(text: str) -> List[str]:
            if not text:
                return []
            collected = []
            for raw in re.split(r"[\s/\-_.]+", str(text).lower()):
                token = re.sub(r"[^\w]+", "", raw, flags=re.UNICODE)
                if not token:
                    continue
                if token.isdigit():
                    continue
                if len(token) < 2:
                    continue
                if token in stopwords:
                    continue
                if token in brand_tokens and token not in brand_allowlist:
                    continue
                collected.append(token)
            return collected

        for source_name, text, weight in sources:
            if not text:
                continue
            for token in tokenize(text):
                multiplier = 0.35 if token in generic_terms else 1.0
                scores[token] = scores.get(token, 0.0) + (weight * multiplier)
                if token not in source_hits:
                    source_hits[token] = set()
                source_hits[token].add(source_name)
                if token not in first_pos:
                    first_pos[token] = position
                position += 1

        if not scores:
            return []

        final_scores = {
            term: scores[term] + (0.35 * max(0, len(source_hits.get(term, [])) - 1))
            for term in scores
        }
        max_score = max(final_scores.values()) if final_scores else 0
        if max_score < 1.0:
            return []

        ordered = sorted(
            final_scores.keys(),
            key=lambda t: (-final_scores[t], first_pos.get(t, 0)),
        )
        if include_generic:
            candidate = ordered
        else:
            filtered = [t for t in ordered if t not in generic_terms]
            candidate = filtered if filtered else ordered
        top_terms = candidate[:max_terms]
        top_terms = sorted(top_terms, key=lambda t: first_pos.get(t, 0))
        return top_terms

    @staticmethod
    def _extract_anchor_terms_from_queries(
        queries: List[Any], market_hint: Optional[str]
    ) -> List[str]:
        """Extrae términos ancla desde queries del Agente 1 para validar competidores."""
        if not queries:
            return []
        generic_terms = PipelineService._generic_business_terms()
        market_tokens = set(re.findall(r"[a-z0-9]+", (market_hint or "").lower()))
        drop_tokens = {
            "usa",
            "us",
            "united",
            "states",
            "argentina",
            "mexico",
            "chile",
            "spain",
            "b2b",
            "b2c",
            "saas",
            "raas",
        }
        drop_tokens.update(generic_terms)
        drop_tokens.update(market_tokens)

        counts: Dict[str, int] = {}
        for raw in queries:
            text = raw.get("query") if isinstance(raw, dict) else str(raw)
            if not text:
                continue
            for token in re.findall(r"[a-z0-9]+", text.lower()):
                if len(token) < 3:
                    continue
                if token in drop_tokens:
                    continue
                counts[token] = counts.get(token, 0) + 1

        if not counts:
            return []
        anchors = [t for t, count in counts.items() if count >= 2]
        if not anchors:
            # Avoid weak one-off tokens that amplify false positives.
            return []
        return anchors[:6]

    @staticmethod
    def _detect_industry_terms(text: str, is_spanish: bool) -> List[str]:
        """Detecta términos de industria usando heurísticas simples."""
        if not text:
            return []
        core_terms = PipelineService._extract_core_terms(text)
        return [core_terms] if core_terms else []

    @staticmethod
    def _infer_core_competitor_query(
        target_audit: Dict[str, Any], market_hint: Optional[str]
    ) -> Optional[str]:
        if not isinstance(target_audit, dict):
            return None

        content_block = (
            target_audit.get("content", {})
            if isinstance(target_audit.get("content"), dict)
            else {}
        )
        url_value = target_audit.get("url", "")
        domain_value = (
            urlparse(url_value).netloc.replace("www.", "") if url_value else ""
        )
        brand_hint = (
            PipelineService._extract_brand_from_domain(domain_value)
            if domain_value
            else ""
        )
        structure_block = (
            target_audit.get("structure", {})
            if isinstance(target_audit.get("structure"), dict)
            else {}
        )
        h1_block = (
            structure_block.get("h1_check", {})
            if isinstance(structure_block.get("h1_check"), dict)
            else {}
        )
        h1_details = (
            h1_block.get("details", {})
            if isinstance(h1_block.get("details"), dict)
            else {}
        )
        h1_example = h1_details.get("example", "")
        title = content_block.get("title", "")
        meta_description = content_block.get("meta_description") or content_block.get(
            "description", ""
        )
        text_sample = content_block.get("text_sample", "")

        language = str(target_audit.get("language", "")).lower()
        is_spanish = language.startswith("es") or "es" in language
        market = market_hint or target_audit.get("market") or ""
        market = market.strip()

        category_hint = " ".join(
            str(v)
            for v in [
                target_audit.get("subcategory"),
                target_audit.get("category"),
                target_audit.get("business_type"),
            ]
            if v
        )
        text_for_industry = " ".join(
            str(v)
            for v in [
                title,
                meta_description,
                h1_example,
                text_sample,
                brand_hint,
                domain_value,
                category_hint,
            ]
            if v
        )
        industry_terms = PipelineService._detect_industry_terms(
            text_for_industry, is_spanish=is_spanish
        )
        [t.lower() for t in industry_terms]
        category_hint.lower()

        core_terms_list = PipelineService._extract_core_terms_from_target(
            target_audit, include_generic=True
        )
        base = " ".join(core_terms_list).strip() if core_terms_list else ""
        if not base:
            return None

        if market:
            return f"{base} {market}".strip()
        return base.strip()

    @staticmethod
    def _extract_pagespeed_fixes(
        pagespeed_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Extrae fixes a partir de oportunidades/diagnósticos de PageSpeed."""
        if not isinstance(pagespeed_data, dict):
            return []

        suggestion_map = {
            "uses_long_cache_ttl": "Configure long-lived cache headers for static assets",
            "uses_optimized_images": "Compress and optimize images (lossless/lossy)",
            "uses_responsive_images": "Serve responsive images with srcset/sizes",
            "modern_image_formats": "Serve images in WebP/AVIF",
            "offscreen_images": "Lazy-load offscreen images",
            "font_display": "Add font-display: swap to improve rendering",
            "render_blocking_resources": "Inline critical CSS and defer non-critical JS",
            "server_response_time": "Reduce server response time (TTFB) via caching/CDN",
            "redirects": "Remove unnecessary redirects",
            "uses_rel_preconnect": "Add rel=preconnect for key third-party origins",
            "uses_rel_preload": "Preload critical resources (fonts/hero images)",
            "critical_request_chains": "Reduce critical request chains",
            "network_rtt": "Improve network RTT with CDN and edge caching",
            "network_server_latency": "Reduce server latency and optimize origin",
            "lcp_lazy_loaded": "Do not lazy-load the LCP element",
            "largest_contentful_paint_element": "Optimize LCP element (size, preload, priority)",
            "layout_shift_elements": "Set image/video dimensions to reduce CLS",
            "duplicated_javascript": "Remove duplicate JS bundles",
            "legacy_javascript": "Serve modern JS bundles to modern browsers",
            "third_party_summary": "Reduce third-party scripts impact",
            "third_party_facades": "Use facades for heavy third-party scripts",
            "unused_javascript": "Remove unused JavaScript",
            "unused_css_rules": "Remove unused CSS",
            "unsized_images": "Set explicit width/height for images",
            "total_byte_weight": "Reduce total page weight",
            "long_tasks": "Reduce long main-thread tasks",
            "dom_size": "Reduce DOM size",
            "bootup_time": "Reduce JS bootup time",
        }

        fixes: List[Dict[str, Any]] = []

        def is_issue(audit: Dict[str, Any]) -> bool:
            score = audit.get("score")
            numeric = audit.get("numericValue")
            display = audit.get("displayValue", "")
            if score is None:
                return bool(numeric) or bool(display)
            return score < 0.9

        def priority_from(audit: Dict[str, Any], key: str) -> str:
            score = audit.get("score")
            if score is not None and score < 0.5:
                return "HIGH"
            if key in [
                "server_response_time",
                "render_blocking_resources",
                "largest_contentful_paint_element",
            ]:
                return "HIGH"
            return "MEDIUM"

        for strategy in ["mobile", "desktop"]:
            data = pagespeed_data.get(strategy) or {}
            opportunities = data.get("opportunities") or {}
            diagnostics = data.get("diagnostics") or {}

            for key, audit in opportunities.items():
                if not isinstance(audit, dict) or not is_issue(audit):
                    continue
                title = audit.get("title") or key.replace("_", " ").title()
                fixes.append(
                    {
                        "page_path": "ALL_PAGES",
                        "issue_code": f"PAGESPEED_{key.upper()}_{strategy.upper()}",
                        "priority": priority_from(audit, key),
                        "description": f"{title} ({strategy})",
                        "snippet": audit.get("displayValue", ""),
                        "suggestion": suggestion_map.get(
                            key, f"Address PageSpeed opportunity: {title}"
                        ),
                    }
                )

            for key, audit in diagnostics.items():
                if not isinstance(audit, dict) or not is_issue(audit):
                    continue
                title = audit.get("title") or key.replace("_", " ").title()
                fixes.append(
                    {
                        "page_path": "ALL_PAGES",
                        "issue_code": f"PAGESPEED_{key.upper()}_{strategy.upper()}",
                        "priority": "MEDIUM",
                        "description": f"{title} ({strategy})",
                        "snippet": audit.get("displayValue", ""),
                        "suggestion": suggestion_map.get(
                            key, f"Address PageSpeed diagnostic: {title}"
                        ),
                    }
                )

            # Core Web Vitals thresholds (ms or unitless)
            cwv = data.get("core_web_vitals") or {}
            lcp = cwv.get("lcp")
            cls = cwv.get("cls")
            ttfb = cwv.get("ttfb")
            if isinstance(lcp, (int, float)) and lcp > 2500:
                fixes.append(
                    {
                        "page_path": "ALL_PAGES",
                        "issue_code": f"PAGESPEED_LCP_HIGH_{strategy.upper()}",
                        "priority": "HIGH",
                        "description": f"LCP is high ({lcp} ms) on {strategy}",
                        "snippet": str(lcp),
                        "suggestion": "Optimize LCP by reducing render-blocking resources and optimizing hero media",
                    }
                )
            if isinstance(cls, (int, float)) and cls > 0.1:
                fixes.append(
                    {
                        "page_path": "ALL_PAGES",
                        "issue_code": f"PAGESPEED_CLS_HIGH_{strategy.upper()}",
                        "priority": "HIGH",
                        "description": f"CLS is high ({cls}) on {strategy}",
                        "snippet": str(cls),
                        "suggestion": "Set explicit dimensions for images/ads and avoid layout shifts",
                    }
                )
            if isinstance(ttfb, (int, float)) and ttfb > 800:
                fixes.append(
                    {
                        "page_path": "ALL_PAGES",
                        "issue_code": f"PAGESPEED_TTFB_HIGH_{strategy.upper()}",
                        "priority": "HIGH",
                        "description": f"TTFB is high ({ttfb} ms) on {strategy}",
                        "snippet": str(ttfb),
                        "suggestion": "Improve server response time using caching and CDN",
                    }
                )

        return fixes

    @staticmethod
    def _extract_product_intel_fixes(
        product_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Extrae fixes a partir de Product Intelligence (ecommerce)."""
        if not isinstance(product_data, dict):
            return []
        if not product_data.get("is_ecommerce"):
            return []

        fixes: List[Dict[str, Any]] = []

        def map_priority(value: str) -> str:
            val = (value or "").lower()
            if val in ["critical", "high"]:
                return "HIGH" if val == "high" else "CRITICAL"
            if val in ["medium", "low"]:
                return "MEDIUM" if val == "medium" else "LOW"
            return "MEDIUM"

        schema_analysis = product_data.get("schema_analysis") or {}
        for issue in schema_analysis.get("issues", []) or []:
            issue_type = str(issue.get("type", "SCHEMA_ISSUE")).upper()
            fixes.append(
                {
                    "page_path": "ALL_PAGES",
                    "issue_code": f"PRODUCT_SCHEMA_{issue_type}",
                    "priority": map_priority(issue.get("severity", "high")),
                    "description": issue.get(
                        "description", "Product schema issue detected"
                    ),
                    "snippet": issue.get("impact", ""),
                    "suggestion": "Improve Product schema completeness for LLM visibility",
                }
            )

        for rec in schema_analysis.get("recommendations", []) or []:
            fixes.append(
                {
                    "page_path": "ALL_PAGES",
                    "issue_code": f"PRODUCT_SCHEMA_{str(rec.get('field', 'RECOMMENDATION')).upper()}",
                    "priority": map_priority(rec.get("priority", "high")),
                    "description": rec.get(
                        "issue",
                        rec.get("recommendation", "Schema optimization recommended"),
                    ),
                    "snippet": rec.get("impact", ""),
                    "suggestion": rec.get(
                        "recommendation", "Improve Product schema fields"
                    ),
                }
            )

        for gap in product_data.get("content_gaps", []) or []:
            fixes.append(
                {
                    "page_path": "ALL_PAGES",
                    "issue_code": f"PRODUCT_CONTENT_{str(gap.get('type', 'GAP')).upper()}",
                    "priority": map_priority(gap.get("priority", "medium")),
                    "description": gap.get(
                        "description", "Product content gap detected"
                    ),
                    "snippet": gap.get("example", ""),
                    "suggestion": gap.get("example", "Add missing product content"),
                }
            )

        for rec in product_data.get("optimization_recommendations", []) or []:
            fixes.append(
                {
                    "page_path": "ALL_PAGES",
                    "issue_code": f"PRODUCT_OPT_{str(rec.get('category', 'RECOMMENDATION')).upper()}",
                    "priority": map_priority(rec.get("priority", "medium")),
                    "description": rec.get(
                        "action", "Product optimization recommended"
                    ),
                    "snippet": rec.get("impact", ""),
                    "suggestion": rec.get(
                        "action", "Improve product visibility for LLMs"
                    ),
                }
            )

        return fixes

    @staticmethod
    def _generate_fallback_queries(
        target_audit: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Deterministic fallback queries from core terms + market (no brand)."""
        if not isinstance(target_audit, dict):
            return []

        language = str(target_audit.get("language") or "").strip().lower() or "en"
        market_hint = PipelineService._normalize_market_value(
            (target_audit or {}).get("market")
        ) or PipelineService._infer_market_from_url((target_audit or {}).get("url", ""))
        core_profile = PipelineService._build_core_business_profile(
            target_audit, max_terms=6
        )
        recovered = PipelineService._recover_queries_from_core_profile(
            core_profile=core_profile,
            market_hint=market_hint,
            language=language,
            max_queries=5,
        )
        if recovered:
            return recovered

        url = (target_audit or {}).get("url", "")
        core_terms = PipelineService._extract_core_terms_from_target(
            target_audit, max_terms=3, include_generic=True
        )
        if not core_terms:
            return []

        market_hint = PipelineService._normalize_market_value(
            (target_audit or {}).get("market")
        ) or PipelineService._infer_market_from_url(url)

        market_suffix = f" {market_hint}" if market_hint else ""
        generic_terms = PipelineService._generic_business_terms()
        query_stopwords = {
            "our",
            "your",
            "my",
            "their",
            "nuestro",
            "nuestra",
            "nuestros",
            "nuestras",
            "mi",
            "mis",
            "tu",
            "tus",
            "su",
            "sus",
            "best",
            "top",
            "mejor",
            "mejores",
        }
        strong_terms = [
            t for t in core_terms if t not in generic_terms and t not in query_stopwords
        ]
        if not strong_terms:
            return []
        phrase_terms = strong_terms[:3]
        if len(phrase_terms) < 2:
            for term in core_terms:
                if (
                    term not in phrase_terms
                    and term not in generic_terms
                    and term not in query_stopwords
                ):
                    phrase_terms.append(term)
                    break
        if not phrase_terms:
            return []

        brand_tokens = set()
        domain = urlparse(url).netloc.replace("www.", "") if url else ""
        brand_hint = (
            PipelineService._extract_brand_from_domain(domain) if domain else ""
        )
        if brand_hint:
            for token in re.findall(r"[a-z0-9]+", brand_hint.lower()):
                if token:
                    brand_tokens.add(token)

        def _clean_phrase(raw_phrase: str) -> str:
            tokens = [
                t
                for t in re.findall(r"[a-z0-9áéíóúñ]+", str(raw_phrase).lower())
                if t
                and t not in generic_terms
                and t not in query_stopwords
                and t not in brand_tokens
            ]
            if not tokens:
                return ""
            return " ".join(tokens[:3]).strip()

        content_block = (
            target_audit.get("content", {})
            if isinstance(target_audit.get("content"), dict)
            else {}
        )
        phrases: List[str] = []
        # Prefer multi-word nav phrases when available (core business cues).
        nav_items = content_block.get("nav_items", [])
        if isinstance(nav_items, list) and nav_items:
            nav_stopwords = {
                "y",
                "and",
                "or",
                "the",
                "of",
                "de",
                "la",
                "el",
                "los",
                "las",
                "del",
                "un",
                "una",
                "para",
                "con",
                "sobre",
                "contacto",
                "contact",
                "servicio",
                "servicios",
                "service",
                "services",
                "insights",
                "blog",
                "news",
                "careers",
                "jobs",
                "login",
                "signup",
            }
            nav_phrases = []
            for item in nav_items:
                if not item:
                    continue
                tokens = [
                    t
                    for t in re.findall(r"[a-z0-9áéíóúñ]+", str(item).lower())
                    if t and t not in nav_stopwords and t not in brand_tokens
                ]
                tokens = [t for t in tokens if t not in generic_terms]
                if len(tokens) >= 2:
                    nav_phrases.append(_clean_phrase(" ".join(tokens[:3])))
                elif len(tokens) == 1:
                    nav_phrases.append(_clean_phrase(tokens[0]))
            for phrase in nav_phrases:
                if phrase and phrase not in phrases:
                    phrases.append(phrase)
        if len(phrase_terms) >= 3:
            phrases.append(_clean_phrase(" ".join(phrase_terms[:3])))
        if len(phrase_terms) >= 2:
            phrases.append(_clean_phrase(" ".join(phrase_terms[:2])))
        else:
            phrases.append(_clean_phrase(phrase_terms[0]))

        phrases = [p for p in phrases if p]
        # Keep a small diverse set of phrases.
        phrases = list(dict.fromkeys(phrases))[:3]
        if not phrases:
            return []

        queries: List[Dict[str, str]] = []
        seen = set()

        def add_query(query_text: str, purpose: str):
            qt = (query_text or "").strip()
            if not qt:
                return
            qt_lower = qt.lower()
            if brand_tokens and any(token in qt_lower for token in brand_tokens):
                return
            key = qt_lower
            if key in seen:
                return
            seen.add(key)
            queries.append(
                {"id": f"q{len(queries) + 1}", "query": qt, "purpose": purpose}
            )

        templates = [
            ("{phrase}{market}", "Core market competitors"),
            ("best {phrase}{market}", "Top competitors"),
            ("top {phrase}{market}", "Top competitors"),
            ("{phrase} companies{market}", "Core market companies"),
            ("{phrase} providers{market}", "Core market providers"),
        ]
        for template, purpose in templates:
            for phrase in phrases:
                if len(queries) >= 5:
                    break
                add_query(
                    template.format(phrase=phrase, market=market_suffix),
                    purpose,
                )
            if len(queries) >= 5:
                break

        return queries[:5]

    @staticmethod
    async def run_serper_search(
        query: str, api_key: str, num_results: int = 10
    ) -> Dict[str, Any]:
        """
        Ejecuta búsqueda en Serper y normaliza la salida al contrato interno {"items": [...] }.
        """
        if not api_key:
            logger.error(
                f"PIPELINE: SERPER_API_KEY missing. SEARCH ABORTED for: {query}"
            )
            return {"error": "SERPER_API_KEY no configurada", "items": []}

        endpoint = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
        }
        all_items: List[Dict[str, Any]] = []
        seen_links = set()
        max_pages = max(1, (num_results + 9) // 10)
        last_error: Optional[str] = None

        logger.info(
            f"PIPELINE: Serper Search iniciado. Query: '{query}' (Objetivo: {num_results} resultados en {max_pages} páginas)"
        )

        try:
            async with aiohttp.ClientSession() as session:
                for page in range(max_pages):
                    if len(all_items) >= num_results:
                        break

                    payload = {
                        "q": query,
                        "num": 10,
                        "page": page + 1,
                    }

                    logger.info(
                        f"PIPELINE: Serper Search página {page + 1}/{max_pages} (num=10)"
                    )

                    async with session.post(
                        endpoint, json=payload, headers=headers, timeout=15
                    ) as resp:
                        if resp.status != 200:
                            error_text = await resp.text()
                            last_error = (
                                f"Serper API Error {resp.status} en página {page + 1}: {error_text}"
                            )
                            logger.error(
                                f"PIPELINE: {last_error}"
                            )
                            break

                        data = await resp.json()
                        organic = data.get("organic", [])
                        if not organic:
                            logger.warning(
                                f"PIPELINE: Serper no devolvió más resultados en la página {page + 1}"
                            )
                            break

                        page_items: List[Dict[str, Any]] = []
                        for entry in organic:
                            link = str(entry.get("link", "")).strip()
                            if not link or link in seen_links:
                                continue
                            seen_links.add(link)
                            page_items.append(
                                {
                                    "title": entry.get("title", ""),
                                    "link": link,
                                    "snippet": entry.get("snippet", ""),
                                }
                            )
                            if len(all_items) + len(page_items) >= num_results:
                                break

                        if not page_items:
                            logger.warning(
                                "PIPELINE: Serper devolvió resultados duplicados o inválidos; finalizando paginación."
                            )
                            break

                        all_items.extend(page_items)
                        logger.info(
                            f"PIPELINE: Serper Search página {page + 1} obtuvo {len(page_items)} items. Total acumulado: {len(all_items)}"
                        )

            trimmed_items = all_items[:num_results]
            logger.info(
                f"PIPELINE: Serper Search completado. Total: {len(trimmed_items)} items para la query: '{query}'"
            )
            if last_error:
                return {"error": last_error, "items": trimmed_items}
            return {"items": trimmed_items}

        except Exception as e:
            logger.error(f"PIPELINE: Error fatal en Serper Search: {e}")
            return {"error": str(e), "items": all_items[:num_results]}

    @staticmethod
    async def run_google_search(
        query: str, api_key: str, cx_id: str, num_results: int = 10
    ) -> Dict[str, Any]:
        """
        Compat shim: mantiene firma histórica pero ejecuta búsqueda con Serper.
        """
        serper_key = settings.SERPER_API_KEY or api_key
        if cx_id:
            logger.debug(
                "run_google_search shim: cx_id recibido pero ignorado (migrado a Serper)."
            )
        return await PipelineService.run_serper_search(
            query=query,
            api_key=serper_key,
            num_results=num_results,
        )

    async def analyze_external_intelligence(
        self,
        target_audit: Dict[str, Any],
        llm_function: Optional[callable] = None,
        mode: str = "full",
        retry_policy: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
        """
        Ejecuta Agente 1: Análisis de Inteligencia Externa.

        Returns:
            Tupla (external_intelligence, search_queries).
        """
        external_intelligence = {}
        search_queries = []

        try:
            target_audit = self._ensure_dict(target_audit)
            normalized_mode = str(mode or "full").strip().lower()
            if normalized_mode not in {"fast", "full"}:
                normalized_mode = "full"

            retry_config = retry_policy if isinstance(retry_policy, dict) else {}

            def _to_float(value: Any, default: Optional[float]) -> Optional[float]:
                if value is None:
                    return default
                try:
                    parsed = float(value)
                    return parsed if parsed > 0 else default
                except Exception:
                    return default

            def _to_int(
                value: Any, default: int, min_value: int, max_value: int
            ) -> int:
                try:
                    parsed = int(value)
                except Exception:
                    parsed = default
                return max(min_value, min(max_value, parsed))

            llm_timeout_seconds = _to_float(
                retry_config.get("timeout_seconds"),
                (
                    settings.AGENT1_LLM_TIMEOUT_SECONDS
                    if settings.AGENT1_LLM_TIMEOUT_SECONDS
                    and settings.AGENT1_LLM_TIMEOUT_SECONDS > 0
                    else (12.0 if normalized_mode == "fast" else 25.0)
                ),
            )
            retry_timeout_seconds = _to_float(
                retry_config.get("retry_timeout_seconds"),
                8.0 if normalized_mode == "fast" else 15.0,
            )
            max_retries = _to_int(
                retry_config.get("max_retries", 1), default=1, min_value=0, max_value=3
            )
            max_queries = 3 if normalized_mode == "fast" else 5

            url_value = target_audit.get("url", "")
            domain_value = target_audit.get("domain") or urlparse(
                url_value
            ).netloc.replace("www.", "")
            market_hint = self._normalize_market_value(
                target_audit.get("market")
            ) or self._infer_market_from_url(url_value)
            language_hint = str(target_audit.get("language") or "").strip().lower()
            if not language_hint:
                sample_text = " ".join(
                    str(v or "")
                    for v in [
                        ((target_audit.get("content") or {}).get("title")),
                        ((target_audit.get("content") or {}).get("meta_description")),
                        ((target_audit.get("content") or {}).get("text_sample")),
                        (
                            (
                                (target_audit.get("structure") or {}).get(
                                    "h1_check", {}
                                )
                                or {}
                            )
                            .get("details", {})
                            .get("example")
                        ),
                    ]
                ).lower()
                language_hint = (
                    "es"
                    if re.search(
                        r"[áéíóúñ]|\b(para|con|servicios|tienda)\b", sample_text
                    )
                    else "en"
                )
            if not language_hint.startswith(("es", "en")):
                language_hint = "en"

            core_profile = self._build_core_business_profile(target_audit, max_terms=6)

            if llm_function is None:
                logger.error("LLM function is None in analyze_external_intelligence")
                raise ValueError(
                    "LLM function required for production. Cannot generate external intelligence without LLM."
                )

            # Cargar prompt desde JSON v2.0
            prompt_data = self.prompt_loader.load_prompt("external_analysis")
            system_prompt = prompt_data.get("system_prompt", "")
            user_template = prompt_data.get("user_template", "")

            agent1_input_data = {
                "target_audit": {
                    "url": url_value,
                    "domain": domain_value,
                    "market": market_hint,
                    "language": language_hint,
                    "status": target_audit.get("status"),
                    "content_type": target_audit.get("content_type"),
                    "structure": target_audit.get("structure", {}),
                    "content": target_audit.get("content", {}),
                    "eeat": target_audit.get("eeat", {}),
                    "schema": target_audit.get("schema", {}),
                    "meta_robots": target_audit.get("meta_robots", ""),
                }
            }

            agent1_context, agent1_input = self._shrink_context_to_budget(
                agent1_input_data, system_prompt
            )

            logger.info(
                f"Enviando datos al Agente 1 (KIMI). Tamaño del input: {len(agent1_input)} caracteres."
            )

            # Preparar user prompt
            user_prompt = user_template.replace("{input_data}", agent1_input)
            if normalized_mode == "fast":
                user_prompt += (
                    "\n\nFAST MODE: prioritize concise, high-signal output. "
                    "Return 2-3 strategic competitor queries only."
                )

            async def _call_agent(
                system_prompt_value: str,
                user_prompt_value: str,
                timeout_seconds: Optional[float],
            ) -> str:
                llm_call = llm_function(
                    system_prompt=system_prompt_value,
                    user_prompt=user_prompt_value,
                )
                if timeout_seconds is not None and timeout_seconds > 0:
                    return await asyncio.wait_for(llm_call, timeout=timeout_seconds)
                return await llm_call

            try:
                agent1_response_text = await _call_agent(
                    system_prompt, user_prompt, llm_timeout_seconds
                )
                logger.info(
                    f"Respuesta recibida del Agente 1. Tamaño: {len(agent1_response_text)} caracteres."
                )
                logger.debug(
                    f"Respuesta raw del Agente 1: {agent1_response_text[:500]}..."
                )
            except Exception as llm_err:
                logger.error(f"Error llamando al LLM en Agente 1: {llm_err}")
                raise RuntimeError("Agent 1 LLM call failed.") from llm_err

            # Parsear respuesta del Agente 1
            agent1_json = self.parse_agent_json_or_raw(agent1_response_text)
            payload = self._extract_agent_payload(agent1_json)
            category_source = "agent1"
            query_source = "agent1"

            logger.info(
                f"[AGENTE 1] Payload extraído exitosamente. "
                f"Keys disponibles: {list(payload.keys())}"
            )

            # Extraer queries raw del payload
            raw_queries = (
                payload.get("queries_to_run")
                or payload.get("queries")
                or payload.get("search_queries")
            )

            # Log de las queries crudas recibidas
            if raw_queries:
                logger.info(
                    f"[AGENTE 1] Queries recibidas del LLM: {len(raw_queries)} queries"
                )
                for i, q in enumerate(raw_queries[:5]):
                    query_text = q.get("query") if isinstance(q, dict) else str(q)
                    logger.info(f"[AGENTE 1] Query {i + 1}: '{query_text}'")
            else:
                logger.warning(
                    "[AGENTE 1] No se recibieron queries del LLM (queries_to_run vacío o inexistente)"
                )

            # Normalizar queries
            raw_queries_norm = self._normalize_queries(raw_queries)
            logger.info(
                f"[AGENTE 1] Queries normalizadas: {len(raw_queries_norm)} (antes: {len(raw_queries) if raw_queries else 0})"
            )

            # Extraer valores de categoría del LLM
            category_value = (
                payload.get("category")
                or payload.get("primary_category")
                or payload.get("industry")
                or payload.get("sector")
                or "Unknown Category"
            )
            category_value = self._sanitize_context_label(
                category_value, fallback="Unknown Category"
            )
            subcategory_value = (
                payload.get("subcategory")
                or payload.get("sub_category")
                or payload.get("niche")
            )
            subcategory_value = self._sanitize_context_label(
                subcategory_value, fallback=None
            )
            category_value, subcategory_value = self._normalize_category_fields(
                category_value, subcategory_value
            )
            category_value = self._sanitize_context_label(
                category_value, fallback="Unknown Category"
            )
            subcategory_value = self._sanitize_context_label(
                subcategory_value, fallback=None
            )

            # Si la categoría es desconocida, inferir desde señales del sitio (sin fabricar datos).
            if self._is_unknown_category(category_value):
                (
                    inferred_category,
                    inferred_subcategory,
                    inference_source,
                ) = self._infer_category_from_site_signals(target_audit)
                if inferred_category and not self._is_unknown_category(
                    inferred_category
                ):
                    category_value = inferred_category
                    subcategory_value = inferred_subcategory or subcategory_value
                    category_source = inference_source

            logger.info(
                f"[AGENTE 1] Categoría detectada: '{category_value}', "
                f"Subcategoría: '{subcategory_value}'"
            )

            # Filtrar queries con la nueva firma que incluye categoría del LLM
            search_queries = self._prune_competitor_queries(
                raw_queries_norm,
                target_audit,
                category_value,
                subcategory_value,
                market_hint,
                core_profile=core_profile,
            )

            # Verificar si necesitamos reintento
            needs_retry = self._needs_agent_retry(
                category_value, raw_queries_norm, search_queries
            )
            retries_done = 0
            while needs_retry and retries_done < max_retries:
                retries_done += 1
                logger.warning(
                    "[AGENTE 1] Se detectó salida incompleta. Detalles:\n"
                    f"  - Categoría: '{category_value}' (is_unknown: {self._is_unknown_category(category_value)})\n"
                    f"  - Queries raw: {len(raw_queries_norm)}\n"
                    f"  - Queries válidas después de filtrado: {len(search_queries)}\n"
                    f"Reintentando extracción de queries... ({retries_done}/{max_retries})"
                )
                retry_payload = await self._retry_external_intelligence(
                    target_audit,
                    market_hint,
                    language_hint,
                    system_prompt,
                    llm_function,
                    timeout_seconds=retry_timeout_seconds,
                )
                if retry_payload:
                    logger.info("[AGENTE 1] Retry exitoso. Reprocesando...")
                    payload = self._extract_agent_payload(retry_payload)
                    raw_queries = (
                        payload.get("queries_to_run")
                        or payload.get("queries")
                        or payload.get("search_queries")
                    )
                    raw_queries_norm = self._normalize_queries(raw_queries)

                    # Actualizar categorías del retry
                    category_value = (
                        payload.get("category")
                        or payload.get("primary_category")
                        or payload.get("industry")
                        or payload.get("sector")
                        or "Unknown Category"
                    )
                    category_value = self._sanitize_context_label(
                        category_value, fallback="Unknown Category"
                    )
                    subcategory_value = (
                        payload.get("subcategory")
                        or payload.get("sub_category")
                        or payload.get("niche")
                    )
                    subcategory_value = self._sanitize_context_label(
                        subcategory_value, fallback=None
                    )
                    category_value, subcategory_value = self._normalize_category_fields(
                        category_value, subcategory_value
                    )
                    category_value = self._sanitize_context_label(
                        category_value, fallback="Unknown Category"
                    )
                    subcategory_value = self._sanitize_context_label(
                        subcategory_value, fallback=None
                    )
                    if not self._is_unknown_category(category_value):
                        category_source = "agent1_retry"
                    query_source = "agent1_retry"

                    search_queries = self._prune_competitor_queries(
                        raw_queries_norm,
                        target_audit,
                        category_value,
                        subcategory_value,
                        market_hint,
                        core_profile=core_profile,
                    )
                    logger.info(
                        f"[AGENTE 1] Después del retry: {len(search_queries)} queries válidas"
                    )
                needs_retry = self._needs_agent_retry(
                    category_value, raw_queries_norm, search_queries
                )

            if search_queries:
                search_queries = self._prune_competitor_queries(
                    search_queries,
                    target_audit,
                    category_value,
                    subcategory_value,
                    market_hint,
                    core_profile=core_profile,
                )
            pruned_queries_snapshot = [
                item for item in search_queries if isinstance(item, dict)
            ]
            pruned_count = len(pruned_queries_snapshot)

            # Filtrado final: conservar solo queries emitidas por Agent 1 y alineadas al core profile.
            final_queries: List[Dict[str, str]] = []
            seen_queries = set()
            strict_rejection_reasons: List[str] = []

            def _append_query(query_text: str, purpose: str, query_id: str) -> None:
                normalized = re.sub(r"\s+", " ", str(query_text or "").strip())
                if not normalized:
                    return
                key = normalized.lower()
                if key in seen_queries:
                    return
                seen_queries.add(key)
                final_queries.append(
                    {
                        "id": query_id or f"q{len(final_queries) + 1}",
                        "query": normalized,
                        "purpose": purpose or "Competitor discovery",
                    }
                )

            for item in search_queries:
                if not isinstance(item, dict):
                    continue
                candidate_query = str(item.get("query", "")).strip()
                if not candidate_query:
                    continue
                if self._query_uses_only_outlier_terms(candidate_query, core_profile):
                    strict_rejection_reasons.append(
                        f"outlier_only:'{candidate_query[:80]}'"
                    )
                    continue
                if not self._query_matches_core_profile(candidate_query, core_profile):
                    strict_rejection_reasons.append(
                        f"no_core_match:'{candidate_query[:80]}'"
                    )
                    continue
                _append_query(
                    candidate_query,
                    str(item.get("purpose", "")).strip() or "Competitor discovery",
                    query_id=str(item.get("id", "")).strip(),
                )
                if len(final_queries) >= max_queries:
                    break

            strict_final_count = len(final_queries)
            bypass_used = False
            if strict_final_count == 0 and pruned_count > 0:
                bypass_used = True
                logger.warning(
                    "[AGENTE 1] Filtro final estricto vació queries válidas de _prune; "
                    f"aplicando bypass permisivo. pruned_count={pruned_count} strict_final_count={strict_final_count}"
                )
                if strict_rejection_reasons:
                    logger.warning(
                        "[AGENTE 1] Diagnóstico filtro final estricto (primeras 5): "
                        f"{strict_rejection_reasons[:5]}"
                    )
                for item in pruned_queries_snapshot:
                    _append_query(
                        str(item.get("query", "")).strip(),
                        str(item.get("purpose", "")).strip()
                        or "Competitor discovery",
                        query_id=str(item.get("id", "")).strip(),
                    )
                    if len(final_queries) >= max_queries:
                        break

            logger.info(
                "[AGENTE 1] Query filter summary. "
                f"pruned_count={pruned_count} strict_final_count={strict_final_count} "
                f"final_count={len(final_queries)} bypass_used={bypass_used}"
            )
            search_queries = final_queries[:max_queries]

            if self._is_unknown_category(category_value):
                (
                    inferred_category,
                    inferred_subcategory,
                    inference_source,
                ) = self._infer_category_from_site_signals(target_audit)
                if not self._is_unknown_category(inferred_category):
                    category_value = inferred_category
                    if not subcategory_value and inferred_subcategory:
                        subcategory_value = inferred_subcategory
                    category_source = inference_source
                    logger.info(
                        f"[AGENTE 1] Categoría inferida desde señales onsite: {category_value}"
                    )
            if self._is_unknown_category(category_value):
                category_source = "unresolved"

            # Coerciones defensivas
            is_ymyl_raw = payload.get("is_ymyl", payload.get("ymyl_status", False))
            if isinstance(is_ymyl_raw, str):
                is_ymyl = is_ymyl_raw.strip().lower() in ["true", "yes", "y", "1"]
            else:
                is_ymyl = bool(is_ymyl_raw)

            payload_subcategory = (
                payload.get("subcategory")
                or payload.get("sub_category")
                or payload.get("niche")
                or payload.get("subindustry")
            )
            payload_subcategory = self._sanitize_context_label(
                payload_subcategory, fallback=None
            )
            if payload_subcategory and not subcategory_value:
                subcategory_value = payload_subcategory
            market_value = (
                self._normalize_market_value(
                    payload.get("market") or payload.get("market_country")
                )
                or market_hint
            )

            if isinstance(target_audit, dict):
                if category_value and not target_audit.get("category"):
                    target_audit["category"] = category_value
                if subcategory_value and not target_audit.get("subcategory"):
                    target_audit["subcategory"] = subcategory_value
                if market_value and not target_audit.get("market"):
                    target_audit["market"] = market_value

            external_intelligence = {
                "is_ymyl": is_ymyl,
                "category": category_value,
                "subcategory": subcategory_value,
                "business_type": payload.get("business_type", "OTHER"),
                "business_model": payload.get("business_model", {}),
                "market_maturity": payload.get("market_maturity", "unknown"),
                "strategic_insights": payload.get("strategic_insights", {}),
                "market": market_value,
                "category_source": category_source,
                "analysis_mode": normalized_mode,
                "status": "ok",
            }

            normalized_queries: List[Dict[str, str]] = []
            for idx, item in enumerate(search_queries, start=1):
                if isinstance(item, dict):
                    query_text = str(item.get("query", "")).strip()
                    purpose = (
                        str(item.get("purpose", "")).strip() or "Competitor discovery"
                    )
                    query_id = str(item.get("id", "")).strip() or f"q{idx}"
                else:
                    query_text = str(item).strip() if isinstance(item, str) else ""
                    purpose = "Competitor discovery"
                    query_id = f"q{idx}"

                if not query_text:
                    continue
                normalized_queries.append(
                    {"id": query_id, "query": query_text, "purpose": purpose}
                )

            if normalized_queries:
                search_queries = normalized_queries[:max_queries]

            if not search_queries:
                logger.error(
                    f"[AGENTE 1 FALLÓ CRÍTICAMENTE] No se generaron queries válidas para la búsqueda de competidores.\n"
                    f"  - Dominio: {domain_value}\n"
                    f"  - Categoría detectada: '{category_value}'\n"
                    f"  - Mercado: '{market_hint}'\n"
                    f"  - Queries recibidas del LLM: {len(raw_queries) if raw_queries else 0}\n"
                    f"  - Queries normalizadas: {len(raw_queries_norm)}\n"
                    "REVISAR LOS LOGS ANTERIORES PARA VER POR QUÉ SE RECHAZARON LAS QUERIES."
                )
                raise RuntimeError(
                    "AGENT1_CORE_QUERY_EMPTY: No valid business-aligned competitor queries were generated."
                )

            external_intelligence["queries_to_run"] = search_queries
            external_intelligence["query_source"] = query_source
            if settings.AGENT1_QUERY_DIAGNOSTICS:
                external_intelligence["query_diagnostics"] = {
                    "core_terms_used": core_profile.get("core_terms", []),
                    "outlier_terms": core_profile.get("outlier_terms", []),
                    "accepted_queries": [q.get("query", "") for q in search_queries],
                }

            logger.info(
                f"Agente 1: YMYL={external_intelligence['is_ymyl']}, "
                f"Category={external_intelligence['category']}, "
                f"Queries={len(search_queries)}, "
                f"Mode={normalized_mode}"
            )

            return external_intelligence, search_queries

        except Exception:
            raise

    @staticmethod
    async def generate_competitor_audits(
        competitor_urls: List[str], audit_local_function: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Audita localmente un conjunto de URLs de competidores.

        Args:
            competitor_urls: Lista de URLs a auditar
            audit_local_function: Función para ejecutar auditoría local

        Returns:
            Lista de resúmenes de auditoría
        """
        competitor_audits: List[Dict[str, Any]] = []
        total_competitors = len(competitor_urls[:5])
        logger.info(
            f"PIPELINE: Iniciando auditoría de {total_competitors} competidores."
        )

        if not audit_local_function:
            logger.warning(
                "PIPELINE: audit_local_function no definido; omitiendo competidores."
            )
            return competitor_audits

        semaphore = asyncio.Semaphore(3)

        async def audit_one(comp_url: str, idx: int) -> Optional[Dict[str, Any]]:
            async with semaphore:
                logger.info(
                    f"PIPELINE: Auditando competidor {idx + 1}/{total_competitors}: {comp_url}"
                )
                try:
                    if inspect.iscoroutinefunction(audit_local_function):
                        res = await audit_local_function(comp_url)
                    else:
                        res = await asyncio.to_thread(audit_local_function, comp_url)

                    if isinstance(res, (tuple, list)) and len(res) > 0:
                        summary = res[0]
                    else:
                        summary = res

                    if not isinstance(summary, dict):
                        logger.warning(
                            f"PIPELINE: Resultado de auditoría para {comp_url} no es un diccionario: {type(summary)}"
                        )
                        return None

                    status = summary.get("status") if isinstance(summary, dict) else 500
                    try:
                        from app.services.audit_service import CompetitorService
                    except Exception:
                        CompetitorService = None

                    if status == 200:
                        domain = urlparse(comp_url).netloc.replace("www.", "")
                        summary.setdefault("url", comp_url)
                        summary.setdefault("domain", domain)
                        if CompetitorService is not None:
                            summary["geo_score"] = (
                                CompetitorService._calculate_geo_score(summary)
                            )
                            summary["benchmark"] = (
                                CompetitorService._format_competitor_data(
                                    summary, summary["geo_score"], comp_url
                                )
                            )
                        logger.info(
                            f"PIPELINE: Auditoría de competidor {comp_url} exitosa."
                        )
                        return summary

                    logger.warning(
                        f"PIPELINE: Auditoría de {comp_url} retornó status {status}. Se omitirá este competidor."
                    )
                    return {
                        "url": comp_url,
                        "status": status,
                        "error": f"No se pudo acceder al sitio (HTTP {status})",
                        "domain": urlparse(comp_url).netloc.replace("www.", ""),
                        "geo_score": 0.0,
                    }
                except Exception as e:
                    logger.error(
                        f"PIPELINE: Falló auditoría de competidor {comp_url}: {e}"
                    )
                    return {
                        "url": comp_url,
                        "status": 500,
                        "error": str(e),
                        "domain": urlparse(comp_url).netloc.replace("www.", ""),
                        "geo_score": 0.0,
                    }

        tasks = [
            asyncio.create_task(audit_one(url, idx))
            for idx, url in enumerate(competitor_urls[:5])
        ]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        for res in results:
            if isinstance(res, dict):
                competitor_audits.append(res)

        logger.info(
            f"PIPELINE: Auditados {len(competitor_audits)} competidores (incluyendo fallidos)."
        )
        return competitor_audits

    @staticmethod
    def calculate_scores(audit_data: Dict[str, Any]) -> Dict[str, float]:
        """Calcula puntajes numéricos de una auditoría."""
        scores = {}

        structure = audit_data.get("structure", {})
        structure_score = 0
        structure_score += (
            25 if structure.get("h1_check", {}).get("status") == "pass" else 0
        )
        structure_score += (
            25
            if len(structure.get("header_hierarchy", {}).get("issues", [])) == 0
            else 0
        )
        structure_score += (
            structure.get("semantic_html", {}).get("score_percent", 0) * 0.5
        )
        scores["structure"] = round(structure_score, 1)

        content = audit_data.get("content", {})
        content_score = 0
        content_score += max(
            0, 100 - content.get("fragment_clarity", {}).get("score", 0) * 5
        )
        content_score += content.get("conversational_tone", {}).get("score", 0) * 10
        content_score += (
            25 if content.get("question_targeting", {}).get("status") == "pass" else 0
        )
        content_score += (
            25
            if content.get("inverted_pyramid_style", {}).get("status") == "pass"
            else 0
        )
        scores["content"] = round(content_score / 2, 1)

        eeat = audit_data.get("eeat", {})
        eeat_score = 0
        eeat_score += (
            25 if eeat.get("author_presence", {}).get("status") == "pass" else 0
        )
        eeat_score += min(
            25, eeat.get("citations_and_sources", {}).get("external_links", 0) * 0.5
        )
        eeat_score += (
            25
            if len(eeat.get("content_freshness", {}).get("dates_found", [])) > 0
            else 0
        )
        trans = eeat.get("transparency_signals", {})
        eeat_score += (
            25
            * sum(
                [
                    trans.get("about", False),
                    trans.get("contact", False),
                    trans.get("privacy", False),
                ]
            )
            / 3
        )
        scores["eeat"] = round(eeat_score, 1)

        schema = audit_data.get("schema", {})
        schema_score = 0
        schema_score += (
            50 if schema.get("schema_presence", {}).get("status") == "present" else 0
        )
        schema_score += min(50, len(schema.get("schema_types", [])) * 25)
        scores["schema"] = round(schema_score, 1)

        scores["total"] = round(
            (
                scores["structure"]
                + scores["content"]
                + scores["eeat"]
                + scores["schema"]
            )
            / 4,
            1,
        )

        return scores

    @staticmethod
    async def generate_comparative_analysis(
        target_audit: Dict[str, Any], competitor_audits: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Genera análisis comparativo automático."""
        all_scores = []

        target_scores = PipelineService.calculate_scores(target_audit)
        target_url = target_audit.get("url", "Target Site")
        all_scores.append({"url": target_url, "scores": target_scores})

        for comp in competitor_audits:
            comp_scores = PipelineService.calculate_scores(comp)
            comp_url = comp.get("url", "Unknown")
            all_scores.append({"url": comp_url, "scores": comp_scores})

        sorted_scores = sorted(
            all_scores, key=lambda x: x["scores"]["total"], reverse=True
        )

        analysis = []
        for item in all_scores:
            strengths = []
            weaknesses = []
            for category, score in item["scores"].items():
                if category == "total":
                    continue
                if score >= 70:
                    strengths.append(f"{category.upper()}: {score}/100")
                elif score < 50:
                    weaknesses.append(f"{category.upper()}: {score}/100")

            analysis.append(
                {
                    "url": item["url"],
                    "scores": item["scores"],
                    "strengths": strengths,
                    "weaknesses": weaknesses,
                }
            )

        return {
            "scores": all_scores,
            "ranking": sorted_scores,
            "analysis": analysis,
            "summary": {
                "target_position": next(
                    (
                        i + 1
                        for i, x in enumerate(sorted_scores)
                        if x["url"] == target_url
                    ),
                    None,
                ),
                "total_competitors": len(competitor_audits),
                "target_score": target_scores["total"],
                "best_competitor_score": (
                    sorted_scores[0]["scores"]["total"] if sorted_scores else 0
                ),
            },
        }

    @staticmethod
    def _enrich_fix_plan_with_audit_issues(
        fix_plan: List[Dict],
        target_audit: Dict[str, Any],
        pagespeed_data: Optional[Dict[str, Any]] = None,
        product_intelligence_data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        """
        Enrich the fix_plan with specific issues extracted from target_audit data.
        """
        if not isinstance(fix_plan, list):
            fix_plan = []

        existing_items = {
            (item.get("page_path", ""), item.get("issue_code", "")) for item in fix_plan
        }
        new_items = []

        audited_page_paths = target_audit.get("audited_page_paths") or ["/"]

        def _add_issue(
            page_path: str,
            code: str,
            priority: str,
            description: str,
            suggestion: str,
            snippet: str = "",
        ):
            key = (page_path, code)
            if key in existing_items:
                return
            new_items.append(
                {
                    "page_path": page_path,
                    "issue_code": code,
                    "priority": priority,
                    "description": description,
                    "snippet": snippet,
                    "suggestion": suggestion,
                }
            )
            existing_items.add(key)

        # 1. H1 Issues
        h1_check = target_audit.get("structure", {}).get("h1_check", {})
        if h1_check.get("status") != "pass":
            pages_pass = h1_check.get("pages_pass")
            if isinstance(pages_pass, list) and pages_pass:
                missing_pages = [p for p in audited_page_paths if p not in pages_pass]
                for path in missing_pages:
                    _add_issue(
                        path,
                        "H1_MISSING",
                        "CRITICAL",
                        f"H1 missing or invalid on page {path}",
                        f"Add a unique, descriptive H1 tag to {path}",
                    )
            else:
                details = h1_check.get("details", {})
                count = details.get("count") if isinstance(details, dict) else None
                if isinstance(count, int) and count > 1:
                    _add_issue(
                        "/",
                        "H1_MULTIPLE",
                        "HIGH",
                        "Multiple H1 tags detected on the page",
                        "Ensure exactly one H1 per page",
                    )
                else:
                    _add_issue(
                        "/",
                        "H1_MISSING",
                        "CRITICAL",
                        "Home page missing H1 tag",
                        "Add <h1> tag with main page title",
                    )

        # 2. Schema Issues
        schema_presence = target_audit.get("schema", {}).get("schema_presence", {})
        if schema_presence.get("status") not in ["present", "pass"]:
            pages_with_schema = schema_presence.get("pages_with_schema")
            if isinstance(pages_with_schema, list) and pages_with_schema:
                missing_pages = [
                    p for p in audited_page_paths if p not in pages_with_schema
                ]
                for path in missing_pages:
                    _add_issue(
                        path,
                        "SCHEMA_MISSING",
                        "CRITICAL",
                        f"No JSON-LD Schema.org markup found on {path}",
                        "Implement Organization + WebSite Schema in <head>",
                    )
            else:
                _add_issue(
                    "ALL_PAGES",
                    "SCHEMA_MISSING",
                    "CRITICAL",
                    "No JSON-LD Schema.org markup found on any page",
                    "Implement Organization + WebSite Schema in <head> of all pages",
                )

        # 3. Author Issues
        author_presence = target_audit.get("eeat", {}).get("author_presence", {})
        if author_presence.get("status") != "pass":
            pages_missing = author_presence.get("pages_missing_author")
            if isinstance(pages_missing, list) and pages_missing:
                for path in pages_missing:
                    _add_issue(
                        path,
                        "AUTHOR_MISSING",
                        "HIGH",
                        f"Author information missing on {path}",
                        "Add author bio and Person Schema to content pages",
                    )
            else:
                _add_issue(
                    "ALL_PAGES",
                    "AUTHOR_MISSING",
                    "HIGH",
                    "Author information missing on all pages",
                    "Add author bio and Person Schema to content pages",
                )

        # 4. Header Hierarchy Issues
        header_hierarchy = target_audit.get("structure", {}).get("header_hierarchy", {})
        header_issues = (
            header_hierarchy.get("issues")
            or header_hierarchy.get("issue_examples")
            or []
        )
        for issue in header_issues:
            page_path = issue.get("page_path", "/")
            prev_tag = issue.get("prev_tag_html", "<h1>").strip("<>")
            current_tag = issue.get("current_tag_html", "<h3>").strip("<>")
            try:
                prev_level = int(prev_tag[1:]) if prev_tag.startswith("h") else 1
                next_level = prev_level + 1
                suggestion = f"Fix header hierarchy by adding missing H{next_level} or changing to correct level"
            except ValueError:
                suggestion = "Fix header hierarchy by adding missing header levels"

            _add_issue(
                page_path,
                "H1_HIERARCHY_SKIP",
                "HIGH",
                f"Header hierarchy skip: {prev_tag} -> {current_tag}",
                suggestion,
                snippet=f"<{current_tag}>",
            )

        # 5. Long Paragraph Issues
        fragment_clarity = target_audit.get("content", {}).get("fragment_clarity", {})
        long_paragraph_pages = fragment_clarity.get("pages_with_issues", [])
        if not long_paragraph_pages and isinstance(
            fragment_clarity.get("details"), str
        ):
            try:
                count = int(fragment_clarity["details"].split("=")[-1])
                if count > 0:
                    long_paragraph_pages = ["/"]
            except Exception:  # nosec B110
                pass
        for page_path in long_paragraph_pages:
            _add_issue(
                page_path,
                "LONG_PARAGRAPH",
                "MEDIUM",
                f"Long paragraphs found on {page_path}",
                "Break long paragraphs into shorter ones with subheadings and bullet points",
            )

        # 6. FAQ Missing
        question_targeting = target_audit.get("content", {}).get(
            "question_targeting", {}
        )
        if question_targeting.get("status") != "pass":
            pages_with_faqs = question_targeting.get("pages_with_faqs")
            if isinstance(pages_with_faqs, list) and pages_with_faqs:
                missing_pages = [
                    p for p in audited_page_paths if p not in pages_with_faqs
                ]
                for path in missing_pages:
                    _add_issue(
                        path,
                        "FAQ_MISSING",
                        "MEDIUM",
                        f"No FAQ sections found on {path}",
                        "Add FAQ sections with Schema.org FAQPage markup",
                    )
            else:
                _add_issue(
                    "ALL_PAGES",
                    "FAQ_MISSING",
                    "MEDIUM",
                    "No FAQ sections found on any page",
                    "Add FAQ sections with Schema.org FAQPage markup",
                )

        # 7. Content Freshness Issues
        pages_missing_dates = (
            target_audit.get("eeat", {})
            .get("content_freshness", {})
            .get("pages_missing_dates", [])
        )
        if isinstance(pages_missing_dates, list) and pages_missing_dates:
            for path in pages_missing_dates:
                _add_issue(
                    path,
                    "CONTENT_FRESHNESS_MISSING",
                    "MEDIUM",
                    f"Content freshness dates missing on {path}",
                    "Add publication and last modified dates to content",
                )

        # 8. Authoritative citations missing
        pages_missing_authoritative = (
            target_audit.get("eeat", {})
            .get("citations_and_sources", {})
            .get("pages_missing_authoritative_links", [])
        )
        if (
            isinstance(pages_missing_authoritative, list)
            and pages_missing_authoritative
        ):
            for path in pages_missing_authoritative:
                _add_issue(
                    path,
                    "AUTHORITATIVE_CITATIONS_MISSING",
                    "MEDIUM",
                    f"No authoritative citations found on {path}",
                    "Add references to authoritative sources (.gov, .edu, major industry bodies)",
                )
        else:
            citations = target_audit.get("eeat", {}).get("citations_and_sources", {})
            if (
                citations.get("authoritative_links", 0) == 0
                and citations.get("external_links", 0) > 0
            ):
                _add_issue(
                    "/",
                    "AUTHORITATIVE_CITATIONS_MISSING",
                    "MEDIUM",
                    "No authoritative citations found",
                    "Add references to authoritative sources (.gov, .edu, major industry bodies)",
                )

        # 9. Transparency signals missing
        transparency = target_audit.get("eeat", {}).get("transparency_signals", {})
        if isinstance(transparency, dict):
            missing = [k for k, v in transparency.items() if v is False]
            if missing:
                _add_issue(
                    "ALL_PAGES",
                    "TRANSPARENCY_SIGNALS_MISSING",
                    "MEDIUM",
                    f"Missing transparency pages: {', '.join(missing)}",
                    "Add/Link About, Contact, and Privacy pages in the global navigation/footer",
                )

        # 10. Meta robots noindex
        meta_robots = target_audit.get("meta_robots")
        if isinstance(meta_robots, list):
            if any("noindex" in str(v).lower() for v in meta_robots):
                _add_issue(
                    "ALL_PAGES",
                    "META_ROBOTS_NOINDEX",
                    "HIGH",
                    "Meta robots contains noindex on one or more pages",
                    "Remove noindex if pages should be discoverable",
                )
        elif isinstance(meta_robots, str):
            if "noindex" in meta_robots.lower():
                _add_issue(
                    "/",
                    "META_ROBOTS_NOINDEX",
                    "HIGH",
                    "Meta robots contains noindex",
                    "Remove noindex if page should be discoverable",
                )

        # 11. PageSpeed issues
        if pagespeed_data:
            for fix in PipelineService._extract_pagespeed_fixes(pagespeed_data):
                _add_issue(
                    fix.get("page_path", "ALL_PAGES"),
                    fix.get("issue_code", "PAGESPEED_ISSUE"),
                    fix.get("priority", "MEDIUM"),
                    fix.get("description", "PageSpeed opportunity detected"),
                    fix.get("suggestion", "Optimize PageSpeed opportunity"),
                    fix.get("snippet", ""),
                )

        # 12. Product/Ecommerce issues
        if product_intelligence_data:
            for fix in PipelineService._extract_product_intel_fixes(
                product_intelligence_data
            ):
                _add_issue(
                    fix.get("page_path", "ALL_PAGES"),
                    fix.get("issue_code", "PRODUCT_OPTIMIZATION"),
                    fix.get("priority", "MEDIUM"),
                    fix.get("description", "Product optimization issue detected"),
                    fix.get("suggestion", "Improve product visibility for LLMs"),
                    fix.get("snippet", ""),
                )

        enriched_fix_plan = fix_plan + new_items

        priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        enriched_fix_plan.sort(
            key=lambda x: priority_order.get(x.get("priority", "MEDIUM"), 2)
        )

        logger.info(
            f"Enriched fix_plan: {len(fix_plan)} LLM items + {len(new_items)} extracted = {len(enriched_fix_plan)} total"
        )
        return enriched_fix_plan

    @staticmethod
    def _minimize_context(context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Minimiza el contexto para evitar exceder el límite de tokens (Kimi K2 262K).
        """
        import copy

        minimized = copy.deepcopy(context)

        if "search_results" in minimized and isinstance(
            minimized["search_results"], dict
        ):
            for q_id, results in minimized["search_results"].items():
                if isinstance(results, dict) and "items" in results:
                    minimized_items = []
                    for item in results["items"][:10]:
                        minimized_items.append(
                            {
                                "title": item.get("title"),
                                "link": item.get("link"),
                                "snippet": item.get("snippet", "")[:150],
                            }
                        )
                    minimized["search_results"][q_id] = {"items": minimized_items}

        def minimize_audit(audit):
            if not isinstance(audit, dict):
                return audit
            a = audit.copy()

            for heavy_key in [
                "_individual_page_audits",
                "crawled_page_paths",
                "crawled_pages_count",
                "crawled_pages",
                "crawled_urls",
            ]:
                if heavy_key in a:
                    a.pop(heavy_key, None)

            if "audited_page_paths" in a and isinstance(a["audited_page_paths"], list):
                a["audited_page_paths"] = a["audited_page_paths"][:20]

            if "schema" in a and isinstance(a["schema"], dict):
                a["schema"] = a["schema"].copy()
                if "raw_jsonld" in a["schema"]:
                    a["schema"]["raw_jsonld"] = []
                if "raw_jsonld_found" in a["schema"]:
                    a["schema"]["raw_jsonld_found"] = []

            if "content" in a and isinstance(a["content"], dict):
                a["content"] = a["content"].copy()
                for key, limit in {
                    "text_sample": 800,
                    "meta_description": 400,
                    "title": 200,
                    "meta_keywords": 200,
                }.items():
                    value = a["content"].get(key)
                    if isinstance(value, str) and len(value) > limit:
                        a["content"][key] = value[:limit]
                question_targeting = a["content"].get("question_targeting")
                if isinstance(question_targeting, dict):
                    examples = question_targeting.get("examples")
                    if isinstance(examples, list):
                        question_targeting["examples"] = examples[:5]
                    a["content"]["question_targeting"] = question_targeting

            if "structure" in a and isinstance(a["structure"], dict):
                structure = a["structure"]
                # Trim large lists inside structure to keep prompts within context limits
                h1_check = structure.get("h1_check")
                if isinstance(h1_check, dict):
                    for key in ["pages_missing", "pages_pass", "examples"]:
                        if isinstance(h1_check.get(key), list):
                            h1_check[key] = h1_check[key][:10]
                header_hierarchy = structure.get("header_hierarchy")
                if isinstance(header_hierarchy, dict):
                    for key in ["pages_with_issues", "issue_examples", "issues"]:
                        if isinstance(header_hierarchy.get(key), list):
                            header_hierarchy[key] = header_hierarchy[key][:10]
                structure["h1_check"] = h1_check
                structure["header_hierarchy"] = header_hierarchy

                if "h1_details" in a["structure"] and isinstance(
                    a["structure"]["h1_details"], list
                ):
                    a["structure"]["h1_details"] = a["structure"]["h1_details"][:5]

            return a

        if "target_audit" in minimized:
            minimized["target_audit"] = minimize_audit(minimized["target_audit"])

        if "competitor_audits" in minimized and isinstance(
            minimized["competitor_audits"], list
        ):
            minimized["competitor_audits"] = [
                minimize_audit(a) for a in minimized["competitor_audits"]
            ]

        list_keys = [
            "keywords",
            "backlinks",
            "rank_tracking",
            "llm_visibility",
            "ai_content_suggestions",
        ]
        for key in list_keys:
            if (
                key in minimized
                and isinstance(minimized[key], dict)
                and "items" in minimized[key]
            ):
                minimized[key]["items"] = minimized[key]["items"][:20]
            elif key in minimized and isinstance(minimized[key], list):
                minimized[key] = minimized[key][:20]

        if "pagespeed" in minimized and isinstance(minimized["pagespeed"], dict):

            def _compact_audit_items(audits: Any, limit: int = 5) -> list:
                items = []
                if isinstance(audits, dict):
                    for audit_id, audit in audits.items():
                        if not isinstance(audit, dict):
                            continue
                        items.append(
                            {
                                "id": audit_id,
                                "title": audit.get("title"),
                                "score": audit.get("score"),
                                "numericValue": audit.get("numericValue"),
                                "displayValue": audit.get("displayValue"),
                            }
                        )
                elif isinstance(audits, list):
                    for audit in audits:
                        if isinstance(audit, dict):
                            items.append(
                                {
                                    "id": audit.get("id"),
                                    "title": audit.get("title"),
                                    "score": audit.get("score"),
                                    "numericValue": audit.get("numericValue"),
                                    "displayValue": audit.get("displayValue"),
                                }
                            )
                return items[:limit]

            for device in ["mobile", "desktop"]:
                if device in minimized["pagespeed"] and isinstance(
                    minimized["pagespeed"][device], dict
                ):
                    ps_data = minimized["pagespeed"][device]

                    # Keep only high-signal metrics to avoid massive payloads (screenshots/audits are huge).
                    core_web_vitals = (
                        ps_data.get("core_web_vitals")
                        if isinstance(ps_data.get("core_web_vitals"), dict)
                        else {}
                    )
                    metrics = (
                        ps_data.get("metrics")
                        if isinstance(ps_data.get("metrics"), dict)
                        else {}
                    )
                    metadata = (
                        ps_data.get("metadata")
                        if isinstance(ps_data.get("metadata"), dict)
                        else {}
                    )

                    compact = {
                        "url": ps_data.get("url"),
                        "strategy": ps_data.get("strategy", device),
                        "performance_score": ps_data.get("performance_score"),
                        "accessibility_score": ps_data.get("accessibility_score"),
                        "best_practices_score": ps_data.get("best_practices_score"),
                        "seo_score": ps_data.get("seo_score"),
                        "core_web_vitals": {
                            k: core_web_vitals.get(k)
                            for k in ["lcp", "fid", "cls", "fcp", "ttfb"]
                            if k in core_web_vitals
                        },
                        "metrics": {
                            k: metrics.get(k)
                            for k in [
                                "fcp",
                                "lcp",
                                "cls",
                                "tbt",
                                "tti",
                                "speed_index",
                                "ttfb",
                            ]
                            if k in metrics
                        },
                        "opportunities": _compact_audit_items(
                            ps_data.get("opportunities", {})
                        ),
                        "diagnostics": _compact_audit_items(
                            ps_data.get("diagnostics", {})
                        ),
                        "metadata": {
                            "fetch_time": metadata.get("fetch_time"),
                            "benchmark_index": metadata.get("benchmark_index"),
                        },
                    }

                    minimized["pagespeed"][device] = compact

                    for key in ["opportunities", "diagnostics"]:
                        if key in minimized["pagespeed"][device] and isinstance(
                            minimized["pagespeed"][device][key], dict
                        ):
                            try:
                                sorted_items = sorted(
                                    [
                                        (k, v)
                                        for k, v in minimized["pagespeed"][device][
                                            key
                                        ].items()
                                        if isinstance(v, dict)
                                    ],
                                    key=lambda x: (
                                        x[1].get("numericValue", 0)
                                        if x[1].get("numericValue") is not None
                                        else 0
                                    ),
                                    reverse=True,
                                )
                                minimized["pagespeed"][device][key] = dict(
                                    sorted_items[:5]
                                )
                            except Exception as e:
                                logger.warning(f"Error sorting {key} for {device}: {e}")
                                items = list(
                                    minimized["pagespeed"][device][key].items()
                                )[:5]
                                minimized["pagespeed"][device][key] = dict(items)

        return minimized

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        if not text:
            return 0
        return max(1, len(text) // 4)

    @staticmethod
    def _context_budget_chars(system_prompt: str) -> int:
        try:
            from app.core.config import settings

            max_context_tokens = getattr(settings, "NV_MAX_CONTEXT_TOKENS", 262144)
            safety_ratio = getattr(settings, "NV_CONTEXT_SAFETY_RATIO", 0.7)
        except Exception:
            max_context_tokens = 262144
            safety_ratio = 0.7
        system_tokens = PipelineService._estimate_tokens(system_prompt)
        budget_tokens = int(max_context_tokens * safety_ratio) - system_tokens
        if budget_tokens < 1000:
            budget_tokens = max(1000, max_context_tokens - system_tokens - 1000)
        return max(4000, int(budget_tokens * 4))

    @staticmethod
    def _truncate_long_strings(data: Any, max_len: int) -> Any:
        if isinstance(data, str):
            return data[:max_len]
        if isinstance(data, list):
            return [PipelineService._truncate_long_strings(v, max_len) for v in data]
        if isinstance(data, dict):
            return {
                k: PipelineService._truncate_long_strings(v, max_len)
                for k, v in data.items()
            }
        return data

    @staticmethod
    def _compact_audit_for_llm(audit: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(audit, dict):
            return {}
        content = audit.get("content") if isinstance(audit.get("content"), dict) else {}
        schema = audit.get("schema") if isinstance(audit.get("schema"), dict) else {}
        compact = {
            "url": audit.get("url"),
            "domain": audit.get("domain"),
            "market": audit.get("market"),
            "language": audit.get("language"),
            "status": audit.get("status"),
            "structure": audit.get("structure", {}),
            "content": {
                "title": content.get("title"),
                "meta_description": content.get("meta_description"),
                "meta_keywords": content.get("meta_keywords"),
                "text_sample": content.get("text_sample"),
            },
            "eeat": audit.get("eeat", {}),
            "schema": {
                "schema_presence": schema.get("schema_presence"),
                "schema_types": (schema.get("schema_types") or [])[:10],
            },
            "audited_pages_count": audit.get("audited_pages_count"),
            "audited_page_paths": (audit.get("audited_page_paths") or [])[:20],
        }
        return compact

    def _shrink_context_to_budget(
        self, context: Dict[str, Any], system_prompt: str
    ) -> Tuple[Dict[str, Any], str]:
        import copy

        budget_chars = self._context_budget_chars(system_prompt)
        minimized = self._minimize_context(context)

        def _strip_cycles(obj: Any, seen: Optional[set] = None) -> Any:
            if seen is None:
                seen = set()
            obj_id = id(obj)
            if obj_id in seen:
                return "<CYCLE_REF>"
            if isinstance(obj, dict):
                seen.add(obj_id)
                return {k: _strip_cycles(v, seen) for k, v in obj.items()}
            if isinstance(obj, list):
                seen.add(obj_id)
                return [_strip_cycles(v, seen) for v in obj]
            if isinstance(obj, tuple):
                seen.add(obj_id)
                return [_strip_cycles(v, seen) for v in obj]
            return obj

        def serialize(ctx: Dict[str, Any]) -> str:
            safe_ctx = _strip_cycles(ctx)
            return json.dumps(safe_ctx, ensure_ascii=False, default=str)

        def current_size(ctx: Dict[str, Any]) -> int:
            return len(serialize(ctx))

        prompt_text = serialize(minimized)
        if len(prompt_text) <= budget_chars:
            return minimized, prompt_text

        logger.warning(
            f"Context size {len(prompt_text)} chars exceeds budget {budget_chars}. Trimming."
        )

        def reduce_search(ctx: Dict[str, Any], limit: int) -> None:
            search = ctx.get("search_results")
            if not isinstance(search, dict):
                return
            for key, results in search.items():
                if isinstance(results, dict) and isinstance(results.get("items"), list):
                    results["items"] = results["items"][:limit]

        def reduce_competitors(ctx: Dict[str, Any], limit: int) -> None:
            comps = ctx.get("competitor_audits")
            if isinstance(comps, list):
                ctx["competitor_audits"] = comps[:limit]

        reducers = [
            lambda ctx: reduce_search(ctx, 5),
            lambda ctx: reduce_search(ctx, 3),
            lambda ctx: reduce_search(ctx, 1),
            lambda ctx: ctx.pop("search_results", None),
            lambda ctx: reduce_competitors(ctx, 3),
            lambda ctx: reduce_competitors(ctx, 1),
            lambda ctx: ctx.__setitem__("competitor_audits", []),
            lambda ctx: ctx.update(
                {
                    "llm_visibility": {},
                    "ai_content_suggestions": {},
                    "rank_tracking": {},
                    "keywords": {},
                    "backlinks": {},
                }
            ),
            lambda ctx: ctx.__setitem__(
                "product_intelligence", ctx.get("product_intelligence") or {}
            ),
            lambda ctx: ctx.__setitem__(
                "target_audit", self._compact_audit_for_llm(ctx.get("target_audit", {}))
            ),
            lambda ctx: ctx.update(
                {
                    "target_audit": self._truncate_long_strings(
                        ctx.get("target_audit", {}), 800
                    )
                }
            ),
            lambda ctx: ctx.update(
                {
                    "target_audit": self._truncate_long_strings(
                        ctx.get("target_audit", {}), 400
                    ),
                    "external_intelligence": self._truncate_long_strings(
                        ctx.get("external_intelligence", {}), 400
                    ),
                }
            ),
        ]

        trimmed = copy.deepcopy(minimized)
        for reducer in reducers:
            reducer(trimmed)
            prompt_text = serialize(trimmed)
            if len(prompt_text) <= budget_chars:
                logger.warning(
                    f"Context trimmed to {len(prompt_text)} chars (budget {budget_chars})."
                )
                return trimmed, prompt_text

        # Final fallback: minimal context
        minimal = {
            "target_audit": self._compact_audit_for_llm(
                trimmed.get("target_audit", {})
            ),
            "external_intelligence": trimmed.get("external_intelligence", {}),
        }
        prompt_text = serialize(minimal)
        logger.warning(
            f"Context reduced to minimal size {len(prompt_text)} chars (budget {budget_chars})."
        )
        return minimal, prompt_text

    @staticmethod
    def select_important_urls(
        all_urls: List[str], base_url: str, max_sample: int = 5
    ) -> List[str]:
        """
        Selecciona una muestra representativa de URLs para auditar.
        """
        logger.info(
            f"PIPELINE: Seleccionando hasta {max_sample} URLs importantes de un total de {len(all_urls)} encontradas."
        )

        if not all_urls:
            logger.info("PIPELINE: No se encontraron URLs, usando la base URL.")
            return [base_url]

        from urllib.parse import urlparse

        def get_path(url: str) -> str:
            try:
                return urlparse(url).path or "/"
            except Exception:
                return "/"

        def sort_urls(urls: List[str]) -> List[str]:
            return sorted(urls, key=lambda u: (len(get_path(u)), u))

        product_patterns = [
            "/product/",
            "/products/",
            "/p/",
            "/sku/",
            "/item/",
            "/buy/",
            "/pd/",
        ]
        category_patterns = [
            "/category/",
            "/categories/",
            "/c/",
            "/collection/",
            "/collections/",
            "/shop/",
            "/store/",
            "/department/",
        ]
        faq_patterns = ["/faq", "/preguntas", "/ayuda", "/help", "/soporte"]
        info_patterns = [
            "/about",
            "/nosotros",
            "/contact",
            "/contacto",
            "/envio",
            "/envíos",
            "/shipping",
            "/returns",
            "/devoluciones",
        ]

        home_urls = []
        product_urls = []
        category_urls = []
        faq_urls = []
        info_urls = []
        other_urls = []

        for u in all_urls:
            path = get_path(u).lower()
            if path in ["/", "", "/index.html"]:
                home_urls.append(u)
            elif any(p in path for p in product_patterns):
                product_urls.append(u)
            elif any(p in path for p in category_patterns):
                category_urls.append(u)
            elif any(p in path for p in faq_patterns):
                faq_urls.append(u)
            elif any(p in path for p in info_patterns):
                info_urls.append(u)
            else:
                other_urls.append(u)

        home_urls = sort_urls(home_urls)
        product_urls = sort_urls(product_urls)
        category_urls = sort_urls(category_urls)
        faq_urls = sort_urls(faq_urls)
        info_urls = sort_urls(info_urls)
        other_urls = sort_urls(other_urls)

        selected: List[str] = []

        def add_from(urls: List[str], limit: int) -> None:
            added = 0
            for u in urls:
                if len(selected) >= max_sample or added >= limit:
                    break
                if u not in selected:
                    selected.append(u)
                    added += 1

        # 1) Home
        if home_urls:
            add_from(home_urls, 1)
        elif base_url:
            selected.append(base_url)

        # 2) Categorías y productos (prioridad ecommerce)
        add_from(category_urls, 2)
        add_from(product_urls, 2)

        # 3) FAQ / Info
        add_from(faq_urls, 1)
        add_from(info_urls, 1)

        # 4) Relleno con otras URLs
        add_from(other_urls, max_sample)

        logger.info(f"PIPELINE: URLs seleccionadas para auditoría: {selected}")
        return selected

    @staticmethod
    def _summarize_crawl_urls(urls: List[str]) -> Dict[str, int]:
        """Resume URLs crawleadas por tipo para enriquecer métricas."""
        from urllib.parse import urlparse

        counts = {
            "total_urls": 0,
            "home_pages": 0,
            "product_pages": 0,
            "category_pages": 0,
            "faq_pages": 0,
            "info_pages": 0,
            "other_pages": 0,
        }

        product_patterns = [
            "/product/",
            "/products/",
            "/p/",
            "/sku/",
            "/item/",
            "/buy/",
            "/pd/",
        ]
        category_patterns = [
            "/category/",
            "/categories/",
            "/collection/",
            "/collections/",
            "/c/",
            "/shop/",
            "/store/",
            "/department/",
        ]
        faq_patterns = ["/faq", "/preguntas", "/ayuda", "/help", "/soporte"]
        info_patterns = [
            "/about",
            "/nosotros",
            "/contact",
            "/contacto",
            "/envio",
            "/envíos",
            "/shipping",
            "/returns",
            "/devoluciones",
        ]

        for u in urls or []:
            counts["total_urls"] += 1
            try:
                path = (urlparse(u).path or "/").lower()
            except Exception:
                path = "/"

            if path in ["/", "", "/index.html"]:
                counts["home_pages"] += 1
            elif any(p in path for p in product_patterns):
                counts["product_pages"] += 1
            elif any(p in path for p in category_patterns):
                counts["category_pages"] += 1
            elif any(p in path for p in faq_patterns):
                counts["faq_pages"] += 1
            elif any(p in path for p in info_patterns):
                counts["info_pages"] += 1
            else:
                counts["other_pages"] += 1

        return counts

    async def generate_full_report(
        self,
        target_audit: Dict[str, Any],
        external_intelligence: Dict[str, Any],
        search_results: Dict[str, Any],
        competitor_audits: List[Dict[str, Any]],
        pagespeed_data: Optional[Dict] = None,
        keywords_data: Optional[Dict] = None,
        backlinks_data: Optional[Dict] = None,
        product_intelligence_data: Optional[Dict] = None,
        llm_function: Optional[callable] = None,
    ) -> Tuple[str, List[Dict]]:
        """
        Genera el reporte completo y el fix_plan usando prompts JSON v2.0.
        """
        try:
            logger.info("Generating full report with v2.0 prompts...")

            competitor_audits = self._normalize_competitor_scores(
                competitor_audits or []
            )

            competitor_query_coverage: Dict[str, Any] = {}
            try:
                from app.services.competitive_intel_service import (
                    CompetitiveIntelService,
                )

                competitor_query_coverage = (
                    CompetitiveIntelService.build_competitor_query_coverage(
                        search_results or {},
                        competitor_audits,
                        target_audit=target_audit,
                    )
                )
            except Exception as e:
                logger.warning(f"Competitive intel coverage build failed: {e}")

            score_definitions = self._build_score_definitions()
            data_quality = self._build_data_quality(
                target_audit=target_audit,
                search_results=search_results or {},
                competitor_audits=competitor_audits,
                pagespeed_data=pagespeed_data or {},
                keywords_data=keywords_data or {},
                backlinks_data=backlinks_data or {},
                competitor_query_coverage=competitor_query_coverage,
            )

            # Preparar contexto
            context = {
                "target_audit": target_audit,
                "external_intelligence": external_intelligence,
                "search_results": search_results,
                "competitor_audits": competitor_audits,
                "competitor_query_coverage": competitor_query_coverage,
                "pagespeed": pagespeed_data or {},
                "keywords": keywords_data or {},
                "backlinks": backlinks_data or {},
                "data_quality": data_quality,
                "score_definitions": score_definitions,
            }

            # Cargar prompt de reporte
            report_prompt_data = self.prompt_loader.load_prompt("report_generation")
            system_prompt = report_prompt_data.get("system_prompt", "")
            user_template = report_prompt_data.get("user_template", "")

            # Minimizar/ajustar contexto al presupuesto de tokens
            minimized_context, _ = self._shrink_context_to_budget(
                context, system_prompt
            )
            context_json = json.dumps(minimized_context, ensure_ascii=False)

            # Preparar placeholders usando contexto reducido
            reduced_target = minimized_context.get("target_audit", {})
            reduced_external = minimized_context.get("external_intelligence", {})
            reduced_search = minimized_context.get("search_results", {})
            reduced_competitors = minimized_context.get("competitor_audits", [])
            reduced_pagespeed = minimized_context.get("pagespeed", {})
            reduced_keywords = minimized_context.get("keywords", {})
            reduced_backlinks = minimized_context.get("backlinks", {})
            reduced_data_quality = minimized_context.get("data_quality", {})
            reduced_score_definitions = minimized_context.get("score_definitions", {})
            reduced_competitor_coverage = minimized_context.get(
                "competitor_query_coverage", {}
            )

            user_prompt = user_template
            user_prompt = user_prompt.replace(
                "{seo_data}", json.dumps(reduced_target, ensure_ascii=False)
            )
            user_prompt = user_prompt.replace(
                "{competitive_intelligence}",
                json.dumps(
                    {
                        "competitors": reduced_competitors,
                        "search_results": reduced_search,
                    },
                    ensure_ascii=False,
                ),
            )
            user_prompt = user_prompt.replace(
                "{technical_performance_data}",
                json.dumps(reduced_pagespeed or {}, ensure_ascii=False),
            )
            user_prompt = user_prompt.replace(
                "{content_strategy_data}", json.dumps({}, ensure_ascii=False)
            )
            user_prompt = user_prompt.replace(
                "{backlink_data}",
                json.dumps(reduced_backlinks or {}, ensure_ascii=False),
            )
            user_prompt = user_prompt.replace(
                "{keyword_data}", json.dumps(reduced_keywords or {}, ensure_ascii=False)
            )
            user_prompt = user_prompt.replace(
                "{llm_visibility_data}", json.dumps({}, ensure_ascii=False)
            )
            user_prompt = user_prompt.replace(
                "{executive_summary_data}",
                json.dumps(reduced_external, ensure_ascii=False),
            )
            user_prompt = user_prompt.replace(
                "{product_intelligence_data}",
                json.dumps(product_intelligence_data or {}, ensure_ascii=False),
            )
            user_prompt = user_prompt.replace(
                "{data_quality}", json.dumps(reduced_data_quality, ensure_ascii=False)
            )
            user_prompt = user_prompt.replace(
                "{score_definitions}",
                json.dumps(reduced_score_definitions, ensure_ascii=False),
            )
            user_prompt = user_prompt.replace(
                "{competitor_query_coverage}",
                json.dumps(reduced_competitor_coverage, ensure_ascii=False),
            )

            logger.info(
                f"Calling LLM for full report generation. Context size: {len(context_json)} chars"
            )

            if llm_function is None:
                raise ValueError("LLM function is required for report generation")

            response = await llm_function(
                system_prompt=system_prompt, user_prompt=user_prompt
            )

            # Parsear respuesta
            delimiter = self.prompt_loader.get_delimiter()
            parts = response.split(delimiter)

            if len(parts) >= 2:
                report_markdown = parts[0].strip()
                fix_plan_text = parts[1].strip()

                # Parsear fix_plan JSON
                try:
                    fix_plan = json.loads(fix_plan_text)
                    if not isinstance(fix_plan, list):
                        fix_plan = []
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing fix_plan JSON: {e}")
                    fix_plan = []
            else:
                logger.warning(
                    "Delimiter not found in response, returning full response as report"
                )
                report_markdown = response
                fix_plan = []

            report_markdown = self._sanitize_report_sources(
                report_markdown, target_audit
            )

            # Enriquecer fix_plan con issues del audit
            enriched_fix_plan = self._enrich_fix_plan_with_audit_issues(
                fix_plan,
                target_audit,
                pagespeed_data=pagespeed_data,
                product_intelligence_data=product_intelligence_data,
            )

            logger.info(
                f"Report generated successfully. Length: {len(report_markdown)} chars, Fix plan items: {len(enriched_fix_plan)}"
            )

            return report_markdown, enriched_fix_plan

        except Exception as e:
            logger.error(f"Error generating full report: {e}", exc_info=True)
            raise


# Instancia singleton
pipeline_service = PipelineService()


def get_pipeline_service() -> PipelineService:
    """Obtiene la instancia singleton del PipelineService."""
    return pipeline_service


async def run_initial_audit(
    url: str,
    target_audit: Dict[str, Any],
    audit_id: int,
    llm_function: callable,
    google_api_key: Optional[str] = None,
    google_cx_id: Optional[str] = None,
    crawler_service: Optional[callable] = None,
    audit_local_service: Optional[callable] = None,
    progress_callback: Optional[callable] = None,
    generate_report: bool = False,
    enable_llm_external_intel: bool = True,
    external_intel_mode: str = "full",
    external_intel_timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Ejecuta el pipeline inicial de auditoría:
    - Analiza inteligencia externa
    - Ejecuta búsquedas y detecta competidores
    - Audita competidores (si hay)
    - Genera reporte y fix_plan
    """
    service = get_pipeline_service()

    async def emit_progress(value: float):
        if not progress_callback:
            return
        try:
            result = progress_callback(value)
            if asyncio.iscoroutine(result):
                await result
        except Exception as progress_err:
            logger.warning(
                f"run_initial_audit: progress update failed ({value}%): {progress_err}"
            )

    normalized_target = service._ensure_dict(target_audit)
    base_url = (normalized_target.get("url") or url or "").strip()
    if base_url and not urlparse(base_url).scheme:
        base_url = f"https://{base_url}"
    base_host = ""
    if base_url:
        try:
            base_host = (urlparse(base_url).hostname or "").lower()
            if base_host.startswith("www."):
                base_host = base_host[4:]
        except Exception:
            base_host = ""
    if base_url:
        normalized_target.setdefault("url", base_url)
        normalized_target.setdefault(
            "domain", base_host or urlparse(base_url).netloc.replace("www.", "")
        )

    def safe_int(value: Any, default: int) -> int:
        try:
            value_int = int(value)
            return value_int if value_int > 0 else default
        except Exception:
            return default

    def is_valid_summary(summary: Any) -> bool:
        if not isinstance(summary, dict):
            return False
        status = summary.get("status")
        try:
            status_int = int(status) if status is not None else None
        except Exception:
            status_int = None
        if status_int is not None and status_int >= 400:
            return False
        for key in ("structure", "content", "eeat", "schema"):
            if key not in summary or not isinstance(summary.get(key), dict):
                return False
        return True

    crawled_urls: List[str] = []
    audited_summaries: List[Dict[str, Any]] = []
    if normalized_target:
        audited_summaries.append(normalized_target)

    if crawler_service and audit_local_service and base_url:
        try:
            from app.core.config import settings
        except Exception:
            settings = None

        max_crawl = safe_int(getattr(settings, "MAX_CRAWL_PAGES", None), 50)
        max_audit_default = safe_int(
            getattr(settings, "MAX_AUDIT_DEFAULT", None), max_crawl
        )
        max_audit = safe_int(
            getattr(settings, "MAX_AUDIT_PAGES", None), max_audit_default
        )
        if max_crawl < max_audit:
            max_crawl = max_audit

        try:
            crawled_urls = await crawler_service(base_url, max_pages=max_crawl)
        except Exception as e:
            logger.error(
                f"run_initial_audit: crawl failed for {base_url}: {e}",
                exc_info=True,
            )
            crawled_urls = []

        # Fallback 1: si el crawler devolvió muy pocas URLs, intentar sitemap directo
        if base_url and (not crawled_urls or len(crawled_urls) <= 1):
            try:
                from app.services.crawler_service import (
                    CrawlerService as _CrawlerFallback,
                )

                sitemap_urls = await _CrawlerFallback.fetch_sitemap_urls(
                    base_url,
                    allow_subdomains=False,
                    max_urls=max_crawl,
                    mobile_first=True,
                )
                if sitemap_urls:
                    crawled_urls = sitemap_urls
                    logger.info(
                        f"run_initial_audit: fallback sitemap encontró {len(crawled_urls)} URLs."
                    )
            except Exception as e:
                logger.warning(
                    f"run_initial_audit: sitemap fallback failed for {base_url}: {e}",
                )

        # Fallback 2: si sigue siendo muy bajo, intentar discovery vía Serper (site:domain)
        serper_key_for_discovery = getattr(settings, "SERPER_API_KEY", None)
        if base_url and (not crawled_urls or len(crawled_urls) <= 1):
            try:
                if not serper_key_for_discovery:
                    logger.info(
                        "run_initial_audit: search fallback omitido (SERPER_API_KEY ausente)."
                    )
                else:
                    target_domain = base_host or urlparse(base_url).netloc.replace(
                        "www.", ""
                    )
                    site_query = f"site:{target_domain}"
                    search_data = await service.run_serper_search(
                        site_query,
                        serper_key_for_discovery,
                        num_results=max(10, min(max_crawl, 100)),
                    )
                    items = (
                        search_data.get("items", [])
                        if isinstance(search_data, dict)
                        else []
                    )
                    internal_urls = service._extract_internal_urls_from_search(
                        items, target_domain, limit=max_crawl
                    )
                    if internal_urls:
                        crawled_urls = internal_urls
                        logger.info(
                            f"run_initial_audit: search fallback encontró {len(crawled_urls)} URLs internas."
                        )
            except Exception as e:
                logger.warning(
                    f"run_initial_audit: search fallback failed for {base_url}: {e}"
                )

        urls_to_audit = crawled_urls or [base_url]
        if base_host:
            filtered_urls: List[str] = []
            skipped_by_host = 0
            for candidate in urls_to_audit:
                if not candidate:
                    continue
                try:
                    parsed = urlparse(str(candidate))
                except Exception:
                    skipped_by_host += 1
                    continue
                candidate_host = (parsed.hostname or "").lower()
                if candidate_host.startswith("www."):
                    candidate_host = candidate_host[4:]
                if candidate_host != base_host:
                    skipped_by_host += 1
                    continue
                filtered_urls.append(candidate)
            if skipped_by_host:
                logger.info(
                    f"run_initial_audit: filtered {skipped_by_host} URLs outside base host '{base_host}'."
                )
            urls_to_audit = filtered_urls or [base_url]
        logger.info(
            f"run_initial_audit: URLs crawleadas={len(crawled_urls)} | URLs a auditar={len(urls_to_audit)}"
        )
        if len(urls_to_audit) > max_audit:
            urls_to_audit = service.select_important_urls(
                urls_to_audit, base_url, max_sample=max_audit
            )

        def canonical(u: str) -> str:
            return (u or "").rstrip("/").lower()

        seen_urls = set()
        deduped_urls = []
        for u in urls_to_audit:
            if not u:
                continue
            cu = canonical(u)
            if cu in seen_urls:
                continue
            seen_urls.add(cu)
            deduped_urls.append(u)

        has_valid_base = is_valid_summary(normalized_target)
        if has_valid_base:
            base_canon = canonical(base_url)
            deduped_urls = [u for u in deduped_urls if canonical(u) != base_canon]

        if deduped_urls:
            logger.info(
                f"run_initial_audit: auditando {len(deduped_urls)} páginas (excluyendo base_url)."
            )
            sem = asyncio.Semaphore(5)

            async def audit_one(audit_url: str) -> Dict[str, Any]:
                async with sem:
                    return await audit_local_service(audit_url)

            results = await asyncio.gather(
                *[audit_one(u) for u in deduped_urls],
                return_exceptions=True,
            )

            for result in results:
                if isinstance(result, Exception):
                    logger.error(
                        f"run_initial_audit: audit_local_service failed: {result}",
                        exc_info=True,
                    )
                    continue
                if isinstance(result, dict):
                    audited_summaries.append(result)
            await emit_progress(30)

    valid_summaries = [s for s in audited_summaries if is_valid_summary(s)]
    if valid_summaries:
        if len(valid_summaries) > 1:
            aggregated = service._aggregate_summaries(valid_summaries, base_url or url)
            aggregated["aggregate_label"] = aggregated.get("url")
            if base_url:
                aggregated["url"] = base_url
                aggregated.setdefault(
                    "domain", urlparse(base_url).netloc.replace("www.", "")
                )
            if normalized_target.get("market"):
                aggregated["market"] = normalized_target.get("market")
            if normalized_target.get("language"):
                aggregated["language"] = normalized_target.get("language")
            normalized_target = aggregated
        else:
            normalized_target = valid_summaries[0]

    # Attach sample content fields for LLM context
    sample_source = valid_summaries[0] if valid_summaries else normalized_target
    if isinstance(sample_source, dict):
        sample_content = sample_source.get("content", {})
        if isinstance(sample_content, dict):
            target_content = normalized_target.get("content")
            if not isinstance(target_content, dict):
                normalized_target["content"] = {}
                target_content = normalized_target["content"]
            for key in ["title", "meta_description", "meta_keywords", "text_sample"]:
                if sample_content.get(key) and not target_content.get(key):
                    target_content[key] = sample_content.get(key)
        if sample_source.get("meta_robots") and not normalized_target.get(
            "meta_robots"
        ):
            normalized_target["meta_robots"] = sample_source.get("meta_robots")

    # Store per-page audits for UI/DB saving
    ordered_summaries = []
    seen_summary_urls = set()
    for summary in audited_summaries:
        if not is_valid_summary(summary):
            continue
        url_value = summary.get("url")
        if not url_value:
            continue
        key = (url_value or "").rstrip("/").lower()
        if key in seen_summary_urls:
            continue
        seen_summary_urls.add(key)
        ordered_summaries.append(summary)

    def _snapshot_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
        """Create a shallow copy without recursive audit references."""
        if not isinstance(summary, dict):
            return summary
        cleaned = {k: v for k, v in summary.items() if k != "_individual_page_audits"}
        return cleaned

    normalized_target["_individual_page_audits"] = [
        {"index": idx, "url": s.get("url"), "data": _snapshot_summary(s)}
        for idx, s in enumerate(ordered_summaries)
    ]
    if ordered_summaries:
        normalized_target["site_metrics"] = service._compute_site_metrics(
            ordered_summaries
        )
        try:
            from app.services.audit_service import CompetitorService

            normalized_target["geo_score"] = CompetitorService._calculate_geo_score(
                normalized_target
            )
            normalized_target["benchmark"] = CompetitorService._format_competitor_data(
                normalized_target,
                normalized_target["geo_score"],
                normalized_target.get("url"),
            )
        except Exception:  # nosec B110
            pass
    if ordered_summaries and base_url:
        normalized_target.setdefault("audited_pages_count", len(ordered_summaries))
        if "audited_page_paths" not in normalized_target:

            def _path_from_url(u: str) -> str:
                try:
                    path_value = urlparse(u).path
                except Exception:
                    path_value = ""
                if not path_value:
                    return "/"
                return path_value if path_value.startswith("/") else f"/{path_value}"

            normalized_target["audited_page_paths"] = [
                _path_from_url(s.get("url", "")) for s in ordered_summaries
            ]
    if crawled_urls:
        normalized_target["crawled_pages_count"] = len(crawled_urls)
        normalized_target["crawled_page_paths"] = crawled_urls
        normalized_target["crawl_summary"] = service._summarize_crawl_urls(crawled_urls)

    # 1) External intelligence (Agent 1) - optional for fast dashboard mode
    external_intelligence = {}
    search_queries: List[Dict[str, str]] = []
    if enable_llm_external_intel:
        try:
            retry_policy = (
                {"timeout_seconds": external_intel_timeout_seconds, "max_retries": 1}
                if external_intel_timeout_seconds
                else {"max_retries": 1}
            )
            (
                external_intelligence,
                search_queries,
            ) = await service.analyze_external_intelligence(
                normalized_target,
                llm_function=llm_function,
                mode=external_intel_mode,
                retry_policy=retry_policy,
            )
        except Exception as e:
            error_code, error_message = service._resolve_external_intel_error(e)
            external_intelligence = service._build_unavailable_external_intelligence(
                normalized_target,
                error_code=error_code,
                error_message=error_message,
                analysis_mode=external_intel_mode,
            )
            search_queries = []
            timeout_value = (
                f"{external_intel_timeout_seconds}s"
                if external_intel_timeout_seconds
                else "configured-default"
            )
            logger.warning(
                "External intelligence unavailable; continuing with partial completion. "
                f"audit_id={audit_id} error_code={error_code} "
                f"timeout={timeout_value} provider=kimi_async_openai mode={external_intel_mode}"
            )
    else:
        external_intelligence = service._build_unavailable_external_intelligence(
            normalized_target,
            error_code="AGENT1_DISABLED",
            error_message="External intelligence disabled for this audit run.",
            analysis_mode=external_intel_mode,
        )
        search_queries = []

    # 2) Competitor search results (Serper)
    search_results: Dict[str, Any] = {}
    if search_queries:
        serper_api_key = settings.SERPER_API_KEY
        if not serper_api_key:
            logger.warning(
                "run_initial_audit: SERPER_API_KEY missing; competitor search disabled for this audit."
            )
        else:
            search_num_results = 20 if not enable_llm_external_intel else 10
            tasks: Dict[str, asyncio.Task] = {}
            for q in search_queries:
                query_text = q.get("query") if isinstance(q, dict) else str(q)
                if not query_text:
                    continue
                tasks[query_text] = asyncio.create_task(
                    service.run_serper_search(
                        query_text,
                        serper_api_key,
                        num_results=search_num_results,
                    )
                )

            for query_text, task in tasks.items():
                try:
                    search_results[query_text] = await task
                except Exception as e:
                    logger.error(
                        f"run_initial_audit: search failed for '{query_text}': {e}"
                    )
                    search_results[query_text] = {"error": str(e), "items": []}
    await emit_progress(45)

    # 3) Identify competitors
    competitor_urls: List[str] = []
    try:
        target_domain = base_host or urlparse(base_url or url).netloc.replace(
            "www.", ""
        )
        user_competitors = normalized_target.get("competitors")
        if isinstance(user_competitors, list) and user_competitors:
            competitor_urls = service.normalize_competitor_list(
                user_competitors, target_domain
            )
            logger.info(
                f"PIPELINE: Usando {len(competitor_urls)} competidores provistos por el usuario."
            )
        else:
            competitor_urls = service._extract_competitor_urls_from_search(
                search_results=search_results,
                target_domain=target_domain,
                target_audit=normalized_target,
                external_intelligence=external_intelligence,
                core_profile=service._build_core_business_profile(
                    normalized_target, max_terms=6
                ),
                limit=5,
            )
    except Exception as e:
        logger.error(f"run_initial_audit: competitor extraction failed: {e}")

    # 4) Audit competitors
    competitor_audits: List[Dict[str, Any]] = []
    if competitor_urls and audit_local_service:
        try:
            competitor_audits = await service.generate_competitor_audits(
                competitor_urls, audit_local_function=audit_local_service
            )
        except Exception as e:
            logger.error(
                f"run_initial_audit: competitor audits failed: {e}", exc_info=True
            )
    await emit_progress(60)

    # 5) Generate report + fix plan (optional)
    report_markdown = ""
    fix_plan: List[Dict[str, Any]] = []
    if generate_report:
        await emit_progress(80)
        report_markdown, fix_plan = await service.generate_report(
            target_audit=normalized_target,
            external_intelligence=external_intelligence,
            search_results=search_results,
            competitor_audits=competitor_audits,
            llm_function=llm_function,
        )
        await emit_progress(95)
        if not report_markdown:
            report_markdown = service._build_initial_baseline_report(
                normalized_target,
                external_intelligence,
                len(competitor_audits),
            )

    return {
        "audit_id": audit_id,
        "target_audit": normalized_target,
        "external_intelligence": external_intelligence,
        "search_results": search_results,
        "competitor_audits": competitor_audits,
        "report_markdown": report_markdown,
        "fix_plan": fix_plan,
        "pagespeed": {},
    }
