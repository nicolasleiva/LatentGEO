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
        
        # Primary: Usar Kimi vía NVIDIA
        self.nvidia_api_key = settings.NVIDIA_API_KEY or settings.NV_API_KEY
        if self.nvidia_api_key:
            self.client = AsyncOpenAI(
                api_key=self.nvidia_api_key,
                base_url=settings.NV_BASE_URL
            )
            logger.info("✅ Kimi/NVIDIA API configurada para keywords")
        else:
            self.client = None
            logger.warning("⚠️  No se encontró NVIDIA_API_KEY. Usando MOCK data.")

    async def research_keywords(self, audit_id: int, domain: str, seed_keywords: List[str] = None) -> List[Keyword]:
        """
        Generates keyword ideas using Kimi (Moonshot AI).
        """
        # Usar Kimi vía NVIDIA
        if self.client:
            return await self._research_kimi(audit_id, domain, seed_keywords)
        
        # Fallback to Mock
        logger.warning("No AI keys set. Using MOCK data for keywords.")
        return self._get_mock_keywords(audit_id, domain, seed_keywords)

    async def _research_kimi(self, audit_id: int, domain: str, seeds: List[str]) -> List[Keyword]:
        """Genera keywords usando Kimi (Moonshot AI vía NVIDIA)"""
        try:
            prompt = self._get_prompt(domain, seeds)
            
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
            
            logger.info(f"✅ Kimi generó {len(content)} keywords para {domain}")
            return self._process_ai_response(audit_id, content)
            
        except Exception as e:
            logger.error(f"Kimi API error: {e}")
            return self._get_mock_keywords(audit_id, domain, seeds)

    def _get_prompt(self, domain: str, seeds: List[str]) -> str:
        return f"""
        Actúa como un experto en SEO. Genera 10 keywords de alto potencial para el dominio: {domain}.
        
        Contexto/Nicho semillas: {', '.join(seeds) if seeds else 'Análisis general'}
        
        Para cada keyword, estima:
        1. Volumen de búsqueda (mensual)
        2. Dificultad (0-100)
        3. CPC (en USD)
        4. Intención de búsqueda (Informational, Commercial, Transactional, Navigational)

        Retorna SOLO un array JSON válido de objetos con keys: "term", "volume", "difficulty", "cpc", "intent".
        
        Responde únicamente con el JSON, sin texto adicional.
        """

    def _process_ai_response(self, audit_id: int, content: str) -> List[Keyword]:
        try:
            data = json.loads(content)
            keywords_list = data.get("keywords", data) if isinstance(data, dict) else data
            
            # Enriquecer con datos reales de Google Ads si está disponible
            try:
                terms = [kw.get("term") for kw in keywords_list if isinstance(kw, dict) and kw.get("term")]
                if terms:
                    real_metrics = GoogleAdsService().get_keyword_metrics(terms)
                    if real_metrics:
                        logger.info(f"Enriqueciendo {len(real_metrics)} keywords con datos de Google Ads")
                        for kw in keywords_list:
                            term = kw.get("term")
                            if term in real_metrics:
                                metrics = real_metrics[term]
                                kw["volume"] = metrics["volume"]
                                kw["difficulty"] = metrics["difficulty"]
                                kw["cpc"] = metrics["cpc"]
            except Exception as e:
                logger.error(f"Fallo al enriquecer con Google Ads data: {e}")

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
                return results  # Return SQLAlchemy objects, Pydantic will serialize
            return []
        except Exception as e:
            logger.error(f"Error processing Kimi response: {e}")
            return []


    def _get_mock_keywords(self, audit_id: int, domain: str, seeds: List[str] = None) -> List[Keyword]:
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
            
        return mock_results  # Return SQLAlchemy objects

    def get_keywords(self, audit_id: int) -> List[Keyword]:
        keywords = self.db.query(Keyword).filter(Keyword.audit_id == audit_id).all()
        return keywords  # Return SQLAlchemy objects
