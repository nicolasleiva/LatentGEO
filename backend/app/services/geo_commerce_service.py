#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
geo_commerce_service.py

Commerce LLM campaign planner for GEO:
- Focused on beating marketplaces in AI citations.
- Uses real audit data (target + competitors + search signals).
- Stores decision-ready payloads per audit.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from app.core.llm_kimi import kimi_search_serp
from app.core.logger import get_logger
from app.models import Audit, GeoCommerceCampaign
from app.services.competitive_intel_service import CompetitiveIntelService
from sqlalchemy.orm import Session

logger = get_logger(__name__)


class GeoCommerceService:
    """Service to build ecommerce GEO campaigns based on real audit data."""

    @staticmethod
    def _normalize_domain(value: str) -> str:
        if not value:
            return ""
        raw = str(value).strip().lower()
        if "://" not in raw:
            raw = f"https://{raw}"
        try:
            domain = urlparse(raw).netloc.lower()
        except Exception:
            return ""
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    @staticmethod
    def _extract_brand_name(domain: str) -> str:
        if not domain:
            return "Your Brand"
        root = domain.split(".")[0]
        cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", root).strip()
        return cleaned.title() if cleaned else "Your Brand"

    @staticmethod
    def _extract_market(audit: Audit, fallback_market: Optional[str]) -> str:
        if fallback_market:
            return fallback_market.upper()
        if getattr(audit, "market", None):
            return str(audit.market).upper()
        if getattr(audit, "target_audit", None):
            market = (audit.target_audit or {}).get("market")
            if market:
                return str(market).upper()
        return "GLOBAL"

    @staticmethod
    def _extract_competitor_domains(
        audit: Audit,
        competitor_domains: Optional[List[str]] = None,
    ) -> List[str]:
        normalized: List[str] = []

        for item in competitor_domains or []:
            domain = GeoCommerceService._normalize_domain(item)
            if domain and domain not in normalized:
                normalized.append(domain)

        for comp in getattr(audit, "competitor_audits", None) or []:
            if not isinstance(comp, dict):
                continue
            domain = GeoCommerceService._normalize_domain(
                comp.get("domain") or comp.get("url")
            )
            if domain and domain not in normalized:
                normalized.append(domain)

        for item in getattr(audit, "competitors", None) or []:
            domain = GeoCommerceService._normalize_domain(item)
            if domain and domain not in normalized:
                normalized.append(domain)

        return normalized[:8]

    @staticmethod
    def _extract_baseline(
        audit: Audit,
        normalized_competitors: List[str],
    ) -> Dict[str, Any]:
        target_audit = getattr(audit, "target_audit", None) or {}
        site_metrics = (
            target_audit.get("site_metrics", {})
            if isinstance(target_audit, dict)
            else {}
        )
        benchmark = (
            target_audit.get("benchmark", {}) if isinstance(target_audit, dict) else {}
        )

        coverage = CompetitiveIntelService.build_competitor_query_coverage(
            getattr(audit, "search_results", None) or {},
            getattr(audit, "competitor_audits", None) or [],
            target_audit=target_audit if isinstance(target_audit, dict) else None,
        )

        top_competitors = []
        top_competitor_rate = 0.0
        if isinstance(coverage, dict) and coverage.get("status") == "ok":
            for row in coverage.get("coverage_by_competitor", [])[:5]:
                if not isinstance(row, dict):
                    continue
                top_competitors.append(
                    {
                        "domain": row.get("domain"),
                        "appearance_rate_percent": row.get(
                            "appearance_rate_percent", 0
                        ),
                        "sample_queries": row.get("sample_queries", []),
                    }
                )
            if top_competitors:
                top_competitor_rate = float(
                    top_competitors[0].get("appearance_rate_percent", 0) or 0
                )
        elif normalized_competitors:
            top_competitors = [
                {"domain": d, "appearance_rate_percent": None, "sample_queries": []}
                for d in normalized_competitors[:5]
            ]

        geo_score = float(getattr(audit, "geo_score", 0) or 0)
        if not geo_score and isinstance(benchmark, dict):
            geo_score = float(benchmark.get("geo_score", 0) or 0)

        schema_coverage = float(site_metrics.get("schema_coverage_percent", 0) or 0)
        faq_pages = int(site_metrics.get("faq_page_count", 0) or 0)
        product_pages = int(site_metrics.get("product_page_count", 0) or 0)
        structure_score = float(site_metrics.get("structure_score_percent", 0) or 0)
        citation_rate = 0.0
        if hasattr(audit, "citation_tracking") and audit.citation_tracking:
            # Defensive fallback if relation exists in future.
            citation_rate = 0.0

        return {
            "geo_score": geo_score,
            "schema_coverage_percent": schema_coverage,
            "faq_page_count": faq_pages,
            "product_page_count": product_pages,
            "structure_score_percent": structure_score,
            "citation_rate_percent": citation_rate,
            "top_competitor_rate_proxy_percent": top_competitor_rate,
            "top_competitors": top_competitors,
        }

    @staticmethod
    def _build_opportunities(
        baseline: Dict[str, Any],
        market: str,
        channels: List[str],
    ) -> List[Dict[str, Any]]:
        schema_gap = max(
            0.0, 100.0 - float(baseline.get("schema_coverage_percent", 0) or 0)
        )
        faq_gap = 1 if int(baseline.get("faq_page_count", 0) or 0) == 0 else 0
        product_pages = int(baseline.get("product_page_count", 0) or 0)
        top_comp_rate = float(baseline.get("top_competitor_rate_proxy_percent", 0) or 0)

        opportunities: List[Dict[str, Any]] = [
            {
                "priority": "P1",
                "title": "Product Entity Coverage for AI Citations",
                "problem": "Product pages are not fully machine-citable by generative engines.",
                "why_it_matters": "LLMs cite pages with complete product entities, FAQs, reviews and merchant trust signals.",
                "actions": [
                    "Deploy Product + Offer + Review schema on top revenue pages first.",
                    "Add answer-ready blocks: specs, sizing, returns, shipping and trust FAQs.",
                    "Normalize titles to intent-driven format: Brand + model + use-case + differentiator.",
                ],
                "expected_impact": {
                    "citation_share_delta_percent": 8 if schema_gap >= 40 else 4,
                    "time_to_signal_days": 14,
                },
            },
            {
                "priority": "P1",
                "title": "Marketplace Displacement Pages",
                "problem": "Marketplaces dominate broad queries with aggregator content.",
                "why_it_matters": "You can win high-intent citation windows with first-party comparison pages and proof-focused PDP clusters.",
                "actions": [
                    "Build comparison pages (brand-vs-marketplace) for top product categories.",
                    "Publish buying guides aligned to commercial and transactional intents.",
                    "Add compact Q/A sections optimized for ChatGPT, Perplexity and Google AI summaries.",
                ],
                "expected_impact": {
                    "citation_share_delta_percent": 10 if top_comp_rate >= 40 else 6,
                    "time_to_signal_days": 21,
                },
            },
            {
                "priority": "P2",
                "title": "Evidence and Source Layer",
                "problem": "LLMs down-rank unsupported claims or weak evidence chains.",
                "why_it_matters": "External trusted references and verifiable claims increase citation reliability.",
                "actions": [
                    "Attach credible external references to performance/quality claims.",
                    "Instrument source blocks and author profiles for E-E-A-T strength.",
                    "Create recurring citation monitoring and refresh stale pages every 30 days.",
                ],
                "expected_impact": {
                    "citation_share_delta_percent": 5 if faq_gap else 3,
                    "time_to_signal_days": 30,
                },
            },
        ]

        if product_pages == 0:
            opportunities.append(
                {
                    "priority": "P0",
                    "title": "Product Taxonomy Discovery",
                    "problem": "No product page footprint was detected in the audit crawl.",
                    "why_it_matters": "Without crawlable product inventory, GEO/SEO optimization is structurally limited.",
                    "actions": [
                        "Expose product/category URLs in sitemap and internal navigation.",
                        "Ensure canonical, indexable product pages with stable URL patterns.",
                        "Re-run audit after crawl expansion before citation tracking sprint.",
                    ],
                    "expected_impact": {
                        "citation_share_delta_percent": 0,
                        "time_to_signal_days": 7,
                    },
                }
            )

        return [
            {
                **item,
                "market": market,
                "channels": channels,
            }
            for item in opportunities
        ]

    @staticmethod
    async def _optional_ai_playbook(
        llm_function: Optional[callable],
        brand_name: str,
        domain: str,
        baseline: Dict[str, Any],
        opportunities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if llm_function is None:
            return []

        system_prompt = (
            "You are a senior GEO strategist for ecommerce. " "Return only valid JSON."
        )
        user_prompt = json.dumps(
            {
                "brand_name": brand_name,
                "domain": domain,
                "baseline": baseline,
                "opportunities": opportunities,
                "task": "Create 3 concise strategic plays to beat marketplaces in LLM citations. "
                "Each play: name, execution, risk, metric.",
            },
            ensure_ascii=False,
        )

        try:
            text = await llm_function(
                system_prompt=system_prompt, user_prompt=user_prompt
            )
            if not text:
                return []
            cleaned = text.strip()
            if "```" in cleaned:
                cleaned = cleaned.replace("```json", "").replace("```", "").strip()
            start = cleaned.find("[")
            end = cleaned.rfind("]")
            if start != -1 and end != -1:
                cleaned = cleaned[start : end + 1]
            parsed = json.loads(cleaned)
            if not isinstance(parsed, list):
                return []
            compact: List[Dict[str, Any]] = []
            for row in parsed[:3]:
                if not isinstance(row, dict):
                    continue
                compact.append(
                    {
                        "name": row.get("name") or row.get("title") or "Play",
                        "execution": row.get("execution") or row.get("actions") or "",
                        "risk": row.get("risk") or "",
                        "metric": row.get("metric") or "Citation share",
                    }
                )
            return compact
        except Exception as exc:
            logger.warning(f"AI playbook generation failed: {exc}")
            return []

    @staticmethod
    async def generate_campaign(
        db: Session,
        audit: Audit,
        competitor_domains: Optional[List[str]] = None,
        market: Optional[str] = None,
        channels: Optional[List[str]] = None,
        objective: Optional[str] = None,
        llm_function: Optional[callable] = None,
        use_ai_playbook: bool = False,
    ) -> GeoCommerceCampaign:
        domain = GeoCommerceService._normalize_domain(audit.url or audit.domain or "")
        brand_name = GeoCommerceService._extract_brand_name(domain)
        selected_market = GeoCommerceService._extract_market(audit, market)
        selected_channels = channels or ["chatgpt", "perplexity", "google-ai"]
        normalized_competitors = GeoCommerceService._extract_competitor_domains(
            audit, competitor_domains
        )
        baseline = GeoCommerceService._extract_baseline(audit, normalized_competitors)
        opportunities = GeoCommerceService._build_opportunities(
            baseline, selected_market, selected_channels
        )

        kpis = {
            "primary_kpi": "Citation Share",
            "target": {
                "citation_share_increase_percent": 18,
                "qualified_clicks_increase_percent": 12,
                "sales_uplift_percent": 8,
            },
            "measurement_window_days": 90,
        }

        roadmap = {
            "week_1_2": [
                "Prioritize revenue pages and normalize schema coverage.",
                "Publish first wave of comparison and answer blocks.",
            ],
            "week_3_6": [
                "Launch competitor displacement pages and FAQ clusters.",
                "Run citation tracking across selected channels and refine low-performing pages.",
            ],
            "week_7_12": [
                "Scale winning templates across product categories.",
                "Operationalize monthly refresh cycle and competitive monitoring.",
            ],
        }

        ai_playbook = []
        if use_ai_playbook:
            ai_playbook = await GeoCommerceService._optional_ai_playbook(
                llm_function=llm_function,
                brand_name=brand_name,
                domain=domain,
                baseline=baseline,
                opportunities=opportunities,
            )

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "brand_name": brand_name,
            "domain": domain,
            "market": selected_market,
            "channels": selected_channels,
            "objective": objective
            or "Increase AI citation share and displace marketplace dominance in high-intent product queries.",
            "baseline": baseline,
            "kpis": kpis,
            "opportunities": opportunities,
            "roadmap": roadmap,
            "ai_playbook": ai_playbook,
            "assumptions": [
                "Citation share is tracked as a proxy metric using available LLM/query signals.",
                "Results depend on implementation quality and crawl/indexation health.",
            ],
        }

        campaign = GeoCommerceCampaign(
            audit_id=audit.id,
            market=selected_market,
            channels=selected_channels,
            objective=payload["objective"],
            payload=payload,
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return campaign

    @staticmethod
    def get_latest_campaign(
        db: Session, audit_id: int
    ) -> Optional[GeoCommerceCampaign]:
        return (
            db.query(GeoCommerceCampaign)
            .filter(GeoCommerceCampaign.audit_id == audit_id)
            .order_by(GeoCommerceCampaign.created_at.desc())
            .first()
        )

    @staticmethod
    def _domain_matches(candidate: str, target: str) -> bool:
        c = (candidate or "").lower().replace("www.", "")
        t = (target or "").lower().replace("www.", "")
        if not c or not t:
            return False
        return c == t or c.endswith(f".{t}") or t.endswith(f".{c}")

    @staticmethod
    def _safe_json_parse(raw_text: str) -> Dict[str, Any] | None:
        cleaned = (raw_text or "").strip()
        if not cleaned:
            return None
        if "```" in cleaned:
            cleaned = cleaned.replace("```json", "").replace("```", "").strip()
        try:
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, dict) else None
        except Exception:  # nosec B110
            pass
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end > start:
            try:
                parsed = json.loads(cleaned[start : end + 1])
                return parsed if isinstance(parsed, dict) else None
            except Exception:
                return None
        return None

    @staticmethod
    def _extract_site_signals(audit: Audit) -> Dict[str, Any]:
        target_audit = getattr(audit, "target_audit", None) or {}
        site_metrics = (
            target_audit.get("site_metrics", {})
            if isinstance(target_audit, dict)
            else {}
        )
        return {
            "geo_score": float(getattr(audit, "geo_score", 0) or 0),
            "schema_coverage_percent": float(
                site_metrics.get("schema_coverage_percent", 0) or 0
            ),
            "structure_score_percent": float(
                site_metrics.get("structure_score_percent", 0) or 0
            ),
            "h1_coverage_percent": float(
                site_metrics.get("h1_coverage_percent", 0) or 0
            ),
            "faq_page_count": int(site_metrics.get("faq_page_count", 0) or 0),
            "product_page_count": int(site_metrics.get("product_page_count", 0) or 0),
            "pages_analyzed": int(site_metrics.get("pages_analyzed", 0) or 0),
        }

    @staticmethod
    def _fallback_query_diagnosis(
        *,
        query: str,
        market: str,
        audited_domain: str,
        top_k: int,
        target_position: Optional[int],
        top_result: Dict[str, Any] | None,
        site_signals: Dict[str, Any],
        audit_url: str,
    ) -> Dict[str, Any]:
        top_domain = (top_result or {}).get("domain", "unknown domain")
        why_not_first: List[str] = []
        disadvantages: List[Dict[str, str]] = []
        action_plan: List[Dict[str, Any]] = []

        if target_position is None:
            why_not_first.append(
                f"{audited_domain} did not appear in the top {top_k} results for '{query}' in market {market}."
            )
        elif target_position > 1:
            why_not_first.append(
                f"{audited_domain} is currently at position #{target_position}; {top_domain} holds position #1."
            )
        else:
            why_not_first.append(
                f"{audited_domain} is already #1 for this query snapshot; monitor stability and defensive optimization."
            )

        schema_coverage = float(site_signals.get("schema_coverage_percent", 0) or 0)
        structure_score = float(site_signals.get("structure_score_percent", 0) or 0)
        faq_pages = int(site_signals.get("faq_page_count", 0) or 0)

        if schema_coverage < 60:
            why_not_first.append(
                f"Schema coverage is low ({schema_coverage:.1f}%), reducing machine-readability for AI ranking and citations."
            )
            disadvantages.append(
                {
                    "area": "Structured data",
                    "gap": f"{audited_domain} has {schema_coverage:.1f}% schema coverage in audit signals.",
                    "impact": "Lower eligibility for rich, citable product and FAQ snippets.",
                }
            )

        if structure_score < 60:
            why_not_first.append(
                f"Structural clarity score is limited ({structure_score:.1f}%), hurting answer extraction quality."
            )
            disadvantages.append(
                {
                    "area": "Content structure",
                    "gap": f"Structure score is {structure_score:.1f}% and may underperform against top-ranked pages.",
                    "impact": "LLMs prioritize cleaner answer fragments and clearer intent mapping.",
                }
            )

        if faq_pages == 0:
            why_not_first.append(
                "No FAQ page footprint detected; you miss high-intent Q&A citation windows."
            )
            disadvantages.append(
                {
                    "area": "FAQ / Q&A coverage",
                    "gap": "No FAQ pages detected in the audited footprint.",
                    "impact": "Reduced inclusion in conversational answer snippets.",
                }
            )

        action_plan.append(
            {
                "priority": "P1",
                "action": "Ship query-specific landing block for the exact query intent with concise answer-first structure.",
                "expected_impact": "High",
                "evidence": f"Query snapshot shows top domain {top_domain} leading this intent.",
            }
        )
        action_plan.append(
            {
                "priority": "P2",
                "action": "Increase Product/Offer/FAQ schema coverage on pages targeting this query cluster.",
                "expected_impact": "High" if schema_coverage < 60 else "Medium",
                "evidence": f"Audit schema coverage is {schema_coverage:.1f}% [Source: {audit_url}].",
            }
        )
        action_plan.append(
            {
                "priority": "P3",
                "action": "Add external trust references and comparative proof blocks versus the current top result.",
                "expected_impact": "Medium",
                "evidence": f"Top result currently attributed to {top_domain}.",
            }
        )

        return {
            "why_not_first": why_not_first,
            "disadvantages_vs_top1": disadvantages,
            "action_plan": action_plan,
        }

    @staticmethod
    async def _llm_query_diagnosis(
        *,
        llm_function: Optional[callable],
        query: str,
        market: str,
        audited_domain: str,
        target_position: Optional[int],
        top_result: Dict[str, Any] | None,
        serp_results: List[Dict[str, Any]],
        site_signals: Dict[str, Any],
        audit_url: str,
    ) -> Dict[str, Any]:
        if llm_function is None:
            return {}

        system_prompt = (
            "You are a senior GEO ecommerce analyst. "
            "Return ONLY valid JSON and never fabricate data."
        )
        user_prompt = json.dumps(
            {
                "task": "Diagnose why audited domain is not #1 and provide plan to beat top #1.",
                "query": query,
                "market": market,
                "audited_domain": audited_domain,
                "target_position": target_position,
                "top_result": top_result or {},
                "serp_results": serp_results,
                "site_signals": site_signals,
                "source": audit_url,
                "output_schema": {
                    "why_not_first": ["reason 1", "reason 2"],
                    "disadvantages_vs_top1": [
                        {"area": "string", "gap": "string", "impact": "string"}
                    ],
                    "action_plan": [
                        {
                            "priority": "P1|P2|P3",
                            "action": "string",
                            "expected_impact": "High|Medium|Low",
                            "evidence": "string",
                        }
                    ],
                },
                "constraints": [
                    "Use only provided signals.",
                    "No invented metrics.",
                    "Keep max 5 items per list.",
                ],
            },
            ensure_ascii=False,
        )

        try:
            raw = await llm_function(
                system_prompt=system_prompt, user_prompt=user_prompt
            )
            parsed = GeoCommerceService._safe_json_parse(raw)
            if not parsed:
                return {}
            return {
                "why_not_first": parsed.get("why_not_first")
                if isinstance(parsed.get("why_not_first"), list)
                else [],
                "disadvantages_vs_top1": parsed.get("disadvantages_vs_top1")
                if isinstance(parsed.get("disadvantages_vs_top1"), list)
                else [],
                "action_plan": parsed.get("action_plan")
                if isinstance(parsed.get("action_plan"), list)
                else [],
            }
        except Exception as exc:
            logger.warning(f"LLM diagnosis failed for commerce query analyzer: {exc}")
            return {}

    @staticmethod
    async def analyze_query(
        *,
        db: Session,
        audit: Audit,
        query: str,
        market: str,
        top_k: int = 10,
        language: str = "es",
        llm_function: Optional[callable] = None,
    ) -> GeoCommerceCampaign:
        domain = GeoCommerceService._normalize_domain(audit.url or audit.domain or "")
        if not domain:
            raise ValueError(
                "Unable to resolve audited domain for commerce query analysis."
            )

        search_payload = await kimi_search_serp(
            query=query,
            market=market,
            top_k=top_k,
            language=language,
        )
        serp_results = (
            search_payload.get("results", [])
            if isinstance(search_payload, dict)
            else []
        )
        if not serp_results:
            raise ValueError("Kimi search returned zero results for this query.")

        top_result = serp_results[0] if serp_results else None
        target_position = None
        for row in serp_results:
            if GeoCommerceService._domain_matches(row.get("domain", ""), domain):
                target_position = int(row.get("position", 0) or 0) or None
                break

        site_signals = GeoCommerceService._extract_site_signals(audit)
        fallback = GeoCommerceService._fallback_query_diagnosis(
            query=query,
            market=market,
            audited_domain=domain,
            top_k=top_k,
            target_position=target_position,
            top_result=top_result,
            site_signals=site_signals,
            audit_url=audit.url,
        )
        llm_diagnosis = await GeoCommerceService._llm_query_diagnosis(
            llm_function=llm_function,
            query=query,
            market=market,
            audited_domain=domain,
            target_position=target_position,
            top_result=top_result,
            serp_results=serp_results,
            site_signals=site_signals,
            audit_url=audit.url,
        )

        why_not_first = llm_diagnosis.get("why_not_first") or fallback["why_not_first"]
        disadvantages = (
            llm_diagnosis.get("disadvantages_vs_top1")
            or fallback["disadvantages_vs_top1"]
        )
        action_plan = llm_diagnosis.get("action_plan") or fallback["action_plan"]
        evidence = search_payload.get("evidence", [])
        if isinstance(evidence, list):
            evidence = evidence[: min(len(evidence), top_k)]
        else:
            evidence = []

        payload = {
            "mode": "query_analyzer",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "market": market.upper(),
            "audited_domain": domain,
            "target_position": target_position,
            "top_k": top_k,
            "top_result": top_result,
            "results": serp_results,
            "why_not_first": why_not_first,
            "disadvantages_vs_top1": disadvantages,
            "action_plan": action_plan,
            "site_signals": site_signals,
            "evidence": evidence,
            "provider": search_payload.get("provider", "kimi-2.5-search"),
        }

        record = GeoCommerceCampaign(
            audit_id=audit.id,
            market=market.upper(),
            channels=["kimi-search"],
            objective=f"Beat current #1 for query '{query}' in market {market.upper()}",
            payload=payload,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def get_latest_query_analysis(
        db: Session, audit_id: int
    ) -> Optional[GeoCommerceCampaign]:
        recent = (
            db.query(GeoCommerceCampaign)
            .filter(GeoCommerceCampaign.audit_id == audit_id)
            .order_by(GeoCommerceCampaign.created_at.desc())
            .limit(25)
            .all()
        )
        for row in recent:
            if (
                isinstance(row.payload, dict)
                and row.payload.get("mode") == "query_analyzer"
            ):
                return row
        return None
