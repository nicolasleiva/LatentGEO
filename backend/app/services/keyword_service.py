import json
import logging
import re
from typing import Any, Dict, List

from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.external_resilience import run_external_call
from ..core.llm_kimi import (
    KimiGenerationError,
    KimiUnavailableError,
    resolve_kimi_api_key,
)
from ..models import Keyword
from .google_ads_service import GoogleAdsService

logger = logging.getLogger(__name__)


class KeywordService:
    def __init__(self, db: Session):
        self.db = db

        # Primary: Usar Kimi vía NVIDIA
        self.nvidia_api_key = resolve_kimi_api_key()
        if self.nvidia_api_key:
            self.client = AsyncOpenAI(
                api_key=self.nvidia_api_key,
                base_url=settings.NV_BASE_URL,
                timeout=float(settings.NVIDIA_TIMEOUT_SECONDS),
            )
            logger.info("Kimi/NVIDIA API configurada para keywords")
        else:
            self.client = None
            logger.error(
                "No se encontró NVIDIA_API_KEY. El servicio de keywords fallará."
            )

    async def research_keywords(
        self, audit_id: int, domain: str, seed_keywords: List[str] = None
    ) -> List[Keyword]:
        """
        Generates keyword ideas using Kimi (Moonshot AI).
        """
        # Usar Kimi vía NVIDIA
        if self.client:
            return await self._research_kimi(audit_id, domain, seed_keywords)

        logger.error("No AI keys set. Cannot generate keywords without NVIDIA API.")
        raise KimiUnavailableError(
            "Kimi provider is not configured. Set NV_API_KEY_ANALYSIS or NVIDIA_API_KEY or NV_API_KEY."
        )

    async def _research_kimi(
        self, audit_id: int, domain: str, seeds: List[str]
    ) -> List[Keyword]:
        """Genera keywords usando Kimi (Moonshot AI vía NVIDIA)"""
        try:
            prompt = self._get_prompt(domain, seeds)

            response = await run_external_call(
                "nvidia-keyword-service",
                lambda: self.client.chat.completions.create(
                    model=settings.NV_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    top_p=1.0,
                    max_tokens=settings.NV_MAX_TOKENS,
                ),
                timeout_seconds=float(settings.NVIDIA_TIMEOUT_SECONDS),
            )

            content = response.choices[0].message.content.strip()

            # Limpiar respuesta si viene con markdown
            if "```" in content:
                content = content.replace("```json", "").replace("```", "")

            logger.info(f"Kimi generó {len(content)} keywords para {domain}")
            return self._process_ai_response(audit_id, content)

        except Exception as e:
            logger.error(f"Kimi API error: {e}")
            raise KimiGenerationError(f"Keyword generation failed: {e}") from e

    def _get_prompt(self, domain: str, seeds: List[str]) -> str:
        seed_text = ", ".join(
            [s for s in (seeds or []) if isinstance(s, str) and s.strip()]
        )
        return f"""
        You are a senior SEO strategist.
        Generate exactly 10 keyword ideas for the target business domain: {domain}.

        Business context seeds: {seed_text if seed_text else "General business context"}

        Requirements:
        - Keep keywords tightly aligned with the business model, audience, and services inferred from the seeds.
        - Do NOT include unrelated verticals or random industries.
        - Mix intents (Informational, Commercial, Transactional, Navigational) while preserving business relevance.
        - Prefer query forms that buyers and high-intent learners/customers use.
        - If reliable metrics are not available, do NOT invent them. Use null.

        For each keyword include:
        1. "term" (string)
        2. "volume" (monthly search volume, integer or null)
        3. "difficulty" (0-100 integer or null)
        4. "cpc" (USD float or null)
        5. "intent" (Informational | Commercial | Transactional | Navigational)

        Return only valid JSON as an array of objects with keys:
        "term", "volume", "difficulty", "cpc", "intent".
        """

    def _process_ai_response(self, audit_id: int, content: str) -> List[Keyword]:
        try:
            data = json.loads(content)
            keywords_list = (
                data.get("keywords", data) if isinstance(data, dict) else data
            )
            if not isinstance(keywords_list, list):
                raise KimiGenerationError(
                    "Kimi returned invalid JSON payload for keyword research."
                )

            # Enriquecer con datos reales de Google Ads si está disponible
            real_metrics_lookup: Dict[str, Dict[str, Any]] = {}
            try:
                terms = [
                    kw.get("term")
                    for kw in keywords_list
                    if isinstance(kw, dict) and kw.get("term")
                ]
                if terms:
                    real_metrics = GoogleAdsService().get_keyword_metrics(terms)
                    if real_metrics:
                        logger.info(
                            f"Enriqueciendo {len(real_metrics)} keywords con datos de Google Ads"
                        )
                        for key, value in real_metrics.items():
                            normalized_key = re.sub(
                                r"\s+", " ", str(key or "").strip().lower()
                            )
                            if not normalized_key:
                                continue
                            real_metrics_lookup[normalized_key] = value or {}
            except Exception as e:
                logger.error(f"Fallo al enriquecer con Google Ads data: {e}")

            results = []
            if isinstance(keywords_list, list):
                existing_keywords = (
                    self.db.query(Keyword).filter(Keyword.audit_id == audit_id).all()
                )
                existing_by_term = {
                    re.sub(r"\s+", " ", (kw.term or "").strip().lower()): kw
                    for kw in existing_keywords
                    if getattr(kw, "term", None)
                }
                seen_terms = set()

                for kw in keywords_list:
                    if not isinstance(kw, dict):
                        continue
                    term = kw.get("term")
                    normalized_term = re.sub(
                        r"\s+", " ", str(term or "").strip().lower()
                    )
                    if not normalized_term or normalized_term in seen_terms:
                        continue
                    seen_terms.add(normalized_term)

                    metrics = real_metrics_lookup.get(normalized_term, {})
                    has_real_metrics = bool(metrics)

                    if has_real_metrics:
                        volume_value = metrics.get("volume", 0)
                        difficulty_value = metrics.get("difficulty", 0)
                        cpc_value = metrics.get("cpc", 0.0)
                        metrics_source = "google_ads"
                    else:
                        # Política estricta: sin inventar métricas cuando no hay fuente real
                        volume_value = 0
                        difficulty_value = 0
                        cpc_value = 0.0
                        metrics_source = "not_available"

                    try:
                        volume_value = int(volume_value or 0)
                    except Exception:
                        volume_value = 0
                    try:
                        difficulty_value = int(difficulty_value or 0)
                    except Exception:
                        difficulty_value = 0
                    try:
                        cpc_value = float(cpc_value or 0.0)
                    except Exception:
                        cpc_value = 0.0

                    existing = existing_by_term.get(normalized_term)
                    if existing:
                        existing.volume = volume_value
                        existing.difficulty = difficulty_value
                        existing.cpc = cpc_value
                        existing.intent = kw.get(
                            "intent", existing.intent or "Informational"
                        )
                        keyword = existing
                    else:
                        keyword = Keyword(
                            audit_id=audit_id,
                            term=str(term).strip(),
                            volume=volume_value,
                            difficulty=difficulty_value,
                            cpc=cpc_value,
                            intent=kw.get("intent", "Informational"),
                        )
                        self.db.add(keyword)
                        existing_by_term[normalized_term] = keyword

                    setattr(keyword, "metrics_source", metrics_source)
                    results.append(keyword)

                self.db.commit()
                for kw in results:
                    self.db.refresh(kw)
                return results  # Return SQLAlchemy objects, Pydantic will serialize
            raise KimiGenerationError(
                "Kimi returned invalid JSON payload for keyword research."
            )
        except Exception as e:
            logger.error(f"Error processing Kimi response: {e}")
            self.db.rollback()
            if isinstance(e, KimiGenerationError):
                raise
            raise KimiGenerationError(
                "Kimi returned invalid JSON payload for keyword research."
            ) from e

    def get_keywords(self, audit_id: int) -> List[Keyword]:
        keywords = self.db.query(Keyword).filter(Keyword.audit_id == audit_id).all()
        return keywords  # Return SQLAlchemy objects
