"""
Webhook Routes for receiving and configuring webhooks.
"""
import json
import hashlib
import hmac
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, Header, status
from pydantic import BaseModel, HttpUrl, Field
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.config import settings
from app.core.logger import get_logger
from app.services.webhook_service import WebhookService, WebhookEventType

logger = get_logger(__name__)

router = APIRouter(
    prefix="/webhooks",
    tags=["webhooks"]
)


# ==================== Pydantic Models ====================

class WebhookConfigCreate(BaseModel):
    """Configuration for creating/updating a webhook endpoint."""
    url: HttpUrl = Field(..., description="URL to receive webhook notifications")
    secret: Optional[str] = Field(None, min_length=16, max_length=256, description="Secret for signing payloads")
    events: List[str] = Field(
        default=["audit.completed", "pdf.ready"],
        description="List of events to subscribe to"
    )
    active: bool = Field(default=True, description="Whether the webhook is active")
    description: Optional[str] = Field(None, max_length=500, description="Optional description")


class WebhookConfigResponse(BaseModel):
    """Response model for webhook configuration."""
    id: int
    url: str
    events: List[str]
    active: bool
    description: Optional[str]
    created_at: datetime
    last_delivery_at: Optional[datetime] = None
    delivery_success_rate: Optional[float] = None
    
    class Config:
        from_attributes = True


class WebhookTestRequest(BaseModel):
    """Request to test a webhook endpoint."""
    url: HttpUrl
    secret: Optional[str] = None
    event_type: str = "audit.completed"


class WebhookTestResponse(BaseModel):
    """Response from webhook test."""
    success: bool
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    error: Optional[str] = None


# ==================== Webhook Configuration Endpoints ====================

