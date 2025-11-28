"""
PR Generator Service - Creates professional Pull Requests with SEO/GEO fixes
"""
from datetime import datetime
from typing import List, Dict, Any
from ...core.logger import get_logger

logger = get_logger(__name__)


class PRGeneratorService:
    """Genera Pull Requests profesionales con fixes SEO/GEO"""
    
    @staticmethod
    def generate_pr_title(audit_data: Dict, fixes_count: int) -> str:
        """
        Genera título descriptivo para el PR
        
        Args:
            audit_data: Datos de la auditoría
            fixes_count: Número de fixes aplicados
            
        Returns:
            Título del PR
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        # Contar tipos de issues
        critical = audit_data.get("critical_issues", 0)
        high = audit_data.get("high_issues", 0)
        
        if critical > 0:
            priority = "🔴 Critical"
        elif high > 0:
            priority = "🟠 High Priority"
        else:
            priority = "✨"
        
        return f"{priority} SEO/GEO Fixes - {fixes_count} improvements ({date_str})"
    
    @staticmethod
    def generate_pr_body(audit_data: Dict, fixes: List[Dict], file_changes: Dict) -> str:
        """
        Genera cuerpo del PR en Markdown con toda la información
        
        Args:
            audit_data: Datos completos de la auditoría
            fixes: Lista de fixes aplicados
            file_changes: Dict con archivos modificados y sus cambios
            
        Returns:
            Markdown body del PR
        """
        # Header
        body = "## 🚀 Automated SEO/GEO Improvements\n\n"
        body += "This PR contains automated fixes to improve your site's SEO and GEO (Generative Engine Optimization) performance.\n\n"
        
        # Audit Summary
        body += "### 📊 Audit Summary\n\n"
        body += f"- **Total Pages Analyzed**: {audit_data.get('total_pages', 0)}\n"
        body += f"- **Critical Issues Found**: {audit_data.get('critical_issues', 0)}\n"
        body += f"- **High Priority Issues**: {audit_data.get('high_issues', 0)}\n"
        body += f"- **Medium Priority Issues**: {audit_data.get('medium_issues', 0)}\n\n"
        
        # Changes Summary
        body += "### ✅ Changes Applied\n\n"
        
        # Agrupar fixes por tipo
        fixes_by_type = {}
        for fix in fixes:
            fix_type = fix.get("type", "other")
            if fix_type not in fixes_by_type:
                fixes_by_type[fix_type] = []
            fixes_by_type[fix_type].append(fix)
        
        for fix_type, items in fixes_by_type.items():
            type_name = fix_type.replace("_", " ").title()
            body += f"#### {type_name} ({len(items)} files)\n\n"
            
            for item in items[:5]:  # Mostrar max 5 ejemplos
                file_path = item.get("file_path", "")
                if fix_type == "meta_description":
                    body += f"- `{file_path}`: Added meta description\n"
                elif fix_type == "title":
                    body += f"- `{file_path}`: Optimized title tag\n"
                elif fix_type == "h1":
                    body += f"- `{file_path}`: Fixed H1 heading\n"
                elif fix_type == "alt_text":
                    body += f"- `{file_path}`: Added image alt text\n"
            
            if len(items) > 5:
                body += f"- ... and {len(items) - 5} more files\n"
            
            body += "\n"
        
        # Files Modified
        body += "### 📝 Files Modified\n\n"
        for file_path in file_changes.keys():
            body += f"- `{file_path}`\n"
        body += "\n"
        
        # Expected Impact
        body += "### 📈 Expected Impact\n\n"
        body += PRGeneratorService._generate_impact_section(audit_data, fixes)
        
        # Technical Details
        body += "\n### 🔧 Technical Details\n\n"
        body += "<details>\n"
        body += "<summary>Click to expand detailed changes</summary>\n\n"
        
        for file_path, changes in file_changes.items():
            body += f"#### `{file_path}`\n\n"
            for change in changes:
                body += f"- **{change['type']}**: "
                if change.get('before'):
                    body += f"Changed from `{change['before'][:50]}...` to `{change['after'][:50]}...`\n"
                else:
                    body += f"Added: `{change['after'][:100]}...`\n"
            body += "\n"
        
        body += "</details>\n\n"
        
        # Instructions
        body += "### ✨ Next Steps\n\n"
        body += "1. **Review the changes** to ensure they align with your brand voice\n"
        body += "2. **Test locally** if you want to verify the changes\n"
        body += "3. **Merge this PR** to apply the improvements\n"
        body += "4. **Monitor results** in your analytics after deployment\n\n"
        
        # Footer
        body += "---\n\n"
        body += "🤖 *This PR was automatically generated by [Auditor GEO/SEO](https://your-domain.com)*\n"
        body += f"📊 [View full audit report](https://your-domain.com/audits/{audit_data.get('id')})\n\n"
        body += "**Questions or issues?** Comment below or contact support.\n"
        
        return body
    
    @staticmethod
    def _generate_impact_section(audit_data: Dict, fixes: List[Dict]) -> str:
        """Genera sección de impacto esperado"""
        impact = ""
        
        # SEO Impact
        if any(fix.get('type') in ['meta_description', 'title', 'h1'] for fix in fixes):
            impact += "#### SEO Improvements\n\n"
            impact += "- **Search Visibility**: Better meta descriptions and titles improve click-through rates\n"
            impact += "- **Ranking Potential**: Proper H1 structure helps search engines understand content\n"
            impact += "- **User Experience**: Optimized titles attract more qualified traffic\n\n"
        
        # GEO Impact
        if any(fix.get('type') in ['conversational_tone', 'schema', 'eeat'] for fix in fixes):
            impact += "#### GEO (Generative Engine Optimization) Impact\n\n"
            impact += "- **AI Visibility**: Improved structure helps LLMs understand and cite your content\n"
            impact += "- **Citation Quality**: Better metadata increases chances of being referenced\n"
            impact += "- **Answer Engineering**: Optimized for AI-powered search results\n\n"
        
        # Accessibility
        if any(fix.get('type') == 'alt_text' for fix in fixes):
            impact += "#### Accessibility Improvements\n\n"
            impact += "- **Screen Readers**: Added alt text helps visually impaired users\n"
            impact += "- **Image SEO**: Search engines can now index your images properly\n\n"
        
        if not impact:
            impact = "- General SEO improvements across multiple areas\n\n"
        
        return impact
    
    @staticmethod
    def generate_commit_message(file_path: str, fix_type: str) -> str:
        """
        Genera mensaje de commit descriptivo
        
        Args:
            file_path: Path del archivo modificado
            fix_type: Tipo de fix aplicado
            
        Returns:
            Mensaje de commit
        """
        type_messages = {
            "meta_description": "Add/update meta description",
            "title": "Optimize title tag",
            "h1": "Fix H1 heading structure",
            "alt_text": "Add image alt text",
            "og_title": "Add Open Graph title",
            "og_description": "Add Open Graph description",
            "schema": "Add structured data",
            "canonical": "Add canonical URL"
        }
        
        message = type_messages.get(fix_type, "SEO improvements")
        return f"chore(seo): {message} in {file_path}"
    
    @staticmethod
    def generate_branch_name(audit_id: int) -> str:
        """
        Genera nombre de branch descriptivo
        
        Args:
            audit_id: ID de la auditoría
            
        Returns:
            Nombre de branch
        """
        date_str = datetime.now().strftime("%Y%m%d")
        return f"seo-geo-fixes-{audit_id}-{date_str}"
    
    @staticmethod
    def calculate_expected_score_improvement(audit_data: Dict, fixes: List[Dict]) -> Dict[str, float]:
        """
        Calcula mejora esperada en scores
        
        Args:
            audit_data: Datos de auditoría
            fixes: Lista de fixes
            
        Returns:
            Dict con scores esperados antes/después
        """
        # Calcular score actual
        current_score = 100.0
        
        # Penalizaciones actuales
        current_score -= audit_data.get("critical_issues", 0) * 10
        current_score -= audit_data.get("high_issues", 0) * 5
        current_score -= audit_data.get("medium_issues", 0) * 2
        
        current_score = max(0, current_score)
        
        # Calcular mejora potencial
        improvements = 0
        for fix in fixes:
            if fix.get("priority") == "CRITICAL":
                improvements += 10
            elif fix.get("priority") == "HIGH":
                improvements += 5
            elif fix.get("priority") == "MEDIUM":
                improvements += 2
        
        expected_score = min(100, current_score + improvements)
        
        return {
            "current": round(current_score, 1),
            "expected": round(expected_score, 1),
            "improvement": round(expected_score - current_score, 1)
        }
