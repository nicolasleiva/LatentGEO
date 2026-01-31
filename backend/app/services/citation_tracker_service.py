#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
citation_tracker_service.py - Monitoreo de Citaciones en LLMs

Rastrea diariamente dónde y cómo tu marca es mencionada en respuestas de LLMs.
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc

logger = logging.getLogger(__name__)


class CitationTrackerService:
    """
    Servicio para rastrear menciones/citaciones de marcas en LLMs.
    
    Funcionalidades:
    - Ejecutar queries de monitoreo en LLMs
    - Detectar y extraer citaciones
    - Análisis de sentimiento de las menciones
    - Tracking histórico
    """
    
    # Queries base para diferentes industrias
    INDUSTRY_QUERY_TEMPLATES = {
        'ecommerce': [
            "¿Dónde puedo comprar {product_category}?",
            "¿Cuáles son las mejores tiendas de {product_category}?",
            "Recomiéndame sitios para comprar {product_category}",
        ],
        'saas': [
            "¿Qué herramientas existen para {use_case}?",
            "Recomiéndame software para {use_case}",
            "Compara las mejores plataformas de {use_case}",
        ],
        'services': [
            "¿Quién ofrece servicios de {service_type}?",
            "Recomiéndame empresas de {service_type}",
            "¿Cuáles son los mejores proveedores de {service_type}?",
        ],
        'content': [
            "¿Dónde puedo aprender sobre {topic}?",
            "Recomiéndame recursos sobre {topic}",
            "¿Qué blogs hablan de {topic}?",
        ],
    }
    
    @staticmethod
    async def track_citations(
        db: Session,
        audit_id: int,
        brand_name: str,
        domain: str,
        industry: str = 'general',
        keywords: List[str] = None,
        llm_name: str = 'kimi'
    ) -> List[Dict[str, Any]]:
        """
        Ejecuta tracking de citaciones para una marca.
        
        Args:
            db: Sesión de base de datos
            audit_id: ID del audit
            brand_name: Nombre de la marca
            domain: Dominio del sitio
            industry: Industria (para queries relevantes)
            keywords: Keywords adicionales
            llm_name: LLM a usar (kimi, chatgpt, etc)
        
        Returns:
            Lista de citaciones encontradas
        """
        from app.services.llm_visibility_service import LLMVisibilityService
        
        logger.info(f"Iniciando citation tracking para {brand_name}")
        
        # Generar queries relevantes
        queries = CitationTrackerService._generate_tracking_queries(
            brand_name, industry, keywords
        )
        
        citations = []
        visibility_service = LLMVisibilityService(db)
        
        for query in queries:
            try:
                # Consultar LLM
                result = await visibility_service._query_llm(query, llm_name)
                
                if not result:
                    continue
                
                response_text = result.get('response', '')
                
                # Detectar si la marca fue mencionada
                is_mentioned = CitationTrackerService._is_brand_mentioned(
                    response_text, brand_name, domain
                )
                
                if is_mentioned:
                    # Extraer contexto de la citación
                    citation_context = CitationTrackerService._extract_citation_context(
                        response_text, brand_name, domain
                    )
                    
                    # Analizar sentimiento
                    sentiment = CitationTrackerService._analyze_sentiment(
                        citation_context
                    )
                    
                    # Detectar posición en la respuesta
                    position = CitationTrackerService._get_mention_position(
                        response_text, brand_name, domain
                    )
                    
                    citation = {
                        'query': query,
                        'llm_name': llm_name,
                        'is_mentioned': True,
                        'citation_text': citation_context,
                        'sentiment': sentiment,
                        'position': position,
                        'response_length': len(response_text),
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'full_response': response_text
                    }
                    
                    citations.append(citation)
                    logger.info(f"✓ Citación encontrada en query: '{query[:50]}...'")
                else:
                    # Registrar query sin mención
                    citations.append({
                        'query': query,
                        'llm_name': llm_name,
                        'is_mentioned': False,
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    logger.info(f"✗ No mencionado en query: '{query[:50]}...'")
                    
            except Exception as e:
                logger.error(f"Error en query '{query}': {e}")
                continue
        
        # Guardar en base de datos
        CitationTrackerService._save_citations(db, audit_id, citations)
        
        # Calcular métricas
        total_queries = len(queries)
        mentioned_count = sum(1 for c in citations if c.get('is_mentioned'))
        citation_rate = (mentioned_count / total_queries * 100) if total_queries > 0 else 0
        
        logger.info(f"Citation Tracking completado: {mentioned_count}/{total_queries} ({citation_rate:.1f}%)")
        
        return citations
    
    @staticmethod
    def _generate_tracking_queries(
        brand_name: str,
        industry: str,
        keywords: List[str] = None
    ) -> List[str]:
        """Genera queries relevantes para tracking."""
        queries = []
        
        # Queries directas de la marca
        queries.extend([
            f"¿Qué es {brand_name}?",
            f"Cuéntame sobre {brand_name}",
            f"¿{brand_name} es recomendable?",
        ])
        
        # Queries de industria
        if industry in CitationTrackerService.INDUSTRY_QUERY_TEMPLATES:
            templates = CitationTrackerService.INDUSTRY_QUERY_TEMPLATES[industry]
            
            # Si hay keywords, usarlas
            if keywords:
                for template in templates:
                    for keyword in keywords[:3]:  # Máximo 3 keywords
                        query = template.replace('{product_category}', keyword)
                        query = query.replace('{use_case}', keyword)
                        query = query.replace('{service_type}', keyword)
                        query = query.replace('{topic}', keyword)
                        queries.append(query)
        
        # Queries comparativas
        if keywords:
            queries.append(f"Compara {brand_name} con alternativas")
            queries.append(f"¿Cuáles son las ventajas de {brand_name}?")
        
        # Limitar a 15 queries por ejecución
        return queries[:15]
    
    @staticmethod
    def _is_brand_mentioned(text: str, brand_name: str, domain: str) -> bool:
        """Detecta si la marca fue mencionada."""
        text_lower = text.lower()
        brand_lower = brand_name.lower()
        domain_clean = domain.replace('www.', '').replace('.com', '').replace('.io', '')
        
        # Buscar nombre de marca o dominio
        return brand_lower in text_lower or domain_clean in text_lower
    
    @staticmethod
    def _extract_citation_context(text: str, brand_name: str, domain: str) -> str:
        """Extrae el contexto de la citación (±100 caracteres)."""
        text_lower = text.lower()
        brand_lower = brand_name.lower()
        
        # Buscar posición de la mención
        pos = text_lower.find(brand_lower)
        
        if pos == -1:
            # Buscar por dominio
            domain_clean = domain.replace('www.', '').replace('.com', '').replace('.io', '')
            pos = text_lower.find(domain_clean)
        
        if pos == -1:
            return text[:200]  # Fallback
        
        # Extraer ±100 caracteres
        start = max(0, pos - 100)
        end = min(len(text), pos + 100)
        
        context = text[start:end]
        if start > 0:
            context = "..." + context
        if end < len(text):
            context = context + "..."
        
        return context
    
    @staticmethod
    def _analyze_sentiment(text: str) -> str:
        """Análisis básico de sentimiento."""
        positive_words = ['mejor', 'excelente', 'recomiendo', 'bueno', 'útil', 'efectivo', 'líder']
        negative_words = ['malo', 'peor', 'evitar', 'problema', 'deficiente', 'limitado']
        
        text_lower = text.lower()
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'
    
    @staticmethod
    def _get_mention_position(text: str, brand_name: str, domain: str) -> int:
        """Obtiene la posición de la mención (1=primero, 2=segundo, etc)."""
        # Dividir en oraciones o párrafos
        sentences = text.split('.')
        
        brand_lower = brand_name.lower()
        
        for i, sentence in enumerate(sentences):
            if brand_lower in sentence.lower():
                return i + 1
        
        return 0
    
    @staticmethod
    def _save_citations(db: Session, audit_id: int, citations: List[Dict]):
        """Guarda citaciones en la base de datos."""
        try:
            from app.models import CitationTracking
            
            for citation in citations:
                tracking = CitationTracking(
                    audit_id=audit_id,
                    query=citation.get('query'),
                    llm_name=citation.get('llm_name'),
                    is_mentioned=citation.get('is_mentioned', False),
                    citation_text=citation.get('citation_text'),
                    sentiment=citation.get('sentiment'),
                    position=citation.get('position'),
                    full_response=citation.get('full_response'),
                    tracked_at=datetime.now(timezone.utc)
                )
                db.add(tracking)
            
            db.commit()
            logger.info(f"Guardadas {len(citations)} citaciones en DB")
        except Exception as e:
            logger.error(f"Error guardando citaciones: {e}")
            db.rollback()
    
    @staticmethod
    def get_citation_history(
        db: Session,
        audit_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Obtiene historial de citaciones.
        
        Returns:
            Métricas y tendencias
        """
        try:
            from app.models import CitationTracking
            
            since_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            citations = db.query(CitationTracking).filter(
                CitationTracking.audit_id == audit_id,
                CitationTracking.tracked_at >= since_date
            ).order_by(desc(CitationTracking.tracked_at)).all()
            
            if not citations:
                return {
                    'total_queries': 0,
                    'mentions': 0,
                    'citation_rate': 0,
                    'sentiment_breakdown': {},
                    'trending': []
                }
            
            total = len(citations)
            mentioned = sum(1 for c in citations if c.is_mentioned)
            
            # Breakdown de sentimiento
            sentiments = {}
            for c in citations:
                if c.is_mentioned and c.sentiment:
                    sentiments[c.sentiment] = sentiments.get(c.sentiment, 0) + 1
            
            return {
                'total_queries': total,
                'mentions': mentioned,
                'citation_rate': (mentioned / total * 100) if total > 0 else 0,
                'sentiment_breakdown': sentiments,
                'recent_citations': [
                    {
                        'query': c.query,
                        'citation_text': c.citation_text,
                        'sentiment': c.sentiment,
                        'date': c.tracked_at.isoformat()
                    }
                    for c in citations if c.is_mentioned
                ][:10]
            }
        except Exception as e:
            logger.error(f"Error obteniendo historial: {e}")
            return {}
