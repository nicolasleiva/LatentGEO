from sqlalchemy.orm import Session
from ..models import RankTracking, Audit
from ..core.config import settings
from typing import List, Dict, Any
import logging
import aiohttp
import asyncio

logger = logging.getLogger(__name__)

class RankTrackerService:
    def __init__(self, db: Session):
        self.db = db
        self.google_key = settings.GOOGLE_API_KEY
        self.cse_id = settings.CSE_ID

    async def _get_position_and_top_results(self, query: str, domain: str) -> tuple:
        """
        Returns position of domain and top 10 results.
        Returns: (position, top_results_list)
        """
        if not settings.GOOGLE_API_KEY or not settings.CSE_ID:
            return 0, []
        
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": settings.GOOGLE_API_KEY,
            "cx": settings.CSE_ID,
            "q": query,
            "num": 10
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data.get("items", [])
                        
                        # Normalize domain for comparison
                        clean_domain = domain.replace("www.", "").replace("https://", "").replace("http://", "").split('/')[0]
                        
                        position = 0
                        top_results = []
                        
                        for i, item in enumerate(items):
                            link = item.get("link", "")
                            title = item.get("title", "")
                            
                            # Extract domain from result URL
                            try:
                                result_domain = link.replace("https://", "").replace("http://", "").replace("www.", "").split('/')[0]
                            except:
                                result_domain = "Unknown"
                            
                            # Save in top results
                            top_results.append({
                                "position": i + 1,
                                "url": link,
                                "title": title,
                                "domain": result_domain
                            })
                            
                            # Check if it's our domain
                            if clean_domain in link and position == 0:
                                position = i + 1
                        
                        return position, top_results
                    else:
                        logger.error(f"Google CSE Error: {resp.status}")
                        return 0, []
        except Exception as e:
            logger.error(f"Rank Check Error: {e}")
            return 0, []

    async def track_rankings(self, audit_id: int, domain: str, keywords: List[str]) -> List[RankTracking]:
        """
        Tracks rankings using Google Custom Search API.
        """
        logger.info(f"Tracking rankings for audit {audit_id}, domain {domain}")
        
        created_rankings = []
        
        for kw in keywords:
            position, top_results = await self._get_position_and_top_results(kw, domain)
            
            ranking = RankTracking(
                audit_id=audit_id,
                keyword=kw,
                position=position,
                url=f"https://{domain}" if position > 0 else "Not Ranked",
                device="desktop",
                location="Global",
                top_results=top_results
            )
            self.db.add(ranking)
            created_rankings.append(ranking)
        
        self.db.commit()
        for r in created_rankings:
            self.db.refresh(r)
        
        return created_rankings

    def get_rankings(self, audit_id: int) -> List[RankTracking]:
        return self.db.query(RankTracking).filter(RankTracking.audit_id == audit_id).all()
