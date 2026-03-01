"""
GitHub API Routes
"""

import hashlib
import hmac
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.access_control import (
    ensure_audit_access,
    ensure_connection_access,
    is_connection_owned_by_user,
)
from ...core.auth import AuthUser, get_current_user
from ...core.config import settings
from ...core.database import get_db
from ...core.llm_kimi import KimiGenerationError, KimiUnavailableError, get_llm_function
from ...core.logger import get_logger
from ...core.oauth_state import build_oauth_state, validate_oauth_state
from ...integrations.github.oauth import GitHubOAuth
from ...integrations.github.service import GitHubService
from ...models.github import (
    GitHubConnection,
    GitHubPullRequest,
    GitHubRepository,
    PRStatus,
)
from ...services.audit_service import AuditService

router = APIRouter(prefix="/github", tags=["github"])
logger = get_logger(__name__)


def _get_owned_audit(db: Session, audit_id: int, current_user: AuthUser):
    audit = AuditService.get_audit(db, audit_id)
    return ensure_audit_access(audit, current_user)


def _get_owned_connection(
    db: Session, connection_id: str, current_user: AuthUser
) -> GitHubConnection:
    connection = (
        db.query(GitHubConnection)
        .filter(
            GitHubConnection.id == connection_id,
            GitHubConnection.is_active.is_(True),
        )
        .first()
    )
    return ensure_connection_access(
        connection,
        current_user,
        db,
        resource_label="conexión de GitHub",
    )


