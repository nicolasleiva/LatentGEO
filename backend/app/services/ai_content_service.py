from sqlalchemy.orm import Session
from ..models import AIContentSuggestion
from ..core.config import settings
from .crawler_service import CrawlerService
from typing import List, Dict, Any
import logging
import json
import random
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class AIContentService:
    def __init__(self, db: Session):
        self.db = db
        self.api_key = settings.OPENAI_API_KEY
        if self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key)
        else:
            self.client = None

    async def generate_suggestions(self, audit_id: int, domain: str, topics: List[str]) -> List[dict]:
        """
        Generates content suggestions based on crawled content and OpenAI/Gemini analysis.
        """
        # 1. Crawl the site to get context (Real implementation)
        try:
            url = f"https://{domain}" if not domain.startswith("http") else domain
            page_content = await CrawlerService.get_page_content(url)
            if not page_content:
                logger.warning(f"Could not crawl {url}, proceeding with limited context.")
                page_content = "Content unavailable."
            else:
                page_content = page_content[:5000]
        except Exception as e:
            logger.error(f"Crawling error: {e}")
            page_content = "Content unavailable."

        # 2. Generate Suggestions
        if self.client:
            return await self._generate_openai(audit_id, domain, topics, page_content)
        
        if settings.GEMINI_API_KEY:
            return await self._generate_gemini(audit_id, domain, topics, page_content)

        logger.warning("No AI keys set. Using MOCK data for content suggestions.")
        return self._get_mock_suggestions(audit_id, domain, topics)

    async def _generate_openai(self, audit_id: int, domain: str, topics: List[str], context: str) -> List[dict]:
        try:
            prompt = self._get_prompt(domain, topics, context)
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content.strip()
            return self._process_ai_response(audit_id, content, topics)
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            if settings.GEMINI_API_KEY:
                return await self._generate_gemini(audit_id, domain, topics, context)
            return self._get_mock_suggestions(audit_id, domain, topics)

    async def _generate_gemini(self, audit_id: int, domain: str, topics: List[str], context: str) -> List[dict]:
        import aiohttp
        try:
            prompt = self._get_prompt(domain, topics, context) + "\n\nReturn raw JSON only."
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
            headers = {"Content-Type": "application/json"}
            data = {"contents": [{"parts": [{"text": prompt}]}]}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        content = result["candidates"][0]["content"]["parts"][0]["text"]
                        if "```" in content:
                            content = content.replace("```json", "").replace("```", "")
                        return self._process_ai_response(audit_id, content, topics)
                    else:
                        logger.error(f"Gemini API error: {resp.status}")
                        return self._get_mock_suggestions(audit_id, domain, topics)
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            return self._get_mock_suggestions(audit_id, domain, topics)

    def _get_prompt(self, domain: str, topics: List[str], context: str) -> str:
        return f"""
        Analyze the following website content summary for domain: {domain}.
        Content snippet: {context}
        
        Target Topics: {', '.join(topics)}
        
        Generate 3 content suggestions to improve topical authority:
        1. A "Missing Sub-topic" (new_content) that is relevant but not covered.
        2. A "FAQ" (faq) that users likely ask.
        3. A "Content Outline" (outline) for a pillar page on one of the target topics.
        
        Return ONLY a valid JSON array of objects with keys: "topic", "suggestion_type" (new_content, faq, outline), "content_outline" (JSON object), "priority" (high, medium, low).
        """

    def _process_ai_response(self, audit_id: int, content: str, topics: List[str]) -> List[dict]:
        try:
            data = json.loads(content)
            suggestions_list = data.get("suggestions", data) if isinstance(data, dict) else data

            results = []
            if isinstance(suggestions_list, list):
                for item in suggestions_list:
                    suggestion = AIContentSuggestion(
                        audit_id=audit_id,
                        topic=item.get("topic", "General"),
                        suggestion_type=item.get("suggestion_type", "new_content"),
                        content_outline=item.get("content_outline", {}),
                        priority=item.get("priority", "medium")
                    )
                    self.db.add(suggestion)
                    results.append(suggestion)
                
                self.db.commit()
                for s in results:
                    self.db.refresh(s)
                return [s.__dict__ for s in results]
            return self._get_mock_suggestions(audit_id, domain, topics)
        except Exception as e:
            logger.error(f"Error processing AI response: {e}")
            return self._get_mock_suggestions(audit_id, domain, topics)


    def _get_mock_suggestions(self, audit_id: int, domain: str, topics: List[str]) -> List[dict]:
        """Returns realistic mock suggestions."""
        mock_results = []
        topic = topics[0] if topics else "Industry Trends"
        
        # 1. New Content
        s1 = AIContentSuggestion(
            audit_id=audit_id,
            topic=topic,
            suggestion_type="new_content",
            content_outline={"sections": ["Introduction to " + topic, "Benefits", "Case Studies", "Conclusion"]},
            priority="high"
        )
        self.db.add(s1)
        mock_results.append(s1)
        
        # 2. FAQ
        s2 = AIContentSuggestion(
            audit_id=audit_id,
            topic=topic,
            suggestion_type="faq",
            content_outline={"question": f"Why is {topic} important?", "answer": f"{topic} is crucial for scaling your business..."},
            priority="medium"
        )
        self.db.add(s2)
        mock_results.append(s2)
        
        self.db.commit()
        for s in mock_results:
            self.db.refresh(s)
            
        return [s.__dict__ for s in mock_results]

    def get_suggestions(self, audit_id: int) -> List[dict]:
        suggestions = self.db.query(AIContentSuggestion).filter(AIContentSuggestion.audit_id == audit_id).all()
        return [s.__dict__ for s in suggestions]
