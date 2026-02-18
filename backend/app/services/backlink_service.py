import json
import logging
import re
from typing import Any, Dict, List, Set
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.llm_kimi import get_llm_function
from ..models import Audit, Backlink
from .crawler_service import CrawlerService

logger = logging.getLogger(__name__)


class BacklinkService:
    def __init__(self, db: Session):
        self.db = db
        self.llm_function = get_llm_function()  # KIMI via NVIDIA NIM

    _CONTEXT_STOPWORDS = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "from",
        "this",
        "your",
        "our",
        "you",
        "are",
        "como",
        "para",
        "con",
        "por",
        "una",
        "uno",
        "del",
        "las",
        "los",
        "que",
        "www",
        "http",
        "https",
    }

    _IRRELEVANT_SIGNAL_TERMS = {
        "unrelated",
        "irrelevant",
        "not related",
        "no relation",
        "exclude from brand monitoring",
        "completely unrelated",
        "no relacionado",
        "irrelevante",
        "sin relación",
        "excluir del monitoreo",
    }

    _NOISE_TERMS = {
        "trailer",
        "flatbed",
        "industrial platform",
        "plataforma de carga",
        "mudanzas",
        "wheel",
        "ruedas",
        "zapatos",
        "heels",
    }

    @staticmethod
    def _clean_domain(domain: str) -> str:
        return (
            (domain or "")
            .replace("www.", "")
            .replace("https://", "")
            .replace("http://", "")
            .strip("/")
            .lower()
        )

    @staticmethod
    def _extract_brand_name(clean_domain: str) -> str:
        return (clean_domain.split(".")[0] if clean_domain else "").lower()

    @classmethod
    def _extract_context_terms(cls, audit: Audit, brand_name: str) -> List[str]:
        if not audit:
            return []

        texts: List[str] = []
        try:
            ext = audit.external_intelligence or {}
            if isinstance(ext, dict):
                category = ext.get("category")
                if isinstance(category, str):
                    texts.append(category)
        except Exception:  # nosec B110
            pass

        try:
            target = audit.target_audit or {}
            if isinstance(target, dict):
                content = target.get("content", {})
                if isinstance(content, dict):
                    title = content.get("title")
                    meta = content.get("meta_description")
                    if isinstance(title, str):
                        texts.append(title)
                    if isinstance(meta, str):
                        texts.append(meta)
        except Exception:  # nosec B110
            pass

        brand_tokens = set(re.findall(r"[a-z0-9]+", brand_name.lower()))
        terms: List[str] = []
        for text in texts:
            for token in re.findall(r"[a-z0-9]+", (text or "").lower()):
                if (
                    len(token) >= 4
                    and token not in cls._CONTEXT_STOPWORDS
                    and token not in brand_tokens
                    and not token.isdigit()
                ):
                    terms.append(token)

        # Stable order + dedupe
        deduped = []
        seen = set()
        for t in terms:
            if t not in seen:
                deduped.append(t)
                seen.add(t)
        return deduped[:8]

    @classmethod
    def _build_brand_mentions_query(
        cls, brand_name: str, domain: str, context_terms: List[str]
    ) -> str:
        if context_terms:
            context_clause = " OR ".join(f'"{t}"' for t in context_terms[:4])
            return f'"{brand_name}" ({context_clause}) -site:{domain}'
        return f'"{brand_name}" -site:{domain}'

    @staticmethod
    def _is_excluded_domain(url: str, excluded_domains: List[str]) -> bool:
        host = (urlparse(url).netloc or "").lower()
        return any(ex in host for ex in excluded_domains)

    @classmethod
    def _is_relevant_technical_result(
        cls, item: Dict[str, Any], clean_domain: str, excluded_domains: List[str]
    ) -> bool:
        link = (item.get("link") or "").strip().lower()
        if not link.startswith("http"):
            return False
        if clean_domain and clean_domain in link:
            return False
        if cls._is_excluded_domain(link, excluded_domains):
            return False

        text_blob = (
            f"{item.get('title', '')} {item.get('snippet', '')} {item.get('link', '')}"
        ).lower()
        return clean_domain in text_blob or f"www.{clean_domain}" in text_blob

    @classmethod
    def _is_relevant_brand_result(
        cls,
        item: Dict[str, Any],
        brand_name: str,
        clean_domain: str,
        context_terms: List[str],
        excluded_domains: List[str],
    ) -> bool:
        link = (item.get("link") or "").strip().lower()
        if not link.startswith("http"):
            return False
        if cls._is_excluded_domain(link, excluded_domains):
            return False

        text_blob = (
            f"{item.get('title', '')} {item.get('snippet', '')} {item.get('link', '')}"
        ).lower()

        brand_present = brand_name in text_blob or clean_domain in text_blob
        if not brand_present:
            return False

        # If we have contextual terms from the audited site, require at least one.
        if context_terms and not any(term in text_blob for term in context_terms):
            return False

        # Generic noise guard for ambiguous brands.
        if any(noise in text_blob for noise in cls._NOISE_TERMS):
            return False

        return True

    @classmethod
    def _analysis_is_irrelevant(cls, analysis: Dict[str, Any]) -> bool:
        if not isinstance(analysis, dict):
            return False

        text = (
            f"{analysis.get('summary', '')} {analysis.get('recommendation', '')}"
        ).lower()
        if any(term in text for term in cls._IRRELEVANT_SIGNAL_TERMS):
            return True

        score = analysis.get("relevance_score", 0)
        try:
            score_val = int(score)
        except (TypeError, ValueError):
            score_val = 0
        return score_val < 30

    @staticmethod
    def _build_anchor_text(item: Dict[str, Any], analysis: Dict[str, Any]) -> str:
        title = (item.get("title") or "").strip()
        topic = str((analysis or {}).get("topic") or "").strip()
        summary = str((analysis or {}).get("summary") or "").strip()

        if summary:
            candidate = f"{topic}: {summary}" if topic else summary
        elif title:
            candidate = title
        else:
            candidate = "Brand mention"

        return candidate[:500]

    async def _crawl_and_build_graph(
        self, domain: str, max_pages: int = 50
    ) -> Dict[str, Set[str]]:
        """
        Crawls the site to build an internal link graph.
        Returns: {url: {set of outgoing links}}
        """
        base_url = f"https://{domain}"
        queue = [base_url]
        visited = set()
        graph = {}  # url -> set(outgoing_links)

        # Simple BFS crawl
        while queue and len(visited) < max_pages:
            url = queue.pop(0)
            if url in visited:
                continue

            visited.add(url)
            content = await CrawlerService.get_page_content(url)
            if not content:
                continue

            soup = BeautifulSoup(content, "html.parser")
            outgoing = set()

            for a in soup.find_all("a", href=True):
                href = a.get("href")
                full_url = urljoin(url, href)

                # Normalize
                parsed = urlparse(full_url)
                if parsed.netloc == domain or parsed.netloc == f"www.{domain}":
                    # Internal link
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    outgoing.add(clean_url)
                    if clean_url not in visited and clean_url not in queue:
                        queue.append(clean_url)

            graph[url] = outgoing

        return graph

    async def analyze_backlinks(self, audit_id: int, domain: str) -> List[Backlink]:
        """
        Analyzes Internal Links, Technical Backlinks, and Brand Mentions with AI analysis.
        """
        logger.info(f"Starting backlink analysis for audit {audit_id}, domain {domain}")

        created_backlinks = []

        try:
            # 1. Internal Link Analysis (Real Crawl)
            logger.info("Step 1: Crawling internal links...")
            graph = await self._crawl_and_build_graph(domain)
            logger.info(f"Crawled {len(graph)} pages")

            # Calculate simplified PageRank or just count incoming links
            incoming_counts = {}
            for source, targets in graph.items():
                for target in targets:
                    incoming_counts[target] = incoming_counts.get(target, 0) + 1

            # For this feature, we will store the top internal pages by incoming link count
            sorted_pages = sorted(
                incoming_counts.items(), key=lambda x: x[1], reverse=True
            )[:20]

            for url, count in sorted_pages:
                bl = Backlink(
                    audit_id=audit_id,
                    source_url="INTERNAL_NETWORK",
                    target_url=url,
                    anchor_text=f"{count} internal links",
                    is_dofollow=True,
                    domain_authority=None,
                )
                self.db.add(bl)
                created_backlinks.append(bl)

            logger.info(f"Added {len(sorted_pages)} internal links")

            # 2. Technical External Backlinks (link: operator)
            logger.info("🔗 Step 2: Fetching technical backlinks...")
            technical_backlinks = await self._fetch_technical_backlinks_google(
                audit_id, domain
            )
            created_backlinks.extend(technical_backlinks)
            logger.info(f"Added {len(technical_backlinks)} technical backlinks")

            # 3. Brand Mentions with AI Analysis
            logger.info("🏷️ Step 3: Analyzing brand mentions...")
            brand_mentions = await self._fetch_brand_mentions_with_analysis(
                audit_id, domain
            )
            created_backlinks.extend(brand_mentions)
            logger.info(f"Added {len(brand_mentions)} brand mentions")

            self.db.commit()
            logger.info(
                f"Backlink analysis completed: {len(created_backlinks)} total backlinks"
            )
            return created_backlinks

        except Exception as e:
            logger.error(f"Backlink analysis failed: {e}", exc_info=True)
            self.db.rollback()
            raise

    async def _fetch_technical_backlinks_google(
        self, audit_id: int, domain: str
    ) -> List[Backlink]:
        """
        Fetches technical backlinks using Google CSE 'link:' operator.
        """
        if not settings.GOOGLE_API_KEY or not settings.CSE_ID:
            return []
        clean_domain = self._clean_domain(domain)
        excluded_domains = [
            "mercadolibre",
            "mercadolivre",
            "amazon",
            "ebay",
            "aliexpress",
            "alibaba",
            "walmart",
            "target",
            "bestbuy",
            "wish.com",
            "shopee",
            "lazada",
            "etsy",
            "rakuten",
            "zalando",
            "facebook.com",
            "instagram.com",
            "twitter.com",
            "x.com",
            "youtube.com",
            "pinterest.com",
            "linkedin.com",
            "tiktok.com",
        ]

        query = f"link:{domain} -site:{domain}"
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": settings.GOOGLE_API_KEY,
            "cx": settings.CSE_ID,
            "q": query,
            "num": 10,
        }

        links = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data.get("items", [])
                        seen_links = set()
                        for item in items:
                            source_url = (item.get("link") or "").strip()
                            if source_url in seen_links:
                                continue
                            if not self._is_relevant_technical_result(
                                item, clean_domain, excluded_domains
                            ):
                                continue
                            seen_links.add(source_url)

                            bl = Backlink(
                                audit_id=audit_id,
                                source_url="TECHNICAL_BACKLINK",
                                target_url=source_url,
                                anchor_text=(item.get("title") or "Technical Backlink")[
                                    :500
                                ],
                                is_dofollow=True,
                                domain_authority=0,
                            )
                            self.db.add(bl)
                            links.append(bl)
                    else:
                        logger.warning(
                            f"Google CSE Technical Backlink Error: {resp.status}"
                        )
        except Exception as e:
            logger.error(f"Error fetching technical backlinks: {e}")

        return links

    async def _fetch_brand_mentions_with_analysis(
        self, audit_id: int, domain: str
    ) -> List[Backlink]:
        """
        Fetches brand mentions and analyzes them with AI in BATCH for speed and quality.
        Filters out irrelevant e-commerce results and non-existent pages.
        """
        if not settings.GOOGLE_API_KEY or not settings.CSE_ID:
            return []

        # Extract brand name from domain + load contextual terms from audited content
        clean_domain = self._clean_domain(domain)
        brand_name = self._extract_brand_name(clean_domain)
        audit = self.db.query(Audit).filter(Audit.id == audit_id).first()
        context_terms = self._extract_context_terms(audit, brand_name)

        # Domains to exclude - e-commerce sites and generic platforms that cause noise
        EXCLUDED_DOMAINS = [
            "mercadolibre",
            "mercadolivre",
            "amazon",
            "ebay",
            "aliexpress",
            "alibaba",
            "walmart",
            "target",
            "bestbuy",
            "wish.com",
            "shopee",
            "lazada",
            "etsy",
            "rakuten",
            "zalando",
            "facebook.com",
            "instagram.com",
            "twitter.com",
            "x.com",
            "youtube.com",
            "pinterest.com",
            "linkedin.com",
            "tiktok.com",
        ]

        # Search for brand mentions excluding the domain itself; add context terms when available.
        query = self._build_brand_mentions_query(brand_name, domain, context_terms)
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": settings.GOOGLE_API_KEY,
            "cx": settings.CSE_ID,
            "q": query,
            "num": 10,
        }

        mentions = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data.get("items", [])

                        # Pre-filter items
                        filtered_items = []
                        seen_links = set()
                        for item in items:
                            source_url = (item.get("link", "") or "").strip().lower()
                            if source_url in seen_links:
                                continue
                            if not self._is_relevant_brand_result(
                                item,
                                brand_name=brand_name,
                                clean_domain=clean_domain,
                                context_terms=context_terms,
                                excluded_domains=EXCLUDED_DOMAINS,
                            ):
                                continue
                            seen_links.add(source_url)
                            filtered_items.append(item)

                        if not filtered_items:
                            logger.info(
                                "No relevant brand mentions found after filtering."
                            )
                            return []

                        logger.info(
                            f"📋 Analyzing {len(filtered_items)} mentions in BATCH..."
                        )

                        # --- BATCH ANALYSIS WITH AI ---
                        batch_data = []
                        for i, item in enumerate(filtered_items):
                            batch_data.append(
                                {
                                    "id": i,
                                    "title": item.get("title", ""),
                                    "snippet": item.get("snippet", ""),
                                    "url": item.get("link", ""),
                                }
                            )

                        system_prompt = f"You are an expert SEO and brand analyst. Analyze brand mentions for '{brand_name}' and provide insights in a JSON array."
                        user_prompt = f"""
Analyze the following brand mentions. For each one, provide:
- id: match the provided id
- sentiment: "positive", "negative", or "neutral"
- topic: Main topic (e.g., "Tutorial", "Review", "Discussion", "Comparison")
- summary: A 1-sentence summary of what they're saying
- recommendation: 1-sentence action for the brand owner
- relevance_score: 0-100 (how relevant/important is this mention)

Data to analyze:
{json.dumps(batch_data, ensure_ascii=False)}

Return ONLY a JSON array of objects.
"""
                        try:
                            from .pipeline_service import PipelineService

                            response = await self.llm_function(
                                system_prompt, user_prompt
                            )

                            # Use robust parsing from PipelineService
                            parsed_results = PipelineService.parse_agent_json_or_raw(
                                response
                            )

                            if not isinstance(parsed_results, list):
                                # If it returned a dict with a key like 'fix_plan' or similar
                                if isinstance(parsed_results, dict):
                                    for key in ["results", "mentions", "items"]:
                                        if key in parsed_results and isinstance(
                                            parsed_results[key], list
                                        ):
                                            parsed_results = parsed_results[key]
                                            break

                            if isinstance(parsed_results, list):
                                for res_idx, analysis in enumerate(parsed_results):
                                    # Fallback index matching if ID not returned
                                    idx_raw = analysis.get("id", res_idx)
                                    try:
                                        idx = int(idx_raw)
                                    except (TypeError, ValueError):
                                        idx = res_idx
                                    if idx < len(filtered_items):
                                        if self._analysis_is_irrelevant(analysis):
                                            continue

                                        item = filtered_items[idx]
                                        score_raw = analysis.get("relevance_score", 0)
                                        try:
                                            score_value = int(score_raw or 0)
                                        except (TypeError, ValueError):
                                            score_value = 0
                                        bl = Backlink(
                                            audit_id=audit_id,
                                            source_url="BRAND_MENTION",
                                            target_url=item.get("link"),
                                            anchor_text=self._build_anchor_text(
                                                item, analysis
                                            ),
                                            is_dofollow=analysis.get("sentiment")
                                            == "positive",
                                            domain_authority=score_value,
                                        )
                                        self.db.add(bl)
                                        mentions.append(bl)
                            else:
                                logger.error(
                                    "Failed to parse batch AI response as list"
                                )

                        except Exception as e:
                            logger.error(
                                f"Error in batch AI brand mention analysis: {e}"
                            )
                    else:
                        logger.warning(f"Google CSE Brand Mention Error: {resp.status}")
        except Exception as e:
            logger.error(f"Error fetching brand mentions: {e}")

        return mentions

    async def _analyze_mention_with_ai(
        self, brand_name: str, title: str, snippet: str, url: str
    ) -> Dict[str, Any]:
        """
        DEPRECATED: Individual analysis replaced by _fetch_brand_mentions_with_analysis batching.
        """
        return {
            "sentiment": "neutral",
            "topic": "Deprecated",
            "summary": snippet[:200] if snippet else "N/A",
            "recommendation": "Use batch analysis",
            "relevance_score": 0,
        }

    def get_backlinks(self, audit_id: int) -> List[Backlink]:
        return self.db.query(Backlink).filter(Backlink.audit_id == audit_id).all()