def _get_owned_repo(
    db: Session,
    repo_id: str,
    current_user: AuthUser,
    expected_connection_id: Optional[str] = None,
) -> GitHubRepository:
    repo = db.query(GitHubRepository).filter(GitHubRepository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    _get_owned_connection(db, repo.connection_id, current_user)

    if expected_connection_id and repo.connection_id != expected_connection_id:
        raise HTTPException(
            status_code=403,
            detail="Repository does not belong to provided connection",
        )

    return repo


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


class FixInputField(BaseModel):
    key: str
    label: str
    value: Optional[str] = ""
    placeholder: Optional[str] = ""
    required: bool = False
    input_type: Optional[str] = "text"


class FixInputGroup(BaseModel):
    id: str
    issue_code: str
    page_path: str
    required: bool = False
    prompt: Optional[str] = ""
    fields: List[FixInputField]


class FixInputsResponse(BaseModel):
    audit_id: int
    missing_inputs: List[FixInputGroup]
    missing_required: int


class FixInputAnswer(BaseModel):
    id: str
    issue_code: str
    page_path: str
    values: Dict[str, Any]


class FixInputsSubmit(BaseModel):
    inputs: List[FixInputAnswer]


class FixInputChatMessage(BaseModel):
    role: str
    content: str


class FixInputChatRequest(BaseModel):
    issue_code: str
    field_key: str
    field_label: Optional[str] = ""
    placeholder: Optional[str] = ""
    current_values: Optional[Dict[str, Any]] = None
    language: Optional[str] = "en"
    history: Optional[List[FixInputChatMessage]] = None


class FixInputChatResponse(BaseModel):
    assistant_message: str
    suggested_value: str = ""
    confidence: str = "unknown"


def _extract_domain(url: Optional[str]) -> str:
    if not url:
        return ""
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        cleaned = str(url).replace("https://", "").replace("http://", "")
        return cleaned.split("/")[0]


def _build_chat_fallback(field_label: str, issue_code: str, placeholder: str) -> str:
    label = field_label or issue_code.replace("_", " ").title()
    message = (
        f"Please provide {label}. This helps improve SEO/GEO accuracy for your audit."
    )
    if placeholder:
        message += f" Example based on audit data: {placeholder}"
    return message


# Routes


@router.get("/auth-url", response_model=ConnectResponse)
def get_auth_url(current_user: AuthUser = Depends(get_current_user)):
    """Obtiene URL para iniciar OAuth con GitHub"""
    try:
        state = build_oauth_state("github", current_user)
        data = GitHubOAuth.get_authorization_url(state=state)
        return data
    except Exception:
        logger.exception("Error generating GitHub auth URL")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/oauth/authorize")
def oauth_authorize(current_user: AuthUser = Depends(get_current_user)):
    """Redirige directamente a GitHub OAuth (para compatibilidad con frontend)"""
    from fastapi.responses import RedirectResponse

    try:
        state = build_oauth_state("github", current_user)
        auth_data = GitHubOAuth.get_authorization_url(state=state)
        return RedirectResponse(url=auth_data["url"])
    except Exception:
        logger.exception("Error redirecting to GitHub OAuth")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/callback")
async def oauth_callback(
    request: CallbackRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Maneja callback de OAuth"""
    try:
        validate_oauth_state(request.state or "", "github", current_user)

        # 1. Exchange code for token
        token_data = await GitHubOAuth.exchange_code(request.code)

        # 2. Get user info
        user_info = await GitHubOAuth.get_user_info(token_data["access_token"])

        # 3. Create/update connection
        service = GitHubService(db)
        connection = await service.create_or_update_connection(
            token_data=token_data,
            user_info=user_info,
            owner_user_id=current_user.user_id,
            owner_email=current_user.email,
        )

        # 4. Sync repositories in background to avoid blocking the user
        background_tasks.add_task(service.sync_repositories, connection.id)

        return {
            "status": "success",
            "connection_id": connection.id,
            "username": connection.github_username,
        }

    except HTTPException:
        raise
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden")
    except Exception:
        logger.exception("GitHub OAuth callback error")
        raise HTTPException(status_code=400, detail="Invalid OAuth callback request")


@router.get("/connections")
def get_connections(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Lista conexiones activas de GitHub"""
    all_connections = (
        db.query(GitHubConnection).filter(GitHubConnection.is_active.is_(True)).all()
    )
    connections = []
    for connection in all_connections:
        if is_connection_owned_by_user(connection, current_user):
            connections.append(connection)
            continue

        if (
            not connection.owner_user_id
            and not connection.owner_email
            and current_user
        ):
            try:
                claimed = ensure_connection_access(
                    connection,
                    current_user,
                    db,
                    resource_label="conexión de GitHub",
                )
                connections.append(claimed)
            except HTTPException:
                continue

    return [
        {
            "id": c.id,
            "username": c.github_username,
            "account_type": c.account_type,
            "created_at": c.created_at,
        }
        for c in connections
    ]


@router.post("/sync/{connection_id}")
async def sync_repositories(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Sincroniza repositorios de una conexión"""
    service = GitHubService(db)
    try:
        _get_owned_connection(db, connection_id, current_user)
        repos = await service.sync_repositories(connection_id)
        return {"status": "success", "synced_count": len(repos)}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error syncing repositories")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/repositories/{connection_id}", response_model=List[RepositoryResponse])
@router.get("/repos/{connection_id}", response_model=List[RepositoryResponse])
def get_repositories(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Obtiene repositorios de una conexión"""
    _get_owned_connection(db, connection_id, current_user)
    repos = (
        db.query(GitHubRepository)
        .filter(
            GitHubRepository.connection_id == connection_id,
            GitHubRepository.is_active,
        )
        .all()
    )

    return repos


@router.post("/analyze/{connection_id}/{repo_id}")
async def analyze_repository(
    connection_id: str,
    repo_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Analiza un repositorio para detectar tipo de sitio"""
    service = GitHubService(db)
    try:
        _get_owned_connection(db, connection_id, current_user)
        _get_owned_repo(db, repo_id, current_user, expected_connection_id=connection_id)
        repo = await service.analyze_repository(connection_id, repo_id)
        return {
            "id": repo.id,
            "full_name": repo.full_name,
            "site_type": repo.site_type,
            "build_command": repo.build_command,
            "output_dir": repo.output_dir,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error analyzing repository")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/create-pr", response_model=PRResponse)
async def create_pull_request(
    request: CreatePRRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Crea un Pull Request con fixes SEO/GEO"""
    service = GitHubService(db)

    try:
        _get_owned_audit(db, request.audit_id, current_user)
        _get_owned_connection(db, request.connection_id, current_user)
        _get_owned_repo(
            db,
            request.repo_id,
            current_user,
            expected_connection_id=request.connection_id,
        )
        pr = await service.create_pr_with_fixes(
            connection_id=request.connection_id,
            repo_id=request.repo_id,
            audit_id=request.audit_id,
            fixes=request.fixes,
        )

        return pr

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error creating PR")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/prs/{repo_id}", response_model=List[PRResponse])
async def get_pull_requests(
    repo_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Obtiene PRs de un repositorio"""
    service = GitHubService(db)
    _get_owned_repo(db, repo_id, current_user)
    prs = await service.get_repository_prs(repo_id)
    return prs


@router.post("/audit-blogs/{connection_id}/{repo_id}")
async def audit_repository_blogs(
    connection_id: str,
    repo_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
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
    from ...integrations.github.blog_auditor import BlogAuditorService

    service = GitHubService(db)

    try:
        _get_owned_connection(db, connection_id, current_user)
        repo = _get_owned_repo(
            db,
            repo_id,
            current_user,
            expected_connection_id=connection_id,
        )

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

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error auditing blogs")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/create-blog-fixes-pr/{connection_id}/{repo_id}")
async def create_blog_fixes_pr(
    connection_id: str,
    repo_id: str,
    blog_paths: List[str],
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
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
    from ...integrations.github.blog_auditor import BlogAuditorService

    service = GitHubService(db)

    try:
        _get_owned_connection(db, connection_id, current_user)
        repo = _get_owned_repo(
            db,
            repo_id,
            current_user,
            expected_connection_id=connection_id,
        )

        # Obtener cliente
        client = await service.get_valid_client(connection_id)

        # Re-auditar blogs seleccionados
        auditor = BlogAuditorService(client)
        gh_repo = client.get_repo(repo.full_name)

        all_fixes = []
        for blog_path in blog_paths:
            blog_audit = await auditor._audit_single_blog(
                gh_repo, blog_path, repo.site_type
            )
            fixes = auditor.generate_fixes_from_audit(blog_audit)
            all_fixes.extend(fixes)

        if not all_fixes:
            return {
                "status": "no_fixes_needed",
                "message": "No fixes required for selected blogs",
            }

        # Crear un pseudo audit_id o usar el sistema actual
        # Por ahora, creamos un registro temporal para tracking
        from ...models import Audit

        temp_audit = Audit(
            url=repo.homepage_url or repo.url,
            status="completed",
            source="github_blog_audit",
        )
        db.add(temp_audit)
        db.commit()
        db.refresh(temp_audit)

        # Crear PR con fixes
        pr = await service.create_pr_with_fixes(
            connection_id=connection_id,
            repo_id=repo_id,
            audit_id=temp_audit.id,
            fixes=all_fixes,
        )

        return {
            "status": "success",
            "pr": pr,
            "fixes_applied": len(all_fixes),
            "blogs_fixed": len(blog_paths),
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error creating blog fixes PR")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/audit-to-fixes/{audit_id}")
async def convert_audit_to_fixes(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Convierte el fix_plan de una auditoría en fixes aplicables a código

    Este endpoint toma una auditoría existente y genera una lista de fixes
    que pueden ser aplicados directamente al código fuente.

    Args:
        audit_id: ID de la auditoría

    Returns:
        Dict con audit_id y lista de fixes formateados para aplicar
    """
    audit = _get_owned_audit(db, audit_id, current_user)

    service = GitHubService(db)
    # Ensure fix_plan exists (on-demand generation if needed)
    await AuditService.ensure_fix_plan(db, audit_id)
    fixes = service.prepare_fixes_from_audit(audit)

    return {
        "audit_id": audit_id,
        "total_fixes": len(fixes),
        "fixes": fixes,
        "audit_url": audit.url,
        "audit_date": audit.created_at.isoformat() if audit.created_at else None,
    }


@router.get("/fix-inputs/{audit_id}", response_model=FixInputsResponse)
async def get_fix_inputs(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Returns missing inputs required to safely apply fixes (user-provided, no fabrication).
    """
    audit = _get_owned_audit(db, audit_id, current_user)
    missing_inputs = await AuditService.get_fix_plan_missing_inputs(db, audit_id)
    missing_required = len([g for g in missing_inputs if g.get("required")])
    return {
        "audit_id": audit.id,
        "missing_inputs": missing_inputs,
        "missing_required": missing_required,
    }


@router.post("/fix-inputs/{audit_id}", response_model=FixInputsResponse)
async def submit_fix_inputs(
    audit_id: int,
    payload: FixInputsSubmit,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Persist user-provided inputs into fix_plan and return remaining missing inputs.
    """
    _get_owned_audit(db, audit_id, current_user)
    await AuditService.apply_fix_plan_inputs(db, audit_id, payload.inputs)
    missing_inputs = await AuditService.get_fix_plan_missing_inputs(db, audit_id)
    missing_required = len([g for g in missing_inputs if g.get("required")])
    return {
        "audit_id": audit_id,
        "missing_inputs": missing_inputs,
        "missing_required": missing_required,
    }


@router.post("/fix-inputs/chat/{audit_id}", response_model=FixInputChatResponse)
async def fix_inputs_chat(
    audit_id: int,
    payload: FixInputChatRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Returns LLM-guided suggestions for missing inputs using audit evidence only.
    """
    audit = _get_owned_audit(db, audit_id, current_user)
    await AuditService.ensure_fix_plan(db, audit_id, min_items=1)
    db.refresh(audit)

    issue_code = (payload.issue_code or "").upper().strip()
    field_label = (payload.field_label or "").strip()
    placeholder = (payload.placeholder or "").strip()

    # Ensure FAQ suggestions are only provided when FAQ_MISSING exists in fix_plan
    if issue_code.startswith("FAQ_"):
        fix_plan = audit.fix_plan if isinstance(audit.fix_plan, list) else []
        has_faq = any(
            str(item.get("issue_code") or "").upper().startswith("FAQ_")
            for item in fix_plan
        )
        if not has_faq:
            return {
                "assistant_message": "FAQ inputs are not required for this audit.",
                "suggested_value": "",
                "confidence": "unknown",
            }

    audit_context = AuditService.get_complete_audit_context(db, audit_id) or {}
    target_audit = audit_context.get("target_audit") or {}
    content = target_audit.get("content") or {}
    title = content.get("title") or ""
    meta_description = content.get("meta_description") or ""
    text_sample = content.get("text_sample") or ""
    if isinstance(text_sample, str) and len(text_sample) > 700:
        text_sample = text_sample[:700] + "..."

    keywords = audit_context.get("keywords", {}).get("items") or []
    keyword_terms = []
    for item in keywords:
        if isinstance(item, dict):
            term = item.get("term") or item.get("keyword")
            if term:
                keyword_terms.append(str(term))
    keyword_terms = keyword_terms[:8]

    history_items = []
    if payload.history:
        for msg in payload.history[-6:]:
            if not msg:
                continue
            history_items.append({"role": msg.role, "content": msg.content})

    system_prompt = (
        "You are a strict SEO/GEO assistant. "
        "Use ONLY the audit evidence provided. Do NOT invent facts. "
        'If evidence is insufficient, set suggested_value to "" and confidence to "unknown". '
        "Return ONLY JSON with keys: assistant_message, suggested_value, confidence. "
        "assistant_message should be 1-3 sentences and explain why the field matters for SEO/GEO."
    )

    user_prompt = (
        "AUDIT EVIDENCE (ONLY SOURCE OF TRUTH):\n"
        f"- url: {audit.url or ''}\n"
        f"- domain: {audit.domain or _extract_domain(audit.url)}\n"
        f"- title: {title}\n"
        f"- meta_description: {meta_description}\n"
        f"- text_sample: {text_sample}\n"
        f"- keywords: {', '.join(keyword_terms)}\n"
        "\nFIELD REQUEST:\n"
        f"- issue_code: {payload.issue_code}\n"
        f"- field_key: {payload.field_key}\n"
        f"- field_label: {field_label}\n"
        f"- placeholder: {placeholder}\n"
        f"- current_values: {json.dumps(payload.current_values or {}, ensure_ascii=False)}\n"
    )

    if history_items:
        history_lines = "\n".join(
            [f"{m['role']}: {m['content']}" for m in history_items]
        )
        user_prompt += f"\nCHAT HISTORY:\n{history_lines}\n"

    llm_function = None
    try:
        llm_function = get_llm_function()
    except Exception:
        llm_function = None

    if llm_function is None:
        return {
            "assistant_message": _build_chat_fallback(
                field_label, issue_code, placeholder
            ),
            "suggested_value": "",
            "confidence": "unknown",
        }

    try:
        raw = await llm_function(
            system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=512
        )
    except (KimiUnavailableError, KimiGenerationError) as exc:
        logger.warning(f"Kimi chat unavailable for fix inputs: {exc}")
        return {
            "assistant_message": _build_chat_fallback(
                field_label, issue_code, placeholder
            ),
            "suggested_value": "",
            "confidence": "unknown",
        }

    parsed = AuditService._safe_json_dict(raw) if isinstance(raw, str) else None
    if not parsed:
        return {
            "assistant_message": _build_chat_fallback(
                field_label, issue_code, placeholder
            ),
            "suggested_value": "",
            "confidence": "unknown",
        }

    assistant_message = str(parsed.get("assistant_message") or "").strip()
    suggested_value = str(parsed.get("suggested_value") or "").strip()
    confidence = str(parsed.get("confidence") or "unknown").strip().lower()
    if confidence not in {"evidence", "unknown"}:
        confidence = "unknown"
    if not assistant_message:
        assistant_message = _build_chat_fallback(field_label, issue_code, placeholder)
    if not suggested_value:
        confidence = "unknown"

    return {
        "assistant_message": assistant_message,
        "suggested_value": suggested_value,
        "confidence": confidence,
    }


# ===== GEO (Generative Engine Optimization) Endpoints =====


@router.get("/geo-score/{audit_id}")
async def get_geo_score(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
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

    audit = _get_owned_audit(db, audit_id, current_user)

    try:
        geo_service = GEOScoreService(db)
        geo_score = await geo_service.calculate_site_geo_score(
            url=audit.url, audit_id=audit_id
        )

        return geo_score

    except Exception:
        logger.exception("Error calculating GEO score")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/audit-blogs-geo/{connection_id}/{repo_id}")
async def audit_repository_blogs_geo(
    connection_id: str,
    repo_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
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
    from ...integrations.github.geo_blog_auditor import GEOBlogAuditor

    service = GitHubService(db)

    try:
        _get_owned_connection(db, connection_id, current_user)
        repo = _get_owned_repo(
            db,
            repo_id,
            current_user,
            expected_connection_id=connection_id,
        )

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
        audit_results = await geo_auditor.audit_all_blogs_geo(
            repo.full_name, repo.site_type
        )

        return audit_results

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error auditing blogs with GEO")
        raise HTTPException(status_code=500, detail="Internal server error")


class CreateGeoPRRequest(BaseModel):
    blog_paths: List[str]
    include_geo: bool = True


@router.post("/create-geo-fixes-pr/{connection_id}/{repo_id}")
async def create_geo_fixes_pr(
    connection_id: str,
    repo_id: str,
    request: CreateGeoPRRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Crea PR con fixes SEO + GEO para blogs
    """
    blog_paths = request.blog_paths
    include_geo = request.include_geo
    from ...integrations.github.geo_blog_auditor import GEOBlogAuditor

    service = GitHubService(db)

    try:
        _get_owned_connection(db, connection_id, current_user)
        repo = _get_owned_repo(
            db,
            repo_id,
            current_user,
            expected_connection_id=connection_id,
        )

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
            blog_audit = await geo_auditor._audit_single_blog(
                gh_repo, blog_path, repo.site_type
            )

            # Agregar GEO issues si está habilitado
            if include_geo:
                geo_issues = await geo_auditor._audit_blog_geo(blog_audit)
                blog_audit["geo_issues"] = geo_issues
                blog_audit["geo_score"] = geo_auditor._calculate_blog_geo_score(
                    geo_issues
                )

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
                "message": "No fixes required for selected blogs",
            }

        # Crear auditoría temporal para tracking
        from ...models import Audit

        temp_audit = Audit(
            url=repo.homepage_url or repo.url,
            status="completed",
            source="github_geo_blog_audit",
        )
        db.add(temp_audit)
        db.commit()
        db.refresh(temp_audit)

        # Crear PR con todos los fixes
        pr = await service.create_pr_with_fixes(
            connection_id=connection_id,
            repo_id=repo_id,
            audit_id=temp_audit.id,
            fixes=all_fixes,
        )

        return {
            "status": "success",
            "pr": pr,
            "fixes_applied": len(all_fixes),
            "seo_fixes": seo_fixes_count,
            "geo_fixes": geo_fixes_count,
            "blogs_fixed": len(blog_paths),
            "geo_enabled": include_geo,
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error creating GEO fixes PR")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/geo-compare/{audit_id}")
async def compare_geo_with_competitors(
    audit_id: int,
    competitor_urls: Optional[List[str]] = None,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
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

    audit = _get_owned_audit(db, audit_id, current_user)

    # Si no se proveen competidores, usar los de la auditoría
    if not competitor_urls:
        external_intel = audit.external_intelligence or {}
        competitor_urls = [
            comp.get("url") for comp in external_intel.get("competitors", [])[:3]
        ]

    if not competitor_urls:
        raise HTTPException(
            status_code=400, detail="No competitor URLs provided or found in audit"
        )

    try:
        geo_service = GEOScoreService(db)
        comparison = await geo_service.compare_with_competitors(
            url=audit.url, competitor_urls=competitor_urls
        )

        return comparison

    except Exception:
        logger.exception("Error comparing GEO scores")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/webhook")
async def github_webhook(
    request: Request,
    x_github_event: Optional[str] = Header(None),
    x_hub_signature_256: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Maneja webhooks de GitHub

    Eventos soportados:
    - push: Auto-auditar cuando hay cambios
    - pull_request: Actualizar estado del PR
    - installation: Manejar instalación de la app
    """
    webhook_secret = (settings.GITHUB_WEBHOOK_SECRET or "").strip()
    if not webhook_secret and not settings.DEBUG:
        raise HTTPException(
            status_code=503,
            detail="GitHub webhook secret is not configured on server",
        )

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
            payload=payload,
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
        logger.exception("Error processing webhook")
        if "event" in locals():
            event.error_message = str(e)
            db.commit()
        raise HTTPException(status_code=500, detail="Internal server error")


# Helper functions


def _verify_webhook_signature(
    payload_body: bytes, signature_header: Optional[str]
) -> bool:
    """Verifica la firma del webhook de GitHub"""
    webhook_secret = (settings.GITHUB_WEBHOOK_SECRET or "").strip()
    if not webhook_secret:
        return settings.DEBUG
    if not signature_header:
        return False

    hash_object = hmac.new(
        webhook_secret.encode(),
        msg=payload_body,
        digestmod=hashlib.sha256,
    )
    expected_signature = "sha256=" + hash_object.hexdigest()

    return hmac.compare_digest(expected_signature, signature_header)


async def _handle_push_event(payload: Dict, db: Session):
    """Maneja evento push - potencialmente auto-auditar"""
    repo_full_name = payload["repository"]["full_name"]

    # Buscar repo en BD
    repo = (
        db.query(GitHubRepository)
        .filter(GitHubRepository.full_name == repo_full_name)
        .first()
    )

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
    pr = (
        db.query(GitHubPullRequest)
        .filter(GitHubPullRequest.pr_number == pr_number)
        .first()
    )

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
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Crea un PR automático basado en auditoría existente.

    Utiliza el método GitHubService.create_pr_with_fixes que ya tiene toda
    la lógica de extracción de contexto enriquecido (PageSpeed, Technical, etc.)
    """
    from ...models import AuditStatus

    service = GitHubService(db)

    try:
        _get_owned_connection(db, connection_id, current_user)
        _get_owned_repo(
            db,
            repo_id,
            current_user,
            expected_connection_id=connection_id,
        )

        # 1. Obtener auditoría
        audit = _get_owned_audit(db, request.audit_id, current_user)

        if audit.status != AuditStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Audit is not completed yet")

        # 2. Ensure fix_plan exists (on-demand generation if needed)
        await AuditService.ensure_fix_plan(db, request.audit_id)

        # 2.1 Ensure required user inputs are present
        missing_inputs = await AuditService.get_fix_plan_missing_inputs(
            db, request.audit_id
        )
        missing_required = [g for g in missing_inputs if g.get("required")]
        if missing_required:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Missing required inputs to generate safe fixes",
                    "missing_inputs": missing_inputs,
                },
            )

        # 3. Prepare fixes using centralized logic
        fixes = service.prepare_fixes_from_audit(audit)

        # 4. Llamar al método existente que ya tiene toda la lógica
        # Este método extrae automáticamente:
        # - Keywords, Competitors, PageSpeed, Technical Audit, Content Suggestions
        pr = await service.create_pr_with_fixes(
            connection_id=connection_id,
            repo_id=repo_id,
            audit_id=request.audit_id,
            fixes=fixes,
        )

        return {
            "success": True,
            "pr_url": pr.html_url,
            "pr_number": pr.pr_number,
            "title": pr.title,
        }

    except HTTPException:
        raise
    except ValueError:
        logger.exception("Validation error creating auto-fix PR")
        raise HTTPException(status_code=400, detail="Invalid request data")
    except Exception:
        logger.exception("Error creating auto-fix PR")
        raise HTTPException(status_code=500, detail="Internal server error")
