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
        
        for file_path in page_files[:10]:  # Limitar a 10 archivos para el MVP
            try:
                # Obtener contenido actual
                original_content = client.get_file_content(gh_repo, file_path, repo.default_branch)
                
                # Aplicar fixes
                modified_content = CodeModifierService.apply_fixes(
                    original_content, 
                    file_path, 
                    fixes,
                    repo.site_type
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
