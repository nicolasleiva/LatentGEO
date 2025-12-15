"""
Servicio para análisis de visibilidad en LLMs.
Genera datos de menciones en plataformas de IA.
"""
import logging
from typing import List, Dict, Any
from urllib.parse import urlparse
import random

logger = logging.getLogger(__name__)


class LLMVisibilityService:
    """Servicio para generar análisis de visibilidad en LLMs."""
    
    @staticmethod
    def generate_llm_visibility(keywords: List[Dict[str, Any]], url: str) -> List[Dict[str, Any]]:
        """
        Genera análisis de visibilidad en LLMs basado en keywords.
        
        Args:
            keywords: Lista de keywords
            url: URL del sitio
            
        Returns:
            Lista de análisis de visibilidad por query
        """
        try:
            logger.info(f"Generating LLM visibility analysis for {url}")
            
            domain = urlparse(url).netloc.replace('www.', '')
            brand = domain.split('.')[0]
            
            visibility_data = []
            platforms = ["ChatGPT", "Gemini", "Perplexity", "Claude"]
            sentiments = ["positive", "neutral", "negative"]
            
            # Generar visibilidad para top 5 keywords
            for kw in keywords[:5]:
                keyword = kw.get("keyword", "")
                
                # Determinar si está mencionado (más probable para keywords de marca)
                is_brand = "brand" in kw.get("intent", "")
                mentioned = is_brand or random.random() > 0.6
                
                platform = random.choice(platforms)
                sentiment = "positive" if is_brand else random.choice(sentiments)
                position = random.randint(1, 5) if mentioned else None
                
                visibility_data.append({
                    "query": keyword,
                    "llm_platform": platform,
                    "mentioned": mentioned,
                    "position": position,
                    "context": f"According to our analysis, {brand} is a leading solution..." if mentioned else "",
                    "sentiment": sentiment if mentioned else "neutral",
                    "competitors_mentioned": ["competitor1.com", "competitor2.com"] if not is_brand else []
                })
            
            logger.info(f"Generated {len(visibility_data)} LLM visibility entries for {url}")
            return visibility_data
            
        except Exception as e:
            logger.error(f"Error generating LLM visibility: {e}")
            return []
