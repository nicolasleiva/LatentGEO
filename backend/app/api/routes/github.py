"""
GitHub API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import hmac
import hashlib
from datetime import datetime

from ...core.database import get_db
from ...core.config import settings
from ...core.logger import get_logger
from ...integrations.github.oauth import GitHubOAuth
from ...integrations.github.service import GitHubService
from ...models.github import GitHubConnection, GitHubRepository, GitHubPullRequest, PRStatus

router = APIRouter()
logger = get_logger(__name__)


# Request/Response Models

class ConnectResponse(BaseModel):
    url: str
    state: str

class CallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None

class RepositoryResponse(BaseModel):
    id: str
    full_name: str
    name: str
    owner: str
    url: str
    homepage_url: Optional[str]
    site_type: Optional[str]
    auto_audit: bool
    auto_pr: bool

    class Config:
        from_attributes = True

class CreatePRRequest(BaseModel):
    connection_id: str
    repo_id: str
    audit_id: int
    fixes: List[Dict[str, Any]]

class PRResponse(BaseModel):
    id: str
    pr_number: int
    title: str
    html_url: str
    status: str
    files_changed: int
    expected_improvements: Optional[Dict]

    class Config:
        from_attributes = True


# Routes

@router.get("/auth-url", response_model=ConnectResponse)
def get_auth_url():
    """Obtiene URL para iniciar OAuth con GitHub"""
    try:
        data = GitHubOAuth.get_authorization_url()
        return data
    except Exception as e:
        logger.error(f"Error generating GitHub auth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/oauth/authorize")
def oauth_authorize():
    """Redirige directamente a GitHub OAuth (para compatibilidad con frontend)"""
    from fastapi.responses import RedirectResponse
    try:
        auth_data = GitHubOAuth.get_authorization_url()
        return RedirectResponse(url=auth_data["url"])
    except Exception as e:
        logger.error(f"Error redirecting to GitHub OAuth: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/callback")
async def oauth_callback(request: CallbackRequest, db: Session = Depends(get_db)):
    """Maneja callback de OAuth"""
    try:
        # 1. Exchange code for token
        token_data = await GitHubOAuth.exchange_code(request.code)
        
        # 2. Get user info
        user_info = await GitHubOAuth.get_user_info(token_data["access_token"])
        
        # 3. Create/update connection
        service = GitHubService(db)
        connection = await service.create_or_update_connection(token_data, user_info)
        
        # 4. Sync repositories in background
        # (En producción, esto debería ser una tarea de Celery)
        try:
            await service.sync_repositories(connection.id)
        except Exception as e:
            logger.warning(f"Error syncing repos during callback: {e}")
        
        return {
            "status": "success",
            "connection_id": connection.id,
            "username": connection.github_username
        }
        
    except Exception as e:
        logger.error(f"GitHub OAuth callback error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/connections")
def get_connections(db: Session = Depends(get_db)):
    """Lista conexiones activas de GitHub"""
    connections = db.query(GitHubConnection).filter(
        GitHubConnection.is_active == True
    ).all()
    
    return [{
        "id": c.id,
        "username": c.github_username,
        "account_type": c.account_type,
        "created_at": c.created_at
    } for c in connections]


@router.post("/sync/{connection_id}")
async def sync_repositories(connection_id: str, db: Session = Depends(get_db)):
    """Sincroniza repositorios de una conexión"""
    service = GitHubService(db)
    try:
        repos = await service.sync_repositories(connection_id)
        return {"status": "success", "synced_count": len(repos)}
    except Exception as e:
        logger.error(f"Error syncing repositories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/repos/{connection_id}", response_model=List[RepositoryResponse])
def get_repositories(connection_id: str, db: Session = Depends(get_db)):
    """Obtiene repositorios de una conexión"""
    repos = db.query(GitHubRepository).filter(
        GitHubRepository.connection_id == connection_id,
        GitHubRepository.is_active == True
    ).all()
    
    return repos


@router.post("/analyze/{connection_id}/{repo_id}")
async def analyze_repository(connection_id: str, repo_id: str, db: Session = Depends(get_db)):
    """Analiza un repositorio para detectar tipo de sitio"""
    service = GitHubService(db)
    try:
        repo = await service.analyze_repository(connection_id, repo_id)
        return {
            "id": repo.id,
            "full_name": repo.full_name,
            "site_type": repo.site_type,
            "build_command": repo.build_command,
            "output_dir": repo.output_dir
        }
    except Exception as e:
        logger.error(f"Error analyzing repository: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-pr", response_model=PRResponse)
async def create_pull_request(request: CreatePRRequest, db: Session = Depends(get_db)):
    """Crea un Pull Request con fixes SEO/GEO"""
    service = GitHubService(db)
    
    try:
        pr = await service.create_pr_with_fixes(
            connection_id=request.connection_id,
            repo_id=request.repo_id,
            audit_id=request.audit_id,
            fixes=request.fixes
        )
        
        return pr
        
    except Exception as e:
        logger.error(f"Error creating PR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prs/{repo_id}", response_model=List[PRResponse])
async def get_pull_requests(repo_id: str, db: Session = Depends(get_db)):
    """Obtiene PRs de un repositorio"""
    service = GitHubService(db)
    prs = await service.get_repository_prs(repo_id)
    return prs


@router.post("/audit-blogs/{connection_id}/{repo_id}")
async def audit_repository_blogs(connection_id: str, repo_id: str, db: Session = Depends(get_db)):
    """
    Audita todos los blogs de un repositorio
    
    Encuentra automáticamente todos los archivos de blog según el framework
    y ejecuta una auditoría SEO completa en cada uno.
    
    Args:
        connection_id: ID de la conexión de GitHub
        repo_id: ID del repositorio
        
    Returns:
        Reporte completo con todos los blogs auditados y sus issues
    """
    from ...models.github import GitHubRepository
    from ...integrations.github.blog_auditor import BlogAuditorService
    
    service = GitHubService(db)
    
    try:
        # Obtener repo
        repo = db.query(GitHubRepository).filter(GitHubRepository.id == repo_id).first()
        
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        # Asegurarse que el repo esté analizado
        if not repo.site_type or repo.site_type == "unknown":
            await service.analyze_repository(connection_id, repo_id)
            db.refresh(repo)
        
        # Obtener cliente de GitHub
        client = await service.get_valid_client(connection_id)
        
        # Crear auditor
        auditor = BlogAuditorService(client)
        
        # Auditar todos los blogs
        logger.info(f"Starting blog audit for {repo.full_name}")
        audit_results = await auditor.audit_all_blogs(repo.full_name, repo.site_type)
        
        return audit_results
        
    except Exception as e:
        logger.error(f"Error auditing blogs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-blog-fixes-pr/{connection_id}/{repo_id}")
async def create_blog_fixes_pr(
    connection_id: str,
    repo_id: str,
    blog_paths: List[str],
    db: Session = Depends(get_db)
):
    """
    Crea un PR con fixes para blogs específicos
    
    Toma los resultados de una auditoría de blogs y crea un PR
    aplicando todos los fixes necesarios.
    
    Args:
        connection_id: ID de la conexión
        repo_id: ID del repositorio
        blog_paths: Lista de paths de blogs a aplicar fixes
        
    Returns:
        PR creado con fixes aplicados
    """
    from ...models.github import GitHubRepository
    from ...integrations.github.blog_auditor import BlogAuditorService
    
    service = GitHubService(db)
    
    try:
        # Obtener repo
        repo = db.query(GitHubRepository).filter(GitHubRepository.id == repo_id).first()
        
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        # Obtener cliente
        client = await service.get_valid_client(connection_id)
        
        # Re-auditar blogs seleccionados
        auditor = BlogAuditorService(client)
        gh_repo = client.get_repo(repo.full_name)
        
        all_fixes = []
        for blog_path in blog_paths:
            blog_audit = await auditor._audit_single_blog(gh_repo, blog_path, repo.site_type)
            fixes = auditor.generate_fixes_from_audit(blog_audit)
            all_fixes.extend(fixes)
        
        if not all_fixes:
            return {
                "status": "no_fixes_needed",
                "message": "No fixes required for selected blogs"
            }
        
        # Crear un pseudo audit_id o usar el sistema actual
        # Por ahora, creamos un registro temporal para tracking
        from ...models import Audit
        temp_audit = Audit(
            url=repo.homepage_url or repo.url,
            status="completed",
            source="github_blog_audit"
        )
        db.add(temp_audit)
        db.commit()
        db.refresh(temp_audit)
        
        # Crear PR con fixes
        pr = await service.create_pr_with_fixes(
            connection_id=connection_id,
            repo_id=repo_id,
            audit_id=temp_audit.id,
            fixes=all_fixes
        )
        
        return {
            "status": "success",
            "pr": pr,
            "fixes_applied": len(all_fixes),
            "blogs_fixed": len(blog_paths)
        }
        
    except Exception as e:
        logger.error(f"Error creating blog fixes PR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit-to-fixes/{audit_id}")
def convert_audit_to_fixes(audit_id: int, db: Session = Depends(get_db)):
    """
    Convierte el fix_plan de una auditoría en fixes aplicables a código
    
    Este endpoint toma una auditoría existente y genera una lista de fixes
    que pueden ser aplicados directamente al código fuente.
    
    Args:
        audit_id: ID de la auditoría
        
    Returns:
        Dict con audit_id y lista de fixes formateados para aplicar
    """
    from ...models import Audit
    
    audit = db.query(Audit).filter(Audit.id == audit_id).first()
    
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    
    if not audit.fix_plan:
        raise HTTPException(status_code=400, detail="Audit has no fix plan")
    
    # Convertir fix_plan a fixes aplicables
    fixes = []
    for item in audit.fix_plan:
        fix_type = _map_issue_to_fix_type(item.get("issue", ""))
        
        if fix_type != "other":  # Solo incluir fixes que podemos aplicar
            fix = {
                "type": fix_type,
                "priority": item.get("priority", "MEDIUM"),
                "value": item.get("recommended_value", ""),
                "page_url": item.get("page", ""),
                "description": item.get("issue", ""),
                "current_value": item.get("current_value"),
                "impact": item.get("impact", "")
            }
            fixes.append(fix)
    
    return {
        "audit_id": audit_id,
        "total_fixes": len(fixes),
        "fixes": fixes,
        "audit_url": audit.url,
        "audit_date": audit.created_at.isoformat() if audit.created_at else None
    }


def _map_issue_to_fix_type(issue: str) -> str:
    """
    Mapea issues detectados en auditoría a tipos de fixes aplicables en código
    
    Args:
        issue: Descripción del issue de la auditoría
        
    Returns:
        Tipo de fix (meta_description, title, h1, etc.)
    """
    if not issue:
        return "other"
    
    issue_lower = issue.lower()
    
    # Meta Description
    if any(term in issue_lower for term in ["meta description", "description tag", "meta desc"]):
        return "meta_description"
    
    # Title
    if any(term in issue_lower for term in ["title tag", "page title", "<title>"]):
        return "title"
    
    # H1
    if any(term in issue_lower for term in ["h1", "heading 1", "main heading"]):
        return "h1"
    
    # Alt Text
    if any(term in issue_lower for term in ["alt text", "alt attribute", "image alt", "missing alt"]):
        return "alt_text"
    
    # Open Graph
    if "og:title" in issue_lower or "open graph title" in issue_lower:
        return "og_title"
    
    if "og:description" in issue_lower or "open graph description" in issue_lower:
        return "og_description"
    
    # Schema/Structured Data
    if any(term in issue_lower for term in ["schema", "structured data", "json-ld"]):
        return "schema"
    
    # Canonical
    if "canonical" in issue_lower:
        return "canonical"
    
    # Keywords (menos común ahora, pero por si acaso)
    if "meta keywords" in issue_lower:
        return "meta_keywords"
    
    return "other"


# ===== GEO (Generative Engine Optimization) Endpoints =====

@router.get("/geo-score/{audit_id}")
async def get_geo_score(audit_id: int, db: Session = Depends(get_db)):
    """
    Calcula GEO Score de una auditoría
    
    GEO (Generative Engine Optimization) mide qué tan optimizado está
    el contenido para ser detectado y citado por LLMs como ChatGPT, Gemini, Claude.
    
    Args:
        audit_id: ID de la auditoría a evaluar
        
    Returns:
        Score 0-100 con breakdown por categoría y recomendaciones
    """
    from ...services.geo_score_service import GEOScoreService
    from ...models import Audit
    
    audit = db.query(Audit).filter(Audit.id == audit_id).first()
    
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    
    try:
        geo_service = GEOScoreService(db)
        geo_score = await geo_service.calculate_site_geo_score(
            url=audit.url,
            audit_id=audit_id
        )
        
        return geo_score
        
    except Exception as e:
        logger.error(f"Error calculating GEO score: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/audit-blogs-geo/{connection_id}/{repo_id}")
async def audit_repository_blogs_geo(connection_id: str, repo_id: str, db: Session = Depends(get_db)):
    """
    Audita blogs de un repositorio para SEO + GEO
    
    GEO (Generative Engine Optimization) detecta issues adicionales a SEO:
    - Formato Q&A (LLMs prefieren preguntas-respuestas)
    - E-E-A-T signals (Experience, Expertise, Authority, Trust)
    - Estructura de fragmentos (snippet-level clarity)
    - Lenguaje conversacional vs keyword-stuffed
    - Respuestas directas (pirámide invertida)
    
    Args:
        connection_id: ID de la conexión de GitHub
        repo_id: ID del repositorio
        
    Returns:
        Reporte completo con SEO issues + GEO issues + GEO score por blog
    """
    from ...models.github import GitHubRepository
    from ...integrations.github.geo_blog_auditor import GEOBlogAuditor
    
    service = GitHubService(db)
    
    try:
        # Obtener repo
        repo = db.query(GitHubRepository).filter(GitHubRepository.id == repo_id).first()
        
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        # Asegurarse que el repo esté analizado
        if not repo.site_type or repo.site_type == "unknown":
            await service.analyze_repository(connection_id, repo_id)
            db.refresh(repo)
        
        # Obtener cliente de GitHub
        client = await service.get_valid_client(connection_id)
        
        # Crear GEO auditor
        geo_auditor = GEOBlogAuditor(client, db)
        
        # Auditar todos los blogs (SEO + GEO)
        logger.info(f"Starting GEO blog audit for {repo.full_name}")
        audit_results = await geo_auditor.audit_all_blogs_geo(repo.full_name, repo.site_type)
        
        return audit_results
        
    except Exception as e:
        logger.error(f"Error auditing blogs with GEO: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class CreateGeoPRRequest(BaseModel):
    blog_paths: List[str]
    include_geo: bool = True

@router.post("/create-geo-fixes-pr/{connection_id}/{repo_id}")
async def create_geo_fixes_pr(
    connection_id: str,
    repo_id: str,
    request: CreateGeoPRRequest,
    db: Session = Depends(get_db)
):
    """
    Crea PR con fixes SEO + GEO para blogs
    """
    blog_paths = request.blog_paths
    include_geo = request.include_geo
    from ...models.github import GitHubRepository
    from ...integrations.github.geo_blog_auditor import GEOBlogAuditor
    
    service = GitHubService(db)
    
    try:
        # Obtener repo
        repo = db.query(GitHubRepository).filter(GitHubRepository.id == repo_id).first()
        
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        # Obtener cliente
        client = await service.get_valid_client(connection_id)
        
        # Re-auditar blogs seleccionados con GEO
        geo_auditor = GEOBlogAuditor(client, db)
        gh_repo = client.get_repo(repo.full_name)
        
        all_fixes = []
        geo_fixes_count = 0
        seo_fixes_count = 0
        
        for blog_path in blog_paths:
            # Auditar blog individual
            blog_audit = await geo_auditor._audit_single_blog(gh_repo, blog_path, repo.site_type)
            
            # Agregar GEO issues si está habilitado
            if include_geo:
                geo_issues = await geo_auditor._audit_blog_geo(blog_audit)
                blog_audit["geo_issues"] = geo_issues
                blog_audit["geo_score"] = geo_auditor._calculate_blog_geo_score(geo_issues)
            
            # Generar fixes (SEO + GEO)
            fixes = geo_auditor.generate_geo_fixes_from_audit(blog_audit)
            
            # Contar fixes por tipo
            for fix in fixes:
                if fix.get("category") == "geo":
                    geo_fixes_count += 1
                else:
                    seo_fixes_count += 1
            
            all_fixes.extend(fixes)
        
        if not all_fixes:
            return {
                "status": "no_fixes_needed",
                "message": "No fixes required for selected blogs"
            }
        
        # Crear auditoría temporal para tracking
        from ...models import Audit
        temp_audit = Audit(
            url=repo.homepage_url or repo.url,
            status="completed",
            source="github_geo_blog_audit"
        )
        db.add(temp_audit)
        db.commit()
        db.refresh(temp_audit)
        
        # Crear PR con todos los fixes
        pr = await service.create_pr_with_fixes(
            connection_id=connection_id,
            repo_id=repo_id,
            audit_id=temp_audit.id,
            fixes=all_fixes
        )
        
        return {
            "status": "success",
            "pr": pr,
            "fixes_applied": len(all_fixes),
            "seo_fixes": seo_fixes_count,
            "geo_fixes": geo_fixes_count,
            "blogs_fixed": len(blog_paths),
            "geo_enabled": include_geo
        }
        
    except Exception as e:
        logger.error(f"Error creating GEO fixes PR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/geo-compare/{audit_id}")
async def compare_geo_with_competitors(
    audit_id: int,
    competitor_urls: Optional[List[str]] = None,
    db: Session = Depends(get_db)
):
    """
    Compara GEO score con competidores
    
    Útil para ver gaps de optimización vs competencia directa
    
    Args:
        audit_id: ID de la auditoría a comparar
        competitor_urls: Lista de URLs de competidores (opcional)
        
    Returns:
        Análisis comparativo con ranking y gaps
    """
    from ...services.geo_score_service import GEOScoreService
    from ...models import Audit
    
    audit = db.query(Audit).filter(Audit.id == audit_id).first()
    
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    
    # Si no se proveen competidores, usar los de la auditoría
    if not competitor_urls:
        external_intel = audit.external_intelligence or {}
        competitor_urls = [
            comp.get("url") 
            for comp in external_intel.get("competitors", [])[:3]
        ]
    
    if not competitor_urls:
        raise HTTPException(
            status_code=400,
            detail="No competitor URLs provided or found in audit"
        )
    
    try:
        geo_service = GEOScoreService(db)
        comparison = await geo_service.compare_with_competitors(
            url=audit.url,
            competitor_urls=competitor_urls
        )
        
        return comparison
        
    except Exception as e:
        logger.error(f"Error comparing GEO scores: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.post("/webhook")
async def github_webhook(
    request: Request,
    x_github_event: Optional[str] = Header(None),
    x_hub_signature_256: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Maneja webhooks de GitHub
    
    Eventos soportados:
    - push: Auto-auditar cuando hay cambios
    - pull_request: Actualizar estado del PR
    - installation: Manejar instalación de la app
    """
    # 1. Verificar firma del webhook
    body = await request.body()
    
    if not _verify_webhook_signature(body, x_hub_signature_256):
        logger.warning("Invalid GitHub webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # 2. Parsear payload
    payload = await request.json()
    
    # 3. Procesar según tipo de evento
    try:
        from ...models.github import GitHubWebhookEvent
        
        # Guardar evento
        event = GitHubWebhookEvent(
            event_type=x_github_event,
            event_id=request.headers.get("x-github-delivery", ""),
            payload=payload
        )
        db.add(event)
        db.commit()
        
        # Procesar según tipo
        if x_github_event == "push":
            await _handle_push_event(payload, db)
        elif x_github_event == "pull_request":
            await _handle_pr_event(payload, db)
        elif x_github_event == "installation":
            await _handle_installation_event(payload, db)
        
        # Marcar como procesado
        event.processed = True
        event.processed_at = datetime.utcnow()
        db.commit()
        
        return {"status": "success", "event": x_github_event}
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        if 'event' in locals():
            event.error_message = str(e)
            db.commit()
        raise HTTPException(status_code=500, detail=str(e))


# Helper functions

def _verify_webhook_signature(payload_body: bytes, signature_header: str) -> bool:
    """Verifica la firma del webhook de GitHub"""
    if not signature_header or not settings.GITHUB_WEBHOOK_SECRET:
        return True  # Skip verification in development
    
    hash_object = hmac.new(
        settings.GITHUB_WEBHOOK_SECRET.encode(),
        msg=payload_body,
        digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()
    
    return hmac.compare_digest(expected_signature, signature_header)


async def _handle_push_event(payload: Dict, db: Session):
    """Maneja evento push - potencialmente auto-auditar"""
    repo_full_name = payload["repository"]["full_name"]
    
    # Buscar repo en BD
    repo = db.query(GitHubRepository).filter(
        GitHubRepository.full_name == repo_full_name
    ).first()
    
    if repo and repo.auto_audit:
        logger.info(f"Auto-audit triggered for {repo_full_name}")
        # TODO: Disparar auditoría en background con Celery
        # from ...workers.tasks import run_audit_task
        # run_audit_task.delay(repo.homepage_url or repo.url)


async def _handle_pr_event(payload: Dict, db: Session):
    """Maneja evento pull_request - actualizar estado"""
    pr_number = payload["pull_request"]["number"]
    action = payload["action"]  # opened, closed, merged, etc.
    
    # Buscar PR en BD
    pr = db.query(GitHubPullRequest).filter(
        GitHubPullRequest.pr_number == pr_number
    ).first()
    
    if pr:
        if action == "closed":
            if payload["pull_request"].get("merged"):
                pr.status = PRStatus.MERGED
                pr.merged_at = datetime.utcnow()
            else:
                pr.status = PRStatus.CLOSED
                pr.closed_at = datetime.utcnow()
            
            db.commit()
            logger.info(f"PR #{pr_number} status updated to {action}")


async def _handle_installation_event(payload: Dict, db: Session):
    """Maneja evento installation"""
    action = payload["action"]
    installation_id = payload["installation"]["id"]
    
    if action == "created":
        # Nueva instalación de la app
        logger.info(f"GitHub App installed: {installation_id}")
        # TODO: Guardar installation_id en GitHubConnection
    
    elif action == "deleted":
        # App desinstalada
        logger.info(f"GitHub App uninstalled: {installation_id}")
        # TODO: Desactivar conexión

class CreateAutoFixRequest(BaseModel):
    audit_id: int


@router.get("/geo-compare/{audit_id}")
async def compare_geo_with_competitors(
    audit_id: int,
    competitor_urls: Optional[List[str]] = None,
    db: Session = Depends(get_db)
):
    """
    Compara GEO score con competidores
    
    Útil para ver gaps de optimización vs competencia directa
    
    Args:
        audit_id: ID de la auditoría a comparar
        competitor_urls: Lista de URLs de competidores (opcional)
        
    Returns:
        Análisis comparativo con ranking y gaps
    """
    from ...services.geo_score_service import GEOScoreService
    from ...models import Audit
    
    audit = db.query(Audit).filter(Audit.id == audit_id).first()
    
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    
    # Si no se proveen competidores, usar los de la auditoría
    if not competitor_urls:
        external_intel = audit.external_intelligence or {}
        competitor_urls = [
            comp.get("url") 
            for comp in external_intel.get("competitors", [])[:3]
        ]
    
    if not competitor_urls:
        raise HTTPException(
            status_code=400,
            detail="No competitor URLs provided or found in audit"
        )
    
    try:
        geo_service = GEOScoreService(db)
        comparison = await geo_service.compare_with_competitors(
            url=audit.url,
            competitor_urls=competitor_urls
        )
        
        return comparison
        
    except Exception as e:
        logger.error(f"Error comparing GEO scores: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.post("/webhook")
async def github_webhook(
    request: Request,
    x_github_event: Optional[str] = Header(None),
    x_hub_signature_256: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Maneja webhooks de GitHub
    
    Eventos soportados:
    - push: Auto-auditar cuando hay cambios
    - pull_request: Actualizar estado del PR
    - installation: Manejar instalación de la app
    """
    # 1. Verificar firma del webhook
    body = await request.body()
    
    if not _verify_webhook_signature(body, x_hub_signature_256):
        logger.warning("Invalid GitHub webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # 2. Parsear payload
    payload = await request.json()
    
    # 3. Procesar según tipo de evento
    try:
        from ...models.github import GitHubWebhookEvent
        
        # Guardar evento
        event = GitHubWebhookEvent(
            event_type=x_github_event,
            event_id=request.headers.get("x-github-delivery", ""),
            payload=payload
        )
        db.add(event)
        db.commit()
        
        # Procesar según tipo
        if x_github_event == "push":
            await _handle_push_event(payload, db)
        elif x_github_event == "pull_request":
            await _handle_pr_event(payload, db)
        elif x_github_event == "installation":
            await _handle_installation_event(payload, db)
        
        # Marcar como procesado
        event.processed = True
        event.processed_at = datetime.utcnow()
        db.commit()
        
        return {"status": "success", "event": x_github_event}
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        if 'event' in locals():
            event.error_message = str(e)
            db.commit()
        raise HTTPException(status_code=500, detail=str(e))


# Helper functions

def _verify_webhook_signature(payload_body: bytes, signature_header: str) -> bool:
    """Verifica la firma del webhook de GitHub"""
    if not signature_header or not settings.GITHUB_WEBHOOK_SECRET:
        return True  # Skip verification in development
    
    hash_object = hmac.new(
        settings.GITHUB_WEBHOOK_SECRET.encode(),
        msg=payload_body,
        digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()
    
    return hmac.compare_digest(expected_signature, signature_header)


async def _handle_push_event(payload: Dict, db: Session):
    """Maneja evento push - potencialmente auto-auditar"""
    repo_full_name = payload["repository"]["full_name"]
    
    # Buscar repo en BD
    repo = db.query(GitHubRepository).filter(
        GitHubRepository.full_name == repo_full_name
    ).first()
    
    if repo and repo.auto_audit:
        logger.info(f"Auto-audit triggered for {repo_full_name}")
        # TODO: Disparar auditoría en background con Celery
        # from ...workers.tasks import run_audit_task
        # run_audit_task.delay(repo.homepage_url or repo.url)


async def _handle_pr_event(payload: Dict, db: Session):
    """Maneja evento pull_request - actualizar estado"""
    pr_number = payload["pull_request"]["number"]
    action = payload["action"]  # opened, closed, merged, etc.
    
    # Buscar PR en BD
    pr = db.query(GitHubPullRequest).filter(
        GitHubPullRequest.pr_number == pr_number
    ).first()
    
    if pr:
        if action == "closed":
            if payload["pull_request"].get("merged"):
                pr.status = PRStatus.MERGED
                pr.merged_at = datetime.utcnow()
            else:
                pr.status = PRStatus.CLOSED
                pr.closed_at = datetime.utcnow()
            
            db.commit()
            logger.info(f"PR #{pr_number} status updated to {action}")


async def _handle_installation_event(payload: Dict, db: Session):
    """Maneja evento installation"""
    action = payload["action"]
    installation_id = payload["installation"]["id"]
    
    if action == "created":
        # Nueva instalación de la app
        logger.info(f"GitHub App installed: {installation_id}")
        # TODO: Guardar installation_id en GitHubConnection
    
    elif action == "deleted":
        # App desinstalada
        logger.info(f"GitHub App uninstalled: {installation_id}")
        # TODO: Desactivar conexión

class CreateAutoFixRequest(BaseModel):
    audit_id: int

@router.post("/create-auto-fix-pr/{connection_id}/{repo_id}")
async def create_auto_fix_pr(
    connection_id: str,
    repo_id: str,
    request: CreateAutoFixRequest,
    db: Session = Depends(get_db)
):
    """
    Crea un PR automático basado en auditoría existente.
    
    Utiliza el método GitHubService.create_pr_with_fixes que ya tiene toda
    la lógica de extracción de contexto enriquecido (PageSpeed, Technical, etc.)
    """
    from ...models import Audit, AuditStatus
    from ...integrations.github.service import GitHubService
    
    service = GitHubService(db)
    
    try:
        # 1. Obtener auditoría
        audit = db.query(Audit).filter(Audit.id == request.audit_id).first()
        if not audit:
            raise HTTPException(status_code=404, detail="Audit not found")
        
        if audit.status != AuditStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Audit is not completed yet")
            
        # 2. Convertir fix_plan a fixes con formato correcto para el modificador
        raw_fixes = audit.fix_plan or []
        if not raw_fixes:
            raise HTTPException(status_code=400, detail="Audit has no fix plan")
        
        # Convertir cada item del fix_plan al formato que espera el modificador
        fixes = []
        for item in raw_fixes:
            fix_type = _map_issue_to_fix_type(item.get("issue", ""))
            
            if fix_type != "other":  # Solo incluir fixes que podemos aplicar
                fixes.append({
                    "type": fix_type,
                    "priority": item.get("priority", "MEDIUM"),
                    "value": item.get("recommended_value", ""),
                    "page_url": item.get("page", ""),
                    "description": item.get("issue", ""),
                    "current_value": item.get("current_value"),
                    "impact": item.get("impact", "")
                })
        
        if not fixes:
            # Si no hay fixes mapeables, usar fixes mínimos para mejorar SEO/GEO
            fixes = [
                {"type": "title", "priority": "HIGH", "description": "Optimize title"},
                {"type": "meta_description", "priority": "HIGH", "description": "Add/update meta description"},
                {"type": "schema", "priority": "MEDIUM", "description": "Add Schema.org structured data"},
                {"type": "add_faq_section", "priority": "MEDIUM", "description": "Add FAQ section"},
            ]
        
        logger.info(f"Mapped {len(fixes)} fixes from fix_plan for audit {request.audit_id}")
        
        # 3. Llamar al método existente que ya tiene toda la lógica
        # Este método extrae automáticamente:
        # - Keywords, Competitors, PageSpeed, Technical Audit, Content Suggestions
        pr = await service.create_pr_with_fixes(
            connection_id=connection_id,
            repo_id=repo_id,
            audit_id=request.audit_id,
            fixes=fixes
        )
        
        return {
            "success": True,
            "pr_url": pr.html_url,
            "pr_number": pr.pr_number,
            "title": pr.title
        }
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating auto-fix PR: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
