from typing import List, Dict, Set
from collections import Counter
import re
from bs4 import BeautifulSoup

class KeywordGapService:
    
    STOP_WORDS = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might', 'can', 'this', 'that', 'these', 'those', 'it', 'its'}
    
    @staticmethod
    def extract_keywords(html: str, top_n: int = 50) -> List[Dict]:
        """Extrae keywords del HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Priorizar títulos y headings
        title = soup.find('title')
        title_text = title.get_text() if title else ''
        
        headings = ' '.join([h.get_text() for h in soup.find_all(['h1', 'h2', 'h3'])])
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        meta_text = meta_desc.get('content', '') if meta_desc else ''
        
        # Texto del body
        for script in soup(["script", "style", "nav", "footer"]):
            script.decompose()
        body_text = soup.get_text(separator=' ', strip=True)
        
        # Combinar con pesos
        weighted_text = f"{title_text} {title_text} {title_text} {headings} {headings} {meta_text} {body_text}"
        
        # Tokenizar
        words = re.findall(r'\b[a-z]{3,}\b', weighted_text.lower())
        words = [w for w in words if w not in KeywordGapService.STOP_WORDS]
        
        # Contar frecuencias
        counter = Counter(words)
        
        return [{'keyword': k, 'frequency': v} for k, v in counter.most_common(top_n)]
    
    @staticmethod
    def analyze_gap(your_keywords: List[Dict], competitor_keywords: List[Dict]) -> Dict:
        """Analiza el gap entre tus keywords y las de competidores"""
        your_set = {k['keyword'] for k in your_keywords}
        comp_set = {k['keyword'] for k in competitor_keywords}
        
        # Keywords que tienen competidores pero tú no
        missing = comp_set - your_set
        
        # Keywords que tienes pero competidores no
        unique = your_set - comp_set
        
        # Keywords en común
        common = your_set & comp_set
        
        # Oportunidades (keywords de competidores con alta frecuencia que tú no tienes)
        comp_dict = {k['keyword']: k['frequency'] for k in competitor_keywords}
        opportunities = sorted(
            [{'keyword': k, 'competitor_frequency': comp_dict[k]} for k in missing],
            key=lambda x: x['competitor_frequency'],
            reverse=True
        )[:20]
        
        return {
            'missing_keywords': list(missing),
            'unique_keywords': list(unique),
            'common_keywords': list(common),
            'opportunities': opportunities,
            'gap_score': len(missing) / max(len(comp_set), 1) * 100
        }
    
    @staticmethod
    async def analyze_with_kimi(gap_data: Dict, llm_function) -> str:
        """Usa KIMI para analizar el gap y dar recomendaciones"""
        system_prompt = "Eres un experto analista SEO especializado en Keyword Gap Analysis."
        user_prompt = f"""Analiza este keyword gap y proporciona recomendaciones estratégicas:

Keywords que faltan: {len(gap_data['missing_keywords'])}
Keywords únicas: {len(gap_data['unique_keywords'])}
Keywords en común: {len(gap_data['common_keywords'])}
Gap Score: {gap_data['gap_score']:.1f}%

Top oportunidades:
{chr(10).join([f"- {o['keyword']} (freq: {o['competitor_frequency']})" for o in gap_data['opportunities'][:10]])}

Proporciona:
1. Análisis del gap
2. Top 5 keywords prioritarias
3. Estrategia de contenido recomendada
"""
        
        try:
            response = await llm_function(system_prompt=system_prompt, user_prompt=user_prompt)
            return response
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error in analyze_with_kimi: {e}")
            return "Análisis automático no disponible"
