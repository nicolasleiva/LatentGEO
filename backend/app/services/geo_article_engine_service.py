#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
geo_article_engine_service.py

Strict GEO/SEO article engine:
- Builds a complete article_data_pack per article.
- Uses hybrid keyword strategy (audit keywords + Kimi Search expansion).
- Enforces authority-source minimums and hard failure contracts.
- Generates full articles with Kimi using audited evidence only.
"""

from __future__ import annotations

import inspect
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from app.core.config import settings
from app.core.llm_kimi import (
    KimiGenerationError,
    KimiSearchError,
    KimiSearchUnavailableError,
    KimiUnavailableError,
    get_llm_function,
    is_kimi_configured,
    kimi_search_serp,
)
from app.core.logger import get_logger
from app.models import AIContentSuggestion, Audit, GeoArticleBatch, Keyword
from app.services.crawler_service import CrawlerService
from app.services.competitor_filters import (
    infer_vertical_hint,
    is_valid_competitor_domain,
    normalize_domain,
)
from app.services.duplicate_content_service import DuplicateContentService
from sqlalchemy.orm import Session, load_only

logger = get_logger(__name__)


class ArticleDataPackIncompleteError(ValueError):
    """Raised when article_data_pack cannot be completed for generation."""


class InsufficientAuthoritySourcesError(ValueError):
    """Raised when required authority sources are missing for an article."""


class ArticleStrategyRequiredError(ValueError):
    """Raised when no valid strategy run is available for article generation."""


class LegacyBatchReadOnlyError(ValueError):
    """Raised when legacy batches attempt unsupported mutations."""


class GeoArticleEngineService:
    """Service for strict article generation based on audited context."""

    MAX_ARTICLES = 12
    DEFAULT_TOP_K = 10
    MIN_EXTERNAL_SOURCES = 3
    MIN_INTERNAL_SOURCES = 2
    STATUS_SNAPSHOT_TTL_SECONDS = 86400
    STATUS_STALE_FALLBACK_SECONDS = 10

    STOPWORDS = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "your",
        "this",
        "that",
        "you",
        "are",
        "how",
        "what",
        "why",
        "como",
        "para",
        "con",
        "sin",
        "una",
        "uno",
        "unos",
        "unas",
        "que",
        "del",
        "los",
        "las",
        "por",
        "www",
        "http",
        "https",
    }
    ARTICLE_CUES = {
        "guide",
        "how to",
        "what is",
        "faq",
        "questions",
        "q&a",
        "best practices",
        "report",
        "case study",
        "analysis",
        "overview",
        "strategy",
        "playbook",
        "framework",
        "tutorial",
        "research",
        "insights",
        "resources",
        "whitepaper",
        "benchmark",
        "explained",
        "guia",
        "como",
        "que es",
        "preguntas",
        "preguntas frecuentes",
        "mejores practicas",
        "informe",
        "reporte",
        "estudio",
        "caso de estudio",
        "analisis",
        "estrategia",
        "manual",
    }
    ARTICLE_URL_CUES = {
        "/blog",
        "/guides",
        "/guide",
        "/faq",
        "/faqs",
        "/how-to",
        "/howto",
        "/learn",
        "/academy",
        "/resources",
        "/insights",
        "/articles",
        "/article",
        "/research",
        "/whitepaper",
        "/case-study",
        "/case-studies",
        "/report",
        "/reports",
        "/knowledge",
        "/knowledge-base",
        "/kb/",
    }
    QA_CUES = {
        "faq",
        "q&a",
        "questions",
        "preguntas frecuentes",
        "preguntas y respuestas",
    }
    QA_URL_CUES = {
        "/faq",
        "/faqs",
        "/questions",
        "/preguntas",
        "/preguntas-frecuentes",
        "/qa",
        "/q-a",
    }

    @staticmethod
    def _audit_only_mode() -> bool:
        return bool(getattr(settings, "GEO_ARTICLE_AUDIT_ONLY", True))

    @staticmethod
    def _extract_topic_terms(
        audit: Audit, primary_keyword: str, max_terms: int = 8
    ) -> List[str]:
        terms: List[str] = []
        seen = set()

        def add_tokens(text: str):
            for token in re.findall(r"[a-zA-Z0-9]{3,}", (text or "").lower()):
                if token in GeoArticleEngineService.STOPWORDS:
                    continue
                if token not in seen:
                    seen.add(token)
                    terms.append(token)

        add_tokens(primary_keyword)
        target = getattr(audit, "target_audit", None) or {}
        content = target.get("content", {}) if isinstance(target, dict) else {}
        add_tokens(str(content.get("title") or ""))
        add_tokens(str(content.get("meta_description") or ""))
        add_tokens(str(content.get("text_sample") or "")[:500])

        brand_token = GeoArticleEngineService._extract_brand_token(audit)
        if brand_token and brand_token not in seen:
            terms.insert(0, brand_token)
            seen.add(brand_token)

        return terms[:max_terms]

    @staticmethod
    def _unique_source_count(*source_pools: List[Dict[str, Any]]) -> int:
        seen = set()
        for pool in source_pools:
            for item in pool or []:
                url = str(item.get("url") or "").strip()
                if not url or url in seen:
                    continue
                seen.add(url)
        return len(seen)

    @staticmethod
    def _merge_unique_sources(
        base: List[Dict[str, Any]], extra: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        seen = {str(item.get("url") or "").strip() for item in base if item.get("url")}
        merged = list(base)
        for item in extra or []:
            url = str(item.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            merged.append(item)
        return merged

    @staticmethod
    def _build_authority_search_queries(
        *,
        primary_keyword: str,
        brand_token: str,
        topic_terms: List[str],
        language: str,
        max_queries: int,
    ) -> List[str]:
        if max_queries <= 0:
            return []
        modifiers_es = [
            "guia",
            "faq",
            "opiniones",
            "resenas",
            "caso de estudio",
            "informe",
        ]
        modifiers_en = ["guide", "faq", "review", "case study", "report", "insights"]
        modifiers = modifiers_es if language.lower().startswith("es") else modifiers_en

        terms = [t for t in topic_terms if t and t != brand_token]
        seed_terms = terms[:2]
        queries: List[str] = []

        for term in seed_terms:
            for mod in modifiers:
                if brand_token and brand_token not in term:
                    query = f"{brand_token} {term} {mod}"
                else:
                    query = f"{term} {mod}"
                queries.append(query)
                if len(queries) >= max_queries:
                    break
            if len(queries) >= max_queries:
                break

        if not queries and primary_keyword:
            queries.append(primary_keyword)

        deduped: List[str] = []
        seen = set()
        for query in queries:
            cleaned = " ".join(str(query or "").split()).strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            deduped.append(cleaned)
            if len(deduped) >= max_queries:
                break
        return deduped

    @staticmethod
    def _authority_source_metadata(
        *, title: str, snippet: str, url: str, topic_terms: List[str]
    ) -> Dict[str, Any]:
        text = f"{title} {snippet}".lower()
        parsed = urlparse(url if "://" in (url or "") else f"https://{url}")
        url_path = f"{parsed.path or ''} {parsed.query or ''}".lower()
        article_hit = any(
            cue in text for cue in GeoArticleEngineService.ARTICLE_CUES
        ) or any(cue in url_path for cue in GeoArticleEngineService.ARTICLE_URL_CUES)
        qa_hit = any(cue in text for cue in GeoArticleEngineService.QA_CUES) or any(
            cue in url_path for cue in GeoArticleEngineService.QA_URL_CUES
        )
        topic_hits = 0
        for term in topic_terms:
            if term and (term in text or term in url_path):
                topic_hits += 1
        score = (3 if article_hit else 0) + (1 if qa_hit else 0) + min(3, topic_hits)
        return {
            "is_article": article_hit,
            "has_qa_signal": qa_hit,
            "topic_hits": topic_hits,
            "score": score,
        }

    @staticmethod
    def _passes_authority_filters(
        *, title: str, snippet: str, url: str, topic_terms: List[str]
    ) -> Tuple[bool, Dict[str, Any]]:
        metadata = GeoArticleEngineService._authority_source_metadata(
            title=title, snippet=snippet, url=url, topic_terms=topic_terms
        )
        if getattr(
            settings, "GEO_ARTICLE_REQUIRE_AUTHORITY_ARTICLES", True
        ) and not metadata.get("is_article"):
            return False, metadata
        if (
            getattr(settings, "GEO_ARTICLE_REQUIRE_TOPIC_MATCH", True)
            and topic_terms
            and metadata.get("topic_hits", 0) == 0
        ):
            return False, metadata
        return True, metadata

    @staticmethod
    def _rank_authority_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(
            sources,
            key=lambda item: float(item.get("authority_score", 0) or 0),
            reverse=True,
        )

    @staticmethod
    def _extract_brand_token(audit: Audit) -> str:
        domain = GeoArticleEngineService._normalize_domain(
            audit.url or audit.domain or ""
        )
        if not domain:
            return ""
        return domain.split(".")[0].lower()

    @staticmethod
    def _normalize_domain(value: str) -> str:
        return normalize_domain(value)

    @staticmethod
    def _normalize_url(value: str) -> str:
        if not value:
            return ""
        raw = str(value).strip()
        if not raw:
            return ""
        if "://" not in raw:
            raw = f"https://{raw}"
        try:
            parsed = urlparse(raw)
        except Exception:
            return ""
        scheme = "https"
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        path = parsed.path or ""
        if path != "/" and path.endswith("/"):
            path = path[:-1]
        return f"{scheme}://{netloc}{path}"

    @staticmethod
    def _domain_matches(candidate: str, target: str) -> bool:
        c = (candidate or "").lower().replace("www.", "")
        t = (target or "").lower().replace("www.", "")
        if not c or not t:
            return False
        return c == t or c.endswith(f".{t}") or t.endswith(f".{c}")

    @staticmethod
    def _slugify(value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").lower()).strip("-")
        return cleaned or "article"

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        cleaned = (text or "").strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.replace("```json", "```").replace("```", "").strip()
        return cleaned

    @staticmethod
    def _safe_json_dict(raw_text: str) -> Dict[str, Any] | None:
        cleaned = GeoArticleEngineService._strip_code_fences(raw_text)
        if not cleaned:
            return None
        try:
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, dict) else None
        except Exception:  # nosec B110
            pass

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end > start:
            candidate = cleaned[start : end + 1]
            try:
                parsed = json.loads(candidate)
                return parsed if isinstance(parsed, dict) else None
            except Exception:
                return None
        return None

    @staticmethod
    def _safe_json_list(raw_text: str) -> List[Any]:
        cleaned = GeoArticleEngineService._strip_code_fences(raw_text)
        if not cleaned:
            return []
        try:
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, list) else []
        except Exception:  # nosec B110
            pass

        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start != -1 and end > start:
            candidate = cleaned[start : end + 1]
            try:
                parsed = json.loads(candidate)
                return parsed if isinstance(parsed, list) else []
            except Exception:
                return []
        return []

    @staticmethod
    async def _repair_article_json(
        *,
        llm_function: callable,
        raw_text: str,
        output_schema: Dict[str, Any],
        language: str,
    ) -> Dict[str, Any] | None:
        """Second-pass repair to coerce invalid JSON into the expected schema."""
        if not raw_text:
            return None
        truncated = raw_text.strip()
        if len(truncated) > 15000:
            truncated = (
                truncated[:12000] + "\n\n...[truncated]...\n\n" + truncated[-2000:]
            )

        system_prompt = (
            "You are a strict JSON repair tool. "
            "Convert the input into valid JSON matching the provided schema. "
            "Return JSON only, with no markdown or commentary."
        )
        user_prompt = json.dumps(
            {
                "task": "Repair invalid JSON from a previous model output.",
                "language": language,
                "raw_output": truncated,
                "output_schema": output_schema,
                "constraints": [
                    "Return valid JSON only.",
                    "Preserve as much content as possible.",
                    "Do not invent citations or sources.",
                    "If a field is missing, use an empty string or empty array.",
                ],
            },
            ensure_ascii=False,
        )

        repaired = await llm_function(
            system_prompt=system_prompt, user_prompt=user_prompt
        )
        return GeoArticleEngineService._safe_json_dict(repaired or "")

    @staticmethod
    async def _repair_invalid_citations(
        *,
        llm_function: callable,
        markdown: str,
        allowed_sources: List[str],
        required_internal_sources: List[str],
        required_external_sources: List[str],
        language: str,
        qa_requirements: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not markdown:
            return markdown
        allowed_list = [url for url in allowed_sources if url]
        internal_list = [url for url in required_internal_sources if url]
        external_list = [url for url in required_external_sources if url]
        truncated = markdown.strip()
        if len(truncated) > 12000:
            truncated = (
                truncated[:10000] + "\n\n...[truncated]...\n\n" + truncated[-1500:]
            )

        system_prompt = (
            "You are a strict citation repair assistant. "
            "Rewrite the markdown to use ONLY the allowed sources provided. "
            "Return markdown only."
        )
        user_prompt = json.dumps(
            {
                "task": "Repair invalid citations in the article markdown.",
                "language": language,
                "markdown": truncated,
                "allowed_sources": allowed_list,
                "required_internal_sources": internal_list,
                "required_external_sources": external_list,
                "qa_requirements": qa_requirements or {},
                "constraints": [
                    "Do not add new sources outside allowed_sources.",
                    "Replace invalid citations with allowed URLs when possible.",
                    "If a claim cannot be supported by allowed sources, write 'Insufficient data' and remove the invalid citation.",
                    "Preserve section headings and overall structure.",
                    "Ensure at least one internal and one external citation if required lists are provided.",
                    "If qa_requirements.required is true, include the FAQ/Q&A section with at least qa_requirements.min_pairs pairs.",
                    "Return markdown only, no JSON, no commentary.",
                ],
            },
            ensure_ascii=False,
        )

        repaired = await llm_function(
            system_prompt=system_prompt, user_prompt=user_prompt
        )
        return str(repaired or "").strip()

    @staticmethod
    def _extract_market(audit: Audit, market: Optional[str] = None) -> str:
        if market:
            return str(market).strip().upper()
        if getattr(audit, "market", None):
            return str(audit.market).strip().upper()
        target = getattr(audit, "target_audit", None) or {}
        if isinstance(target, dict) and target.get("market"):
            return str(target.get("market")).strip().upper()
        return "GLOBAL"

    @staticmethod
    def _build_focus_urls(audit: Audit, max_urls: int = 24) -> List[str]:
        base_url = (audit.url or "").rstrip("/")
        urls: List[str] = []
        target = getattr(audit, "target_audit", None) or {}
        paths = target.get("audited_page_paths", []) if isinstance(target, dict) else []

        def append_url(candidate: str):
            if candidate and candidate not in urls:
                urls.append(candidate)

        if base_url:
            append_url(f"{base_url}/")

        for raw in paths:
            if not isinstance(raw, str):
                continue
            path = raw.strip()
            if not path:
                continue

            if path.startswith("http://") or path.startswith("https://"):
                append_url(path)
                if len(urls) >= max_urls:
                    break
                continue

            if path == "/":
                append_url(f"{base_url}/" if base_url else "")
                if len(urls) >= max_urls:
                    break
                continue
            if path.startswith("/") and "." not in path.split("/")[0]:
                append_url(f"{base_url}{path}")
                if len(urls) >= max_urls:
                    break

        return [url for url in urls if url][:max_urls]

    @staticmethod
    def _url_path_title(url: str) -> str:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        path = parsed.path.strip("/")
        if not path:
            return "Homepage"
        tokens = [p for p in path.split("/") if p]
        last = tokens[-1] if tokens else path
        return re.sub(r"[-_]+", " ", last).strip().title() or "Page"

    @staticmethod
    def _build_internal_sources(
        audit: Audit, focus_urls: List[str]
    ) -> List[Dict[str, str]]:
        domain = GeoArticleEngineService._normalize_domain(
            audit.url or audit.domain or ""
        )
        seen = set()
        sources: List[Dict[str, str]] = []

        for url in focus_urls:
            normalized = url.strip()
            if not normalized or normalized in seen:
                continue
            if not GeoArticleEngineService._domain_matches(
                GeoArticleEngineService._normalize_domain(normalized), domain
            ):
                continue
            seen.add(normalized)
            sources.append(
                {
                    "title": GeoArticleEngineService._url_path_title(normalized),
                    "url": normalized,
                    "domain": domain,
                    "source_type": "internal",
                }
            )
        return sources

    @staticmethod
    def _build_external_sources_from_audit(
        audit: Audit,
        max_sources: int = 20,
        topic_terms: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        domain = GeoArticleEngineService._normalize_domain(
            audit.url or audit.domain or ""
        )
        search_results = getattr(audit, "search_results", None) or {}
        if not isinstance(search_results, dict):
            return []

        sources: List[Dict[str, str]] = []
        seen = set()
        terms = topic_terms or []
        for query_payload in search_results.values():
            if not isinstance(query_payload, dict):
                continue
            for item in query_payload.get("items", [])[:10]:
                if not isinstance(item, dict):
                    continue
                link = str(item.get("link") or "").strip()
                if not link or link in seen:
                    continue
                link_domain = GeoArticleEngineService._normalize_domain(link)
                if not link_domain:
                    continue
                if GeoArticleEngineService._domain_matches(link_domain, domain):
                    continue
                if not is_valid_competitor_domain(link_domain):
                    continue
                title = str(item.get("title") or link_domain).strip()
                snippet = str(item.get("snippet") or "").strip()
                passes, meta = GeoArticleEngineService._passes_authority_filters(
                    title=title,
                    snippet=snippet,
                    url=link,
                    topic_terms=terms,
                )
                if not passes:
                    continue
                seen.add(link)
                sources.append(
                    {
                        "title": title,
                        "url": link,
                        "domain": link_domain,
                        "snippet": snippet,
                        "source_type": "external",
                        "authority_score": meta.get("score", 0),
                        "authority_topic_hits": meta.get("topic_hits", 0),
                        "authority_has_qa_signal": meta.get("has_qa_signal", False),
                    }
                )
                if len(sources) >= max_sources:
                    return GeoArticleEngineService._rank_authority_sources(sources)
        return GeoArticleEngineService._rank_authority_sources(sources)

    @staticmethod
    def _extract_html_title(html: str, fallback: str) -> str:
        try:
            soup = BeautifulSoup(html or "", "html.parser")
            title = soup.title.string if soup.title and soup.title.string else ""
        except Exception:  # nosec B110
            title = ""
        cleaned = str(title or "").strip()
        return cleaned or fallback

    @staticmethod
    async def _build_user_authority_sources(
        authority_urls: List[str],
    ) -> List[Dict[str, Any]]:
        sources: List[Dict[str, Any]] = []
        seen = set()
        for raw_url in authority_urls or []:
            normalized = GeoArticleEngineService._normalize_url(
                str(raw_url or "").strip()
            )
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            html = await CrawlerService.get_page_content(normalized)
            if not html:
                continue
            text = DuplicateContentService.extract_text(html)
            excerpt = text[:2000].strip()
            if not excerpt:
                continue
            title = GeoArticleEngineService._extract_html_title(
                html,
                GeoArticleEngineService._url_path_title(normalized),
            )
            sources.append(
                {
                    "title": title,
                    "url": normalized,
                    "domain": GeoArticleEngineService._normalize_domain(normalized),
                    "snippet": excerpt[:320],
                    "excerpt": excerpt,
                    "source_type": "user_authority",
                    "authority_score": 10,
                    "authority_topic_hits": 0,
                    "authority_has_qa_signal": False,
                }
            )
        return sources

    @staticmethod
    def _extract_audit_keywords(audit: Audit, max_keywords: int = 80) -> List[str]:
        keywords: List[str] = []
        seen = set()
        brand_token = GeoArticleEngineService._extract_brand_token(audit)

        relation = getattr(audit, "keywords", None) or []
        for item in relation:
            term = None
            if isinstance(item, Keyword):
                term = item.term
            elif isinstance(item, dict):
                term = item.get("term")
            else:
                term = getattr(item, "term", None)
            cleaned = str(term or "").strip().lower()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                keywords.append(cleaned)

        search_results = getattr(audit, "search_results", None) or {}
        if isinstance(search_results, dict):
            for query in search_results.keys():
                cleaned = str(query or "").strip().lower()
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    keywords.append(cleaned)

        target = getattr(audit, "target_audit", None) or {}
        content = target.get("content", {}) if isinstance(target, dict) else {}
        seed_text = " ".join(
            [
                str(content.get("title") or ""),
                str(content.get("meta_description") or ""),
            ]
        ).lower()
        for token in re.findall(r"[a-zA-Z0-9\-]{4,}", seed_text):
            if token in GeoArticleEngineService.STOPWORDS:
                continue
            if token not in seen:
                seen.add(token)
                keywords.append(token)

        if not keywords:
            root = GeoArticleEngineService._normalize_domain(
                audit.url or audit.domain or ""
            )
            root_token = root.split(".")[0] if root else "brand"
            keywords = [
                f"{root_token} buying guide",
                f"{root_token} alternatives",
                f"{root_token} product comparison",
            ]
        elif brand_token and brand_token not in seen:
            keywords.insert(0, brand_token)
            seen.add(brand_token)

        if brand_token:
            # Enrich with brand + top content tokens for relevance.
            base_tokens = []
            if seed_text:
                base_tokens = [
                    t
                    for t in re.findall(r"[a-z0-9\-]{4,}", seed_text)
                    if t and t not in GeoArticleEngineService.STOPWORDS
                ]
            for token in base_tokens[:4]:
                combo = f"{brand_token} {token}"
                if combo not in seen:
                    seen.add(combo)
                    keywords.append(combo)

        return keywords[:max_keywords]

    @staticmethod
    def _priority_weight(priority: str) -> int:
        value = (priority or "").strip().lower()
        if value == "high":
            return 0
        if value == "medium":
            return 1
        return 2

    @staticmethod
    def _parse_ai_strategy_row(row: AIContentSuggestion) -> Dict[str, Any]:
        outline = row.content_outline if isinstance(row.content_outline, dict) else {}
        sections = outline.get("sections") if isinstance(outline, dict) else []
        cleaned_sections = [
            str(s).strip()
            for s in (sections if isinstance(sections, list) else [])
            if str(s).strip()
        ]
        return {
            "title": str(row.topic or "").strip(),
            "target_keyword": str(outline.get("target_keyword") or "").strip().lower(),
            "sections": cleaned_sections,
            "priority": str(row.priority or "medium").strip().lower(),
            "suggestion_type": str(row.suggestion_type or "guide").strip().lower(),
            "business_context": str(outline.get("business_context") or "").strip(),
            "created_at": row.created_at.isoformat() if row.created_at else "",
            "strategy_run_id": str(row.strategy_run_id or "").strip(),
            "strategy_order": int(row.strategy_order or 0),
        }

    @staticmethod
    def _extract_ai_strategy_items(
        db: Session,
        audit_id: int,
        *,
        strategy_run_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = db.query(AIContentSuggestion).filter(
            AIContentSuggestion.audit_id == audit_id
        )
        if strategy_run_id:
            rows = (
                query.filter(AIContentSuggestion.strategy_run_id == strategy_run_id)
                .order_by(
                    AIContentSuggestion.strategy_order.asc(),
                    AIContentSuggestion.created_at.asc(),
                )
                .all()
            )
            return [GeoArticleEngineService._parse_ai_strategy_row(row) for row in rows]

        rows = (
            query.filter(AIContentSuggestion.strategy_run_id.isnot(None))
            .order_by(
                AIContentSuggestion.created_at.desc(),
                AIContentSuggestion.strategy_order.asc(),
            )
            .all()
        )
        parsed = [GeoArticleEngineService._parse_ai_strategy_row(row) for row in rows]
        parsed.sort(
            key=lambda item: (
                item.get("strategy_run_id", ""),
                item.get("strategy_order", 0),
                GeoArticleEngineService._priority_weight(
                    item.get("priority", "medium")
                ),
            )
        )
        return parsed

    @staticmethod
    def _get_latest_strategy_run_id(db: Session, audit_id: int) -> Optional[str]:
        row = (
            db.query(AIContentSuggestion.strategy_run_id)
            .filter(
                AIContentSuggestion.audit_id == audit_id,
                AIContentSuggestion.strategy_run_id.isnot(None),
            )
            .order_by(AIContentSuggestion.created_at.desc())
            .first()
        )
        if not row:
            return None
        return str(row[0] or "").strip() or None

    @staticmethod
    def _strategy_generation_domain(audit: Audit) -> str:
        domain = str(getattr(audit, "domain", "") or "").strip()
        if domain:
            return domain
        parsed = urlparse(str(getattr(audit, "url", "") or "").strip())
        return parsed.netloc.replace("www.", "").strip()

    @staticmethod
    async def _generate_strategy_run(
        db: Session,
        audit: Audit,
        *,
        article_count: int,
        topics: Optional[List[str]] = None,
    ) -> tuple[str, List[Dict[str, Any]]]:
        from app.services.ai_content_service import AIContentService

        suggestions = await AIContentService(db).generate_suggestions(
            audit.id,
            GeoArticleEngineService._strategy_generation_domain(audit),
            [str(topic).strip() for topic in (topics or []) if str(topic).strip()],
            count=article_count,
        )
        items = [
            GeoArticleEngineService._parse_ai_strategy_row(row) for row in suggestions
        ]
        strategy_run_id = str(items[0].get("strategy_run_id") if items else "").strip()
        if not strategy_run_id or len(items) < article_count:
            raise ArticleStrategyRequiredError(
                "ARTICLE_STRATEGY_REQUIRED: unable to build a complete strategy run."
            )
        return strategy_run_id, items[:article_count]

    @staticmethod
    async def resolve_batch_strategy(
        db: Session,
        audit: Audit,
        *,
        article_count: int,
        target_topics: Optional[List[str]] = None,
    ) -> tuple[str, List[Dict[str, Any]], str]:
        normalized_count = max(
            1, min(GeoArticleEngineService.MAX_ARTICLES, int(article_count))
        )
        cleaned_topics = [
            str(topic).strip() for topic in (target_topics or []) if str(topic).strip()
        ]
        if cleaned_topics:
            strategy_run_id, items = (
                await GeoArticleEngineService._generate_strategy_run(
                    db,
                    audit,
                    article_count=normalized_count,
                    topics=cleaned_topics,
                )
            )
            return strategy_run_id, items, "generated_from_topics"

        latest_run_id = GeoArticleEngineService._get_latest_strategy_run_id(
            db, audit.id
        )
        if latest_run_id:
            latest_items = GeoArticleEngineService._extract_ai_strategy_items(
                db,
                audit.id,
                strategy_run_id=latest_run_id,
            )
            if len(latest_items) >= normalized_count:
                return latest_run_id, latest_items[:normalized_count], "reused_latest"

        strategy_run_id, items = await GeoArticleEngineService._generate_strategy_run(
            db,
            audit,
            article_count=normalized_count,
            topics=[],
        )
        return strategy_run_id, items, "generated_auto"

    @staticmethod
    def _resolve_strategy_run_items(
        db: Session,
        audit_id: int,
        *,
        article_count: int,
        strategy_run_id: Optional[str] = None,
    ) -> tuple[str, List[Dict[str, Any]]]:
        resolved_run_id = (
            strategy_run_id
            or GeoArticleEngineService._get_latest_strategy_run_id(db, audit_id)
        )
        if not resolved_run_id:
            raise ArticleStrategyRequiredError(
                "ARTICLE_STRATEGY_REQUIRED: generate titles first or provide target topics."
            )

        items = GeoArticleEngineService._extract_ai_strategy_items(
            db,
            audit_id,
            strategy_run_id=resolved_run_id,
        )
        if len(items) < article_count:
            raise ArticleStrategyRequiredError(
                f"ARTICLE_STRATEGY_REQUIRED: latest strategy run has {len(items)} titles; {article_count} requested."
            )
        return resolved_run_id, items[:article_count]

    @staticmethod
    def _normalize_authority_urls(authority_urls: Optional[List[str]]) -> List[str]:
        normalized_urls: List[str] = []
        seen_urls = set()
        for raw_url in authority_urls or []:
            normalized = GeoArticleEngineService._normalize_url(
                str(raw_url or "").strip()
            )
            if not normalized or normalized in seen_urls:
                continue
            seen_urls.add(normalized)
            normalized_urls.append(normalized)
        return normalized_urls

    @staticmethod
    def _extract_match_tokens(text: str) -> List[str]:
        tokens: List[str] = []
        seen = set()
        for token in re.findall(r"[a-zA-Z0-9\-]{3,}", (text or "").lower()):
            cleaned = token.strip("-")
            if (
                not cleaned
                or cleaned in seen
                or cleaned in GeoArticleEngineService.STOPWORDS
            ):
                continue
            seen.add(cleaned)
            tokens.append(cleaned)
        return tokens

    @staticmethod
    def _strategy_item_match_terms(
        audit: Audit, strategy_item: Dict[str, Any]
    ) -> List[str]:
        primary_keyword = str(strategy_item.get("target_keyword") or "").strip().lower()
        title = str(strategy_item.get("title") or "").strip().lower()
        terms = GeoArticleEngineService._extract_topic_terms(audit, primary_keyword)
        for token in GeoArticleEngineService._extract_match_tokens(title):
            if token not in terms:
                terms.append(token)
        return terms[:20]

    @staticmethod
    def _score_user_authority_source_for_item(
        source: Dict[str, Any],
        strategy_item: Dict[str, Any],
        topic_terms: List[str],
    ) -> int:
        text_parts = [
            str(source.get("title") or ""),
            str(source.get("snippet") or ""),
            str(source.get("excerpt") or "")[:600],
            str(source.get("url") or ""),
        ]
        source_text = " ".join(text_parts).lower()
        source_content_text = " ".join(text_parts[:3]).lower()
        source_tokens = set(
            GeoArticleEngineService._extract_match_tokens(source_content_text)
        )
        keyword = str(strategy_item.get("target_keyword") or "").strip().lower()
        title = str(strategy_item.get("title") or "").strip().lower()
        title_tokens = set(GeoArticleEngineService._extract_match_tokens(title))
        meta = GeoArticleEngineService._authority_source_metadata(
            title=str(source.get("title") or ""),
            snippet=f"{str(source.get('snippet') or '')} {str(source.get('excerpt') or '')[:240]}",
            url=str(source.get("url") or ""),
            topic_terms=topic_terms,
        )

        topic_hits = int(meta.get("topic_hits", 0))
        keyword_match = bool(keyword and keyword in source_text)
        overlap = len(source_tokens.intersection(title_tokens.union(set(topic_terms))))
        if topic_hits == 0 and not keyword_match and overlap == 0:
            return 0

        score = topic_hits * 10 + int(meta.get("score", 0))
        if keyword_match:
            score += 8
        score += overlap
        return score

    @staticmethod
    def _assign_user_authority_urls_to_articles(
        audit: Audit,
        strategy_items: List[Dict[str, Any]],
        authority_sources: List[Dict[str, Any]],
    ) -> tuple[Dict[int, List[str]], List[str]]:
        assignments: Dict[int, List[str]] = {
            idx + 1: [] for idx in range(len(strategy_items))
        }
        if not strategy_items:
            return assignments, [
                str(source.get("url") or "").strip() for source in authority_sources
            ]

        topic_terms_by_item = [
            GeoArticleEngineService._strategy_item_match_terms(audit, item)
            for item in strategy_items
        ]
        unmatched_urls: List[str] = []
        for source in authority_sources:
            url = str(source.get("url") or "").strip()
            if not url:
                continue
            best_index = -1
            best_score = 0
            for idx, item in enumerate(strategy_items):
                score = GeoArticleEngineService._score_user_authority_source_for_item(
                    source,
                    item,
                    topic_terms_by_item[idx],
                )
                if score > best_score:
                    best_score = score
                    best_index = idx
            if best_index >= 0 and best_score > 0:
                assignments[best_index + 1].append(url)
            else:
                unmatched_urls.append(url)
        return assignments, unmatched_urls

    @staticmethod
    def _serialize_authority_source_cache(
        authority_sources: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        serialized: List[Dict[str, Any]] = []
        seen = set()
        for source in authority_sources:
            normalized = GeoArticleEngineService._normalize_url(
                str(source.get("url") or "").strip()
            )
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            serialized.append(
                {
                    "title": str(source.get("title") or "").strip(),
                    "url": normalized,
                    "domain": str(source.get("domain") or "").strip(),
                    "snippet": str(source.get("snippet") or "").strip(),
                    "excerpt": str(source.get("excerpt") or "").strip(),
                    "source_type": "user_authority",
                }
            )
        return serialized

    @staticmethod
    def _resolve_authority_sources_from_cache(
        summary: Dict[str, Any], authority_urls: List[str]
    ) -> List[Dict[str, Any]]:
        cached_rows = summary.get("_authority_source_cache") or []
        cache_map: Dict[str, Dict[str, Any]] = {}
        if isinstance(cached_rows, list):
            for row in cached_rows:
                if not isinstance(row, dict):
                    continue
                normalized = GeoArticleEngineService._normalize_url(
                    str(row.get("url") or "").strip()
                )
                if not normalized:
                    continue
                cache_map[normalized] = {
                    "title": str(row.get("title") or "").strip(),
                    "url": normalized,
                    "domain": str(row.get("domain") or "").strip(),
                    "snippet": str(row.get("snippet") or "").strip(),
                    "excerpt": str(row.get("excerpt") or "").strip(),
                    "source_type": "user_authority",
                }
        resolved: List[Dict[str, Any]] = []
        for raw_url in authority_urls:
            normalized = GeoArticleEngineService._normalize_url(
                str(raw_url or "").strip()
            )
            if not normalized or normalized not in cache_map:
                continue
            resolved.append(cache_map[normalized])
        return resolved

    @staticmethod
    def _build_primary_keyword_pool(
        audit_keywords: List[str],
        ai_strategy_items: List[Dict[str, Any]],
    ) -> List[str]:
        pool: List[str] = []
        seen = set()

        for item in ai_strategy_items:
            keyword = str(item.get("target_keyword") or "").strip().lower()
            if keyword and keyword not in seen:
                seen.add(keyword)
                pool.append(keyword)

        for keyword in audit_keywords:
            cleaned = str(keyword or "").strip().lower()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                pool.append(cleaned)

        return pool

    @staticmethod
    def _build_generated_titles_summary(
        strategy_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        generated_titles: List[Dict[str, Any]] = []
        for idx, item in enumerate(strategy_items):
            generated_titles.append(
                {
                    "index": idx + 1,
                    "title": str(item.get("title") or "").strip(),
                    "target_keyword": str(item.get("target_keyword") or "")
                    .strip()
                    .lower(),
                    "suggestion_type": str(item.get("suggestion_type") or "guide")
                    .strip()
                    .lower(),
                }
            )
        return generated_titles

    @staticmethod
    def _build_placeholder_articles(
        *,
        focus_urls: List[str],
        strategy_items: List[Dict[str, Any]],
        article_authority_assignments: Optional[Dict[int, List[str]]] = None,
    ) -> List[Dict[str, Any]]:
        placeholders: List[Dict[str, Any]] = []
        for idx, item in enumerate(strategy_items):
            focus_url = focus_urls[idx % len(focus_urls)] if focus_urls else ""
            title = str(item.get("title") or "").strip() or f"Article {idx + 1}"
            assigned_authority_urls = [
                str(url).strip()
                for url in (article_authority_assignments or {}).get(idx + 1, [])
                if str(url).strip()
            ]
            placeholders.append(
                {
                    "index": idx + 1,
                    "title": title,
                    "slug": GeoArticleEngineService._slugify(f"{title}-{idx + 1}"),
                    "target_keyword": str(item.get("target_keyword") or "")
                    .strip()
                    .lower(),
                    "focus_url": focus_url,
                    "generation_status": "queued",
                    "generation_error": None,
                    "keyword_strategy": {
                        "primary_keyword": str(item.get("target_keyword") or "")
                        .strip()
                        .lower(),
                        "secondary_keywords": [],
                        "search_intent": "",
                    },
                    "competitor_gap_map": {},
                    "evidence_summary": [],
                    "sources": [],
                    "citation_readiness_score": 0,
                    "markdown": "",
                    "meta_title": "",
                    "meta_description": "",
                    "user_authority_urls": assigned_authority_urls,
                }
            )
        return placeholders

    @staticmethod
    def _strategy_items_from_batch(batch: GeoArticleBatch) -> List[Dict[str, Any]]:
        generated_titles = (batch.summary or {}).get("generated_titles") or []
        strategy_items: List[Dict[str, Any]] = []
        source_rows = generated_titles if isinstance(generated_titles, list) else []
        if not source_rows:
            source_rows = batch.articles or []
        for row in source_rows:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "").strip()
            keyword = (
                str(
                    row.get("target_keyword")
                    or row.get("primary_keyword")
                    or row.get("keyword")
                    or ""
                )
                .strip()
                .lower()
            )
            if not title and not keyword:
                continue
            strategy_items.append(
                {
                    "title": title or f"{keyword.title()}: GEO + SEO Playbook",
                    "target_keyword": keyword,
                    "sections": [],
                    "priority": "medium",
                    "suggestion_type": str(row.get("suggestion_type") or "guide")
                    .strip()
                    .lower(),
                    "business_context": "",
                    "strategy_run_id": str(
                        (batch.summary or {}).get("strategy_run_id") or ""
                    ).strip(),
                    "strategy_order": int((row.get("index") or len(strategy_items) + 1))
                    - 1,
                }
            )
        return strategy_items

    @staticmethod
    def _is_legacy_batch(batch: GeoArticleBatch) -> bool:
        summary = batch.summary or {}
        return not bool(str(summary.get("strategy_run_id") or "").strip())

    @staticmethod
    async def prepare_batch_seed_data(
        db: Session,
        audit: Audit,
        *,
        article_count: int,
        target_topics: Optional[List[str]] = None,
        authority_urls: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        strategy_run_id, strategy_items, strategy_source = (
            await GeoArticleEngineService.resolve_batch_strategy(
                db,
                audit,
                article_count=article_count,
                target_topics=target_topics,
            )
        )

        normalized_authority_urls = GeoArticleEngineService._normalize_authority_urls(
            authority_urls
        )
        authority_sources: List[Dict[str, Any]] = []
        unmatched_authority_urls: List[str] = []
        article_authority_assignments: Dict[int, List[str]] = {
            idx + 1: [] for idx in range(len(strategy_items))
        }

        if normalized_authority_urls:
            authority_sources = (
                await GeoArticleEngineService._build_user_authority_sources(
                    normalized_authority_urls
                )
            )
            fetched_urls = {
                GeoArticleEngineService._normalize_url(
                    str(source.get("url") or "").strip()
                )
                for source in authority_sources
            }
            unmatched_authority_urls.extend(
                [url for url in normalized_authority_urls if url not in fetched_urls]
            )
            matched_assignments, topic_unmatched = (
                GeoArticleEngineService._assign_user_authority_urls_to_articles(
                    audit,
                    strategy_items,
                    authority_sources,
                )
            )
            article_authority_assignments.update(matched_assignments)
            unmatched_authority_urls.extend(topic_unmatched)

        deduped_unmatched: List[str] = []
        seen_unmatched = set()
        for url in unmatched_authority_urls:
            normalized = GeoArticleEngineService._normalize_url(str(url or "").strip())
            if not normalized or normalized in seen_unmatched:
                continue
            seen_unmatched.add(normalized)
            deduped_unmatched.append(normalized)

        return {
            "strategy_run_id": strategy_run_id,
            "strategy_items": strategy_items,
            "strategy_source": strategy_source,
            "article_authority_assignments": article_authority_assignments,
            "global_authority_urls": normalized_authority_urls,
            "unmatched_authority_urls": deduped_unmatched,
            "authority_source_cache": GeoArticleEngineService._serialize_authority_source_cache(
                authority_sources
            ),
        }

    @staticmethod
    def _extract_competitors_from_audit(
        audit: Audit, audit_domain: str, vertical_hint: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        competitors: List[Dict[str, Any]] = []
        seen = set()
        for row in getattr(audit, "competitor_audits", None) or []:
            if not isinstance(row, dict):
                continue
            domain = GeoArticleEngineService._normalize_domain(
                row.get("url") or row.get("domain") or ""
            )
            if not domain or GeoArticleEngineService._domain_matches(
                domain, audit_domain
            ):
                continue
            if not is_valid_competitor_domain(domain, vertical_hint):
                continue
            if domain in seen:
                continue
            seen.add(domain)
            competitors.append(
                {
                    "position": len(competitors) + 1,
                    "title": domain,
                    "url": row.get("url") or f"https://{domain}",
                    "domain": domain,
                    "snippet": row.get("summary") or "",
                }
            )
        return competitors

    @staticmethod
    def _secondary_keywords_from_audit(
        primary_keyword: str, audit_keywords: List[str]
    ) -> List[str]:
        keywords: List[str] = []
        seen = {str(primary_keyword or "").strip().lower()}
        for kw in audit_keywords:
            cleaned = str(kw or "").strip().lower()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            keywords.append(cleaned)
            if len(keywords) >= 10:
                break
        return keywords

    @staticmethod
    def _build_audited_context(
        audit: Audit, focus_url: str, internal_sources: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        target = getattr(audit, "target_audit", None) or {}
        if not isinstance(target, dict):
            target = {}
        content = (
            target.get("content", {}) if isinstance(target.get("content"), dict) else {}
        )
        return {
            "audited_domain": GeoArticleEngineService._normalize_domain(
                audit.url or audit.domain or ""
            ),
            "audited_url": audit.url,
            "focus_url": focus_url,
            "audited_page_paths": target.get("audited_page_paths", []),
            "internal_sources": internal_sources[:8],
            "content_summary": {
                "title": content.get("title"),
                "meta_description": content.get("meta_description"),
                "text_sample": content.get("text_sample"),
            },
            "site_metrics": target.get("site_metrics", {}),
            "structure": target.get("structure", {}),
            "eeat": target.get("eeat", {}),
        }

    @staticmethod
    def _find_invalid_citations(markdown: str, allowed_urls: List[str]) -> List[str]:
        if not markdown:
            return []
        allowed = {
            GeoArticleEngineService._normalize_url(url) for url in allowed_urls if url
        }
        if not allowed:
            return []
        pattern = re.compile(r"\[source:\s*([^\]]+)\]", re.IGNORECASE)
        url_pattern = re.compile(r"https?://[^\s,\]]+")
        invalid = []
        for match in pattern.findall(markdown):
            for url in url_pattern.findall(match):
                cleaned = url.strip()
                normalized = GeoArticleEngineService._normalize_url(cleaned)
                if normalized and normalized not in allowed:
                    invalid.append(cleaned)
        return invalid

    @staticmethod
    def _extract_citation_urls(markdown: str) -> List[str]:
        if not markdown:
            return []
        pattern = re.compile(r"\[source:\s*([^\]]+)\]", re.IGNORECASE)
        url_pattern = re.compile(r"https?://[^\s,\]]+")
        urls = set()
        for match in pattern.findall(markdown):
            for url in url_pattern.findall(match):
                cleaned = url.strip()
                if not cleaned:
                    continue
                normalized = GeoArticleEngineService._normalize_url(cleaned)
                if normalized:
                    urls.add(normalized)
        return [url for url in urls if url]

    @staticmethod
    def _append_required_citations(
        markdown: str,
        *,
        internal_urls: List[str],
        external_urls: List[str],
        user_authority_urls: Optional[List[str]] = None,
        language: str,
    ) -> str:
        if not markdown:
            return markdown
        internal = [url for url in internal_urls if url]
        external = [url for url in external_urls if url]
        user_authority = [url for url in (user_authority_urls or []) if url]
        if not internal and not external and not user_authority:
            return markdown
        section_title = (
            "## Fuentes" if language.lower().startswith("es") else "## Sources"
        )
        lines = [markdown.rstrip(), "", section_title]
        if internal:
            lines.append(f"- Audited internal reference. [Source: {internal[0]}]")
        if user_authority:
            label = (
                "Referencia de autoridad aportada por el usuario."
                if language.lower().startswith("es")
                else "User-provided authority reference."
            )
            lines.append(f"- {label} [Source: {user_authority[0]}]")
        if external:
            lines.append(f"- External reference for context. [Source: {external[0]}]")
        return "\n".join(lines)

    @staticmethod
    def _append_required_faq(
        markdown: str,
        *,
        min_pairs: int,
        internal_urls: List[str],
        external_urls: List[str],
        language: str,
    ) -> str:
        if not markdown:
            return markdown
        sources = [url for url in internal_urls if url] + [
            url for url in external_urls if url
        ]
        if not sources or min_pairs <= 0:
            return markdown
        heading = (
            "## Preguntas frecuentes" if language.lower().startswith("es") else "## FAQ"
        )
        questions_en = [
            "What pricing model is most common in the audited sources?",
            "What implementation requirements are noted in the audited sources?",
            "What evidence is available about outcomes or ROI?",
        ]
        questions_es = [
            "¿Qué modelo de precios es más común en las fuentes auditadas?",
            "¿Qué requisitos de implementación se mencionan en las fuentes auditadas?",
            "¿Qué evidencia hay sobre resultados o ROI?",
        ]
        questions = questions_es if language.lower().startswith("es") else questions_en
        qa_lines = []
        for idx in range(min_pairs):
            question = questions[idx % len(questions)]
            source = sources[idx % len(sources)]
            qa_lines.append(f"Q: {question}")
            qa_lines.append(
                f"A: Insufficient data in the audited sources. [Source: {source}]"
            )
            qa_lines.append("")
        block = "\n".join(qa_lines).rstrip()
        return "\n".join([markdown.rstrip(), "", heading, block])

    @staticmethod
    def _count_qa_pairs(markdown: str) -> int:
        if not markdown:
            return 0
        q_prefix = len(
            re.findall(
                r"^\s*(q|pregunta)\s*[:\-]",
                markdown,
                flags=re.IGNORECASE | re.MULTILINE,
            )
        )
        heading_questions = len(
            re.findall(r"^#{2,4}\s+[^\\n?]{3,}\\?$", markdown, flags=re.MULTILINE)
        )
        return max(q_prefix, heading_questions)

    @staticmethod
    def _has_required_qa(markdown: str, min_pairs: int) -> bool:
        if not markdown:
            return False
        has_header = bool(
            re.search(
                r"^##\s*(faq|preguntas frecuentes|preguntas y respuestas|q&a|questions)",
                markdown,
                flags=re.IGNORECASE | re.MULTILINE,
            )
        )
        pair_count = GeoArticleEngineService._count_qa_pairs(markdown)
        if pair_count >= min_pairs:
            return True
        if has_header and pair_count > 0:
            return True
        return False

    @staticmethod
    def _build_audit_signals(audit: Audit) -> Dict[str, Any]:
        target = getattr(audit, "target_audit", None) or {}
        site_metrics = (
            target.get("site_metrics", {}) if isinstance(target, dict) else {}
        )
        structure = target.get("structure", {}) if isinstance(target, dict) else {}
        eeat = target.get("eeat", {}) if isinstance(target, dict) else {}

        h1_check = structure.get("h1_check", {}) if isinstance(structure, dict) else {}
        author_presence = (
            eeat.get("author_presence", {}) if isinstance(eeat, dict) else {}
        )

        return {
            "geo_score": float(getattr(audit, "geo_score", 0) or 0),
            "structure_score_percent": float(
                site_metrics.get("structure_score_percent", 0) or 0
            ),
            "schema_coverage_percent": float(
                site_metrics.get("schema_coverage_percent", 0) or 0
            ),
            "h1_coverage_percent": float(
                site_metrics.get("h1_coverage_percent", 0) or 0
            ),
            "faq_page_count": int(site_metrics.get("faq_page_count", 0) or 0),
            "product_page_count": int(site_metrics.get("product_page_count", 0) or 0),
            "pages_analyzed": int(site_metrics.get("pages_analyzed", 0) or 0),
            "avg_semantic_score_percent": float(
                site_metrics.get("avg_semantic_score_percent", 0) or 0
            ),
            "conversational_tone_score": float(
                (
                    target.get("content", {})
                    .get("conversational_tone", {})
                    .get("score", 0)
                    if isinstance(target, dict)
                    else 0
                )
                or 0
            ),
            "h1_status": str(
                h1_check.get("status") or site_metrics.get("homepage_h1_status") or ""
            ).lower(),
            "author_presence_status": str(author_presence.get("status") or "").lower(),
        }

    @staticmethod
    def _build_competitor_gap_map(
        *,
        audit_signals: Dict[str, Any],
        top_competitors_for_keyword: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        schema = float(audit_signals.get("schema_coverage_percent", 0) or 0)
        structure = float(audit_signals.get("structure_score_percent", 0) or 0)
        semantic = float(audit_signals.get("avg_semantic_score_percent", 0) or 0)
        faq_pages = int(audit_signals.get("faq_page_count", 0) or 0)
        author_status = str(audit_signals.get("author_presence_status") or "")
        h1_status = str(audit_signals.get("h1_status") or "")
        competitor_domain = (
            top_competitors_for_keyword[0].get("domain")
            if top_competitors_for_keyword
            else "N/A"
        )

        content_gap = []
        if structure < 70:
            content_gap.append(
                {
                    "gap": f"Structure score is {structure:.1f}%, below competitive threshold for answer extraction.",
                    "impact": "Lower relevance in AI answers for commercial intent queries.",
                    "recommended_fix": "Restructure pages into concise Q/A and comparison blocks aligned with query intent.",
                }
            )
        if h1_status != "pass":
            content_gap.append(
                {
                    "gap": "H1 coverage is inconsistent across audited pages.",
                    "impact": "Primary topic clarity is diluted for ranking and citation systems.",
                    "recommended_fix": "Enforce one intent-aligned H1 per target page and tighten heading hierarchy.",
                }
            )

        schema_gap = []
        if schema < 70:
            schema_gap.append(
                {
                    "gap": f"Schema coverage is {schema:.1f}%, reducing machine-readable product context.",
                    "impact": "Lower eligibility for structured AI citation snippets.",
                    "recommended_fix": "Ship Product, FAQPage, Review and Offer schema on commercial URLs first.",
                }
            )

        eeat_gap = []
        if author_status != "pass":
            eeat_gap.append(
                {
                    "gap": "Author/expert transparency signals are weak or missing.",
                    "impact": "Reduced trust score against established competitors.",
                    "recommended_fix": "Add expert bylines, credentials and editorial policy references on strategic pages.",
                }
            )

        clarity_gap = []
        if semantic < 60:
            clarity_gap.append(
                {
                    "gap": f"Semantic clarity average is {semantic:.1f}%, with long fragments on key pages.",
                    "impact": "LLMs may skip citing because answer extraction confidence is low.",
                    "recommended_fix": "Shorten paragraphs, add explicit answer-first summaries and scannable subsections.",
                }
            )

        faq_gap = []
        if faq_pages == 0:
            faq_gap.append(
                {
                    "gap": "No FAQ page coverage detected for transactional/comparison intents.",
                    "impact": "Missed conversational query capture where competitor answers first.",
                    "recommended_fix": "Publish keyword-specific FAQ modules and mark them with FAQPage schema.",
                }
            )

        evidence_gap = [
            {
                "gap": f"{competitor_domain} currently owns top SERP real estate for this keyword cluster.",
                "impact": "Competitor receives citation preference and demand capture.",
                "recommended_fix": "Back claims with authority sources and first-party evidence blocks per keyword page.",
            }
        ]

        return {
            "content": content_gap,
            "schema": schema_gap,
            "eeat": eeat_gap,
            "clarity": clarity_gap,
            "faq": faq_gap,
            "evidence": evidence_gap,
        }

    @staticmethod
    def _extract_serp_sources(
        *,
        audit_domain: str,
        serp_results: List[Dict[str, Any]],
        topic_terms: Optional[List[str]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        top_competitors: List[Dict[str, Any]] = []
        external_sources: List[Dict[str, Any]] = []
        seen_urls = set()
        terms = topic_terms or []

        for row in serp_results:
            if not isinstance(row, dict):
                continue
            url = str(row.get("url") or "").strip()
            domain = str(row.get("domain") or "").strip().lower()
            normalized_domain = GeoArticleEngineService._normalize_domain(domain)
            title = str(row.get("title") or domain).strip()
            snippet = str(row.get("snippet") or "").strip()
            position = int(row.get("position") or len(top_competitors) + 1)
            if not url or not domain:
                continue
            if not normalized_domain:
                continue
            if not is_valid_competitor_domain(normalized_domain):
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)

            entry = {
                "position": position,
                "title": title,
                "url": url,
                "domain": normalized_domain,
                "snippet": snippet,
            }
            if GeoArticleEngineService._domain_matches(normalized_domain, audit_domain):
                continue

            top_competitors.append(entry)
            passes, meta = GeoArticleEngineService._passes_authority_filters(
                title=title,
                snippet=snippet,
                url=url,
                topic_terms=terms,
            )
            if not passes:
                continue
            external_sources.append(
                {
                    "title": title,
                    "url": url,
                    "domain": normalized_domain,
                    "snippet": snippet,
                    "source_type": "external",
                    "authority_score": meta.get("score", 0),
                    "authority_topic_hits": meta.get("topic_hits", 0),
                    "authority_has_qa_signal": meta.get("has_qa_signal", False),
                }
            )

        return top_competitors, GeoArticleEngineService._rank_authority_sources(
            external_sources
        )

    @staticmethod
    def _fallback_secondary_keywords(
        primary_keyword: str, serp_results: List[Dict[str, Any]]
    ) -> List[str]:
        candidates: List[str] = []
        seen = {primary_keyword.lower()}
        for row in serp_results[:8]:
            text = f"{row.get('title', '')} {row.get('snippet', '')}".lower()
            chunks = re.split(r"[\|\-:,;/]", text)
            for chunk in chunks:
                cleaned = " ".join(re.findall(r"[a-zA-Z0-9]+", chunk)).strip()
                if len(cleaned) < 6:
                    continue
                if cleaned in GeoArticleEngineService.STOPWORDS:
                    continue
                if cleaned in seen:
                    continue
                seen.add(cleaned)
                candidates.append(cleaned)
                if len(candidates) >= 8:
                    return candidates
        return candidates

    @staticmethod
    async def _expand_keywords_with_llm(
        *,
        llm_function: callable,
        primary_keyword: str,
        market: str,
        language: str,
        serp_results: List[Dict[str, Any]],
    ) -> Tuple[List[str], str]:
        system_prompt = (
            "You are a senior SEO+GEO keyword strategist. "
            "Return strict JSON only and never invent ranking data."
        )
        user_prompt = json.dumps(
            {
                "task": "Generate secondary keywords from SERP evidence and infer search intent.",
                "primary_keyword": primary_keyword,
                "market": market,
                "language": language,
                "serp_snapshot": serp_results[:8],
                "output_schema": {
                    "secondary_keywords": ["string"],
                    "search_intent": "informational|commercial|transactional|comparison",
                },
                "constraints": [
                    "Use only the provided SERP evidence.",
                    "Return 5 to 10 secondary keywords.",
                    "No fabricated volumes or metrics.",
                ],
            },
            ensure_ascii=False,
        )

        raw = await llm_function(system_prompt=system_prompt, user_prompt=user_prompt)
        payload = GeoArticleEngineService._safe_json_dict(raw or "")
        if not payload:
            return [], ""

        keywords = []
        seen = {primary_keyword.lower()}
        for kw in payload.get("secondary_keywords", []):
            cleaned = str(kw or "").strip().lower()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            keywords.append(cleaned)

        intent = str(payload.get("search_intent") or "").strip().lower()
        return keywords[:10], intent

    @staticmethod
    def _infer_intent(primary_keyword: str) -> str:
        keyword = (primary_keyword or "").lower()
        if any(token in keyword for token in ["vs", "versus", "compar", "alternativ"]):
            return "comparison"
        if any(
            token in keyword
            for token in ["buy", "price", "precio", "shop", "best", "mejor"]
        ):
            return "commercial"
        if any(
            token in keyword for token in ["how", "como", "guide", "tutorial", "guia"]
        ):
            return "informational"
        return "commercial"

    @staticmethod
    def _select_required_sources(
        *,
        focus_url: str,
        internal_sources: List[Dict[str, str]],
        external_sources: List[Dict[str, str]],
        fallback_external_sources: List[Dict[str, str]],
        user_authority_sources: Optional[List[Dict[str, Any]]] = None,
        audit_only: bool = False,
    ) -> Dict[str, List[Dict[str, str]]]:
        ordered_internal: List[Dict[str, str]] = []
        seen_internal = set()
        for item in internal_sources:
            url = str(item.get("url") or "").strip()
            if not url or url in seen_internal:
                continue
            if url == focus_url:
                ordered_internal.insert(0, item)
            else:
                ordered_internal.append(item)
            seen_internal.add(url)

        selected_internal = ordered_internal[
            : GeoArticleEngineService.MIN_INTERNAL_SOURCES
        ]
        if len(selected_internal) < GeoArticleEngineService.MIN_INTERNAL_SOURCES:
            raise InsufficientAuthoritySourcesError(
                "Need at least 2 internal audited sources per article."
            )

        selected_user_authority: List[Dict[str, str]] = []
        for item in user_authority_sources or []:
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            selected_user_authority.append(item)

        selected_external: List[Dict[str, str]] = list(selected_user_authority)
        if not audit_only:
            merged_external = []
            seen_external = set()
            for source_pool in (
                user_authority_sources or [],
                external_sources,
                fallback_external_sources,
            ):
                for item in source_pool:
                    url = str(item.get("url") or "").strip()
                    if not url or url in seen_external:
                        continue
                    seen_external.add(url)
                    merged_external.append(item)

            max_allowed_external = max(
                GeoArticleEngineService.MIN_EXTERNAL_SOURCES,
                int(getattr(settings, "GEO_ARTICLE_ALLOWED_EXTERNAL_SOURCES", 8)),
            )
            selected_external = merged_external[:max_allowed_external]
            if len(selected_external) < GeoArticleEngineService.MIN_EXTERNAL_SOURCES:
                raise InsufficientAuthoritySourcesError(
                    "Need at least 3 external authority sources per article."
                )

        return {
            "internal": selected_internal,
            "external": selected_external,
            "user_authority": selected_user_authority,
            "all": selected_internal + selected_external,
        }

    @staticmethod
    def _validate_article_data_pack(pack: Dict[str, Any]) -> None:
        audit_only = GeoArticleEngineService._audit_only_mode()
        missing = []
        required_fields = [
            "keyword_strategy",
            "market",
            "language",
            "focus_url",
            "competitor_gap_map",
            "required_sources",
            "audit_signals",
        ]
        for field in required_fields:
            value = pack.get(field)
            if value is None or value == "" or value == []:
                missing.append(field)

        strategy = pack.get("keyword_strategy", {})
        if not isinstance(strategy, dict):
            missing.append("keyword_strategy")
        else:
            if not str(strategy.get("primary_keyword") or "").strip():
                missing.append("keyword_strategy.primary_keyword")
            secondary = strategy.get("secondary_keywords", [])
            if not isinstance(secondary, list) or len(secondary) < 2:
                missing.append("keyword_strategy.secondary_keywords")
            if not str(strategy.get("search_intent") or "").strip():
                missing.append("keyword_strategy.search_intent")

        required_sources = pack.get("required_sources", {})
        if isinstance(required_sources, dict):
            internal = required_sources.get("internal", [])
            external = required_sources.get("external", [])
            if len(internal) < GeoArticleEngineService.MIN_INTERNAL_SOURCES:
                missing.append("required_sources.internal")
            if (
                not audit_only
                and len(external) < GeoArticleEngineService.MIN_EXTERNAL_SOURCES
            ):
                missing.append("required_sources.external")
        else:
            missing.append("required_sources")

        competitors = pack.get("top_competitors_for_keyword", [])
        if competitors is not None and not isinstance(competitors, list):
            missing.append("top_competitors_for_keyword")

        if missing:
            raise ArticleDataPackIncompleteError(
                "ARTICLE_DATA_PACK_INCOMPLETE: missing required fields -> "
                + ", ".join(sorted(set(missing)))
            )

    @staticmethod
    async def _build_article_data_pack(
        *,
        audit: Audit,
        primary_keyword: str,
        market: str,
        language: str,
        focus_url: str,
        llm_function: callable,
        internal_sources: List[Dict[str, str]],
        fallback_external_sources: List[Dict[str, str]],
        ai_strategy_item: Optional[Dict[str, Any]],
        user_authority_sources: Optional[List[Dict[str, Any]]] = None,
        audit_keywords: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        audit_domain = GeoArticleEngineService._normalize_domain(
            audit.url or audit.domain or ""
        )
        if not audit_domain:
            raise ArticleDataPackIncompleteError(
                "ARTICLE_DATA_PACK_INCOMPLETE: unable to resolve audited domain."
            )

        audit_only = GeoArticleEngineService._audit_only_mode()
        topic_terms = GeoArticleEngineService._extract_topic_terms(
            audit=audit, primary_keyword=primary_keyword
        )
        target = getattr(audit, "target_audit", None) or {}
        external_intelligence = getattr(audit, "external_intelligence", None) or {}
        if not isinstance(target, dict):
            target = {}
        if not isinstance(external_intelligence, dict):
            external_intelligence = {}
        vertical_hint = infer_vertical_hint(
            external_intelligence.get("category"),
            external_intelligence.get("subcategory"),
            target.get("category"),
            target.get("subcategory"),
            getattr(audit, "category", None),
        )
        serp_results: List[Dict[str, Any]] = []
        external_from_serp: List[Dict[str, Any]] = []
        top_competitors: List[Dict[str, Any]] = (
            GeoArticleEngineService._extract_competitors_from_audit(
                audit=audit,
                audit_domain=audit_domain,
                vertical_hint=vertical_hint,
            )
        )
        inferred_intent = ""
        secondary_keywords: List[str] = []

        if audit_only:
            audit_keywords = (
                audit_keywords or GeoArticleEngineService._extract_audit_keywords(audit)
            )
            secondary_keywords = GeoArticleEngineService._secondary_keywords_from_audit(
                primary_keyword, audit_keywords
            )
        else:
            search_payload = await kimi_search_serp(
                query=primary_keyword,
                market=market,
                top_k=GeoArticleEngineService.DEFAULT_TOP_K,
                language=language,
            )
            serp_results = (
                search_payload.get("results", [])
                if isinstance(search_payload, dict)
                else []
            )
            if not isinstance(serp_results, list) or not serp_results:
                raise ArticleDataPackIncompleteError(
                    "ARTICLE_DATA_PACK_INCOMPLETE: Kimi Search returned no SERP results."
                )

            (
                _serp_competitors,
                external_from_serp,
            ) = GeoArticleEngineService._extract_serp_sources(
                audit_domain=audit_domain,
                serp_results=serp_results,
                topic_terms=topic_terms,
            )

            existing_external = GeoArticleEngineService._unique_source_count(
                external_from_serp, fallback_external_sources
            )
            extra_queries = []
            if existing_external < GeoArticleEngineService.MIN_EXTERNAL_SOURCES:
                extra_queries = GeoArticleEngineService._build_authority_search_queries(
                    primary_keyword=primary_keyword,
                    brand_token=GeoArticleEngineService._extract_brand_token(audit),
                    topic_terms=topic_terms,
                    language=language,
                    max_queries=int(
                        getattr(settings, "GEO_ARTICLE_EXTRA_SEARCH_QUERIES", 3)
                    ),
                )

            extra_searches: List[Dict[str, Any]] = []
            if extra_queries:
                logger.info(
                    "Authority source shortfall. Running extra searches for keyword=%s queries=%s",
                    primary_keyword,
                    extra_queries,
                )
                for query in extra_queries:
                    try:
                        extra_payload = await kimi_search_serp(
                            query=query,
                            market=market,
                            top_k=int(
                                getattr(
                                    settings,
                                    "GEO_ARTICLE_EXTRA_SEARCH_TOP_K",
                                    GeoArticleEngineService.DEFAULT_TOP_K,
                                )
                            ),
                            language=language,
                        )
                    except Exception as search_err:
                        logger.warning(
                            "Extra authority search failed for query=%s error=%s",
                            query,
                            search_err,
                        )
                        continue

                    extra_results = (
                        extra_payload.get("results", [])
                        if isinstance(extra_payload, dict)
                        else []
                    )
                    if not isinstance(extra_results, list) or not extra_results:
                        continue

                    _, extra_sources = GeoArticleEngineService._extract_serp_sources(
                        audit_domain=audit_domain,
                        serp_results=extra_results,
                        topic_terms=topic_terms,
                    )
                    external_from_serp = GeoArticleEngineService._merge_unique_sources(
                        external_from_serp, extra_sources
                    )
                    extra_searches.append(
                        {
                            "query": query,
                            "provider": extra_payload.get("provider", ""),
                            "results": extra_results[
                                : GeoArticleEngineService.DEFAULT_TOP_K
                            ],
                        }
                    )
                    if (
                        GeoArticleEngineService._unique_source_count(
                            external_from_serp, fallback_external_sources
                        )
                        >= GeoArticleEngineService.MIN_EXTERNAL_SOURCES
                    ):
                        break

            (
                secondary_keywords,
                inferred_intent,
            ) = await GeoArticleEngineService._expand_keywords_with_llm(
                llm_function=llm_function,
                primary_keyword=primary_keyword,
                market=market,
                language=language,
                serp_results=serp_results,
            )
            if not secondary_keywords:
                secondary_keywords = (
                    GeoArticleEngineService._fallback_secondary_keywords(
                        primary_keyword, serp_results
                    )
                )

        secondary_keywords = [
            kw
            for kw in secondary_keywords
            if kw and kw.lower() != primary_keyword.lower()
        ][:10]
        if len(secondary_keywords) < 2:
            raise ArticleDataPackIncompleteError(
                "ARTICLE_DATA_PACK_INCOMPLETE: keyword expansion did not produce enough secondary keywords."
            )

        search_intent = inferred_intent or GeoArticleEngineService._infer_intent(
            primary_keyword
        )
        audit_signals = GeoArticleEngineService._build_audit_signals(audit)
        competitor_gap_map = GeoArticleEngineService._build_competitor_gap_map(
            audit_signals=audit_signals,
            top_competitors_for_keyword=top_competitors,
        )

        required_sources = GeoArticleEngineService._select_required_sources(
            focus_url=focus_url,
            internal_sources=internal_sources,
            external_sources=external_from_serp,
            fallback_external_sources=fallback_external_sources,
            user_authority_sources=user_authority_sources,
            audit_only=audit_only,
        )
        audited_context = GeoArticleEngineService._build_audited_context(
            audit=audit, focus_url=focus_url, internal_sources=internal_sources
        )

        pack = {
            "keyword_strategy": {
                "primary_keyword": primary_keyword,
                "secondary_keywords": secondary_keywords,
                "search_intent": search_intent,
                "strategy_mode": (
                    "audit_only" if audit_only else "audit_plus_kimi_search_expansion"
                ),
            },
            "market": market,
            "language": language,
            "focus_url": focus_url,
            "top_competitors_for_keyword": top_competitors[:5],
            "competitor_gap_map": competitor_gap_map,
            "required_sources": required_sources,
            "audit_signals": audit_signals,
            "serp_results": serp_results[: GeoArticleEngineService.DEFAULT_TOP_K],
            "evidence": [] if audit_only else search_payload.get("evidence", []),
            "provider": (
                "audit-only"
                if audit_only
                else search_payload.get("provider", "kimi-2.5-search")
            ),
            "ai_content_strategy": ai_strategy_item or {},
            "audited_context": audited_context,
            "topic_terms": topic_terms,
            "extra_searches": extra_searches if not audit_only else [],
            "user_authority_context": [
                {
                    "title": str(source.get("title") or "").strip(),
                    "url": str(source.get("url") or "").strip(),
                    "excerpt": str(source.get("excerpt") or "").strip(),
                }
                for source in (required_sources.get("user_authority") or [])
            ],
        }
        GeoArticleEngineService._validate_article_data_pack(pack)
        return pack

    @staticmethod
    def _ensure_competitor_section(markdown: str, data_pack: Dict[str, Any]) -> str:
        content = (markdown or "").strip()
        required_header = "## How to beat top competitor for this keyword"
        if required_header.lower() in content.lower():
            return content

        competitors = data_pack.get("top_competitors_for_keyword")
        competitor = "N/A"
        if isinstance(competitors, list) and competitors:
            competitor = str(competitors[0].get("domain") or "").strip() or "N/A"
        schema_gaps = data_pack.get("competitor_gap_map", {}).get("schema", [])
        content_gaps = data_pack.get("competitor_gap_map", {}).get("content", [])
        recommendations: List[str] = []
        if schema_gaps:
            recommendations.append(
                f"- Fix schema gap first: {schema_gaps[0].get('recommended_fix', 'Improve schema coverage.')}"
            )
        if content_gaps:
            recommendations.append(
                f"- Upgrade content structure: {content_gaps[0].get('recommended_fix', 'Improve answer blocks.')}"
            )
        if not recommendations:
            recommendations.append(
                "- Publish stronger evidence-led comparison modules and FAQ blocks."
            )

        return (
            f"{content}\n\n"
            f"{required_header}\n"
            f"- Current top competitor: `{competitor}`.\n"
            + "\n".join(recommendations)
            + "\n"
        )

    @staticmethod
    def _citation_score(markdown: str, include_schema: bool, sources_count: int) -> int:
        text = markdown or ""
        source_tags = len(
            re.findall(r"\[source:\s*https?://[^\]]+\]", text, flags=re.IGNORECASE)
        )
        faq_section = "faq" in text.lower()
        competitor_section = (
            "how to beat top competitor for this keyword" in text.lower()
        )

        score = 30
        score += min(30, source_tags * 6)
        score += min(20, max(0, sources_count - 2) * 4)
        score += 10 if faq_section else 0
        score += 10 if competitor_section else 0
        score += 5 if include_schema else 0
        return max(0, min(100, score))

    @staticmethod
    async def _generate_article_content(
        *,
        llm_function: callable,
        data_pack: Dict[str, Any],
        tone: str,
        include_schema: bool,
        language: str,
    ) -> Dict[str, Any]:
        ai_strategy = data_pack.get("ai_content_strategy", {})
        title_hint = str(ai_strategy.get("title") or "").strip()
        if not title_hint:
            primary_kw = data_pack.get("keyword_strategy", {}).get(
                "primary_keyword", "keyword"
            )
            title_hint = f"{primary_kw.title()}: GEO + SEO Playbook"
        section_hints = ai_strategy.get("sections", [])
        section_hints = [str(s).strip() for s in section_hints if str(s).strip()]
        audit_only = (
            str(data_pack.get("provider") or "").lower() == "audit-only"
            or str(
                data_pack.get("keyword_strategy", {}).get("strategy_mode") or ""
            ).lower()
            == "audit_only"
        )
        require_qa = bool(
            getattr(settings, "GEO_ARTICLE_REQUIRE_QA", True)
            and data_pack.get("required_sources", {}).get("external")
        )
        min_qa_pairs = max(1, int(getattr(settings, "GEO_ARTICLE_MIN_QA_PAIRS", 3)))
        allowed_sources = [
            src.get("url")
            for src in data_pack.get("required_sources", {}).get("all", [])
            if isinstance(src, dict) and src.get("url")
        ]
        user_authority_urls = {
            GeoArticleEngineService._normalize_url(str(src.get("url") or ""))
            for src in data_pack.get("required_sources", {}).get("user_authority", [])
            if isinstance(src, dict) and src.get("url")
        }
        require_user_authority = bool(user_authority_urls)

        current_year = datetime.now().year
        system_prompt = (
            f"You are a senior GEO + SEO editorial strategist. Current year is {current_year}. "
            "Write production-ready articles only from the provided evidence. "
            "Never fabricate data. Return strict JSON only."
        )
        if audit_only:
            system_prompt += (
                " Use ONLY audited context and internal audited sources. "
                "Do not reference or cite any external websites not explicitly listed."
            )
        user_prompt = json.dumps(
            {
                "task": "Generate a complete GEO/SEO article ready to publish.",
                "language": language,
                "tone": tone,
                "include_schema": include_schema,
                "article_data_pack": data_pack,
                "audited_context": data_pack.get("audited_context", {}),
                "allowed_sources": allowed_sources,
                "user_authority_context": data_pack.get("user_authority_context", []),
                "title_hint": title_hint,
                "section_hints": section_hints,
                "mandatory_section_heading": "How to beat top competitor for this keyword",
                "qa_requirements": {
                    "required": require_qa,
                    "min_pairs": min_qa_pairs,
                    "section_heading": (
                        "Preguntas frecuentes"
                        if language.lower().startswith("es")
                        else "FAQ"
                    ),
                    "format": "Use question headings or Q:/A: pairs.",
                },
                "citation_format": "[Source: https://...]",
                "constraints": [
                    f"Write content relevant for {current_year}, avoiding outdated year references unless historical.",
                    "Use only audited evidence and required sources.",
                    "Map every major claim to source tags.",
                    "Do not invent competitors, metrics or sources.",
                    "Write full article content, not an outline.",
                    "If a claim cannot be supported by the audited sources, label it as 'Insufficient data'.",
                    "If external sources are provided, include a dedicated Q&A/FAQ section with citations.",
                    "Every Q&A answer should include at least one source citation.",
                    f"Use the exact title_hint as the final article title: {title_hint}",
                    "Do not rewrite or replace the title_hint.",
                ],
                "output_schema": {
                    "title": "string",
                    "markdown": "string",
                    "meta_title": "string",
                    "meta_description": "string",
                    "schema_json": {"optional": "object"},
                    "evidence_summary": [
                        {
                            "claim": "string",
                            "source_url": "https://...",
                        }
                    ],
                },
            },
            ensure_ascii=False,
        )

        raw = await llm_function(system_prompt=system_prompt, user_prompt=user_prompt)
        output_schema = {
            "title": "string",
            "markdown": "string",
            "meta_title": "string",
            "meta_description": "string",
            "schema_json": {"optional": "object"},
            "evidence_summary": [
                {
                    "claim": "string",
                    "source_url": "https://...",
                }
            ],
        }
        parsed = GeoArticleEngineService._safe_json_dict(raw or "")
        if not parsed:
            parsed = await GeoArticleEngineService._repair_article_json(
                llm_function=llm_function,
                raw_text=raw or "",
                output_schema=output_schema,
                language=language,
            )
        if not parsed:
            raise KimiGenerationError(
                "Kimi returned invalid JSON while generating article content."
            )

        markdown = str(parsed.get("markdown") or "").strip()
        if not markdown:
            raise KimiGenerationError("Kimi returned empty article markdown.")

        invalid_citations = GeoArticleEngineService._find_invalid_citations(
            markdown, allowed_sources
        )
        citation_urls = GeoArticleEngineService._extract_citation_urls(markdown)
        internal_urls = {
            GeoArticleEngineService._normalize_url(str(src.get("url") or ""))
            for src in data_pack.get("required_sources", {}).get("internal", [])
            if isinstance(src, dict) and src.get("url")
        }
        external_urls = {
            GeoArticleEngineService._normalize_url(str(src.get("url") or ""))
            for src in data_pack.get("required_sources", {}).get("external", [])
            if isinstance(src, dict) and src.get("url")
        }
        require_internal = bool(
            getattr(settings, "GEO_ARTICLE_REQUIRE_INTERNAL_CITATION", True)
            and internal_urls
        )
        require_external = bool(
            getattr(settings, "GEO_ARTICLE_REQUIRE_EXTERNAL_CITATION", True)
            and external_urls
        )
        missing_internal = require_internal and not internal_urls.intersection(
            citation_urls
        )
        missing_external = require_external and not external_urls.intersection(
            citation_urls
        )
        missing_user_authority = (
            require_user_authority
            and not user_authority_urls.intersection(citation_urls)
        )
        missing_qa = require_qa and not GeoArticleEngineService._has_required_qa(
            markdown, min_pairs=min_qa_pairs
        )

        needs_repair = (
            invalid_citations
            or missing_internal
            or missing_external
            or missing_user_authority
            or missing_qa
        )
        if needs_repair and getattr(
            settings, "GEO_ARTICLE_REPAIR_INVALID_CITATIONS", True
        ):
            internal_required = [
                src.get("url")
                for src in data_pack.get("required_sources", {}).get("internal", [])
                if isinstance(src, dict) and src.get("url")
            ]
            external_required = [
                src.get("url")
                for src in data_pack.get("required_sources", {}).get("external", [])
                if isinstance(src, dict) and src.get("url")
            ]
            repaired_markdown = await GeoArticleEngineService._repair_invalid_citations(
                llm_function=llm_function,
                markdown=markdown,
                allowed_sources=allowed_sources,
                required_internal_sources=internal_required,
                required_external_sources=external_required,
                language=language,
                qa_requirements={
                    "required": require_qa,
                    "min_pairs": min_qa_pairs,
                    "section_heading": (
                        "Preguntas frecuentes"
                        if language.lower().startswith("es")
                        else "FAQ"
                    ),
                },
            )
            if repaired_markdown:
                markdown = repaired_markdown
            invalid_citations = GeoArticleEngineService._find_invalid_citations(
                markdown, allowed_sources
            )
            citation_urls = GeoArticleEngineService._extract_citation_urls(markdown)
            missing_internal = require_internal and not internal_urls.intersection(
                citation_urls
            )
            missing_external = require_external and not external_urls.intersection(
                citation_urls
            )
            missing_user_authority = (
                require_user_authority
                and not user_authority_urls.intersection(citation_urls)
            )
            missing_qa = require_qa and not GeoArticleEngineService._has_required_qa(
                markdown, min_pairs=min_qa_pairs
            )

        if getattr(settings, "GEO_ARTICLE_REPAIR_INVALID_CITATIONS", True) and (
            missing_internal or missing_external or missing_user_authority
        ):
            markdown = GeoArticleEngineService._append_required_citations(
                markdown,
                internal_urls=sorted(internal_urls),
                external_urls=sorted(external_urls),
                user_authority_urls=sorted(user_authority_urls),
                language=language,
            )
            citation_urls = GeoArticleEngineService._extract_citation_urls(markdown)
            missing_internal = require_internal and not internal_urls.intersection(
                citation_urls
            )
            missing_external = require_external and not external_urls.intersection(
                citation_urls
            )
            missing_user_authority = (
                require_user_authority
                and not user_authority_urls.intersection(citation_urls)
            )
        if (
            getattr(settings, "GEO_ARTICLE_REPAIR_INVALID_CITATIONS", True)
            and missing_qa
        ):
            markdown = GeoArticleEngineService._append_required_faq(
                markdown,
                min_pairs=min_qa_pairs,
                internal_urls=sorted(internal_urls),
                external_urls=sorted(external_urls),
                language=language,
            )
            missing_qa = require_qa and not GeoArticleEngineService._has_required_qa(
                markdown, min_pairs=min_qa_pairs
            )

        if invalid_citations:
            raise KimiGenerationError(
                "Article cites sources outside the audited evidence set."
            )
        if missing_internal:
            raise KimiGenerationError("Article missing required internal citations.")
        if missing_external:
            raise KimiGenerationError("Article missing required external citations.")
        if missing_user_authority:
            raise KimiGenerationError(
                "Article missing required user authority citation."
            )
        if missing_qa:
            raise KimiGenerationError("Article missing required Q&A/FAQ section.")

        markdown = GeoArticleEngineService._ensure_competitor_section(
            markdown, data_pack
        )
        title = title_hint

        primary_kw = data_pack.get("keyword_strategy", {}).get("primary_keyword", "")
        meta_title = str(parsed.get("meta_title") or title).strip()
        meta_description = str(parsed.get("meta_description") or "").strip()
        if not meta_description:
            meta_description = f"Actionable GEO and SEO strategy for {primary_kw} with competitor gap closure and source-backed recommendations."
        meta_description = meta_description[:160]

        citation_urls = GeoArticleEngineService._extract_citation_urls(markdown)
        evidence_summary = parsed.get("evidence_summary", [])
        normalized_evidence: List[Dict[str, str]] = []
        if isinstance(evidence_summary, list):
            for item in evidence_summary:
                if not isinstance(item, dict):
                    continue
                claim = str(item.get("claim") or "").strip()
                source_url = GeoArticleEngineService._normalize_url(
                    str(item.get("source_url") or "").strip()
                )
                if claim and source_url and source_url in citation_urls:
                    normalized_evidence.append(
                        {"claim": claim, "source_url": source_url}
                    )
        if not normalized_evidence:
            for src in data_pack.get("required_sources", {}).get("user_authority", [])[
                :1
            ]:
                normalized_evidence.append(
                    {
                        "claim": "User-provided authority reference used in article rationale.",
                        "source_url": src.get("url", ""),
                    }
                )
            for src in data_pack.get("required_sources", {}).get("external", [])[:3]:
                normalized_evidence.append(
                    {
                        "claim": "External benchmark reference used in article rationale.",
                        "source_url": src.get("url", ""),
                    }
                )

        schema_json = parsed.get("schema_json")
        if include_schema and not isinstance(schema_json, dict):
            schema_json = {
                "@context": "https://schema.org",
                "@type": "Article",
                "headline": title,
                "mainEntityOfPage": data_pack.get("focus_url"),
                "inLanguage": "es" if language.lower().startswith("es") else "en",
            }
        if not include_schema:
            schema_json = None

        return {
            "title": title,
            "markdown": markdown,
            "meta_title": meta_title,
            "meta_description": meta_description,
            "schema_json": schema_json,
            "evidence_summary": normalized_evidence,
        }

    @staticmethod
    def _error_payload(exc: Exception) -> Dict[str, str]:
        if isinstance(exc, LegacyBatchReadOnlyError):
            return {
                "code": "LEGACY_BATCH_READ_ONLY",
                "message": str(exc),
            }
        if isinstance(exc, ArticleStrategyRequiredError):
            return {
                "code": "ARTICLE_STRATEGY_REQUIRED",
                "message": str(exc),
            }
        if isinstance(exc, InsufficientAuthoritySourcesError):
            return {
                "code": "INSUFFICIENT_AUTHORITY_SOURCES",
                "message": str(exc),
            }
        if isinstance(exc, ArticleDataPackIncompleteError):
            return {
                "code": "ARTICLE_DATA_PACK_INCOMPLETE",
                "message": str(exc),
            }
        if isinstance(exc, (KimiUnavailableError, KimiSearchUnavailableError)):
            return {
                "code": "KIMI_UNAVAILABLE",
                "message": str(exc),
            }
        if isinstance(exc, (KimiGenerationError, KimiSearchError)):
            return {
                "code": "KIMI_GENERATION_FAILED",
                "message": str(exc),
            }
        return {
            "code": "ARTICLE_GENERATION_FAILED",
            "message": str(exc),
        }

    @staticmethod
    def _serialize_batch(batch: GeoArticleBatch) -> Dict[str, Any]:
        is_legacy = GeoArticleEngineService._is_legacy_batch(batch)
        return {
            "batch_id": batch.id,
            "audit_id": batch.audit_id,
            "created_at": batch.created_at.isoformat() if batch.created_at else None,
            "status": batch.status,
            "summary": GeoArticleEngineService._public_batch_summary(batch.summary),
            "articles": batch.articles or [],
            "is_legacy": is_legacy,
            "can_regenerate": not is_legacy,
        }

    @staticmethod
    def _public_batch_summary(summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(summary, dict):
            return {}
        return {
            str(key): value
            for key, value in summary.items()
            if isinstance(key, str) and not key.startswith("_")
        }

    @staticmethod
    def _serialize_compact_article(article: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "index": int(article.get("index") or 0),
            "title": str(article.get("title") or "").strip(),
            "target_keyword": str(article.get("target_keyword") or "").strip(),
            "focus_url": str(article.get("focus_url") or "").strip(),
            "generation_status": str(article.get("generation_status") or "").strip(),
            "generation_error": (
                dict(article.get("generation_error"))
                if isinstance(article.get("generation_error"), dict)
                else article.get("generation_error")
            ),
            "citation_readiness_score": float(
                article.get("citation_readiness_score") or 0
            ),
            "user_authority_urls": [
                str(url).strip()
                for url in (article.get("user_authority_urls") or [])
                if str(url).strip()
            ],
        }

    @staticmethod
    def _serialize_batch_status(batch: GeoArticleBatch) -> Dict[str, Any]:
        is_legacy = GeoArticleEngineService._is_legacy_batch(batch)
        return {
            "batch_id": batch.id,
            "audit_id": batch.audit_id,
            "created_at": batch.created_at.isoformat() if batch.created_at else None,
            "status": batch.status,
            "summary": GeoArticleEngineService._public_batch_summary(batch.summary),
            "articles": [
                GeoArticleEngineService._serialize_compact_article(article)
                for article in (batch.articles or [])
                if isinstance(article, dict)
            ],
            "is_legacy": is_legacy,
            "can_regenerate": not is_legacy,
        }

    @staticmethod
    def article_batch_channel(batch_id: int) -> str:
        return f"article.batch.{int(batch_id)}"

    @staticmethod
    def article_batch_snapshot_key(batch_id: int) -> str:
        return f"article:batch:{int(batch_id)}:status"

    @staticmethod
    def get_batch_status_projection(
        db: Session, batch_id: int
    ) -> Optional[GeoArticleBatch]:
        return (
            db.query(GeoArticleBatch)
            .options(
                load_only(
                    GeoArticleBatch.id,
                    GeoArticleBatch.audit_id,
                    GeoArticleBatch.status,
                    GeoArticleBatch.summary,
                    GeoArticleBatch.created_at,
                )
            )
            .filter(GeoArticleBatch.id == batch_id)
            .first()
        )

    @staticmethod
    def cache_batch_status_payload(payload: Dict[str, Any] | None) -> None:
        from app.services.cache_service import cache

        if not isinstance(payload, dict) or not cache.enabled:
            return
        batch_id = payload.get("batch_id")
        try:
            normalized_batch_id = int(batch_id)
        except (TypeError, ValueError):
            return
        cache.set(
            GeoArticleEngineService.article_batch_snapshot_key(normalized_batch_id),
            payload,
            ttl=max(
                60,
                int(
                    getattr(
                        settings,
                        "GEO_ARTICLE_STATUS_SNAPSHOT_TTL_SECONDS",
                        GeoArticleEngineService.STATUS_SNAPSHOT_TTL_SECONDS,
                    )
                    or GeoArticleEngineService.STATUS_SNAPSHOT_TTL_SECONDS
                ),
            ),
        )

    @staticmethod
    def get_cached_batch_status_payload(batch_id: int) -> Optional[Dict[str, Any]]:
        from app.services.cache_service import cache

        if not cache.enabled:
            return None
        payload = cache.get(
            GeoArticleEngineService.article_batch_snapshot_key(batch_id)
        )
        if not isinstance(payload, dict):
            return None
        try:
            if int(payload.get("batch_id")) != int(batch_id):
                return None
        except (TypeError, ValueError):
            return None
        return payload

    @staticmethod
    def invalidate_batch_status_payload(batch_id: int) -> None:
        from app.services.cache_service import cache

        if not cache.enabled:
            return
        cache.delete(GeoArticleEngineService.article_batch_snapshot_key(batch_id))

    @staticmethod
    def batch_status_payload_requires_refresh(payload: Dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return True
        status = str(payload.get("status") or "").strip().lower()
        if status in {"completed", "failed", "partial_failed"}:
            return False
        summary = (
            payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        )
        last_progress_raw = summary.get("last_progress_at")
        if not isinstance(last_progress_raw, str) or not last_progress_raw.strip():
            return True
        try:
            last_progress = datetime.fromisoformat(
                last_progress_raw.replace("Z", "+00:00")
            )
        except ValueError:
            return True
        if last_progress.tzinfo is None:
            last_progress = last_progress.replace(tzinfo=timezone.utc)
        else:
            last_progress = last_progress.astimezone(timezone.utc)
        stale_after = max(
            1,
            int(
                getattr(
                    settings,
                    "GEO_ARTICLE_STATUS_STALE_FALLBACK_SECONDS",
                    max(
                        int(
                            getattr(settings, "SSE_FALLBACK_DB_INTERVAL_SECONDS", 10)
                            or 10
                        ),
                        GeoArticleEngineService.STATUS_STALE_FALLBACK_SECONDS,
                    ),
                )
                or GeoArticleEngineService.STATUS_STALE_FALLBACK_SECONDS
            ),
        )
        return datetime.now(timezone.utc) - last_progress > timedelta(
            seconds=stale_after
        )

    @staticmethod
    def publish_batch_status_payload(payload: Dict[str, Any] | None) -> None:
        from app.services.cache_service import cache

        if not isinstance(payload, dict):
            return
        GeoArticleEngineService.cache_batch_status_payload(payload)
        if not cache.enabled or not cache.redis_client:
            return
        try:
            cache.redis_client.publish(
                GeoArticleEngineService.article_batch_channel(
                    int(payload.get("batch_id") or 0)
                ),
                json.dumps(payload, default=str),
            )
        except Exception as exc:  # nosec B110
            logger.warning("Error publishing article batch status to Redis: %s", exc)

    @staticmethod
    def publish_batch_status_for_batch(batch: GeoArticleBatch) -> None:
        GeoArticleEngineService.publish_batch_status_payload(
            GeoArticleEngineService._serialize_batch_status(batch)
        )

    @staticmethod
    def create_batch(
        *,
        db: Session,
        audit: Audit,
        article_count: int,
        language: str = "en",
        tone: str = "executive",
        include_schema: bool = True,
        market: Optional[str] = None,
        strategy_run_id: Optional[str] = None,
        strategy_items: Optional[List[Dict[str, Any]]] = None,
        strategy_source: str = "reused_latest",
        article_authority_assignments: Optional[Dict[int, List[str]]] = None,
        global_authority_urls: Optional[List[str]] = None,
        unmatched_authority_urls: Optional[List[str]] = None,
        authority_source_cache: Optional[List[Dict[str, Any]]] = None,
    ) -> GeoArticleBatch:
        if not is_kimi_configured():
            raise KimiUnavailableError(
                "Kimi provider is not configured. Set NV_API_KEY_ANALYSIS or NVIDIA_API_KEY or NV_API_KEY."
            )

        normalized_count = max(
            1, min(GeoArticleEngineService.MAX_ARTICLES, int(article_count))
        )
        focus_urls = GeoArticleEngineService._build_focus_urls(audit)
        if len(focus_urls) < GeoArticleEngineService.MIN_INTERNAL_SOURCES:
            raise ArticleDataPackIncompleteError(
                "ARTICLE_DATA_PACK_INCOMPLETE: not enough audited pages to build internal evidence set."
            )

        internal_sources = GeoArticleEngineService._build_internal_sources(
            audit, focus_urls
        )
        if len(internal_sources) < GeoArticleEngineService.MIN_INTERNAL_SOURCES:
            raise ArticleDataPackIncompleteError(
                "ARTICLE_DATA_PACK_INCOMPLETE: internal source coverage below minimum (2)."
            )

        audit_keywords = GeoArticleEngineService._extract_audit_keywords(audit)
        if not audit_keywords:
            raise ArticleDataPackIncompleteError(
                "ARTICLE_DATA_PACK_INCOMPLETE: no keyword seeds found in audit."
            )

        resolved_strategy_run_id = strategy_run_id
        resolved_strategy_items = strategy_items or []
        if not resolved_strategy_items:
            (
                resolved_strategy_run_id,
                resolved_strategy_items,
            ) = GeoArticleEngineService._resolve_strategy_run_items(
                db,
                audit.id,
                article_count=normalized_count,
                strategy_run_id=strategy_run_id,
            )
        elif not resolved_strategy_run_id:
            resolved_strategy_run_id = str(
                resolved_strategy_items[0].get("strategy_run_id") or ""
            ).strip()

        if not resolved_strategy_run_id:
            raise ArticleStrategyRequiredError(
                "ARTICLE_STRATEGY_REQUIRED: generate titles first or provide target topics."
            )

        selected_market = GeoArticleEngineService._extract_market(audit, market)
        placeholder_articles = GeoArticleEngineService._build_placeholder_articles(
            focus_urls=focus_urls,
            strategy_items=resolved_strategy_items[:normalized_count],
            article_authority_assignments=article_authority_assignments,
        )

        batch = GeoArticleBatch(
            audit_id=audit.id,
            requested_count=normalized_count,
            language=language,
            tone=tone,
            include_schema=include_schema,
            status="processing",
            summary={
                "requested_count": normalized_count,
                "processed_count": 0,
                "generated_count": 0,
                "failed_count": 0,
                "average_citation_readiness_score": 0.0,
                "language": language,
                "tone": tone,
                "include_schema": include_schema,
                "market": selected_market,
                "strategy_run_id": resolved_strategy_run_id,
                "strategy_source": str(strategy_source or "reused_latest").strip()
                or "reused_latest",
                "pipeline_stage": "titles_ready",
                "generated_titles": GeoArticleEngineService._build_generated_titles_summary(
                    resolved_strategy_items[:normalized_count]
                ),
                "global_authority_urls": [
                    str(url).strip()
                    for url in (global_authority_urls or [])
                    if str(url).strip()
                ],
                "unmatched_authority_urls": [
                    str(url).strip()
                    for url in (unmatched_authority_urls or [])
                    if str(url).strip()
                ],
                "_authority_source_cache": authority_source_cache or [],
                "keyword_strategy_mode": (
                    "audit_only"
                    if GeoArticleEngineService._audit_only_mode()
                    else "audit_plus_kimi_search_expansion"
                ),
                "started_at": datetime.now(timezone.utc).isoformat(),
                "last_progress_at": datetime.now(timezone.utc).isoformat(),
            },
            articles=placeholder_articles,
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)
        GeoArticleEngineService.publish_batch_status_for_batch(batch)
        return batch

    @staticmethod
    def _is_kimi_timeout_error(error_payload: Dict[str, Any]) -> bool:
        code = str(error_payload.get("code") or "").upper()
        message = str(error_payload.get("message") or "").upper()
        return "KIMI_TIMEOUT" in code or "KIMI_TIMEOUT" in message

    @staticmethod
    def _llm_supports_timeout_seconds(llm_function: callable) -> bool:
        try:
            signature = inspect.signature(llm_function)
        except (TypeError, ValueError):
            return False

        parameters = signature.parameters.values()
        if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in parameters):
            return True
        return "timeout_seconds" in signature.parameters

    @staticmethod
    def _resolve_article_llm_timeout_seconds() -> float:
        configured_timeout = float(
            getattr(settings, "GEO_ARTICLE_LLM_TIMEOUT_SECONDS", 0) or 0
        )
        if configured_timeout > 0:
            return configured_timeout
        return float(getattr(settings, "NVIDIA_TIMEOUT_SECONDS", 300))

    @staticmethod
    def _persist_batch_progress(
        db: Session,
        *,
        batch: GeoArticleBatch,
        status: str,
        requested_count: int,
        generated_articles: List[Dict[str, Any]],
        success_count: int,
        total_score: float,
        extra_summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        processed_count = len(generated_articles)
        failed_count = max(processed_count - success_count, 0)
        summary = {
            **(batch.summary or {}),
            "requested_count": requested_count,
            "processed_count": processed_count,
            "generated_count": success_count,
            "failed_count": failed_count,
            "average_citation_readiness_score": round(
                total_score / max(success_count, 1), 1
            ),
            "last_progress_at": datetime.now(timezone.utc).isoformat(),
        }
        if extra_summary:
            summary.update(extra_summary)

        batch.status = status
        batch.articles = generated_articles
        batch.summary = summary
        db.commit()
        db.refresh(batch)
        GeoArticleEngineService.publish_batch_status_for_batch(batch)

    @staticmethod
    async def process_batch(db: Session, batch_id: int) -> GeoArticleBatch:
        batch = db.query(GeoArticleBatch).filter(GeoArticleBatch.id == batch_id).first()
        if not batch:
            raise ValueError(f"GeoArticleBatch {batch_id} not found.")

        audit = db.query(Audit).filter(Audit.id == batch.audit_id).first()
        if not audit:
            raise ValueError(f"Audit {batch.audit_id} not found for batch {batch_id}.")

        if not is_kimi_configured():
            raise KimiUnavailableError(
                "Kimi provider is not configured. Set NV_API_KEY_ANALYSIS or NVIDIA_API_KEY or NV_API_KEY."
            )

        llm_function = get_llm_function()
        if llm_function is None:
            raise KimiUnavailableError("Kimi provider function is unavailable.")

        article_llm_timeout_seconds = (
            GeoArticleEngineService._resolve_article_llm_timeout_seconds()
        )
        llm_supports_timeout = GeoArticleEngineService._llm_supports_timeout_seconds(
            llm_function
        )

        async def article_llm_function(
            *, system_prompt: str, user_prompt: str, max_tokens: Optional[int] = None
        ) -> str:
            llm_kwargs: Dict[str, Any] = {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
            }
            if max_tokens is not None:
                llm_kwargs["max_tokens"] = max_tokens
            if llm_supports_timeout:
                llm_kwargs["timeout_seconds"] = article_llm_timeout_seconds
            return await llm_function(**llm_kwargs)

        logger.info(
            "Article batch %s will use KIMI timeout=%.1fs (supports_timeout_param=%s).",
            batch_id,
            article_llm_timeout_seconds,
            llm_supports_timeout,
        )

        market = str(
            (batch.summary or {}).get("market")
            or GeoArticleEngineService._extract_market(audit)
        )
        language = batch.language or "en"
        tone = batch.tone or "executive"
        include_schema = bool(batch.include_schema)

        focus_urls = GeoArticleEngineService._build_focus_urls(audit)
        internal_sources = GeoArticleEngineService._build_internal_sources(
            audit, focus_urls
        )
        fallback_topic_terms = GeoArticleEngineService._extract_topic_terms(audit, "")
        fallback_external_sources = (
            GeoArticleEngineService._build_external_sources_from_audit(
                audit, topic_terms=fallback_topic_terms
            )
        )
        audit_keywords = GeoArticleEngineService._extract_audit_keywords(audit)
        summary = dict(batch.summary or {})
        strategy_run_id = str(summary.get("strategy_run_id") or "").strip()
        has_authority_cache = bool(summary.get("_authority_source_cache"))
        if strategy_run_id:
            ai_strategy_items = GeoArticleEngineService._extract_ai_strategy_items(
                db,
                audit.id,
                strategy_run_id=strategy_run_id,
            )
        else:
            ai_strategy_items = GeoArticleEngineService._strategy_items_from_batch(
                batch
            )

        generated_articles: List[Dict[str, Any]] = []
        total_score = 0.0
        success_count = 0
        requested_count = int(batch.requested_count or 1)
        article_retry_count = 1
        if len(ai_strategy_items) < requested_count:
            raise ArticleStrategyRequiredError(
                f"ARTICLE_STRATEGY_REQUIRED: batch needs {requested_count} titled slots, found {len(ai_strategy_items)}."
            )
        ai_strategy_items = ai_strategy_items[:requested_count]

        # Initialize runtime progress metadata for watchdog reconciliation.
        batch.status = "processing"
        batch.summary = {
            **summary,
            "requested_count": requested_count,
            "processed_count": 0,
            "generated_count": 0,
            "failed_count": 0,
            "generated_titles": summary.get("generated_titles")
            or GeoArticleEngineService._build_generated_titles_summary(
                ai_strategy_items
            ),
            "pipeline_stage": "generating_articles",
            "last_progress_at": datetime.now(timezone.utc).isoformat(),
        }
        db.commit()
        db.refresh(batch)
        GeoArticleEngineService.publish_batch_status_for_batch(batch)

        brand_token = GeoArticleEngineService._extract_brand_token(audit)
        existing_articles = {
            int(item.get("index") or idx + 1): item
            for idx, item in enumerate(batch.articles or [])
            if isinstance(item, dict)
        }

        def _build_article_context(
            idx: int,
        ) -> tuple[Optional[Dict[str, Any]], str, str, Dict[str, Any]]:
            ai_item = ai_strategy_items[idx] if idx < len(ai_strategy_items) else None
            existing_article = existing_articles.get(idx + 1, {})
            primary_keyword = (
                str((ai_item or {}).get("target_keyword") or "").strip().lower()
                or str(existing_article.get("target_keyword") or "").strip().lower()
            )
            if brand_token and brand_token not in primary_keyword.lower():
                primary_keyword = f"{brand_token} {primary_keyword}".strip()
            focus_url = str(existing_article.get("focus_url") or "").strip()
            if not focus_url:
                focus_url = focus_urls[idx % len(focus_urls)]
            title_hint = str(
                (ai_item or {}).get("title") or existing_article.get("title") or ""
            ).strip()
            user_authority_urls = existing_article.get("user_authority_urls") or []
            if not isinstance(user_authority_urls, list):
                user_authority_urls = []
            base_article = {
                "index": idx + 1,
                "focus_url": focus_url,
                "target_keyword": primary_keyword,
                "title": title_hint or f"{primary_keyword.title()}: GEO + SEO Playbook",
                "slug": GeoArticleEngineService._slugify(
                    f"{title_hint or primary_keyword}-{idx + 1}"
                ),
                "generation_status": "failed",
                "generation_error": None,
                "keyword_strategy": {},
                "competitor_gap_map": {},
                "evidence_summary": [],
                "sources": [],
                "citation_readiness_score": 0,
                "markdown": "",
                "meta_title": "",
                "meta_description": "",
                "user_authority_urls": [
                    str(url).strip() for url in user_authority_urls if str(url).strip()
                ],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            return ai_item, primary_keyword, focus_url, base_article

        for index in range(requested_count):
            ai_item, primary_keyword, focus_url, base_article = _build_article_context(
                index
            )

            try:
                user_authority_sources: List[Dict[str, Any]] = []
                if base_article["user_authority_urls"]:
                    user_authority_sources = (
                        GeoArticleEngineService._resolve_authority_sources_from_cache(
                            summary,
                            base_article["user_authority_urls"],
                        )
                    )
                    if not has_authority_cache and not user_authority_sources:
                        user_authority_sources = (
                            await GeoArticleEngineService._build_user_authority_sources(
                                base_article["user_authority_urls"]
                            )
                        )

                last_error: Optional[Exception] = None
                data_pack: Dict[str, Any] = {}
                generated: Dict[str, Any] = {}
                for attempt in range(article_retry_count + 1):
                    try:
                        data_pack = (
                            await GeoArticleEngineService._build_article_data_pack(
                                audit=audit,
                                primary_keyword=primary_keyword,
                                market=market,
                                language=language,
                                focus_url=focus_url,
                                llm_function=article_llm_function,
                                internal_sources=internal_sources,
                                fallback_external_sources=fallback_external_sources,
                                ai_strategy_item=ai_item,
                                user_authority_sources=user_authority_sources,
                                audit_keywords=audit_keywords,
                            )
                        )
                        generated = (
                            await GeoArticleEngineService._generate_article_content(
                                llm_function=article_llm_function,
                                data_pack=data_pack,
                                tone=tone,
                                include_schema=include_schema,
                                language=language,
                            )
                        )
                        last_error = None
                        break
                    except Exception as exc:  # pylint: disable=broad-except
                        last_error = exc
                        error_payload = GeoArticleEngineService._error_payload(exc)
                        should_retry = (
                            attempt < article_retry_count
                            and error_payload.get("code") == "KIMI_GENERATION_FAILED"
                        )
                        if should_retry:
                            logger.warning(
                                "Retrying article batch=%s idx=%s after %s.",
                                batch_id,
                                index + 1,
                                error_payload.get("code"),
                            )
                            continue
                        raise last_error

                markdown = generated.get("markdown", "")
                sources = data_pack.get("required_sources", {}).get("all", [])
                score = GeoArticleEngineService._citation_score(
                    markdown=markdown,
                    include_schema=include_schema,
                    sources_count=len(sources),
                )

                article = {
                    **base_article,
                    "title": base_article["title"],
                    "slug": GeoArticleEngineService._slugify(
                        f"{base_article['title']}-{index + 1}"
                    ),
                    "markdown": markdown,
                    "meta_title": generated.get("meta_title"),
                    "meta_description": generated.get("meta_description"),
                    "schema_json": generated.get("schema_json"),
                    "generation_status": "completed",
                    "generation_error": None,
                    "keyword_strategy": data_pack.get("keyword_strategy", {}),
                    "search_intent": data_pack.get("keyword_strategy", {}).get(
                        "search_intent"
                    ),
                    "top_competitors_for_keyword": data_pack.get(
                        "top_competitors_for_keyword", []
                    ),
                    "competitor_to_beat": (
                        data_pack.get("top_competitors_for_keyword", [{}])[0].get(
                            "domain"
                        )
                        if data_pack.get("top_competitors_for_keyword")
                        else None
                    ),
                    "competitor_gap_map": data_pack.get("competitor_gap_map", {}),
                    "evidence_summary": generated.get("evidence_summary", []),
                    "required_sources": data_pack.get("required_sources", {}),
                    "sources": sources,
                    "audit_signals": data_pack.get("audit_signals", {}),
                    "citation_readiness_score": score,
                    "provider": data_pack.get("provider", "kimi-2.5-search"),
                    "user_authority_urls": base_article.get("user_authority_urls", []),
                }
                generated_articles.append(article)
                success_count += 1
                total_score += score
            except Exception as exc:  # pylint: disable=broad-except
                error_payload = GeoArticleEngineService._error_payload(exc)
                logger.error(
                    f"Article generation failed for batch={batch_id}, idx={index + 1}, "
                    f"keyword='{primary_keyword}': {error_payload['code']} - {error_payload['message']}"
                )
                generated_articles.append(
                    {
                        **base_article,
                        "generation_status": "failed",
                        "generation_error": error_payload,
                    }
                )

            GeoArticleEngineService._persist_batch_progress(
                db,
                batch=batch,
                status="processing",
                requested_count=requested_count,
                generated_articles=generated_articles,
                success_count=success_count,
                total_score=total_score,
            )

        if success_count == requested_count:
            status = "completed"
        elif success_count == 0:
            status = "failed"
        else:
            status = "partial_failed"

        final_summary = {
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "pipeline_stage": "completed",
        }

        GeoArticleEngineService._persist_batch_progress(
            db,
            batch=batch,
            status=status,
            requested_count=requested_count,
            generated_articles=generated_articles,
            success_count=success_count,
            total_score=total_score,
            extra_summary=final_summary,
        )
        return batch

    @staticmethod
    async def regenerate_article(
        db: Session,
        *,
        batch_id: int,
        article_index: int,
        authority_urls: List[str],
    ) -> GeoArticleBatch:
        batch = db.query(GeoArticleBatch).filter(GeoArticleBatch.id == batch_id).first()
        if not batch:
            raise ValueError(f"GeoArticleBatch {batch_id} not found.")
        if GeoArticleEngineService._is_legacy_batch(batch):
            raise LegacyBatchReadOnlyError(
                "LEGACY_BATCH_READ_ONLY: This batch was generated before the strategy-run system. Create a new batch to regenerate articles."
            )
        if batch.status not in {"completed", "failed", "partial_failed"}:
            raise ValueError("Batch is still processing.")

        audit = db.query(Audit).filter(Audit.id == batch.audit_id).first()
        if not audit:
            raise ValueError(f"Audit {batch.audit_id} not found for batch {batch_id}.")

        llm_function = get_llm_function()
        if llm_function is None:
            raise KimiUnavailableError("Kimi provider function is unavailable.")

        article_llm_timeout_seconds = (
            GeoArticleEngineService._resolve_article_llm_timeout_seconds()
        )
        llm_supports_timeout = GeoArticleEngineService._llm_supports_timeout_seconds(
            llm_function
        )

        async def article_llm_function(
            *, system_prompt: str, user_prompt: str, max_tokens: Optional[int] = None
        ) -> str:
            llm_kwargs: Dict[str, Any] = {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
            }
            if max_tokens is not None:
                llm_kwargs["max_tokens"] = max_tokens
            if llm_supports_timeout:
                llm_kwargs["timeout_seconds"] = article_llm_timeout_seconds
            return await llm_function(**llm_kwargs)

        articles = list(batch.articles or [])
        target_article = None
        target_position = None
        for idx, item in enumerate(articles):
            if not isinstance(item, dict):
                continue
            if int(item.get("index") or idx + 1) == article_index:
                target_article = dict(item)
                target_position = idx
                break
        if target_article is None or target_position is None:
            raise ValueError(
                f"Article index {article_index} not found in batch {batch_id}."
            )

        normalized_urls = GeoArticleEngineService._normalize_authority_urls(
            authority_urls
        )

        user_authority_sources = []
        if normalized_urls:
            user_authority_sources = (
                await GeoArticleEngineService._build_user_authority_sources(
                    normalized_urls
                )
            )
            if not user_authority_sources:
                raise ValueError(
                    "No valid authority URLs could be fetched for regeneration."
                )

        summary = dict(batch.summary or {})
        if user_authority_sources:
            cached_sources = GeoArticleEngineService._serialize_authority_source_cache(
                user_authority_sources
            )
            existing_cache = summary.get("_authority_source_cache") or []
            summary["_authority_source_cache"] = (
                GeoArticleEngineService._serialize_authority_source_cache(
                    [
                        *(existing_cache if isinstance(existing_cache, list) else []),
                        *cached_sources,
                    ]
                )
            )
        strategy_run_id = str(summary.get("strategy_run_id") or "").strip()
        strategy_items = GeoArticleEngineService._extract_ai_strategy_items(
            db,
            audit.id,
            strategy_run_id=strategy_run_id,
        )
        if len(strategy_items) < article_index:
            raise ArticleStrategyRequiredError(
                "ARTICLE_STRATEGY_REQUIRED: strategy run does not include this article slot."
            )
        ai_item = strategy_items[article_index - 1]

        primary_keyword = (
            str(ai_item.get("target_keyword") or "").strip().lower()
            or str(target_article.get("target_keyword") or "").strip().lower()
        )
        brand_token = GeoArticleEngineService._extract_brand_token(audit)
        if brand_token and brand_token not in primary_keyword.lower():
            primary_keyword = f"{brand_token} {primary_keyword}".strip()

        focus_urls = GeoArticleEngineService._build_focus_urls(audit)
        focus_url = str(target_article.get("focus_url") or "").strip()
        if not focus_url and focus_urls:
            focus_url = focus_urls[(article_index - 1) % len(focus_urls)]

        internal_sources = GeoArticleEngineService._build_internal_sources(
            audit, focus_urls
        )
        fallback_topic_terms = GeoArticleEngineService._extract_topic_terms(audit, "")
        fallback_external_sources = (
            GeoArticleEngineService._build_external_sources_from_audit(
                audit, topic_terms=fallback_topic_terms
            )
        )
        audit_keywords = GeoArticleEngineService._extract_audit_keywords(audit)

        data_pack = await GeoArticleEngineService._build_article_data_pack(
            audit=audit,
            primary_keyword=primary_keyword,
            market=str(
                summary.get("market") or GeoArticleEngineService._extract_market(audit)
            ),
            language=batch.language or "en",
            focus_url=focus_url,
            llm_function=article_llm_function,
            internal_sources=internal_sources,
            fallback_external_sources=fallback_external_sources,
            ai_strategy_item=ai_item,
            user_authority_sources=user_authority_sources,
            audit_keywords=audit_keywords,
        )
        generated = await GeoArticleEngineService._generate_article_content(
            llm_function=article_llm_function,
            data_pack=data_pack,
            tone=batch.tone or "executive",
            include_schema=bool(batch.include_schema),
            language=batch.language or "en",
        )

        markdown = generated.get("markdown", "")
        sources = data_pack.get("required_sources", {}).get("all", [])
        score = GeoArticleEngineService._citation_score(
            markdown=markdown,
            include_schema=bool(batch.include_schema),
            sources_count=len(sources),
        )

        updated_article = {
            **target_article,
            "title": str(
                ai_item.get("title") or target_article.get("title") or ""
            ).strip(),
            "slug": GeoArticleEngineService._slugify(
                f"{str(ai_item.get('title') or target_article.get('title') or '').strip()}-{article_index}"
            ),
            "target_keyword": primary_keyword,
            "focus_url": focus_url,
            "markdown": markdown,
            "meta_title": generated.get("meta_title"),
            "meta_description": generated.get("meta_description"),
            "schema_json": generated.get("schema_json"),
            "generation_status": "completed",
            "generation_error": None,
            "keyword_strategy": data_pack.get("keyword_strategy", {}),
            "search_intent": data_pack.get("keyword_strategy", {}).get("search_intent"),
            "top_competitors_for_keyword": data_pack.get(
                "top_competitors_for_keyword", []
            ),
            "competitor_to_beat": (
                data_pack.get("top_competitors_for_keyword", [{}])[0].get("domain")
                if data_pack.get("top_competitors_for_keyword")
                else None
            ),
            "competitor_gap_map": data_pack.get("competitor_gap_map", {}),
            "evidence_summary": generated.get("evidence_summary", []),
            "required_sources": data_pack.get("required_sources", {}),
            "sources": sources,
            "audit_signals": data_pack.get("audit_signals", {}),
            "citation_readiness_score": score,
            "provider": data_pack.get("provider", "kimi-2.5-search"),
            "user_authority_urls": normalized_urls,
        }
        articles[target_position] = updated_article

        success_count = 0
        total_score = 0.0
        for item in articles:
            if not isinstance(item, dict):
                continue
            if str(item.get("generation_status") or "") == "completed":
                success_count += 1
                total_score += float(item.get("citation_readiness_score") or 0)

        if success_count == len(articles):
            status = "completed"
        elif success_count == 0:
            status = "failed"
        else:
            status = "partial_failed"

        GeoArticleEngineService._persist_batch_progress(
            db,
            batch=batch,
            status=status,
            requested_count=int(batch.requested_count or len(articles) or 1),
            generated_articles=articles,
            success_count=success_count,
            total_score=total_score,
            extra_summary={
                "_authority_source_cache": summary.get("_authority_source_cache", []),
                "pipeline_stage": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return batch

    @staticmethod
    def get_batch(db: Session, batch_id: int) -> Optional[GeoArticleBatch]:
        return db.query(GeoArticleBatch).filter(GeoArticleBatch.id == batch_id).first()

    @staticmethod
    def get_latest_batch(db: Session, audit_id: int) -> Optional[GeoArticleBatch]:
        return (
            db.query(GeoArticleBatch)
            .filter(GeoArticleBatch.audit_id == audit_id)
            .order_by(GeoArticleBatch.created_at.desc())
            .first()
        )

    @staticmethod
    def serialize_batch(batch: GeoArticleBatch) -> Dict[str, Any]:
        return GeoArticleEngineService._serialize_batch(batch)

    @staticmethod
    def serialize_batch_status(batch: GeoArticleBatch) -> Dict[str, Any]:
        return GeoArticleEngineService._serialize_batch_status(batch)
