from sqlalchemy.orm import Session
from ..models import Backlink, Audit
from ..core.config import settings
from ..core.llm_kimi import get_llm_function
from .crawler_service import CrawlerService
from typing import List, Dict, Any, Set
import logging
import aiohttp
import asyncio
import json
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class BacklinkService:
    def __init__(self, db: Session):
        self.db = db
        self.llm_function = get_llm_function()  # KIMI via NVIDIA NIM

    async def _crawl_and_build_graph(self, domain: str, max_pages: int = 50) -> Dict[str, Set[str]]:
        """
        Crawls the site to build an internal link graph.
        Returns: {url: {set of outgoing links}}
        """
        base_url = f"https://{domain}"
        queue = [base_url]
        visited = set()
        graph = {} # url -> set(outgoing_links)
        
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
        logger.info(f"🔍 Starting backlink analysis for audit {audit_id}, domain {domain}")
        
        created_backlinks = []
        
        try:
            # 1. Internal Link Analysis (Real Crawl)
            logger.info("📊 Step 1: Crawling internal links...")
            graph = await self._crawl_and_build_graph(domain)
            logger.info(f"✅ Crawled {len(graph)} pages")
            
            # Calculate simplified PageRank or just count incoming links
            incoming_counts = {}
            for source, targets in graph.items():
                for target in targets:
                    incoming_counts[target] = incoming_counts.get(target, 0) + 1

            # For this feature, we will store the top internal pages by incoming link count
            sorted_pages = sorted(incoming_counts.items(), key=lambda x: x[1], reverse=True)[:20]
            
            for url, count in sorted_pages:
                bl = Backlink(
                    audit_id=audit_id,
                    source_url="INTERNAL_NETWORK",
                    target_url=url,
                    anchor_text=f"{count} internal links",
                    is_dofollow=True,
                    domain_authority=None
                )
                self.db.add(bl)
                created_backlinks.append(bl)
            
            logger.info(f"✅ Added {len(sorted_pages)} internal links")

            # 2. Technical External Backlinks (link: operator)
            logger.info("🔗 Step 2: Fetching technical backlinks...")
            technical_backlinks = await self._fetch_technical_backlinks_google(audit_id, domain)
            created_backlinks.extend(technical_backlinks)
            logger.info(f"✅ Added {len(technical_backlinks)} technical backlinks")

            # 3. Brand Mentions with AI Analysis
            logger.info("🏷️ Step 3: Analyzing brand mentions...")
            brand_mentions = await self._fetch_brand_mentions_with_analysis(audit_id, domain)
            created_backlinks.extend(brand_mentions)
            logger.info(f"✅ Added {len(brand_mentions)} brand mentions")
                
            self.db.commit()
            logger.info(f"✅ Backlink analysis completed: {len(created_backlinks)} total backlinks")
            return created_backlinks
            
        except Exception as e:
            logger.error(f"❌ Backlink analysis failed: {e}", exc_info=True)
            self.db.rollback()
            raise

    async def _fetch_technical_backlinks_google(self, audit_id: int, domain: str) -> List[Backlink]:
        """
        Fetches technical backlinks using Google CSE 'link:' operator.
        """
        if not settings.GOOGLE_API_KEY or not settings.CSE_ID:
            return []
            
        query = f"link:{domain} -site:{domain}"
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": settings.GOOGLE_API_KEY,
            "cx": settings.CSE_ID,
            "q": query,
            "num": 10
        }
        
        links = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data.get("items", [])
                        for item in items:
                            source_url = item.get("link")
                            
                            # Filter self-references
                            if domain in source_url:
                                continue
                                
                            bl = Backlink(
                                audit_id=audit_id,
                                source_url="TECHNICAL_BACKLINK",
                                target_url=source_url,
                                anchor_text=item.get("title", "Technical Backlink"),
                                is_dofollow=True,
                                domain_authority=0
                            )
                            self.db.add(bl)
                            links.append(bl)
                    else:
                        logger.warning(f"Google CSE Technical Backlink Error: {resp.status}")
        except Exception as e:
            logger.error(f"Error fetching technical backlinks: {e}")
            
        return links

    async def _fetch_brand_mentions_with_analysis(self, audit_id: int, domain: str) -> List[Backlink]:
        """
        Fetches brand mentions and analyzes them with AI in BATCH for speed and quality.
        Filters out irrelevant e-commerce results and non-existent pages.
        """
        if not settings.GOOGLE_API_KEY or not settings.CSE_ID:
            return []
        
        # Extract brand name from domain
        clean_domain = domain.replace("www.", "").replace("https://", "").replace("http://", "")
        brand_name = clean_domain.split(".")[0]
        
        # Domains to exclude - e-commerce sites and generic platforms that cause noise
        EXCLUDED_DOMAINS = [
            "mercadolibre", "mercadolivre", "amazon", "ebay", "aliexpress",
            "alibaba", "walmart", "target", "bestbuy", "wish.com",
            "shopee", "lazada", "etsy", "rakuten", "zalando",
            "facebook.com", "instagram.com", "twitter.com", "x.com", 
            "youtube.com", "pinterest.com", "linkedin.com", "tiktok.com"
        ]
        
        # FIX: Search for brand mentions EXCLUDING the domain itself
        # This avoids finding the target site's own pages as "external mentions"
        query = f'"{brand_name}" -site:{domain}'
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": settings.GOOGLE_API_KEY,
            "cx": settings.CSE_ID,
            "q": query,
            "num": 10
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
                        for item in items:
                            source_url = item.get("link", "").lower()
                            
                            # 1. Exclude irrelevant domains
                            if any(excluded in source_url for excluded in EXCLUDED_DOMAINS):
                                continue
                            
                            # 2. Basic URL validation (skip obviously broken links if any)
                            if not source_url.startswith("http"):
                                continue
                                
                            filtered_items.append(item)
                        
                        if not filtered_items:
                            logger.info("No relevant brand mentions found after filtering.")
                            return []

                        logger.info(f"📋 Analyzing {len(filtered_items)} mentions in BATCH...")
                        
                        # --- BATCH ANALYSIS WITH AI ---
                        batch_data = []
                        for i, item in enumerate(filtered_items):
                            batch_data.append({
                                "id": i,
                                "title": item.get("title", ""),
                                "snippet": item.get("snippet", ""),
                                "url": item.get("link", "")
                            })
                            
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
                            response = await self.llm_function(system_prompt, user_prompt)
                            
                            # Use robust parsing from PipelineService
                            parsed_results = PipelineService.parse_agent_json_or_raw(response)
                            
                            if not isinstance(parsed_results, list):
                                # If it returned a dict with a key like 'fix_plan' or similar
                                if isinstance(parsed_results, dict):
                                    for key in ["results", "mentions", "items"]:
                                        if key in parsed_results and isinstance(parsed_results[key], list):
                                            parsed_results = parsed_results[key]
                                            break
                            
                            if isinstance(parsed_results, list):
                                for res_idx, analysis in enumerate(parsed_results):
                                    # Fallback index matching if ID not returned
                                    idx = analysis.get("id", res_idx)
                                    if idx < len(filtered_items):
                                        item = filtered_items[idx]
                                        bl = Backlink(
                                            audit_id=audit_id,
                                            source_url="BRAND_MENTION",
                                            target_url=item.get("link"),
                                            anchor_text=json.dumps(analysis),
                                            is_dofollow=analysis.get("sentiment") == "positive",
                                            domain_authority=analysis.get("relevance_score", 0)
                                        )
                                        self.db.add(bl)
                                        mentions.append(bl)
                            else:
                                logger.error("Failed to parse batch AI response as list")
                                
                        except Exception as e:
                            logger.error(f"Error in batch AI brand mention analysis: {e}")
                    else:
                        logger.warning(f"Google CSE Brand Mention Error: {resp.status}")
        except Exception as e:
            logger.error(f"Error fetching brand mentions: {e}")
            
        return mentions

    async def _analyze_mention_with_ai(self, brand_name: str, title: str, snippet: str, url: str) -> Dict[str, Any]:
        """
        DEPRECATED: Individual analysis replaced by _fetch_brand_mentions_with_analysis batching.
        """
        return {
            "sentiment": "neutral",
            "topic": "Deprecated",
            "summary": snippet[:200] if snippet else "N/A",
            "recommendation": "Use batch analysis",
            "relevance_score": 0
        }

    def get_backlinks(self, audit_id: int) -> List[Backlink]:
        return self.db.query(Backlink).filter(Backlink.audit_id == audit_id).all()
