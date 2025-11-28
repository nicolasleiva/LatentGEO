from sqlalchemy.orm import Session
from ..models import AIContentSuggestion
from ..core.config import settings
from .crawler_service import CrawlerService
from typing import List, Dict, Any
import logging
import json
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class AIContentService:
    def __init__(self, db: Session):
        self.db = db
        
        # Primary: Usar Kimi vía NVIDIA
        self.nvidia_api_key = settings.NVIDIA_API_KEY or settings.NV_API_KEY
        if self.nvidia_api_key:
            self.client = AsyncOpenAI(
                api_key=self.nvidia_api_key,
                base_url=settings.NV_BASE_URL
            )
            logger.info("✅ Kimi/NVIDIA API configurada correctamente")
        else:
            self.client = None
            logger.warning("⚠️  No se encontró NVIDIA_API_KEY. Usando MOCK data.")

    async def generate_suggestions(self, audit_id: int, domain: str, topics: List[str]) -> List[dict]:
        """
        Generates content suggestions based on crawled content and Kimi analysis.
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

        # 2. Generate Suggestions usando Kimi
        if self.client:
            return await self._generate_kimi(audit_id, domain, topics, page_content)
        
        logger.warning("No AI keys set. Using MOCK data for content suggestions.")
        return self._get_mock_suggestions(audit_id, domain, topics)

    async def _generate_kimi(self, audit_id: int, domain: str, topics: List[str], context: str) -> List[dict]:
        """Genera sugerencias usando Kimi (Moonshot AI vía NVIDIA)"""
        try:
            prompt = self._get_prompt(domain, topics, context)
            
            response = await self.client.chat.completions.create(
                model=settings.NV_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=settings.NV_MAX_TOKENS
            )
            
            content = response.choices[0].message.content.strip()
            
            # Limpiar respuesta si viene con markdown
            if "```" in content:
                content = content.replace("```json", "").replace("```", "")
            
            logger.info(f"✅ Kimi generó sugerencias exitosamente para {domain}")
            return self._process_ai_response(audit_id, content, topics, domain)
            
        except Exception as e:
            logger.error(f"Kimi API error: {e}")
            return self._get_mock_suggestions(audit_id, domain, topics)

    def _get_prompt(self, domain: str, topics: List[str], context: str) -> str:
        return f"""
        Analiza el siguiente contenido del sitio web: {domain}
        
        Contenido: {context}
        
        Temas objetivo: {', '.join(topics)}
        
        Genera 3 sugerencias de contenido para mejorar la autoridad temática:
        1. Un "Sub-tema Faltante" (new_content) que sea relevante pero no esté cubierto
        2. Una "FAQ" (faq) que los usuarios probablemente busquen
        3. Un "Content Outline" (outline) para una página pilar sobre uno de los temas objetivo
        
        Retorna SOLO un array JSON válido de objetos con estas keys:
        - "topic": string
        - "suggestion_type": "new_content" | "faq" | "outline"
        - "content_outline": object con la estructura propuesta
        - "priority": "high" | "medium" | "low"
        
        Responde únicamente con el JSON, sin texto adicional.
        """

    def _process_ai_response(self, audit_id: int, content: str, topics: List[str], domain: str) -> List[dict]:
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
            logger.error(f"Error processing Kimi response: {e}")
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
