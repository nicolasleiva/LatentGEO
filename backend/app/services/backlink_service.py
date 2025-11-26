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
        logger.info(f"Analyzing links for audit {audit_id}, domain {domain}")
        
        created_backlinks = []
        
        # 1. Internal Link Analysis (Real Crawl)
        graph = await self._crawl_and_build_graph(domain)
        
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

        # 2. Technical External Backlinks (link: operator)
        technical_backlinks = await self._fetch_technical_backlinks_google(audit_id, domain)
        created_backlinks.extend(technical_backlinks)

        # 3. Brand Mentions with AI Analysis
        brand_mentions = await self._fetch_brand_mentions_with_analysis(audit_id, domain)
        created_backlinks.extend(brand_mentions)
            
        self.db.commit()
        return created_backlinks

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
        Fetches brand mentions and analyzes them with AI for sentiment, topic, and context.
        Searches ONLY by brand name, not by domain (e.g., "codegpt" not "www.codegpt.co").
        """
        if not settings.GOOGLE_API_KEY or not settings.CSE_ID:
            return []
        
        # Extract brand name from domain (e.g., www.codegpt.co -> codegpt)
        clean_domain = domain.replace("www.", "").replace("https://", "").replace("http://", "")
        brand_name = clean_domain.split(".")[0]
        
        # Search for brand mentions (NO domain filtering - we want ALL mentions)
        query = f'"{brand_name}"'
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
                        
                        for item in items:
                            source_url = item.get("link")
                            title = item.get("title", "")
                            snippet = item.get("snippet", "")
                            
                            # NO FILTERING - Brand mentions should include everything
                            # (docs.codegpt.co, blog.codegpt.co, github.com, etc.)
                            
                            # Analyze with AI
                            analysis = await self._analyze_mention_with_ai(brand_name, title, snippet, source_url)
                            
                            bl = Backlink(
                                audit_id=audit_id,
                                source_url="BRAND_MENTION",
                                target_url=source_url,
                                anchor_text=json.dumps(analysis),  # Store as JSON
                                is_dofollow=analysis.get("sentiment") == "positive",
                                domain_authority=analysis.get("relevance_score", 0)
                            )
                            self.db.add(bl)
                            mentions.append(bl)
                    else:
                        logger.warning(f"Google CSE Brand Mention Error: {resp.status}")
        except Exception as e:
            logger.error(f"Error fetching brand mentions: {e}")
            
        return mentions

    async def _analyze_mention_with_ai(self, brand_name: str, title: str, snippet: str, url: str) -> Dict[str, Any]:
        """
        Uses KIMI (via NVIDIA NIM) to analyze a brand mention for sentiment, topic, and recommendation.
        """
        system_prompt = "You are an expert SEO and brand analyst. Analyze brand mentions and provide insights in JSON format."
        
        user_prompt = f"""
Analyze this mention of the brand "{brand_name}":

**Title:** {title}
**Snippet:** {snippet}
**URL:** {url}

Provide a JSON response with:
- sentiment: "positive", "negative", or "neutral"
- topic: Main topic (e.g., "Tutorial", "Review", "Discussion", "Documentation")
- snippet: A 1-sentence summary of what they're saying
- recommendation: 1-sentence action for the brand owner
- relevance_score: 0-100 (how relevant/important is this mention)
        """
        
        try:
            response = await self.llm_function(system_prompt, user_prompt)
            # Try to extract JSON from response (KIMI might wrap it in markdown)
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            return json.loads(response.strip())
        except Exception as e:
            logger.error(f"KIMI Analysis Error: {e}")
            return {
                "sentiment": "neutral",
                "topic": "Analysis Failed",
                "snippet": snippet[:200] if snippet else "N/A",
                "recommendation": f"Error: {str(e)[:100]}",
                "relevance_score": 0
            }

    def get_backlinks(self, audit_id: int) -> List[Backlink]:
        return self.db.query(Backlink).filter(Backlink.audit_id == audit_id).all()
