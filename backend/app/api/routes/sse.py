"""
Server-Sent Events (SSE) endpoint for real-time audit progress updates.
Replaces polling to reduce server load and improve responsiveness.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import asyncio
import json
from typing import AsyncGenerator

from app.core.database import get_db
from app.services.audit_service import AuditService
from app.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/sse",
    tags=["sse"],
)


async def audit_progress_stream(audit_id: int, db: Session) -> AsyncGenerator[str, None]:
    """
    Stream audit progress updates using Server-Sent Events.
    Sends updates every 2 seconds until audit is completed or failed.
    Includes heartbeat to keep connection alive.
    """
    max_duration = 600  # 10 minutes max
    start_time = asyncio.get_event_loop().time()
    last_status = None
    last_progress = None
    heartbeat_counter = 0
    
    try:
        while True:
            # Check timeout
            if asyncio.get_event_loop().time() - start_time > max_duration:
                logger.warning(f"SSE stream timeout for audit {audit_id}")
                yield f"data: {json.dumps({'error': 'Stream timeout'})}\n\n"
                break
            
            # Get fresh DB session for each query to avoid stale data
            from app.core.database import SessionLocal
            db_session = SessionLocal()
            try:
                audit = AuditService.get_audit(db_session, audit_id)
                
                if not audit:
                    yield f"data: {json.dumps({'error': 'Audit not found'})}\n\n"
                    break
                
                # Send update if something changed
                if audit.status != last_status or audit.progress != last_progress:
                    data = {
                        "audit_id": audit.id,
                        "status": audit.status.value if audit.status else "unknown",
                        "progress": audit.progress or 0,
                        "error_message": audit.error_message,
                        "geo_score": audit.geo_score,
                        "total_pages": audit.total_pages,
                    }
                    
                    yield f"data: {json.dumps(data)}\n\n"
                    
                    last_status = audit.status
                    last_progress = audit.progress
                    
                    # Stop streaming if audit is completed or failed
                    if audit.status.value in ["completed", "failed"]:
                        logger.info(f"SSE stream ended for audit {audit_id}: {audit.status.value}")
                        break
                else:
                    # Send heartbeat every 30 seconds to keep connection alive
                    heartbeat_counter += 1
                    if heartbeat_counter >= 15:  # 15 * 2s = 30s
                        yield ": heartbeat\n\n"
                        heartbeat_counter = 0
            finally:
                db_session.close()
            
            await asyncio.sleep(2)
            
    except asyncio.CancelledError:
        logger.info(f"SSE stream cancelled for audit {audit_id}")
        raise
    except Exception as e:
        logger.error(f"Error in SSE stream for audit {audit_id}: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


@router.get("/audits/{audit_id}/progress")
async def stream_audit_progress(audit_id: int):
    """
    SSE endpoint for streaming audit progress updates.
    No DB dependency needed - creates fresh session per query.
    """
    logger.info(f"SSE connection established for audit {audit_id}")
    
    return StreamingResponse(
        audit_progress_stream(audit_id, None),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
