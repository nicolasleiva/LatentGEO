"""
Servicio para análisis de backlinks.
Genera backlinks de ejemplo basados en el perfil del sitio.
"""
import logging
from typing import Dict, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class BacklinksService:
    """Servicio para generar análisis de backlinks."""
    
    @staticmethod
    def generate_backlinks_from_audit(target_audit: Dict[str, Any], url: str) -> Dict[str, Any]:
        """
        Genera análisis de backlinks basado en el sitio.
        
        Args:
            target_audit: Datos de la auditoría técnica
            url: URL del sitio
            
        Returns:
            Diccionario con análisis de backlinks
        """
        try:
            logger.info(f"Generating backlinks analysis for {url}")
            
            domain = urlparse(url).netloc.replace('www.', '')
            
            # Generar backlinks de ejemplo
            backlinks = []
            
            # Backlinks de alta autoridad
            high_authority_sources = [
                {"domain": "techcrunch.com", "da": 92, "type": "article"},
                {"domain": "forbes.com", "da": 95, "type": "mention"},
                {"domain": "medium.com", "da": 88, "type": "blog"},
                {"domain": "github.com", "da": 94, "type": "profile"},
                {"domain": "linkedin.com", "da": 98, "type": "company"},
            ]
            
            for source in high_authority_sources:
                backlinks.append({
                    "source_url": f"https://{source['domain']}/article-about-{domain.split('.')[0]}",
                    "target_url": url,
                    "anchor_text": domain.split('.')[0].title(),
                    "domain_authority": source["da"],
                    "page_authority": source["da"] - 10,
                    "spam_score": 1,
                    "is_dofollow": True
                })
            
            # Backlinks de autoridad media
            medium_authority_sources = [
                {"domain": "reddit.com", "da": 85, "anchor": "discussion"},
                {"domain": "quora.com", "da": 82, "anchor": "answer"},
                {"domain": "dev.to", "da": 78, "anchor": "tutorial"},
                {"domain": "hackernews.com", "da": 80, "anchor": "submission"},
                {"domain": "producthunt.com", "da": 83, "anchor": "launch"},
            ]
            
            for source in medium_authority_sources:
                backlinks.append({
                    "source_url": f"https://{source['domain']}/topic/{domain.split('.')[0]}",
                    "target_url": url,
                    "anchor_text": f"Check out {domain.split('.')[0]}",
                    "domain_authority": source["da"],
                    "page_authority": source["da"] - 15,
                    "spam_score": 2,
                    "is_dofollow": True
                })
            
            # Backlinks de blogs y directorios
            blog_sources = [
                {"domain": f"blog-{i}.com", "da": 45 + i*5, "spam": 5 + i} 
                for i in range(10)
            ]
            
            for source in blog_sources:
                backlinks.append({
                    "source_url": f"https://{source['domain']}/review-{domain.split('.')[0]}",
                    "target_url": url,
                    "anchor_text": f"{domain.split('.')[0]} review",
                    "domain_authority": source["da"],
                    "page_authority": source["da"] - 20,
                    "spam_score": source["spam"],
                    "is_dofollow": source["spam"] < 8
                })
            
            # Calcular métricas agregadas
            total_backlinks = len(backlinks)
            referring_domains = len(set(b["source_url"].split('/')[2] for b in backlinks))
            avg_da = sum(b["domain_authority"] for b in backlinks) / total_backlinks if total_backlinks > 0 else 0
            dofollow_count = len([b for b in backlinks if b["is_dofollow"]])
            nofollow_count = total_backlinks - dofollow_count
            
            result = {
                "total_backlinks": total_backlinks,
                "referring_domains": referring_domains,
                "top_backlinks": backlinks[:20],  # Top 20
                "summary": {
                    "average_domain_authority": round(avg_da, 1),
                    "dofollow_count": dofollow_count,
                    "nofollow_count": nofollow_count,
                    "high_authority_count": len([b for b in backlinks if b["domain_authority"] >= 80]),
                    "spam_score_avg": round(sum(b["spam_score"] for b in backlinks) / total_backlinks, 1)
                }
            }
            
            logger.info(f"Generated {total_backlinks} backlinks for {url}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating backlinks: {e}")
            return {
                "total_backlinks": 0,
                "referring_domains": 0,
                "top_backlinks": []
            }
