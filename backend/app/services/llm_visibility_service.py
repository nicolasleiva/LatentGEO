from sqlalchemy.orm import Session
from ..models import LLMVisibility
from ..core.config import settings
from ..core.llm_kimi import get_llm_function
from typing import List
import logging
import re

logger = logging.getLogger(__name__)

class LLMVisibilityService:
    def __init__(self, db: Session):
        self.db = db
        self.llm_function = get_llm_function()

    async def _query_kimi(self, prompt: str, brand_name: str) -> str:
        """Query KIMI LLM for brand visibility"""
        if not settings.NVIDIA_API_KEY:
            logger.warning("NVIDIA_API_KEY not set. Using MOCK response.")
            # Mock response simulation
            import random
            if random.random() > 0.5:
                return f"Here are the top recommendations for your query. 1. {brand_name} is a leading provider... 2. Competitor A... 3. Competitor B..."
            else:
                return "The top options include: 1. Competitor A... 2. Competitor B... 3. Competitor C..."
        
        try:
            system_prompt = "You are a helpful assistant that provides recommendations based on user queries. List the top 5 options and explain why."
            response = await self.llm_function(system_prompt, prompt)
            return response
        except Exception as e:
            logger.error(f"KIMI API Error: {e}")
            return f"Error accessing KIMI. Mock: {brand_name} analysis unavailable."

    async def _query_llm(self, query: str, llm_name: str = 'kimi') -> dict:
        """Generic method to query an LLM (wrapper for specific LLMs)"""
        try:
            # We pass a dummy brand name because _query_kimi uses it for mock generation
            response_text = await self._query_kimi(query, "Brand")
            return {'response': response_text}
        except Exception as e:
            logger.error(f"Error querying LLM {llm_name}: {e}")
            return {'response': ''}

    async def _query_llm(self, query: str, llm_name: str = 'kimi') -> dict:
        """Generic method to query an LLM (wrapper for specific LLMs)"""
        # For now we only support Kimi/Nvidia, but this structure allows expansion
        # We need a brand name context, but _query_kimi expects it. 
        # However, the caller (CitationTrackerService) expects a dict with 'response'.
        
        # Since _query_kimi takes brand_name but here we only have query, 
        # we might need to adjust or just pass a placeholder if the prompt already contains the context.
        # Looking at CitationTrackerService, it constructs the prompt.
        
        # Actually, CitationTrackerService calls: result = await visibility_service._query_llm(query, llm_name)
        # And expects result.get('response', '')
        
        # Let's assume the query is the full prompt.
        
        try:
            # We pass a dummy brand name because _query_kimi uses it for mock generation
            response_text = await self._query_kimi(query, "Brand")
            return {'response': response_text}
        except Exception as e:
            logger.error(f"Error querying LLM {llm_name}: {e}")
            return {'response': ''}

    async def check_visibility(self, audit_id: int, brand_name: str, queries: List[str]) -> List[dict]:
        """
        Checks visibility of the brand in KIMI LLM.
        """
        logger.info(f"Checking LLM visibility for audit {audit_id}, brand {brand_name}")
        
        created_entries = []
        
        for query in queries:
            prompt = f"I am looking for the best options for '{query}'. Please list the top 5 recommendations and explain why."
            
            # Query KIMI
            kimi_response = await self._query_kimi(prompt, brand_name)
            kimi_visible = bool(re.search(re.escape(brand_name), kimi_response, re.IGNORECASE))
            
            entry_kimi = LLMVisibility(
                audit_id=audit_id,
                llm_name="KIMI (Moonshot AI)",
                query=query,
                is_visible=kimi_visible,
                rank=None,
                citation_text=kimi_response[:500] + "..." if len(kimi_response) > 500 else kimi_response
            )
            self.db.add(entry_kimi)
            created_entries.append(entry_kimi)
            
        self.db.commit()
        for e in created_entries:
            self.db.refresh(e)
            
        return [e.__dict__ for e in created_entries]

    def get_visibility(self, audit_id: int) -> List[dict]:
        entries = self.db.query(LLMVisibility).filter(LLMVisibility.audit_id == audit_id).all()
        return [e.__dict__ for e in entries]
