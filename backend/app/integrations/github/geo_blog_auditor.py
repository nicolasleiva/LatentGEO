"""
GEO Blog Auditor - Audits blogs for LLM optimization (GEO)

Extends BlogAuditorService with additional checks specific to
Generative Engine Optimization (being cited by ChatGPT, Gemini, Claude).
"""
from typing import Dict, List, Any, Optional
import re

from .blog_auditor import BlogAuditorService
from ...core.logger import get_logger
from ...services.geo_score_service import GEOScoreService

logger = get_logger(__name__)


class GEOBlogAuditor(BlogAuditorService):
    """
    Auditor especializado en optimización para LLMs
    
    Además de SEO tradicional, detecta issues de:
    - Formato Q&A (LLMs prefieren preguntas-respuestas)
    - Estructura de fragmentos (snippet-level clarity)
    - E-E-A-T signals (Experience, Expertise, Authority, Trust)
    - Contenido conversacional vs keyword-stuffed
    - Respuestas directas (pirámide invertida)
    """
    
    def __init__(self, github_client, db=None):
        super().__init__(github_client)
        self.db = db
        # GEOScoreService not needed for blog auditing
        # if db:
        #     self.geo_score_service = GEOScoreService(db)
    
    async def audit_all_blogs_geo(self, repo_full_name: str, site_type: str) -> Dict[str, Any]:
        """
        Audita blogs para SEO + GEO
        
        Returns:
            Reporte completo con GEO score por blog
        """
        # 1. Auditoría base de SEO
        base_audit = await self.audit_all_blogs(repo_full_name, site_type)
        
        if base_audit["status"] == "no_blogs_found":
            return base_audit
        
        # 2. Agregar análisis GEO a cada blog
        for blog in base_audit.get("blogs", []):
            geo_issues = await self._audit_blog_geo(blog)
            blog["geo_issues"] = geo_issues
            blog["geo_score"] = self._calculate_blog_geo_score(geo_issues)
            blog["llm_citation_potential"] = self._assess_citation_potential(blog)
        
        # 3. Calcular GEO stats globales
        base_audit["geo_summary"] = self._calculate_geo_summary(base_audit["blogs"])
        
        return base_audit
    
    async def _audit_blog_geo(self, blog_audit: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detecta issues específicos de GEO en un blog individual
        
        Args:
            blog_audit: Resultado de _audit_single_blog (SEO)
            
        Returns:
            Lista de issues GEO adicionales
        """
        geo_issues = []
        file_path = blog_audit.get("file_path", "")
        
        # Obtener contenido del blog (ya parseado en audit base)
        # Por ahora usamos lo que ya tenemos del audit
        
        # 1. Check: Formato Q&A / FAQ
        if not blog_audit.get("has_qa_format"):
            geo_issues.append({
                "type": "missing_qa_format",
                "severity": "high",
                "category": "structure",
                "message": "Blog no usa formato Q&A que LLMs prefieren",
                "recommendation": "Agregar sección FAQ con 5-10 preguntas y respuestas directas",
                "impact": "LLMs son diseñados para responder preguntas. Formato Q&A aumenta 3x citabilidad"
            })
        
        # 2. Check: E-E-A-T - Autor
        if not blog_audit.get("author"):
            geo_issues.append({
                "type": "missing_eeat_author",
                "severity": "critical",
                "category": "eeat",
                "message": "Sin firma de autor (E-E-A-T score bajo)",
                "recommendation": "Agregar metadata de autor: nombre, bio, credenciales, foto",
                "impact": "LLMs priorizan fuentes con autores identificables. Aumenta 50% confiabilidad"
            })
        
        # 3. Check: E-E-A-T - Fuentes citadas
        if not blog_audit.get("has_citations"):
            geo_issues.append({
                "type": "missing_eeat_sources",
                "severity": "high",
                "category": "eeat",
                "message": "No cita fuentes autoritativas",
                "recommendation": "Agregar 3-5 enlaces a estudios, investigaciones o sitios .edu/.gov",
                "impact": "Citar fuentes aumenta percepción de autoridad y factualidad"
            })
        
        # 4. Check: Contenido original / datos únicos
        if not blog_audit.get("has_original_data"):
            geo_issues.append({
                "type": "no_original_research",
                "severity": "medium",
                "category": "content",
                "message": "Sin datos o investigación original",
                "recommendation": "Agregar estadísticas únicas, estudio de caso propio, o encuesta original",
                "impact": "LLMs prefieren citar fuentes con datos únicos. Aumenta 4x probabilidad de citación"
            })
        
        # 5. Check: Pirámide invertida (respuesta directa al inicio)
        if not blog_audit.get("has_direct_answer_first"):
            geo_issues.append({
                "type": "poor_answer_structure",
                "severity": "medium",
                "category": "structure",
                "message": "No da respuesta directa al inicio del contenido",
                "recommendation": "Empezar con párrafo resumen de 2-3 frases con respuesta directa",
                "impact": "Estilo pirámide invertida facilita extracción de fragmentos por LLMs"
            })
        
        # 6. Check: Lenguaje conversacional
        if blog_audit.get("keyword_density", 0) > 3.0:  # > 3% keyword density
            geo_issues.append({
                "type": "non_conversational",
                "severity": "medium",
                "category": "content",
                "message": "Lenguaje muy SEO-optimizado, poco natural",
                "recommendation": "Reescribir con lenguaje conversacional. Usar sinónimos y variaciones naturales",
                "impact": "LLMs prefieren contenido natural. Keyword stuffing reduce citabilidad"
            })
        
        # 7. Check: Fragmentación modular
        if not blog_audit.get("has_lists") and not blog_audit.get("has_tables"):
            geo_issues.append({
                "type": "poor_fragmentation",
                "severity": "medium",
                "category": "structure",
                "message": "Contenido no está fragmentado en bloques reutilizables",
                "recommendation": "Usar listas numeradas, bullets, o tablas para datos estructurados",
                "impact": "Fragmentos claros son más fáciles de extraer y citar por LLMs"
            })
        
        # 8. Check: Experiencia de primera mano
        if not self._has_first_person_experience(blog_audit):
            geo_issues.append({
                "type": "missing_experience",
                "severity": "low",
                "category": "eeat",
                "message": "No demuestra experiencia de primera mano",
                "recommendation": "Agregar ejemplos personales, casos reales, o lecciones aprendidas",
                "impact": "Experiencia práctica aumenta E-E-A-T (primera 'E' es Experience)"
            })
        
        return geo_issues
    
    def _has_first_person_experience(self, blog_audit: Dict) -> bool:
        """Detecta si el blog muestra experiencia de primera mano"""
        # Simplificado: check por palabras clave
        # En implementación real, analizaría el contenido
        return blog_audit.get("word_count", 0) > 500  # Placeholder
    
    def _calculate_blog_geo_score(self, geo_issues: List[Dict]) -> float:
        """
        Calcula GEO score para un blog individual (0-100)
        
        Score alto = alta probabilidad de ser citado por LLMs
        """
        base_score = 100.0
        
        for issue in geo_issues:
            severity = issue.get("severity")
            
            if severity == "critical":
                base_score -= 25
            elif severity == "high":
                base_score -= 15
            elif severity == "medium":
                base_score -= 8
            elif severity == "low":
                base_score -= 3
        
        return max(0, min(100, base_score))
    
    def _assess_citation_potential(self, blog: Dict) -> str:
        """
        Evalúa potencial de citación por LLMs
        
        Returns:
            "very_high", "high", "medium", "low", "very_low"
        """
        geo_score = blog.get("geo_score", 0)
        seo_severity = blog.get("severity_score", 0)
        
        # Combinar GEO score + SEO score
        combined = (geo_score + (100 - seo_severity)) / 2
        
        if combined >= 85:
            return "very_high"
        elif combined >= 70:
            return "high"
        elif combined >= 55:
            return "medium"
        elif combined >= 40:
            return "low"
        else:
            return "very_low"
    
    def _calculate_geo_summary(self, blogs: List[Dict]) -> Dict[str, Any]:
        """Calcula estadísticas GEO globales de todos los blogs"""
        if not blogs:
            return {}
        
        total = len(blogs)
        
        # Contar issues por categoría
        category_counts = {
            "structure": 0,
            "eeat": 0,
            "content": 0
        }
        
        total_geo_score = 0
        citation_distribution = {
            "very_high": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "very_low": 0
        }
        
        for blog in blogs:
            total_geo_score += blog.get("geo_score", 0)
            
            potential = blog.get("llm_citation_potential", "low")
            citation_distribution[potential] = citation_distribution.get(potential, 0) + 1
            
            for issue in blog.get("geo_issues", []):
                category = issue.get("category")
                if category in category_counts:
                    category_counts[category] += 1
        
        avg_geo_score = total_geo_score / total if total > 0 else 0
        
        return {
            "average_geo_score": round(avg_geo_score, 1),
            "blogs_ready_for_llms": citation_distribution.get("very_high", 0) + citation_distribution.get("high", 0),
            "blogs_need_improvement": total - (citation_distribution.get("very_high", 0) + citation_distribution.get("high", 0)),
            "citation_potential_distribution": citation_distribution,
            "top_issue_categories": category_counts,
            "priority_actions": self._get_priority_actions(category_counts, avg_geo_score)
        }
    
    def _get_priority_actions(self, category_counts: Dict, avg_score: float) -> List[str]:
        """Genera acciones prioritarias basadas en issues más comunes"""
        actions = []
        
        # Ordenar categorías por cantidad de issues
        sorted_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        
        category_actions = {
            "eeat": "Prioridad #1: Agregar firmas de autor y citar fuentes en blogs sin E-E-A-T",
            "structure": "Prioridad #2: Implementar formato Q&A y fragmentación modular",
            "content": "Prioridad #3: Mejorar conversacionalidad y agregar datos originales"
        }
        
        for category, count in sorted_categories[:3]:  # Top 3
            if count > 0:
                actions.append(category_actions.get(category, f"Mejorar {category}"))
        
        if avg_score < 60:
            actions.insert(0, "🚨 CRÍTICO: Score GEO general bajo. Revisar manual de GEO completo")
        
        return actions
    
    def generate_geo_fixes_from_audit(self, blog_audit: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Genera fixes GEO aplicables desde una auditoría
        
        Estos fixes pueden ser aplicados automáticamente por GitHubService
        
        Args:
            blog_audit: Resultado de audit_single_blog con geo_issues
            
        Returns:
            Lista de fixes en formato compatible con create_pr
        """
        fixes = []
        
        # Primero agregar fixes SEO tradicionales
        base_fixes = self.generate_fixes_from_audit(blog_audit)
        fixes.extend(base_fixes)
        
        # Luego agregar fixes GEO específicos
        for geo_issue in blog_audit.get("geo_issues", []):
            issue_type = geo_issue.get("type")
            
            fix = {
                "type": self._map_geo_issue_to_fix_type(issue_type),
                "priority": self._severity_to_priority(geo_issue.get("severity")),
                "page_url": blog_audit.get("url_slug", ""),
                "file_path": blog_audit.get("file_path"),
                "description": geo_issue.get("message"),
                "value": geo_issue.get("recommendation"),
                "impact": geo_issue.get("impact"),
                "category": "geo"  # Marca como fix GEO
            }
            
            fixes.append(fix)
        
        return fixes
    
    def _map_geo_issue_to_fix_type(self, issue_type: str) -> str:
        """Mapea tipo de issue GEO a tipo de fix aplicable"""
        mapping = {
            "missing_qa_format": "add_faq_section",
            "missing_eeat_author": "add_author_metadata",
            "missing_eeat_sources": "add_citations",
            "no_original_research": "add_statistics",
            "poor_answer_structure": "restructure_intro",
            "non_conversational": "rewrite_conversational",
            "poor_fragmentation": "add_lists_tables",
            "missing_experience": "add_case_study"
        }
        return mapping.get(issue_type, "other")
