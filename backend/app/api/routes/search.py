"""
API Endpoints para búsqueda AI
"""
import re

from app.core.database import get_db
from app.core.logger import get_logger
from app.schemas import AuditCreate
from app.services.audit_service import AuditService
from app.workers.tasks import run_audit_task
from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

logger = get_logger(__name__)

router = APIRouter(
    prefix="/search",
    tags=["search"],
)


class SearchRequest(BaseModel):
    query: str


class SearchResponse(BaseModel):
    response: str
    suggestions: list[str]
    audit_id: int | None = None
    audit_started: bool = False


def extract_url(text: str) -> str | None:
    """Extraer URL de un texto"""
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    match = re.search(url_pattern, text)
    return match.group(0) if match else None


@router.post("", response_model=SearchResponse)
@router.post("/", response_model=SearchResponse)
async def search_ai(
    request: SearchRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Endpoint de búsqueda AI que procesa consultas y puede iniciar auditorías
    """
    query = request.query.strip()
    url = extract_url(query)

    # Si detecta una URL, iniciar auditoría automáticamente
    if url:
        try:
            # Crear auditoría con parámetros configurables
            audit_create = AuditCreate(
                url=url,
                max_crawl=30,  # Crawlear 30 páginas
                max_audit=3,  # Auditar 3 páginas en detalle
            )
            audit = AuditService.create_audit(db, audit_create)

            # Iniciar tarea en background
            try:
                task = run_audit_task.delay(audit.id)
                AuditService.set_audit_task_id(db, audit.id, task.id)
                logger.info(f"Auditoría {audit.id} iniciada para {url}")
            except Exception as e:
                logger.warning(f"Celery no disponible, usando modo síncrono: {e}")
                from app.api.routes.audits import run_audit_sync

                background_tasks.add_task(run_audit_sync, audit.id)

            return SearchResponse(
                response=f"¡Perfecto! He iniciado una auditoría completa de {url}. Analizaré hasta 30 páginas y realizaré un análisis detallado de 3 páginas principales. Puedes ver el progreso en tiempo real.",
                suggestions=[
                    f"Ver progreso de auditoría #{audit.id}",
                    "Ver todas las auditorías",
                    "Iniciar otra auditoría",
                    "Ver documentación",
                ],
                audit_id=audit.id,
                audit_started=True,
            )
        except Exception as e:
            logger.error(f"Error iniciando auditoría: {e}")
            return SearchResponse(
                response=f"Detecté la URL {url} pero hubo un error al iniciar la auditoría. Por favor, intenta nuevamente.",
                suggestions=[
                    "Reintentar auditoría",
                    "Ver auditorías anteriores",
                    "Contactar soporte",
                ],
            )

    # Respuestas inteligentes sin URL
    query_lower = query.lower()

    if "audit" in query_lower or "analizar" in query_lower or "revisar" in query_lower:
        response = "Para iniciar una auditoría, simplemente escribe o pega la URL completa de tu sitio web (ejemplo: https://tusitio.com). Analizaré hasta 30 páginas y haré un análisis detallado de 3 páginas principales."
        suggestions = [
            "Ejemplo: https://tusitio.com",
            "Ver auditorías anteriores",
            "¿Cómo funciona?",
            "Ver ejemplo de reporte",
        ]
    elif "help" in query_lower or "ayuda" in query_lower:
        response = "Puedo ayudarte a realizar auditorías SEO/GEO profesionales. Simplemente proporciona la URL de tu sitio web y comenzaré el análisis automáticamente."
        suggestions = [
            "¿Qué es una auditoría SEO?",
            "¿Cómo funciona el análisis?",
            "Ver ejemplo de reporte",
            "Iniciar nueva auditoría",
        ]
    else:
        response = "Para comenzar una auditoría, proporciona la URL completa de tu sitio web. Ejemplo: https://tusitio.com"
        suggestions = [
            "Ejemplo: https://ejemplo.com",
            "Ver documentación",
            "Ver auditorías anteriores",
            "¿Cómo funciona?",
        ]

    return SearchResponse(response=response, suggestions=suggestions)
