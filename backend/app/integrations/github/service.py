"""
GitHub Service - Main orchestration service
"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import uuid

from ...models.github import GitHubConnection, GitHubRepository, GitHubPullRequest, PRStatus
from ...models import Audit
from .client import GitHubClient
from .oauth import GitHubOAuth
from .code_modifier import CodeModifierService
from .pr_generator import PRGeneratorService
from ...core.logger import get_logger

logger = get_logger(__name__)


class GitHubService:
    """Servicio principal para gestionar integración con GitHub"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_audit_context_for_fixes(self, audit_id: int) -> Dict[str, Any]:
        """
        Get complete audit context for generating code fixes.
        Uses the same context structure as report generation.
        
        Args:
            audit_id: ID of the audit
            
        Returns:
            Complete audit context dictionary
        """
        from ...services.audit_service import AuditService
        return AuditService.get_complete_audit_context(self.db, audit_id)
    
    async def generate_fixes_with_context(self, audit_id: int, repo_owner: str, 
                                         repo_name: str) -> List[Dict[str, Any]]:
        """
        Generate code fixes using complete audit context.
        
        Args:
            audit_id: ID of the audit
            repo_owner: Repository owner
            repo_name: Repository name
            
        Returns:
            List of fix recommendations
        """
        # Get complete context (same as LLM report generation)
        context = self.get_audit_context_for_fixes(audit_id)
        
        fixes = []
        
        # Example: Use PageSpeed data for performance fixes
        if context.get("pagespeed"):
            pagespeed = context["pagespeed"]
            mobile_score = pagespeed.get("mobile", {}).get("performance_score", 100)
            if mobile_score < 50:
                fixes.append({
                    "type": "performance",
                    "priority": "high",
                    "description": "Critical mobile performance issues detected",
                    "metrics": pagespeed.get("mobile", {}).get("metrics", {}),
                    "file_pattern": "*.html",
                    "suggestion": "Optimize images, defer JavaScript, minimize CSS"
                })
        
        # Example: Use keyword data for SEO fixes
        if context.get("keywords"):
            missing_keywords = [
                k for k in context["keywords"]
                if k.get("search_volume", 0) > 1000
            ]
            if missing_keywords:
                fixes.append({
                    "type": "seo",
                    "priority": "medium",
                    "description": "High-volume keywords not optimized",
                    "keywords": [k["keyword"] for k in missing_keywords[:5]],
                    "file_pattern": "*.html",
                    "suggestion": "Add these keywords to meta tags and content"
                })
        
        # Example: Use backlink data for authority fixes
        if context.get("backlinks"):
            backlinks = context["backlinks"]
            if backlinks.get("total_backlinks", 0) < 10:
                fixes.append({
                    "type": "authority",
                    "priority": "low",
                    "description": "Low backlink count detected",
                    "current_count": backlinks.get("total_backlinks", 0),
                    "suggestion": "Create shareable content and reach out to industry sites"
                })
        
        # Example: Use LLM visibility for GEO fixes
        if context.get("llm_visibility"):
            llm_vis = context["llm_visibility"]
            mentions = len([l for l in llm_vis if l.get("mentioned")])
            if mentions < 3:
                fixes.append({
                    "type": "geo",
                    "priority": "medium",
                    "description": "Low LLM visibility detected",
                    "current_mentions": mentions,
                    "suggestion": "Improve E-E-A-T signals, add author bios, structured data"
                })
        
        logger.info(f"Generated {len(fixes)} fix recommendations for audit {audit_id}")
        return fixes
        if context.get("llm_visibility"):
            invisible_queries = [
                l for l in context["llm_visibility"]
                if not l.get("is_visible", False)
            ]
            if invisible_queries:
                fixes.append({
                    "type": "geo",
                    "priority": "high",
                    "description": "Low visibility in LLM responses",
                    "queries": [q["query"] for q in invisible_queries[:3]],
                    "suggestion": "Improve E-E-A-T signals and structured data"
                })
        
        logger.info(f"Generated {len(fixes)} fixes for audit {audit_id} using complete context")
        return fixes
    
    async def create_or_update_connection(self, token_data: Dict, user_info: Dict) -> GitHubConnection:
        """
        Crea o actualiza conexión de GitHub
        
        Args:
            token_data: Datos del token OAuth
            user_info: Información del usuario de GitHub
            
        Returns:
            GitHubConnection object
        """
        github_user_id = str(user_info["id"])
        
        # Buscar conexión existente
        connection = self.db.query(GitHubConnection).filter(
            GitHubConnection.github_user_id == github_user_id
        ).first()
        
        # Encriptar token
        encrypted_token = GitHubOAuth.encrypt_token(token_data["access_token"])
        
        if connection:
            # Actualizar existente
            connection.access_token = encrypted_token
            connection.token_type = token_data.get("token_type", "bearer")
            connection.scope = token_data.get("scope", "")
            connection.is_active = True
            connection.updated_at = datetime.utcnow()
        else:
            # Crear nueva
            connection = GitHubConnection(
                github_user_id=github_user_id,
                github_username=user_info["login"],
                access_token=encrypted_token,
                token_type=token_data.get("token_type", "bearer"),
                scope=token_data.get("scope", ""),
                account_type=user_info["type"].lower()
            )
            self.db.add(connection)
        
        self.db.commit()
        self.db.refresh(connection)
        
        logger.info(f"GitHub connection created/updated for user {user_info['login']}")
        return connection
    
    async def get_valid_client(self, connection_id: str) -> GitHubClient:
        """
        Obtiene cliente de GitHub con token válido
        
        Args:
            connection_id: ID de la conexión
            
        Returns:
            GitHubClient instance
        """
        connection = self.db.query(GitHubConnection).filter(
            GitHubConnection.id == connection_id
        ).first()
        
        if not connection:
            raise ValueError("GitHub connection not found")
        
        if not connection.is_active:
            raise ValueError("GitHub connection is inactive")
        
        # Desencriptar token
        access_token = GitHubOAuth.decrypt_token(connection.access_token)
        return GitHubClient(access_token)
    
    async def sync_repositories(self, connection_id: str) -> List[GitHubRepository]:
        """
        Sincroniza repositorios de GitHub con la BD local
        
        Args:
            connection_id: ID de la conexión
            
        Returns:
            Lista de repositorios sincronizados
        """
        client = await self.get_valid_client(connection_id)
        
        # Obtener repos de GitHub (sin filtrar por websites para obtener todos)
        github_repos = client.get_user_repos(filter_websites=False)
        
        synced_repos = []
        for gr in github_repos:
            # Buscar repo existente
            repo = self.db.query(GitHubRepository).filter(
                GitHubRepository.connection_id == connection_id,
                GitHubRepository.github_repo_id == gr["github_repo_id"]
            ).first()
            
            if not repo:
                repo = GitHubRepository(
                    connection_id=connection_id,
                    github_repo_id=gr["github_repo_id"]
                )
                self.db.add(repo)
            
            # Actualizar datos
            repo.full_name = gr["full_name"]
            repo.name = gr["name"]
            repo.owner = gr["owner"]
            repo.url = gr["url"]
            repo.homepage_url = gr.get("homepage_url", "")
            repo.default_branch = gr["default_branch"]
            repo.is_private = gr["is_private"]
            repo.updated_at = datetime.utcnow()
            
            synced_repos.append(repo)
        
        self.db.commit()
        logger.info(f"Synced {len(synced_repos)} repositories for connection {connection_id}")
        return synced_repos
    
    async def analyze_repository(self, connection_id: str, repo_id: str) -> GitHubRepository:
        """
        Analiza un repositorio para detectar tipo de sitio
        
        Args:
            connection_id: ID de la conexión
            repo_id: ID del repositorio
            
        Returns:
            GitHubRepository con datos actualizados
        """
        client = await self.get_valid_client(connection_id)
        repo = self.db.query(GitHubRepository).filter(GitHubRepository.id == repo_id).first()
        
        if not repo:
            raise ValueError("Repository not found")
        
        # Obtener objeto Repository de PyGithub
        gh_repo = client.get_repo(repo.full_name)
        
        # Detectar tipo de sitio
        site_config = client.detect_site_type(gh_repo)
        
        # Actualizar en BD
        repo.site_type = site_config["site_type"]
        repo.base_path = site_config["base_path"]
        repo.build_command = site_config["build_command"]
        repo.output_dir = site_config["output_dir"]
        repo.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(repo)
        
        logger.info(f"Analyzed repository {repo.full_name}: {repo.site_type}")
        return repo
    
    async def create_pr_with_fixes(self, connection_id: str, repo_id: str, 
                                   audit_id: int, fixes: List[Dict]) -> GitHubPullRequest:
        """
        Crea un Pull Request con fixes SEO/GEO
        
        Este es el método principal que orquesta todo el proceso:
        1. Obtiene datos del repo y la auditoría
        2. Encuentra archivos a modificar
        3. Aplica fixes
        4. Crea branch y commits
        5. Crea PR
        
        Args:
            connection_id: ID de la conexión
            repo_id: ID del repositorio
            audit_id: ID de la auditoría
            fixes: Lista de fixes a aplicar
            
        Returns:
            GitHubPullRequest creado
        """
        logger.info(f"Starting PR creation for repo {repo_id} with audit {audit_id}")
        
        # 1. Validar y obtener datos
        client = await self.get_valid_client(connection_id)
        repo = self.db.query(GitHubRepository).filter(GitHubRepository.id == repo_id).first()
        audit = self.db.query(Audit).filter(Audit.id == audit_id).first()
        
        if not repo or not audit:
            raise ValueError("Repository or Audit not found")
        
        if not repo.site_type or repo.site_type == "unknown":
            await self.analyze_repository(connection_id, repo_id)
            self.db.refresh(repo)
        
        # 2. Obtener objeto Repository de PyGithub
        gh_repo = client.get_repo(repo.full_name)
        
        # 3. Generar nombre de branch
        branch_name = PRGeneratorService.generate_branch_name(audit_id)
        
        # 4. Crear branch
        logger.info(f"Creating branch: {branch_name}")
        client.create_branch(gh_repo, branch_name, repo.default_branch)
        
        # 5. Encontrar archivos a modificar
        page_files = client.find_page_files(gh_repo, repo.site_type)
        
        if not page_files:
            logger.warning(f"No page files found in {repo.full_name}")
            raise ValueError("No page files found to modify")
        
        # 6. Aplicar fixes a cada archivo
        file_changes = {}
        modified_files = []
        
        # Extract audit context
        audit_context = {
            "keywords": [],
            "competitors": [],
            "issues": [],
            "topic": "Growth Hacking, SEO, Analytics",
            "pagespeed": {},
            "technical_audit": {},
            "content_suggestions": [],
            "fix_plan": []
        }
        
        if audit:
            try:
                # 1. Keywords (from relationship)
                if audit.keywords:
                    audit_context["keywords"] = [k.term for k in audit.keywords[:20]] # Top 20 keywords
                
                # 2. Competitors (from JSON column)
                if audit.competitors:
                    audit_context["competitors"] = audit.competitors
                
                # 3. Issues (from fix_plan or calculated)
                if audit.fix_plan:
                    # Extract issues from fix plan if available
                    if isinstance(audit.fix_plan, list):
                        audit_context["issues"] = [item.get('issue') for item in audit.fix_plan if item.get('issue')]
                        audit_context["fix_plan"] = audit.fix_plan
                    elif isinstance(audit.fix_plan, dict):
                        # Handle dict format if applicable
                        pass
                
                # Fallback issues from counts
                if not audit_context["issues"]:
                    if audit.critical_issues > 0:
                        audit_context["issues"].append(f"{audit.critical_issues} Critical Issues detected")
                    if audit.high_issues > 0:
                        audit_context["issues"].append(f"{audit.high_issues} High Priority Issues detected")

                # 4. PageSpeed Data (use processed structure from PageSpeedService)
                if audit.pagespeed_data:
                    ps = audit.pagespeed_data
                    mobile = ps.get("mobile", {})
                    desktop = ps.get("desktop", {})
                    
                    audit_context["pagespeed"] = {
                        "mobile": {
                            "score": mobile.get("performance_score", 0),
                            "metrics": {
                                "LCP": mobile.get("metrics", {}).get("lcp") or mobile.get("core_web_vitals", {}).get("lcp"),
                                "FCP": mobile.get("metrics", {}).get("fcp") or mobile.get("core_web_vitals", {}).get("fcp"),
                                "CLS": mobile.get("metrics", {}).get("cls") or mobile.get("core_web_vitals", {}).get("cls"),
                                "TBT": mobile.get("metrics", {}).get("tbt"),
                                "SI": mobile.get("metrics", {}).get("si"),
                            },
                            "accessibility_score": mobile.get("accessibility_score"),
                            "seo_score": mobile.get("seo_score"),
                            "best_practices_score": mobile.get("best_practices_score"),
                        },
                        "desktop": {
                            "score": desktop.get("performance_score", 0),
                            "metrics": {
                                "LCP": desktop.get("metrics", {}).get("lcp") or desktop.get("core_web_vitals", {}).get("lcp"),
                                "FCP": desktop.get("metrics", {}).get("fcp") or desktop.get("core_web_vitals", {}).get("fcp"),
                                "CLS": desktop.get("metrics", {}).get("cls") or desktop.get("core_web_vitals", {}).get("cls"),
                                "TBT": desktop.get("metrics", {}).get("tbt"),
                                "SI": desktop.get("metrics", {}).get("si"),
                            }
                        },
                        "opportunities": [],
                        "diagnostics": []
                    }
                    
                    # Extract top opportunities from mobile data
                    opps = mobile.get("opportunities", {})
                    if opps:
                        for key, value in opps.items():
                            if isinstance(value, dict) and value.get("numericValue") and value.get("numericValue") > 0:
                                audit_context["pagespeed"]["opportunities"].append({
                                    "id": key,
                                    "title": value.get("title", key),
                                    "description": value.get("description", ""),
                                    "savings_ms": value.get("numericValue", 0),
                                    "display_value": value.get("displayValue", "")
                                })
                        # Sort by savings
                        audit_context["pagespeed"]["opportunities"].sort(key=lambda x: x["savings_ms"], reverse=True)
                        audit_context["pagespeed"]["opportunities"] = audit_context["pagespeed"]["opportunities"][:5]
                    
                    # Extract top diagnostics
                    diags = mobile.get("diagnostics", {})
                    if diags:
                        for key, value in diags.items():
                            if isinstance(value, dict) and value.get("score") is not None and value.get("score") < 0.5:
                                audit_context["pagespeed"]["diagnostics"].append({
                                    "id": key,
                                    "title": value.get("title", key),
                                    "score": value.get("score", 0),
                                    "display_value": value.get("displayValue", "")
                                })
                        audit_context["pagespeed"]["diagnostics"] = audit_context["pagespeed"]["diagnostics"][:5]

                # 5. Technical Audit (Target Audit)
                if audit.target_audit:
                    ta = audit.target_audit
                    audit_context["technical_audit"] = {
                        "schema_status": ta.get("schema", {}).get("schema_presence", {}).get("status"),
                        "h1_status": ta.get("structure", {}).get("h1_check", {}).get("status"),
                        "meta_description": ta.get("meta", {}).get("meta_description", {}).get("exists"),
                        "canonical": ta.get("meta", {}).get("canonical", {}).get("exists"),
                        "semantic_html_score": ta.get("structure", {}).get("semantic_html", {}).get("score_percent")
                    }

                # 6. AI Content Suggestions
                if audit.ai_content_suggestions:
                    audit_context["content_suggestions"] = [
                        {"topic": s.topic, "type": s.suggestion_type, "suggestion": s.content_outline} 
                        for s in audit.ai_content_suggestions[:5]
                    ]

                logger.info(f"Extracted rich audit context: {len(audit_context['keywords'])} keywords, PageSpeed: {'Yes' if audit_context['pagespeed'] else 'No'}")
            except Exception as e:
                logger.warning(f"Failed to extract rich audit context: {e}")
        
        for file_path in page_files[:10]:  # Limitar a 10 archivos para el MVP
            try:
                # Obtener contenido actual
                original_content = client.get_file_content(gh_repo, file_path, repo.default_branch)
                
                # Aplicar fixes
                modified_content = CodeModifierService.apply_fixes(
                    original_content, 
                    file_path, 
                    fixes,
                    repo.site_type,
                    audit_context
                )
                
                # Si hubo cambios, actualizar archivo
                if modified_content != original_content:
                    commit_message = PRGeneratorService.generate_commit_message(
                        file_path, 
                        fixes[0].get("type") if fixes else "seo"
                    )
                    
                    client.update_file(
                        gh_repo,
                        file_path,
                        modified_content,
                        branch_name,
                        commit_message
                    )
                    
                    modified_files.append(file_path)
                    file_changes[file_path] = [{"type": fix.get("type"), "before": "", "after": fix.get("value")} for fix in fixes]
                    
                    logger.info(f"Modified file: {file_path}")
                    
            except Exception as e:
                logger.error(f"Error modifying {file_path}: {e}")
                continue
        
        if not modified_files:
            raise ValueError("No files were modified")
        
        # 7. Preparar datos de auditoría para el PR
        audit_data = {
            "id": audit.id,
            "total_pages": audit.total_pages or 0,
            "critical_issues": audit.critical_issues or 0,
            "high_issues": audit.high_issues or 0,
            "medium_issues": audit.medium_issues or 0
        }
        
        # 8. Generar título y cuerpo del PR
        pr_title = PRGeneratorService.generate_pr_title(audit_data, len(modified_files))
        pr_body = PRGeneratorService.generate_pr_body(audit_data, fixes, file_changes)
        
        # 9. Crear Pull Request
        logger.info(f"Creating PR: {pr_title}")
        pr_data = client.create_pull_request(
            gh_repo,
            pr_title,
            pr_body,
            branch_name,
            repo.default_branch
        )
        
        # 10. Guardar PR en BD
        pr = GitHubPullRequest(
            repository_id=repo.id,
            audit_id=audit.id,
            github_pr_id=pr_data["github_pr_id"],
            pr_number=pr_data["pr_number"],
            title=pr_title,
            body=pr_body,
            branch_name=branch_name,
            base_branch=repo.default_branch,
            files_changed=len(modified_files),
            modified_files=modified_files,
            status=PRStatus.OPEN,
            html_url=pr_data["html_url"],
            expected_improvements=PRGeneratorService.calculate_expected_score_improvement(audit_data, fixes)
        )
        
        self.db.add(pr)
        self.db.commit()
        self.db.refresh(pr)
        
        logger.info(f"PR created successfully: {pr.html_url}")
        return pr
    
    async def get_repository_prs(self, repo_id: str) -> List[GitHubPullRequest]:
        """Obtiene PRs de un repositorio"""
        return self.db.query(GitHubPullRequest).filter(
            GitHubPullRequest.repository_id == repo_id
        ).order_by(GitHubPullRequest.created_at.desc()).all()
    
    async def update_pr_status(self, pr_id: str, status: PRStatus) -> GitHubPullRequest:
        """Actualiza estado de un PR"""
        pr = self.db.query(GitHubPullRequest).filter(GitHubPullRequest.id == pr_id).first()
        
        if pr:
            pr.status = status
            pr.updated_at = datetime.utcnow()
            
            if status == PRStatus.MERGED:
                pr.merged_at = datetime.utcnow()
            elif status == PRStatus.CLOSED:
                pr.closed_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(pr)
        
        return pr