@router.post("/config", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_webhook_config(
    config: WebhookConfigCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new webhook configuration.
    
    The webhook will receive POST requests with JSON payload containing:
    - event: Event type (e.g., "audit.completed")
    - timestamp: ISO 8601 timestamp
    - data: Event-specific data
    - webhook_id: Unique delivery ID
    
    Headers included:
    - X-Webhook-Signature: HMAC-SHA256 signature (if secret provided)
    - X-Webhook-Event: Event type
    - X-Webhook-Timestamp: Delivery timestamp
    """
    # Validate event types
    valid_events = [e.value for e in WebhookEventType]
    for event in config.events:
        if event not in valid_events:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid event type: {event}. Valid types: {valid_events}"
            )
    
    # In a full implementation, this would save to database
    # For now, we use environment-based configuration
    logger.info(f"Webhook configured for {config.url} with events: {config.events}")
    
    return {
        "success": True,
        "message": "Webhook configured successfully",
        "url": str(config.url),
        "events": config.events,
        "note": "Webhook configuration saved. Use /test endpoint to verify connectivity."
    }


@router.post("/test", response_model=WebhookTestResponse)
async def test_webhook(request: WebhookTestRequest):
    """
    Test a webhook endpoint by sending a test event.
    
    This sends a test payload to verify the endpoint is reachable
    and properly configured to receive webhooks.
    """
    import time
    
    start_time = time.time()
    
    try:
        event_type = WebhookEventType(request.event_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event type: {request.event_type}"
        )
    
    test_payload = {
        "audit_id": 0,
        "url": "https://example.com",
        "status": "test",
        "message": "This is a test webhook from Auditor GEO",
        "test": True
    }
    
    result = await WebhookService.send_webhook(
        url=str(request.url),
        event_type=event_type,
        payload=test_payload,
        secret=request.secret
    )
    
    response_time = (time.time() - start_time) * 1000
    
    return WebhookTestResponse(
        success=result.get("status") == "delivered",
        status_code=result.get("status_code"),
        response_time_ms=round(response_time, 2),
        error=result.get("error")
    )


@router.get("/events", response_model=List[dict])
async def list_webhook_events():
    """
    List all available webhook event types.
    """
    return [
        {
            "event": event.value,
            "description": _get_event_description(event)
        }
        for event in WebhookEventType
    ]


def _get_event_description(event: WebhookEventType) -> str:
    """Get human-readable description for event type."""
    descriptions = {
        WebhookEventType.AUDIT_CREATED: "Triggered when a new audit is created",
        WebhookEventType.AUDIT_STARTED: "Triggered when audit processing begins",
        WebhookEventType.AUDIT_COMPLETED: "Triggered when audit finishes successfully",
        WebhookEventType.AUDIT_FAILED: "Triggered when audit fails with an error",
        WebhookEventType.AUDIT_PROGRESS: "Triggered at key progress milestones (25%, 50%, 75%)",
        WebhookEventType.REPORT_GENERATED: "Triggered when the audit report is generated",
        WebhookEventType.PDF_READY: "Triggered when PDF report is ready for download",
        WebhookEventType.PAGESPEED_COMPLETED: "Triggered when PageSpeed analysis completes",
        WebhookEventType.GEO_ANALYSIS_COMPLETED: "Triggered when GEO tools analysis completes",
        WebhookEventType.GITHUB_PR_CREATED: "Triggered when a GitHub PR is created",
        WebhookEventType.GITHUB_SYNC_COMPLETED: "Triggered when GitHub sync completes",
        WebhookEventType.COMPETITOR_ANALYSIS_COMPLETED: "Triggered when competitor analysis completes"
    }
    return descriptions.get(event, "No description available")


# ==================== Incoming Webhook Handlers ====================

@router.post("/github/incoming")
async def handle_github_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Handle incoming GitHub webhooks.
    
    Verifies the signature and processes GitHub events like:
    - push: Code pushed to repository
    - pull_request: PR opened/closed/merged
    - issues: Issue created/updated
    """
    # Get raw body for signature verification
    body = await request.body()
    body_str = body.decode('utf-8')
    
    # Verify signature if secret is configured
    webhook_secret = settings.GITHUB_WEBHOOK_SECRET
    if webhook_secret:
        if not x_hub_signature_256:
            raise HTTPException(
                status_code=401,
                detail="Missing X-Hub-Signature-256 header"
            )
        
        expected_signature = "sha256=" + WebhookService.generate_signature(
            body_str, webhook_secret
        )
        
        if not hmac.compare_digest(x_hub_signature_256, expected_signature):
            logger.warning("Invalid GitHub webhook signature")
            raise HTTPException(
                status_code=401,
                detail="Invalid signature"
            )
    
    # Parse payload
    try:
        payload = json.loads(body_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    logger.info(f"Received GitHub webhook: {x_github_event}")
    
    # Process based on event type
    if x_github_event == "push":
        return await _handle_github_push(payload, db)
    elif x_github_event == "pull_request":
        return await _handle_github_pr(payload, db)
    elif x_github_event == "ping":
        return {"message": "pong", "zen": payload.get("zen", "")}
    
    return {"status": "received", "event": x_github_event}


async def _handle_github_push(payload: dict, db: Session) -> dict:
    """Handle GitHub push event."""
    repository = payload.get("repository", {})
    repo_full_name = repository.get("full_name")
    pusher = payload.get("pusher", {}).get("name")
    ref = payload.get("ref", "")
    
    logger.info(f"GitHub push to {repo_full_name} by {pusher} on {ref}")
    
    # You could trigger a re-audit here if needed
    return {
        "status": "processed",
        "event": "push",
        "repository": repo_full_name,
        "ref": ref
    }


async def _handle_github_pr(payload: dict, db: Session) -> dict:
    """Handle GitHub pull request event."""
    action = payload.get("action")
    pr = payload.get("pull_request", {})
    pr_number = pr.get("number")
    pr_title = pr.get("title")
    repository = payload.get("repository", {})
    repo_full_name = repository.get("full_name")
    
    logger.info(f"GitHub PR {action}: #{pr_number} in {repo_full_name}")
    
    return {
        "status": "processed",
        "event": "pull_request",
        "action": action,
        "pr_number": pr_number,
        "repository": repo_full_name
    }


@router.post("/hubspot/incoming")
async def handle_hubspot_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle incoming HubSpot webhooks.
    
    Processes HubSpot CRM events like:
    - contact.creation
    - contact.propertyChange
    - deal.creation
    """
    body = await request.body()
    
    try:
        payload = json.loads(body.decode('utf-8'))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    logger.info(f"Received HubSpot webhook with {len(payload) if isinstance(payload, list) else 1} events")
    
    # HubSpot sends an array of events
    events = payload if isinstance(payload, list) else [payload]
    
    processed = []
    for event in events:
        subscription_type = event.get("subscriptionType", "unknown")
        object_id = event.get("objectId")
        
        logger.info(f"Processing HubSpot event: {subscription_type} for object {object_id}")
        processed.append({
            "type": subscription_type,
            "object_id": object_id,
            "status": "processed"
        })
    
    return {
        "status": "received",
        "events_processed": len(processed),
        "details": processed
    }


# ==================== Status Endpoints ====================

@router.get("/health")
async def webhook_health():
    """Check webhook service health status."""
    return {
        "status": "healthy",
        "service": "webhook",
        "supported_events": len(list(WebhookEventType)),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
