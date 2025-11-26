#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
query_discovery_service.py - Descubrimiento de Queries Relevantes

Descubre qué preguntas generan respuestas sobre tu nicho en LLMs.
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class QueryDiscoveryService:
    """
    Servicio para descubrir queries relevantes del nicho.
    
    Funcionalidades:
    - Generar queries candidatas usando LLM
    - Validar queries con búsquedas reales
    - Clasificar queries por intención
    - Rankear por potencial de visibilidad
    """
    
    @staticmethod
    async def discover_queries(
        brand_name: str,
        domain: str,
        industry: str,
        keywords: List[str],
        llm_function: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Descubre queries relevantes para el nicho.
        
        Args:
            brand_name: Nombre de la marca
            domain: Dominio del sitio
            industry: Industria/categoría
            keywords: Keywords principales
            llm_function: Función LLM para generar queries
        
        Returns:
            Lista de queries descubiertas con metadatos
        """
        logger.info(f"Iniciando query discovery para {brand_name}")
        
        # PASO 1: Generar queries candidatas con LLM
        candidate_queries = await QueryDiscoveryService._generate_candidate_queries(
            brand_name, industry, keywords, llm_function
        )
        
        # PASO 2: Validar queries
        validated_queries = await QueryDiscoveryService._validate_queries(
            candidate_queries, brand_name, domain, llm_function
        )
        
        # PASO 3: Clasificar por intención
        classified_queries = QueryDiscoveryService._classify_queries(
            validated_queries
        )
        
        # PASO 4: Rankear por potencial
        ranked_queries = QueryDiscoveryService._rank_by_potential(
            classified_queries
        )
        
        logger.info(f"Query discovery completado: {len(ranked_queries)} queries encontradas")
        
        return ranked_queries
    
    @staticmethod
    async def _generate_candidate_queries(
        brand_name: str,
        industry: str,
        keywords: List[str],
        llm_function: Optional[callable]
    ) -> List[str]:
        """Genera queries candidatas usando LLM."""
        if not llm_function:
            logger.warning("No LLM function provided, usando queries base")
            return QueryDiscoveryService._get_base_queries(industry, keywords)
        
        # Prompt para generar queries
        keywords_str = ", ".join(keywords[:5])
        
        prompt = f"""Genera 20 preguntas que usuarios reales harían a un asistente de IA sobre {industry}.

Keywords relevantes: {keywords_str}
Marca: {brand_name}

Las preguntas deben:
1. Ser naturales y conversacionales
2. Cubrir diferentes intenciones (informacional, comparativa, transaccional)
3. Incluir variaciones long-tail
4. Representar diferentes niveles de awareness del usuario

IMPORTANTE: Devuelve SOLO las preguntas, una por línea, sin numeración ni formato adicional.

Ejemplo:
¿Qué es el SEO y cómo funciona?
¿Cuáles son las mejores herramientas de SEO en 2024?
Cómo mejorar el ranking de mi sitio web
"""
        
        try:
            response = await llm_function(prompt)
            
            # Parsear respuesta
            queries = [
                line.strip()
                for line in response.split('\n')
                if line.strip() and len(line.strip()) > 10
                and line.strip()[0] not in ['#', '-', '*', '1', '2', '3', '4', '5']
            ]
            
            logger.info(f"LLM generó {len(queries)} queries candidatas")
            return queries[:20]
            
        except Exception as e:
            logger.error(f"Error generando queries con LLM: {e}")
            return QueryDiscoveryService._get_base_queries(industry, keywords)
    
    @staticmethod
    def _get_base_queries(industry: str, keywords: List[str]) -> List[str]:
        """Queries base si no hay LLM."""
        base_templates = [
            "¿Qué es {keyword}?",
            "¿Cómo funciona {keyword}?",
            "Mejores prácticas de {keyword}",
            "Guía completa de {keyword}",
            "¿Cuáles son las mejores herramientas de {keyword}?",
            "Comparativa de soluciones de {keyword}",
            "¿Cómo elegir un servicio de {keyword}?",
            "Ventajas y desventajas de {keyword}",
        ]
        
        queries = []
        for keyword in keywords[:3]:
            for template in base_templates:
                queries.append(template.format(keyword=keyword))
        
        return queries
    
    @staticmethod
    async def _validate_queries(
        queries: List[str],
        brand_name: str,
        domain: str,
        llm_function: Optional[callable]
    ) -> List[Dict[str, Any]]:
        """Valida queries consultando a un LLM."""
        from app.services.llm_visibility_service import LLMVisibilityService
        
        validated = []
        
        for query in queries:
            try:
                # Consultar LLM con la query
                if llm_function:
                    response = await llm_function(query)
                else:
                    response = ""
                
                # Verificar si genera contenido relevante
                is_relevant = len(response) > 50
                
                # Verificar si menciona la marca (opcional pero importante)
                mentions_brand = (
                    brand_name.lower() in response.lower() or
                    domain.replace('www.', '').replace('.com', '') in response.lower()
                )
                
                validated.append({
                    'query': query,
                    'is_relevant': is_relevant,
                    'mentions_brand': mentions_brand,
                    'response_length': len(response),
                    'sample_response': response[:200] if response else ""
                })
                
            except Exception as e:
                logger.warning(f"Error validando query '{query}': {e}")
                validated.append({
                    'query': query,
                    'is_relevant': True,  # Asumir relevante por defecto
                    'mentions_brand': False,
                    'response_length': 0
                })
        
        return [q for q in validated if q['is_relevant']]
    
    @staticmethod
    def _classify_queries(queries: List[Dict]) -> List[Dict]:
        """Clasifica queries por intención."""
        intent_keywords = {
            'informational': ['qué es', 'cómo', 'por qué', 'cuándo', 'dónde', 'guía', 'tutorial'],
            'commercial': ['mejor', 'top', 'comparar', 'versus', 'alternativas', 'reviews'],
            'transactional': ['comprar', 'precio', 'costo', 'contratar', 'registrarse', 'demo'],
            'navigational': ['login', 'sitio oficial', 'contacto', 'página']
        }
        
        for query_data in queries:
            query_lower = query_data['query'].lower()
            
            # Determinar intención principal
            intent = 'informational'  # Default
            max_matches = 0
            
            for intent_type, keywords in intent_keywords.items():
                matches = sum(1 for kw in keywords if kw in query_lower)
                if matches > max_matches:
                    max_matches = matches
                    intent = intent_type
            
            query_data['intent'] = intent
        
        return queries
    
    @staticmethod
    def _rank_by_potential(queries: List[Dict]) -> List[Dict]:
        """
        Rankea queries por potencial de visibilidad.
        
        Factores:
        - Ya menciona la marca (mejor)
        - Intención comercial (buena para conversión)
        - Longitud de respuesta (indica relevancia)
        """
        for query_data in queries:
            score = 0
            
            # Ya menciona marca = muy valioso
            if query_data.get('mentions_brand'):
                score += 50
            
            # Intención comercial = bueno para negocio
            if query_data.get('intent') == 'commercial':
                score += 30
            elif query_data.get('intent') == 'transactional':
                score += 25
            elif query_data.get('intent') == 'informational':
                score += 15
            
            # Respuesta larga = query relevante
            response_length = query_data.get('response_length', 0)
            if response_length > 500:
                score += 20
            elif response_length > 200:
                score += 10
            
            query_data['potential_score'] = score
        
        # Ordenar por score
        queries.sort(key=lambda x: x.get('potential_score', 0), reverse=True)
        
        return queries
    
    @staticmethod
    def save_discovered_queries(
        db: Session,
        audit_id: int,
        queries: List[Dict]
    ):
        """Guarda queries descubiertas en la base de datos."""
        try:
            from app.models import DiscoveredQuery
            
            for query_data in queries:
                discovered = DiscoveredQuery(
                    audit_id=audit_id,
                    query=query_data.get('query'),
                    intent=query_data.get('intent'),
                    mentions_brand=query_data.get('mentions_brand', False),
                    potential_score=query_data.get('potential_score', 0),
                    sample_response=query_data.get('sample_response'),
                    discovered_at=datetime.utcnow()
                )
                db.add(discovered)
            
            db.commit()
            logger.info(f"Guardadas {len(queries)} queries descubiertas")
        except Exception as e:
            logger.error(f"Error guardando queries: {e}")
            db.rollback()
    
    @staticmethod
    def get_top_opportunities(
        db: Session,
        audit_id: int,
        limit: int = 10
    ) -> List[Dict]:
        """
        Obtiene las mejores oportunidades de queries.
        
        Returns:
            Top queries que:
            1. No mencionan la marca aún (oportunidad)
            2. Tienen alto potencial
            3. Intención comercial
        """
        try:
            from app.models import DiscoveredQuery
            from sqlalchemy import and_
            
            opportunities = db.query(DiscoveredQuery).filter(
                and_(
                    DiscoveredQuery.audit_id == audit_id,
                    DiscoveredQuery.mentions_brand == False,  # No menciona aún
                    DiscoveredQuery.potential_score > 30  # Alto potencial
                )
            ).order_by(
                DiscoveredQuery.potential_score.desc()
            ).limit(limit).all()
            
            return [
                {
                    'query': q.query,
                    'intent': q.intent,
                    'potential_score': q.potential_score,
                    'sample_response': q.sample_response
                }
                for q in opportunities
            ]
        except Exception as e:
            logger.error(f"Error obteniendo oportunidades: {e}")
            return []
