from sqlalchemy.orm import Session
from ..models import Keyword
from ..core.config import settings
from typing import List, Dict, Optional
import logging
import json
import random
from openai import AsyncOpenAI
from .google_ads_service import GoogleAdsService

logger = logging.getLogger(__name__)

class KeywordService:
    def __init__(self, db: Session):
        self.db = db
        self.api_key = settings.OPENAI_API_KEY
        if self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key)
        else:
            self.client = None

    async def research_keywords(self, audit_id: int, domain: str, seed_keywords: List[str] = None) -> List[dict]:
        """
        Generates keyword ideas using OpenAI, Gemini, or Mock data.
        """
        # 1. Try OpenAI
        if self.client:
            return await self._research_openai(audit_id, domain, seed_keywords)
        
        # 2. Try Gemini
        if settings.GEMINI_API_KEY:
            return await self._research_gemini(audit_id, domain, seed_keywords)

        # 3. Fallback to Mock
        logger.warning("No AI keys set. Using MOCK data for keywords.")
        return self._get_mock_keywords(audit_id, domain, seed_keywords)

    async def _research_openai(self, audit_id: int, domain: str, seeds: List[str]) -> List[dict]:
        try:
            prompt = self._get_prompt(domain, seeds)
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content.strip()
            return self._process_ai_response(audit_id, content)
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            if settings.GEMINI_API_KEY:
                return await self._research_gemini(audit_id, domain, seeds)
            return self._get_mock_keywords(audit_id, domain, seeds)

    async def _research_gemini(self, audit_id: int, domain: str, seeds: List[str]) -> List[dict]:
        import aiohttp
        try:
            prompt = self._get_prompt(domain, seeds) + "\n\nReturn raw JSON only."
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
            headers = {"Content-Type": "application/json"}
            data = {"contents": [{"parts": [{"text": prompt}]}]}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        content = result["candidates"][0]["content"]["parts"][0]["text"]
                        # Clean markdown code blocks if present
                        if "```" in content:
                            content = content.replace("```json", "").replace("```", "")
                        return self._process_ai_response(audit_id, content)
                    else:
                        logger.error(f"Gemini API error: {resp.status}")
                        return self._get_mock_keywords(audit_id, domain, seeds)
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            return self._get_mock_keywords(audit_id, domain, seeds)

    def _get_prompt(self, domain: str, seeds: List[str]) -> str:
        return f"""
        Act as an SEO expert. Generate 10 high-potential keywords for the domain: {domain}.
        Context/Niche seeds: {', '.join(seeds) if seeds else 'General analysis'}
        
        For each keyword, estimate:
        1. Search Volume (monthly)
        2. Difficulty (0-100)
        3. CPC (in USD)
        4. Search Intent (Informational, Commercial, Transactional, Navigational)

        Return ONLY a valid JSON array of objects with keys: "term", "volume", "difficulty", "cpc", "intent".
        """

    def _process_ai_response(self, audit_id: int, content: str) -> List[dict]:
        try:
            data = json.loads(content)
            keywords_list = data.get("keywords", data) if isinstance(data, dict) else data
            
            # Enrich with Real Data from Google Ads if available
            try:
                terms = [kw.get("term") for kw in keywords_list if isinstance(kw, dict) and kw.get("term")]
                if terms:
                    real_metrics = GoogleAdsService().get_keyword_metrics(terms)
                    if real_metrics:
                        logger.info(f"Enriching {len(real_metrics)} keywords with Google Ads data")
                        for kw in keywords_list:
                            term = kw.get("term")
                            if term in real_metrics:
                                metrics = real_metrics[term]
                                kw["volume"] = metrics["volume"]
                                kw["difficulty"] = metrics["difficulty"]
                                kw["cpc"] = metrics["cpc"]
            except Exception as e:
                logger.error(f"Failed to enrich with Google Ads data: {e}")

            results = []
            if isinstance(keywords_list, list):
                for kw in keywords_list:
                    keyword = Keyword(
                        audit_id=audit_id,
                        term=kw.get("term"),
                        volume=kw.get("volume", 0),
                        difficulty=kw.get("difficulty", 50),
                        cpc=kw.get("cpc", 0.0),
                        intent=kw.get("intent", "Informational")
                    )
                    self.db.add(keyword)
                    results.append(keyword)
                
                self.db.commit()
                for kw in results:
                    self.db.refresh(kw)
                return [k.__dict__ for k in results]
            return []
        except Exception as e:
            logger.error(f"Error processing AI response: {e}")
            return []


    def _get_mock_keywords(self, audit_id: int, domain: str, seeds: List[str] = None) -> List[dict]:
        """Returns realistic mock data for testing without API key."""
        base_seeds = seeds if seeds else ["software", "solutions", "platform", "tools"]
        intents = ["Informational", "Commercial", "Transactional"]
        
        mock_results = []
        for i in range(10):
            seed = random.choice(base_seeds)
            term = f"{seed} for {domain.split('.')[0]}" if i % 2 == 0 else f"best {seed} 2025"
            
            kw = Keyword(
                audit_id=audit_id,
                term=term,
                volume=random.randint(100, 10000),
                difficulty=random.randint(20, 90),
                cpc=round(random.uniform(0.5, 15.0), 2),
                intent=random.choice(intents)
            )
            self.db.add(kw)
            mock_results.append(kw)
        
        self.db.commit()
        for kw in mock_results:
            self.db.refresh(kw)
            
        return [k.__dict__ for k in mock_results]

    def get_keywords(self, audit_id: int) -> List[dict]:
        keywords = self.db.query(Keyword).filter(Keyword.audit_id == audit_id).all()
        return [k.__dict__ for k in keywords]
