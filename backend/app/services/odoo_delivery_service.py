"""
Odoo delivery planner grounded in validated audit outputs.

This pack is intentionally modeled after the GitHub delivery flow, but its
scope is limited to changes that can actually be implemented inside Odoo:
- validated SEO/GEO fixes from fix_plan
- article deliverables when content was requested or already generated
- ecommerce merchandising/search fixes when the audited site is ecommerce

Excluded on purpose:
- PageSpeed / Core Web Vitals remediation
- CDN, caching, origin latency, and other DevOps-only work
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.models import AIContentSuggestion, Audit
from app.models.odoo import OdooConnection, OdooDraftAction, OdooSyncRun
from app.services.audit_service import AuditService
from app.services.geo_article_engine_service import GeoArticleEngineService
from app.services.geo_commerce_service import GeoCommerceService
from sqlalchemy.orm import Session


class OdooDeliveryService:
    _PERFORMANCE_TOKENS = {
        "PAGESPEED",
        "PERFORMANCE",
        "CWV",
        "CORE_WEB_VITALS",
        "TTFB",
        "LCP",
        "CLS",
        "INP",
        "FCP",
        "CACHE",
        "CDN",
        "NETWORK",
        "SERVER_RESPONSE",
        "RENDER_BLOCKING",
        "OFFSCREEN_IMAGES",
        "MODERN_IMAGE_FORMATS",
        "USES_OPTIMIZED_IMAGES",
        "USES_RESPONSIVE_IMAGES",
        "USES_LONG_CACHE_TTL",
        "BOOTUP_TIME",
        "LONG_TASKS",
        "TOTAL_BYTE_WEIGHT",
        "CRITICAL_REQUEST_CHAINS",
    }

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return " ".join(str(value or "").split()).strip()

    @staticmethod
    def _slugify(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower())
        return normalized.strip("-") or "odoo-delivery-item"

    @staticmethod
    def _priority_rank(value: Optional[str]) -> int:
        normalized = str(value or "").strip().upper()
        mapping = {
            "CRITICAL": 0,
            "HIGH": 1,
            "P1": 1,
            "MEDIUM": 2,
            "P2": 2,
            "LOW": 3,
            "P3": 3,
        }
        return mapping.get(normalized, 4)

    @staticmethod
    def _extract_issue_code(item: Dict[str, Any]) -> str:
        return str(item.get("issue_code") or "").strip().upper()

    @staticmethod
    def _extract_issue_text(item: Dict[str, Any]) -> str:
        return OdooDeliveryService._normalize_text(
            item.get("issue") or item.get("description") or item.get("issue_code") or ""
        )

    @staticmethod
    def _extract_page_path(item: Dict[str, Any]) -> str:
        return AuditService._path_from_value(
            item.get("page_path") or item.get("page") or item.get("page_url")
        )

    @staticmethod
    def _value_summary(value: Any) -> str:
        if value in (None, "", {}, []):
            return ""
        if isinstance(value, str):
            return OdooDeliveryService._normalize_text(value)[:220]
        if isinstance(value, dict):
            if value.get("org_name"):
                return f"Organization schema for {value.get('org_name')}"
            if value.get("author_name"):
                return f"Author module for {value.get('author_name')}"
            parts = []
            for key in ("title", "topic", "org_url", "logo_url"):
                if value.get(key):
                    parts.append(f"{key}={value.get(key)}")
            return ", ".join(parts)[:220]
        if isinstance(value, list):
            if value and isinstance(value[0], dict):
                if {"question", "answer"}.issubset(set(value[0].keys())):
                    return f"{len(value)} grounded FAQ items"
            return f"{len(value)} structured values"
        return OdooDeliveryService._normalize_text(value)[:220]

    @staticmethod
    def _is_performance_fix(item: Dict[str, Any]) -> bool:
        category = str(item.get("category") or "").strip().upper()
        if category == "PERFORMANCE":
            return True

        haystack = " ".join(
            [
                OdooDeliveryService._extract_issue_code(item),
                OdooDeliveryService._extract_issue_text(item),
                OdooDeliveryService._normalize_text(item.get("suggestion")),
                OdooDeliveryService._normalize_text(item.get("impact")),
            ]
        ).upper()
        return any(
            token in haystack for token in OdooDeliveryService._PERFORMANCE_TOKENS
        )

    @staticmethod
    def _is_ecommerce_path(page_path: str) -> bool:
        normalized = str(page_path or "").lower()
        return any(
            token in normalized
            for token in (
                "/product",
                "/products",
                "/shop",
                "/store",
                "/tienda",
                "/categoria",
                "/category",
                "/collections",
                "/coleccion",
            )
        )

    @staticmethod
    def _fix_area(issue_code: str, issue_text: str, is_ecommerce: bool) -> str:
        haystack = f"{issue_code} {issue_text}".upper()
        if any(
            token in haystack
            for token in ("TITLE", "META", "DESCRIPTION", "CANONICAL", "H1", "HEAD")
        ):
            return "On-page SEO"
        if any(
            token in haystack
            for token in ("SCHEMA", "FAQ", "PRODUCT_SCHEMA", "BREADCRUMB")
        ):
            return "Structured data and entity clarity"
        if any(
            token in haystack
            for token in ("AUTHOR", "EEAT", "TRUST", "ABOUT", "CONTACT")
        ):
            return "Trust and editorial signals"
        if is_ecommerce and any(
            token in haystack
            for token in (
                "PRODUCT",
                "PRICE",
                "AVAILABILITY",
                "MERCH",
                "OFFER",
                "REVIEW",
            )
        ):
            return "Product merchandising"
        if any(
            token in haystack
            for token in ("CONTENT", "READABILITY", "TOPIC", "INTERNAL_LINK", "LINK")
        ):
            return "Content and internal linking"
        return "Template implementation"

    @staticmethod
    def _odoo_surface(
        *,
        page_path: str,
        issue_code: str,
        issue_text: str,
        is_ecommerce: bool,
    ) -> str:
        haystack = f"{issue_code} {issue_text}".upper()
        is_root = page_path in {"", "/"}
        ecommerce_path = OdooDeliveryService._is_ecommerce_path(page_path)

        if any(
            token in haystack for token in ("SCHEMA", "PRODUCT_SCHEMA", "BREADCRUMB")
        ):
            if ecommerce_path or ("PRODUCT" in haystack and is_ecommerce):
                return "website_sale.product / website_sale.products / structured data snippets"
            if is_root:
                return "website.homepage / website.layout / structured data snippets"
            return "website.page / website_blog.post / structured data snippets"

        if any(
            token in haystack
            for token in (
                "FAQ",
                "AUTHOR",
                "CONTENT",
                "READABILITY",
                "TOPIC",
                "INTERNAL_LINK",
            )
        ):
            if ecommerce_path or is_ecommerce:
                return "website_sale.product / website_sale.products / website_blog.blog_post"
            return "website.page / website_blog.blog_post"

        if any(
            token in haystack
            for token in ("TITLE", "META", "DESCRIPTION", "CANONICAL", "H1", "HEAD")
        ):
            if ecommerce_path:
                return "website_sale.product / website_sale.products / website.layout"
            if is_root:
                return "website.homepage / website.layout"
            return "website.page / website_blog.blog_post"

        if is_root:
            return "website.homepage / website.layout"
        if ecommerce_path or is_ecommerce:
            return "website_sale.product / website_sale.products / shared snippets"
        return "website.page / shared snippets"

    @staticmethod
    def _implementation_brief(
        item: Dict[str, Any],
        *,
        page_path: str,
        issue_code: str,
        issue_text: str,
        surface: str,
    ) -> str:
        recommended_value = item.get("recommended_value")
        suggested = OdooDeliveryService._normalize_text(
            item.get("suggestion") or item.get("recommendation") or item.get("impact")
        )

        if issue_code.startswith("H1_MISSING"):
            target_h1 = OdooDeliveryService._value_summary(recommended_value)
            if target_h1:
                return f"Implement the exact primary heading '{target_h1}' on {page_path or '/'} and keep one dominant H1 per template."
            return f"Add a single clear H1 on {page_path or '/'} using Odoo template fields instead of visual-only headings."

        if "SCHEMA" in issue_code:
            value_summary = OdooDeliveryService._value_summary(recommended_value)
            if value_summary:
                return f"Implement validated JSON-LD in {surface}. Use the provided structured values ({value_summary}) without inventing extra fields."
            return f"Add the missing structured data in {surface} using only the validated entity, product, breadcrumb, or FAQ fields from the audit."

        if issue_code.startswith("FAQ"):
            faq_summary = OdooDeliveryService._value_summary(recommended_value)
            if faq_summary:
                return (
                    f"Publish a visible FAQ block in {surface} backed by {faq_summary}."
                )
            return f"Add an FAQ block in {surface} using only grounded answers from the validated audit context."

        if issue_code.startswith("AUTHOR"):
            author_summary = OdooDeliveryService._value_summary(recommended_value)
            if author_summary:
                return f"Add an author module in {surface} using the validated profile data ({author_summary})."
            return f"Expose author identity, role, bio, and profile link in {surface}."

        value_summary = OdooDeliveryService._value_summary(recommended_value)
        if suggested and value_summary:
            return f"{suggested} Recommended value: {value_summary}."
        if suggested:
            return suggested
        return f"Resolve '{issue_text}' in {surface} using Odoo templates, snippets, and managed content fields."

    @staticmethod
    def _acceptance_criteria(issue_code: str, surface: str) -> str:
        normalized = issue_code.upper()
        if normalized.startswith("H1_MISSING"):
            return "Rendered page shows one primary H1, aligned with page intent and visible in the final template."
        if "SCHEMA" in normalized:
            return "Structured data validates cleanly and matches visible page content without invented fields."
        if normalized.startswith("FAQ"):
            return "FAQ content is visible in-page, indexable, and consistent with the provided answers."
        if normalized.startswith("AUTHOR"):
            return "Author module is visible, linked, and consistent across the relevant editorial templates."
        return f"Change is live in {surface}, matches the validated audit finding, and does not regress layout or content integrity."

    @staticmethod
    def _build_fix_deliverables(
        *,
        audit: Audit,
        product_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        raw_fixes = audit.fix_plan if isinstance(audit.fix_plan, list) else []
        seen = set()
        items: List[Dict[str, Any]] = []
        is_ecommerce = bool(product_data.get("is_ecommerce"))

        for item in raw_fixes:
            if not isinstance(item, dict) or OdooDeliveryService._is_performance_fix(
                item
            ):
                continue

            issue_code = OdooDeliveryService._extract_issue_code(item)
            issue_text = OdooDeliveryService._extract_issue_text(item)
            page_path = OdooDeliveryService._extract_page_path(item)
            dedupe_key = (issue_code, page_path, issue_text)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            surface = OdooDeliveryService._odoo_surface(
                page_path=page_path,
                issue_code=issue_code,
                issue_text=issue_text,
                is_ecommerce=is_ecommerce,
            )
            items.append(
                {
                    "issue_code": issue_code,
                    "priority": item.get("priority", "MEDIUM"),
                    "page_path": page_path or "/",
                    "area": OdooDeliveryService._fix_area(
                        issue_code, issue_text, is_ecommerce
                    ),
                    "recommended_odoo_surface": surface,
                    "what_to_change": OdooDeliveryService._implementation_brief(
                        item,
                        page_path=page_path,
                        issue_code=issue_code,
                        issue_text=issue_text,
                        surface=surface,
                    ),
                    "why_it_matters": OdooDeliveryService._normalize_text(
                        item.get("impact") or issue_text
                    ),
                    "evidence": OdooDeliveryService._value_summary(
                        item.get("current_value")
                    )
                    or OdooDeliveryService._value_summary(item.get("recommended_value"))
                    or issue_text,
                    "qa_check": OdooDeliveryService._acceptance_criteria(
                        issue_code, surface
                    ),
                }
            )

        items.sort(
            key=lambda row: (
                OdooDeliveryService._priority_rank(row.get("priority")),
                row.get("page_path") or "",
                row.get("issue_code") or "",
            )
        )
        return items[:16]

    @staticmethod
    def _article_brief(article: Dict[str, Any]) -> str:
        evidence_summary = article.get("evidence_summary") or []
        if isinstance(evidence_summary, list) and evidence_summary:
            return OdooDeliveryService._normalize_text(evidence_summary[0])
        if article.get("meta_description"):
            return OdooDeliveryService._normalize_text(article.get("meta_description"))
        target_keyword = OdooDeliveryService._normalize_text(
            article.get("target_keyword")
        )
        if target_keyword:
            return f"Publish this article around '{target_keyword}' and link it back to the relevant money page."
        return "Publish this article in Odoo blog and connect it to the relevant commercial templates."

    @staticmethod
    def _serialize_articles_from_batch(batch: Any) -> List[Dict[str, Any]]:
        raw_articles = batch.articles or []
        deliverables: List[Dict[str, Any]] = []
        for article in raw_articles:
            if not isinstance(article, dict):
                continue
            if article.get("generation_status") != "completed":
                continue
            title = OdooDeliveryService._normalize_text(article.get("title"))
            if not title:
                continue
            sources = article.get("sources") or []
            deliverables.append(
                {
                    "title": title,
                    "slug": article.get("slug") or OdooDeliveryService._slugify(title),
                    "target_keyword": article.get("target_keyword"),
                    "focus_url": article.get("focus_url"),
                    "citation_readiness_score": article.get("citation_readiness_score"),
                    "schema_included": bool(article.get("schema_json")),
                    "source_count": len(sources) if isinstance(sources, list) else 0,
                    "implementation_surface": "website_blog.blog_post / internal links from related category and product pages",
                    "delivery_brief": OdooDeliveryService._article_brief(article),
                    "source": "article_engine_batch",
                }
            )
        return deliverables

    @staticmethod
    def _serialize_articles_from_suggestions(
        suggestions: List[AIContentSuggestion],
        limit: int,
    ) -> List[Dict[str, Any]]:
        ranked = sorted(
            list(suggestions or []),
            key=lambda row: (
                OdooDeliveryService._priority_rank(getattr(row, "priority", None)),
                getattr(row, "created_at", datetime.now(timezone.utc)),
            ),
        )
        deliverables: List[Dict[str, Any]] = []
        for suggestion in ranked[:limit]:
            topic = OdooDeliveryService._normalize_text(
                getattr(suggestion, "topic", "")
            )
            if not topic:
                continue
            deliverables.append(
                {
                    "title": topic,
                    "slug": OdooDeliveryService._slugify(topic),
                    "target_keyword": topic,
                    "focus_url": getattr(suggestion, "page_url", None),
                    "citation_readiness_score": None,
                    "schema_included": True,
                    "source_count": 0,
                    "implementation_surface": "website_blog.blog_post / editorial cluster linked from relevant Odoo pages",
                    "delivery_brief": (
                        f"Turn the validated {getattr(suggestion, 'suggestion_type', 'content')} opportunity into a publishable Odoo blog article."
                    ),
                    "source": "ai_content_suggestion",
                }
            )
        return deliverables

    @staticmethod
    def _ecommerce_surface(action: str, evidence: str) -> str:
        haystack = f"{action} {evidence}".lower()
        if any(
            token in haystack
            for token in (
                "price",
                "availability",
                "stock",
                "shipping",
                "return",
                "cart",
                "offer",
            )
        ):
            return "website_sale.product / product template fields / offer snippets"
        if any(
            token in haystack
            for token in ("category", "listing", "collection", "facet", "filter")
        ):
            return "website_sale.products / category templates / collection blocks"
        if any(
            token in haystack
            for token in (
                "homepage",
                "root page",
                "root",
                "authority",
                "internal linking",
                "trust",
            )
        ):
            return "website.homepage / website.layout / hero and trust modules"
        if any(
            token in haystack
            for token in ("faq", "comparison", "buyer", "pre-purchase")
        ):
            return "website_sale.product / website.page / FAQ and comparison snippets"
        return "website_sale.product / website_sale.products / website.homepage"

    @staticmethod
    def _serialize_ecommerce_fixes(
        *,
        search_engine_fixes: List[Dict[str, Any]],
        merchandising_fixes: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for source_label, source_items in (
            ("Search visibility", search_engine_fixes),
            ("Merchandising", merchandising_fixes),
        ):
            for row in source_items or []:
                if not isinstance(row, dict):
                    continue
                action = OdooDeliveryService._normalize_text(row.get("action"))
                evidence = OdooDeliveryService._normalize_text(row.get("evidence"))
                if not action:
                    continue
                surface = OdooDeliveryService._ecommerce_surface(action, evidence)
                items.append(
                    {
                        "priority": row.get("priority", "P2"),
                        "area": source_label,
                        "recommended_odoo_surface": surface,
                        "what_to_change": action,
                        "why_it_matters": evidence
                        or "Validated ecommerce gap from the audit context.",
                        "qa_check": f"Validate the change in {surface} and confirm it improves product discoverability without weakening conversion flow.",
                    }
                )
        items.sort(
            key=lambda row: (
                OdooDeliveryService._priority_rank(row.get("priority")),
                row.get("area") or "",
            )
        )
        return items[:10]

    @staticmethod
    def _report_excerpt(markdown: Any) -> Optional[str]:
        text = OdooDeliveryService._normalize_text(markdown)
        if not text:
            return None
        return text[:420]

    @staticmethod
    def _serialize_connection(
        connection: Optional[OdooConnection],
    ) -> Optional[Dict[str, Any]]:
        if not connection:
            return None
        return {
            "id": connection.id,
            "label": connection.label,
            "base_url": connection.base_url,
            "database": connection.database,
            "expected_email": connection.expected_email,
            "odoo_version": connection.odoo_version,
            "capabilities": connection.capabilities or {},
            "warnings": connection.warnings or [],
            "detected_user": connection.detected_user or {},
            "last_validated_at": (
                connection.last_validated_at.isoformat()
                if connection.last_validated_at
                else None
            ),
        }

    @staticmethod
    def _latest_sync_summary(db: Session, audit: Audit) -> Dict[str, Any]:
        if not audit.odoo_connection_id:
            return {
                "status": "not_connected",
                "counts_by_model": {},
                "mapped_count": 0,
                "unmapped_count": 0,
                "mapped_audit_paths": [],
                "unmapped_paths": [],
            }
        latest_sync = (
            db.query(OdooSyncRun)
            .filter(
                OdooSyncRun.audit_id == audit.id,
                OdooSyncRun.connection_id == audit.odoo_connection_id,
            )
            .order_by(OdooSyncRun.started_at.desc())
            .first()
        )
        if not latest_sync:
            return {
                "status": "not_synced",
                "counts_by_model": {},
                "mapped_count": 0,
                "unmapped_count": 0,
                "mapped_audit_paths": [],
                "unmapped_paths": [],
            }
        payload = dict(latest_sync.summary or {})
        payload.setdefault("status", latest_sync.status or "unknown")
        payload.setdefault("counts_by_model", {})
        payload.setdefault("mapped_count", 0)
        payload.setdefault("unmapped_count", 0)
        payload.setdefault("mapped_audit_paths", [])
        payload.setdefault("unmapped_paths", [])
        payload.setdefault(
            "last_synced_at",
            latest_sync.completed_at.isoformat() if latest_sync.completed_at else None,
        )
        return payload

    @staticmethod
    def _draft_summary(db: Session, audit: Audit) -> Dict[str, int]:
        if not audit.odoo_connection_id:
            return {
                "native_draft_count": 0,
                "draft_count": 0,
                "manual_review_count": 0,
                "failed_count": 0,
            }
        rows = (
            db.query(OdooDraftAction)
            .filter(
                OdooDraftAction.audit_id == audit.id,
                OdooDraftAction.connection_id == audit.odoo_connection_id,
            )
            .all()
        )
        return {
            "native_draft_count": len(
                [row for row in rows if row.status == "native_created"]
            ),
            "draft_count": len([row for row in rows if row.status == "draft"]),
            "manual_review_count": len(
                [row for row in rows if row.status == "manual_review"]
            ),
            "failed_count": len([row for row in rows if row.status == "failed"]),
        }

    @staticmethod
    def _recommended_primary_goal(*, is_ecommerce: bool, audit: Audit) -> str:
        category = OdooDeliveryService._normalize_text(
            (
                (audit.external_intelligence or {}).get("category")
                or audit.category
                or ""
            )
        ).lower()
        if is_ecommerce or "e-commerce" in category:
            return "Improve commercial page visibility across homepage, category, and product templates."
        return "Strengthen template-level SEO, entity clarity, and editorial trust signals in Odoo."

    @staticmethod
    async def build_plan(db: Session, audit: Audit) -> Dict[str, Any]:
        selected_connection = (
            db.query(OdooConnection)
            .filter(
                OdooConnection.id == audit.odoo_connection_id,
                OdooConnection.is_active.is_(True),
            )
            .first()
            if audit.odoo_connection_id
            else None
        )
        sync_summary = OdooDeliveryService._latest_sync_summary(db, audit)
        draft_summary = OdooDeliveryService._draft_summary(db, audit)

        should_generate_fix_plan = (
            not isinstance(audit.fix_plan, list) or not audit.fix_plan
        )
        if should_generate_fix_plan:
            await AuditService.ensure_fix_plan(db, audit.id, min_items=1)
            db.refresh(audit)

        intake_profile = audit.intake_profile or {}
        article_limit = max(1, min(12, int(intake_profile.get("article_count") or 3)))
        missing_inputs: List[Dict[str, Any]] = []
        if should_generate_fix_plan:
            missing_inputs = await AuditService.get_fix_plan_missing_inputs(
                db, audit.id
            )

        latest_batch = GeoArticleEngineService.get_latest_batch(db, audit.id)
        latest_query_analysis = GeoCommerceService.get_latest_query_analysis(
            db, audit.id
        )
        latest_query_payload = (
            latest_query_analysis.payload
            if latest_query_analysis and isinstance(latest_query_analysis.payload, dict)
            else {}
        )

        root_snapshot = GeoCommerceService._build_root_page_snapshot(db, audit)
        product_data = latest_query_payload.get("product_intelligence")
        if not isinstance(product_data, dict) or not product_data:
            try:
                product_data = (
                    await GeoCommerceService._build_product_intelligence_snapshot(
                        db, audit
                    )
                )
            except Exception:
                product_data = {}

        category = OdooDeliveryService._normalize_text(
            (
                (audit.external_intelligence or {}).get("category")
                or audit.category
                or ""
            )
        ).lower()
        is_ecommerce = (
            bool(product_data.get("is_ecommerce")) or "e-commerce" in category
        )

        fix_deliverables = OdooDeliveryService._build_fix_deliverables(
            audit=audit,
            product_data=product_data if isinstance(product_data, dict) else {},
        )

        articles_requested = intake_profile.get("add_articles")
        article_deliverables: List[Dict[str, Any]] = []
        if articles_requested is not False and latest_batch:
            article_deliverables = OdooDeliveryService._serialize_articles_from_batch(
                latest_batch
            )
        if (
            articles_requested is not False
            and not article_deliverables
            and (articles_requested or audit.ai_content_suggestions)
        ):
            article_deliverables = (
                OdooDeliveryService._serialize_articles_from_suggestions(
                    list(audit.ai_content_suggestions or []),
                    article_limit,
                )
            )

        ecommerce_fixes: List[Dict[str, Any]] = []
        commerce_context: Dict[str, Any] = {}
        commerce_root_causes: List[Dict[str, Any]] = []
        ecommerce_requested = (
            bool(intake_profile.get("improve_ecommerce_fixes"))
            if "improve_ecommerce_fixes" in intake_profile
            else is_ecommerce
        )
        if is_ecommerce and ecommerce_requested:
            search_engine_fixes = []
            merchandising_fixes = []
            if latest_query_payload:
                search_engine_fixes = (
                    latest_query_payload.get("search_engine_fixes") or []
                )
                merchandising_fixes = (
                    latest_query_payload.get("merchandising_fixes") or []
                )
                commerce_root_causes = (
                    latest_query_payload.get("root_cause_summary") or []
                )
                commerce_context = {
                    "has_analysis": True,
                    "query": latest_query_payload.get("query"),
                    "market": latest_query_payload.get("market"),
                    "target_position": latest_query_payload.get("target_position"),
                    "top_result_domain": (
                        latest_query_payload.get("top_result") or {}
                    ).get("domain"),
                }
            else:
                merchandising_fixes = GeoCommerceService._build_merchandising_fixes(
                    product_data if isinstance(product_data, dict) else {}
                )
                site_signals = GeoCommerceService._extract_site_signals(audit)
                commerce_root_causes = GeoCommerceService._build_root_cause_summary(
                    target_position=None,
                    top_k=10,
                    site_signals=site_signals,
                    product_data=product_data if isinstance(product_data, dict) else {},
                    root_snapshot=root_snapshot,
                    pagespeed_data={},
                )
                commerce_context = {
                    "has_analysis": False,
                    "query": None,
                    "market": OdooDeliveryService._normalize_text(
                        intake_profile.get("market")
                        or ((audit.external_intelligence or {}).get("market") or "")
                    )
                    or None,
                    "target_position": None,
                    "top_result_domain": None,
                }

            ecommerce_fixes = OdooDeliveryService._serialize_ecommerce_fixes(
                search_engine_fixes=search_engine_fixes,
                merchandising_fixes=merchandising_fixes,
            )

        summary = "Implementation-ready Odoo delivery pack built from the validated audit fix plan."
        primary_goal = OdooDeliveryService._normalize_text(
            intake_profile.get("odoo_primary_goal")
        )
        if primary_goal:
            summary += f" Primary goal: {primary_goal}"
        if article_deliverables:
            summary += " Includes editorial deliverables for Odoo blog rollout."
        if ecommerce_fixes:
            summary += " Includes ecommerce merchandising and search fixes for product and category templates."
        summary += " PageSpeed and DevOps-only items are excluded from this pack."

        required_inputs = [row for row in missing_inputs if row.get("required")]
        notes = [
            "This pack excludes PageSpeed, Core Web Vitals, CDN, cache, and origin-latency work by design.",
            "Only validated audit fixes, grounded article deliverables, and ecommerce actions are included.",
        ]
        if required_inputs:
            notes.append(
                f"There are {len(required_inputs)} required fix-plan inputs still missing; complete them before treating this pack as implementation-final."
            )
        if intake_profile.get("add_articles") and not article_deliverables:
            notes.append(
                "Articles were requested in intake, but no generated batch or fallback content suggestions are available yet."
            )
        if articles_requested is False:
            notes.append(
                "Editorial deliverables were intentionally excluded in the Odoo delivery brief."
            )
        if is_ecommerce and not ecommerce_requested:
            notes.append(
                "Ecommerce rollout fixes were intentionally excluded in the Odoo delivery brief."
            )

        briefing_profile = {
            "add_articles": bool(
                intake_profile.get("add_articles") or article_deliverables
            ),
            "article_count": (
                article_limit
                if intake_profile.get("add_articles")
                else (len(article_deliverables) or None)
            ),
            "improve_ecommerce_fixes": bool(ecommerce_requested),
            "market": audit.market,
            "language": audit.language,
            "primary_goal": primary_goal
            or OdooDeliveryService._recommended_primary_goal(
                is_ecommerce=is_ecommerce,
                audit=audit,
            ),
            "team_owner": OdooDeliveryService._normalize_text(
                intake_profile.get("odoo_team_owner")
            )
            or (
                "Regional ecommerce team" if is_ecommerce else "SEO / web content team"
            ),
            "rollout_notes": OdooDeliveryService._normalize_text(
                intake_profile.get("odoo_rollout_notes")
            )
            or "",
        }

        return {
            "audit_id": audit.id,
            "audit_url": audit.url,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "selected_connection": OdooDeliveryService._serialize_connection(
                selected_connection
            ),
            "connection_status": {
                "selected": bool(selected_connection),
                "status": "connected" if selected_connection else "not_connected",
                "message": (
                    "Odoo connection selected and ready for sync."
                    if selected_connection
                    else "Select or create an Odoo connection before syncing content."
                ),
            },
            "capabilities": (
                selected_connection.capabilities if selected_connection else {}
            )
            or {},
            "sync_summary": sync_summary,
            "native_draft_count": draft_summary["native_draft_count"],
            "manual_review_count": draft_summary["manual_review_count"],
            "blocked_scope": [
                "No PageSpeed or infrastructure work in the Odoo tool.",
                "No live writes to ir.ui.view, website.layout, snippets, or global templates in v1.",
                "Homepage and template-backed changes remain manual-review only in this phase.",
            ],
            "implementation_packet": {
                "title": f"Odoo Delivery Pack for {audit.domain or audit.url}",
                "branch_name_suggestion": f"odoo/delivery-audit-{audit.id}",
                "summary": summary,
                "success_metrics": [
                    "Ship the validated SEO/GEO fixes from fix_plan into Odoo templates and managed content.",
                    "Publish the article deliverables in Odoo blog when editorial rollout is requested.",
                    "Strengthen ecommerce product, category, and homepage surfaces when the audited site is ecommerce.",
                ],
                "excluded_scope": [
                    "PageSpeed and Core Web Vitals remediation",
                    "CDN, cache headers, redirects, and origin latency",
                    "Infrastructure-only DevOps workstreams",
                ],
            },
            "delivery_summary": {
                "fix_count": len(fix_deliverables),
                "article_count": len(article_deliverables),
                "ecommerce_fix_count": len(ecommerce_fixes),
                "missing_required_inputs": len(required_inputs),
                "is_ecommerce": is_ecommerce,
                "articles_requested": bool(intake_profile.get("add_articles")),
                "ecommerce_requested": bool(ecommerce_requested),
                "native_draft_count": draft_summary["native_draft_count"],
                "manual_review_count": draft_summary["manual_review_count"],
            },
            "briefing_profile": briefing_profile,
            "root_page_snapshot": root_snapshot,
            "report_excerpt": OdooDeliveryService._report_excerpt(
                audit.report_markdown
            ),
            "odoo_ready_fixes": fix_deliverables,
            "article_deliverables": article_deliverables,
            "ecommerce_fixes": ecommerce_fixes,
            "commerce_context": commerce_context,
            "commerce_root_causes": (
                commerce_root_causes[:6]
                if isinstance(commerce_root_causes, list)
                else []
            ),
            "product_intelligence": {
                "is_ecommerce": bool((product_data or {}).get("is_ecommerce")),
                "confidence_score": (product_data or {}).get("confidence_score"),
                "platform": (product_data or {}).get("platform"),
                "product_pages_count": (product_data or {}).get("product_pages_count"),
                "category_pages_count": (product_data or {}).get(
                    "category_pages_count"
                ),
                "schema_analysis": (product_data or {}).get("schema_analysis", {}),
            },
            "required_inputs": missing_inputs,
            "qa_checklist": [
                "Validate each implemented fix in the rendered Odoo page, not only in the editor.",
                "Confirm titles, headings, schema, FAQ, and author modules match the validated audit inputs.",
                "If articles are included, publish them with internal links back to the intended commercial URLs.",
                "If ecommerce fixes are included, verify PDP, category, and homepage modules still preserve conversion flow.",
            ],
            "notes": notes,
        }


# Backwards-compatible alias while the route layer migrates.
OdooPageSpeedService = OdooDeliveryService
