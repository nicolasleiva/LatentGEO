from __future__ import annotations

import html
import re
from hashlib import sha256
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session, load_only

from ...core.security import sanitize_html_content
from ...models import Audit, GeoArticleBatch
from ...models.odoo import (
    OdooConnection,
    OdooDraftAction,
    OdooRecordSnapshot,
    OdooSyncRun,
)
from ...services.geo_article_engine_service import GeoArticleEngineService
from ...services.odoo_delivery_service import OdooDeliveryService
from .client import OdooAPIError
from .service import OdooConnectionService


class OdooDraftService:
    SAFE_TEMPLATE_BLOCKED_MODELS = {"website.website"}
    ACTION_KEY_MAX_LENGTH = 500
    TITLE_MAX_LENGTH = 500
    TARGET_MODEL_MAX_LENGTH = 120
    TARGET_RECORD_ID_MAX_LENGTH = 120
    TARGET_PATH_MAX_LENGTH = 2048

    def __init__(self, db: Session):
        self.db = db
        self.connection_service = OdooConnectionService(db)

    @staticmethod
    def _slugify(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower())
        return normalized.strip("-") or "odoo-draft"

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return " ".join(str(value or "").split()).strip()

    @classmethod
    def _normalize_optional_text(
        cls,
        value: Any,
        *,
        max_length: int,
        collapse_whitespace: bool = True,
    ) -> Optional[str]:
        if value is None:
            return None
        rendered = str(value)
        normalized = (
            cls._normalize_text(rendered) if collapse_whitespace else rendered.strip()
        )
        if not normalized:
            return None
        return normalized[:max_length]

    @classmethod
    def _normalize_action_key(cls, value: Any) -> str:
        normalized = (
            cls._normalize_optional_text(
                value,
                max_length=cls.ACTION_KEY_MAX_LENGTH * 2,
            )
            or "odoo-draft"
        )
        if len(normalized) <= cls.ACTION_KEY_MAX_LENGTH:
            return normalized

        digest = sha256(normalized.encode("utf-8")).hexdigest()[:16]
        prefix_length = max(1, cls.ACTION_KEY_MAX_LENGTH - len(digest) - 1)
        return f"{normalized[:prefix_length]}:{digest}"

    @classmethod
    def _normalize_action_fields(
        cls,
        *,
        action_key: str,
        title: str,
        target_model: Optional[str],
        target_record_id: Optional[str],
        target_path: Optional[str],
        draft_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_payload = dict(draft_payload or {})

        raw_action_key = cls._normalize_text(action_key)
        normalized_action_key = cls._normalize_action_key(raw_action_key)
        if raw_action_key and normalized_action_key != raw_action_key:
            normalized_payload["source_action_key"] = raw_action_key

        raw_target_path = cls._normalize_optional_text(
            target_path,
            max_length=cls.TARGET_PATH_MAX_LENGTH * 2,
            collapse_whitespace=False,
        )
        normalized_target_path = raw_target_path
        if (
            normalized_target_path
            and len(normalized_target_path) > cls.TARGET_PATH_MAX_LENGTH
        ):
            normalized_payload["source_target_path"] = normalized_target_path
            normalized_target_path = normalized_target_path[
                : cls.TARGET_PATH_MAX_LENGTH
            ]

        return {
            "action_key": normalized_action_key,
            "title": cls._normalize_optional_text(
                title,
                max_length=cls.TITLE_MAX_LENGTH,
            ),
            "target_model": cls._normalize_optional_text(
                target_model,
                max_length=cls.TARGET_MODEL_MAX_LENGTH,
            ),
            "target_record_id": cls._normalize_optional_text(
                target_record_id,
                max_length=cls.TARGET_RECORD_ID_MAX_LENGTH,
            ),
            "target_path": normalized_target_path,
            "draft_payload": normalized_payload,
        }

    @staticmethod
    def _markdown_to_html(markdown: str) -> str:
        lines = str(markdown or "").splitlines()
        output: list[str] = []
        list_items: list[str] = []

        def flush_list() -> None:
            nonlocal list_items
            if list_items:
                output.append("<ul>" + "".join(list_items) + "</ul>")
                list_items = []

        for raw_line in lines:
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped:
                flush_list()
                continue
            if stripped.startswith(("- ", "* ")):
                list_items.append(f"<li>{html.escape(stripped[2:].strip())}</li>")
                continue
            flush_list()
            heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            if heading_match:
                level = len(heading_match.group(1))
                output.append(
                    f"<h{level}>{html.escape(heading_match.group(2).strip())}</h{level}>"
                )
                continue
            output.append(f"<p>{html.escape(stripped)}</p>")

        flush_list()
        return sanitize_html_content("\n".join(output), max_length=50000)

    @staticmethod
    def _upsert_action(
        db: Session,
        *,
        connection: OdooConnection,
        audit: Audit,
        action_key: str,
        draft_type: str,
        status: str,
        title: str,
        target_model: Optional[str],
        target_record_id: Optional[str],
        target_path: Optional[str],
        draft_payload: Dict[str, Any],
        evidence: Dict[str, Any],
        acceptance_criteria: str,
        snapshot: Optional[OdooRecordSnapshot] = None,
        sync_run: Optional[OdooSyncRun] = None,
        external_record_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> OdooDraftAction:
        normalized_fields = OdooDraftService._normalize_action_fields(
            action_key=action_key,
            title=title,
            target_model=target_model,
            target_record_id=target_record_id,
            target_path=target_path,
            draft_payload=draft_payload,
        )
        action_key = normalized_fields["action_key"]
        action = (
            db.query(OdooDraftAction)
            .filter(
                OdooDraftAction.connection_id == connection.id,
                OdooDraftAction.audit_id == audit.id,
                OdooDraftAction.action_key == action_key,
            )
            .first()
        )
        if not action:
            action = OdooDraftAction(
                connection_id=connection.id,
                audit_id=audit.id,
                action_key=action_key,
            )
            db.add(action)

        action.snapshot_id = snapshot.id if snapshot else None
        action.sync_run_id = sync_run.id if sync_run else None
        action.draft_type = draft_type
        action.status = status
        action.title = normalized_fields["title"]
        action.target_model = normalized_fields["target_model"]
        action.target_record_id = normalized_fields["target_record_id"]
        action.target_path = normalized_fields["target_path"]
        action.draft_payload = normalized_fields["draft_payload"]
        action.evidence = evidence
        action.acceptance_criteria = acceptance_criteria
        action.external_record_id = external_record_id
        action.error_message = error_message
        return action

    @staticmethod
    def _latest_sync_run(
        db: Session, *, audit_id: int, connection_id: str
    ) -> Optional[OdooSyncRun]:
        return (
            db.query(OdooSyncRun)
            .filter(
                OdooSyncRun.audit_id == audit_id,
                OdooSyncRun.connection_id == connection_id,
            )
            .order_by(OdooSyncRun.started_at.desc())
            .first()
        )

    @staticmethod
    def _snapshots_for_audit(
        db: Session,
        *,
        audit_id: int,
        connection_id: str,
    ) -> list[OdooRecordSnapshot]:
        return (
            db.query(OdooRecordSnapshot)
            .filter(
                OdooRecordSnapshot.audit_id == audit_id,
                OdooRecordSnapshot.connection_id == connection_id,
            )
            .order_by(OdooRecordSnapshot.last_synced_at.desc())
            .all()
        )

    def _select_snapshot(
        self,
        *,
        snapshots: list[OdooRecordSnapshot],
        page_path: Optional[str],
        prefer_ecommerce: bool = False,
    ) -> Optional[OdooRecordSnapshot]:
        normalized_path = str(page_path or "").strip() or "/"
        exact = [
            row for row in snapshots if (row.record_path or "/") == normalized_path
        ]
        if exact:
            return exact[0]
        if prefer_ecommerce:
            for row in snapshots:
                if row.odoo_model in {"product.template", "product.public.category"}:
                    return row
        for row in snapshots:
            if (row.record_path or "/") == "/":
                return row
        return snapshots[0] if snapshots else None

    @staticmethod
    def _preferred_field(
        writable_fields: list[str],
        *candidates: str,
    ) -> Optional[str]:
        for candidate in candidates:
            if candidate in writable_fields:
                return candidate
        return None

    def _prepare_fix_action(
        self,
        *,
        audit: Audit,
        connection: OdooConnection,
        sync_run: Optional[OdooSyncRun],
        snapshots: list[OdooRecordSnapshot],
        fix_item: Dict[str, Any],
    ) -> None:
        issue_code = str(fix_item.get("issue_code") or "").upper().strip()
        page_path = OdooDeliveryService._extract_page_path(fix_item) or "/"
        issue_text = OdooDeliveryService._extract_issue_text(fix_item)
        action_key = f"fix:{issue_code}:{page_path}"
        prefer_ecommerce = any(
            token in issue_code for token in ("PRODUCT", "OFFER", "PRICE", "CATEGORY")
        )
        snapshot = self._select_snapshot(
            snapshots=snapshots,
            page_path=page_path,
            prefer_ecommerce=prefer_ecommerce,
        )
        if not snapshot or snapshot.odoo_model in self.SAFE_TEMPLATE_BLOCKED_MODELS:
            self._upsert_action(
                self.db,
                connection=connection,
                audit=audit,
                action_key=action_key,
                draft_type="manual_review",
                status="manual_review",
                title=issue_text or issue_code,
                target_model=snapshot.odoo_model if snapshot else None,
                target_record_id=snapshot.odoo_record_id if snapshot else None,
                target_path=page_path,
                draft_payload={
                    "issue_code": issue_code,
                    "reason": "No safe record mapping is available for this fix in Odoo v1.",
                },
                evidence={
                    "issue": issue_text,
                    "page_path": page_path,
                    "recommended_value": fix_item.get("recommended_value"),
                },
                acceptance_criteria="Review and implement manually inside Odoo without touching live templates or layout views.",
                snapshot=snapshot,
                sync_run=sync_run,
            )
            return

        writable_fields = (snapshot.write_capabilities or {}).get(
            "writable_fields"
        ) or []
        payload: Dict[str, Any] = {"issue_code": issue_code, "proposed_changes": {}}
        draft_type = "draft"
        status = "draft"
        acceptance = (
            "Review the proposed draft action before applying any live Odoo change."
        )

        if "TITLE" in issue_code:
            target_field = self._preferred_field(
                writable_fields,
                "website_meta_title",
                "meta_title",
                "name",
            )
            value = OdooDeliveryService._value_summary(
                fix_item.get("recommended_value") or issue_text
            )
            if target_field and value:
                payload["proposed_changes"][target_field] = value[:255]
            else:
                status = "manual_review"
                draft_type = "manual_review"
        elif any(token in issue_code for token in ("DESCRIPTION", "META")):
            target_field = self._preferred_field(
                writable_fields,
                "website_meta_description",
                "meta_description",
                "subtitle",
            )
            value = OdooDeliveryService._value_summary(
                fix_item.get("recommended_value")
                or fix_item.get("suggestion")
                or issue_text
            )
            if target_field and value:
                payload["proposed_changes"][target_field] = value[:320]
            else:
                status = "manual_review"
                draft_type = "manual_review"
        elif any(
            token in issue_code for token in ("CONTENT", "READABILITY", "INTERNAL_LINK")
        ):
            target_field = self._preferred_field(
                writable_fields,
                "description_ecommerce",
                "description_sale",
                "website_description",
                "subtitle",
            )
            value = OdooDeliveryService._normalize_text(
                fix_item.get("suggestion") or fix_item.get("impact") or issue_text
            )
            if target_field and value:
                payload["proposed_changes"][target_field] = value
            else:
                status = "manual_review"
                draft_type = "manual_review"
        else:
            status = "manual_review"
            draft_type = "manual_review"

        self._upsert_action(
            self.db,
            connection=connection,
            audit=audit,
            action_key=action_key,
            draft_type=draft_type,
            status=status,
            title=issue_text or issue_code,
            target_model=snapshot.odoo_model,
            target_record_id=snapshot.odoo_record_id,
            target_path=snapshot.record_path or page_path,
            draft_payload=payload,
            evidence={
                "issue": issue_text,
                "priority": fix_item.get("priority"),
                "recommended_value": fix_item.get("recommended_value"),
            },
            acceptance_criteria=acceptance,
            snapshot=snapshot,
            sync_run=sync_run,
        )

    @staticmethod
    def _article_body_from_batch(
        batch: Optional[GeoArticleBatch], slug: str, title: str
    ) -> Optional[Dict[str, Any]]:
        if not batch or not isinstance(batch.articles, list):
            return None
        for article in batch.articles:
            if not isinstance(article, dict):
                continue
            if article.get("slug") == slug or article.get("title") == title:
                return article
        return None

    async def _prepare_article_drafts(
        self,
        *,
        audit: Audit,
        connection: OdooConnection,
        sync_run: Optional[OdooSyncRun],
        plan: Dict[str, Any],
    ) -> None:
        article_deliverables = list(plan.get("article_deliverables") or [])
        if not article_deliverables:
            return

        latest_batch = GeoArticleEngineService.get_latest_batch(self.db, audit.id)
        async with await self.connection_service.build_client(connection) as client:
            try:
                blog_post_fields = await client.fields_get(
                    "blog.post",
                    attributes=("type", "readonly", "required"),
                )
            except OdooAPIError:
                blog_post_fields = {}

            try:
                blogs = await client.search_read(
                    "blog.blog",
                    fields=["id", "name"],
                    limit=1,
                    order="id asc",
                )
            except OdooAPIError:
                blogs = []

            writable_fields = OdooConnectionService._writable_fields(blog_post_fields)
            supports_native_articles = bool(blog_post_fields) and bool(blogs)
            blog_id = blogs[0].get("id") if blogs else None

            for deliverable in article_deliverables:
                title = str(deliverable.get("title") or "Odoo article draft").strip()
                slug = str(deliverable.get("slug") or self._slugify(title)).strip()
                action_key = f"article:{slug}"
                existing = (
                    self.db.query(OdooDraftAction)
                    .filter(
                        OdooDraftAction.connection_id == connection.id,
                        OdooDraftAction.audit_id == audit.id,
                        OdooDraftAction.action_key == action_key,
                        OdooDraftAction.status == "native_created",
                    )
                    .first()
                )
                if existing and existing.external_record_id:
                    continue

                raw_article = self._article_body_from_batch(latest_batch, slug, title)
                if supports_native_articles and blog_id and raw_article:
                    values: Dict[str, Any] = {}
                    if "name" in writable_fields:
                        values["name"] = title
                    if "blog_id" in blog_post_fields:
                        values["blog_id"] = int(blog_id)
                    if "subtitle" in writable_fields and raw_article.get(
                        "meta_description"
                    ):
                        values["subtitle"] = str(raw_article.get("meta_description"))[
                            :255
                        ]
                    if "website_published" in writable_fields:
                        values["website_published"] = False
                    if "is_published" in writable_fields:
                        values["is_published"] = False
                    body_html = self._markdown_to_html(
                        str(raw_article.get("markdown") or "")
                    )
                    for candidate in ("content", "content_html"):
                        if candidate in writable_fields and body_html:
                            values[candidate] = body_html
                            break
                    for meta_field in ("website_meta_title", "meta_title"):
                        if meta_field in writable_fields:
                            values[meta_field] = title[:255]
                            break
                    for meta_field in ("website_meta_description", "meta_description"):
                        if meta_field in writable_fields and raw_article.get(
                            "meta_description"
                        ):
                            values[meta_field] = str(
                                raw_article.get("meta_description")
                            )[:320]
                            break

                    try:
                        created_id = await client.create("blog.post", vals=values)
                    except OdooAPIError as exc:
                        self._upsert_action(
                            self.db,
                            connection=connection,
                            audit=audit,
                            action_key=action_key,
                            draft_type="article",
                            status="failed",
                            title=title,
                            target_model="blog.post",
                            target_record_id=None,
                            target_path=deliverable.get("focus_url"),
                            draft_payload={"vals": values},
                            evidence={"source": deliverable.get("source")},
                            acceptance_criteria="Fix blog permissions or missing fields before retrying native draft creation.",
                            sync_run=sync_run,
                            error_message=str(exc),
                        )
                        continue

                    self._upsert_action(
                        self.db,
                        connection=connection,
                        audit=audit,
                        action_key=action_key,
                        draft_type="article",
                        status="native_created",
                        title=title,
                        target_model="blog.post",
                        target_record_id=str(created_id),
                        target_path=deliverable.get("focus_url"),
                        draft_payload={"vals": values},
                        evidence={"source": deliverable.get("source")},
                        acceptance_criteria="Review the unpublished blog.post draft in Odoo before publishing.",
                        sync_run=sync_run,
                        external_record_id=str(created_id),
                    )
                    continue

                self._upsert_action(
                    self.db,
                    connection=connection,
                    audit=audit,
                    action_key=action_key,
                    draft_type="article",
                    status="draft",
                    title=title,
                    target_model="blog.post",
                    target_record_id=None,
                    target_path=deliverable.get("focus_url"),
                    draft_payload={
                        "title": title,
                        "slug": slug,
                        "delivery_brief": deliverable.get("delivery_brief"),
                        "target_keyword": deliverable.get("target_keyword"),
                    },
                    evidence={"source": deliverable.get("source")},
                    acceptance_criteria="Create or review the article draft manually inside Odoo blog.",
                    sync_run=sync_run,
                )

    def _prepare_ecommerce_drafts(
        self,
        *,
        audit: Audit,
        connection: OdooConnection,
        sync_run: Optional[OdooSyncRun],
        plan: Dict[str, Any],
        snapshots: list[OdooRecordSnapshot],
    ) -> None:
        for index, item in enumerate(plan.get("ecommerce_fixes") or []):
            title = str(
                item.get("area") or item.get("what_to_change") or "Ecommerce draft"
            )
            snapshot = self._select_snapshot(
                snapshots=snapshots,
                page_path=item.get("page_path") or "/",
                prefer_ecommerce=True,
            )
            action_key = f"ecommerce:{index}:{self._slugify(title)}"
            self._upsert_action(
                self.db,
                connection=connection,
                audit=audit,
                action_key=action_key,
                draft_type="ecommerce",
                status="draft" if snapshot else "manual_review",
                title=title,
                target_model=snapshot.odoo_model if snapshot else "product.template",
                target_record_id=snapshot.odoo_record_id if snapshot else None,
                target_path=snapshot.record_path if snapshot else None,
                draft_payload={
                    "recommended_odoo_surface": item.get("recommended_odoo_surface"),
                    "what_to_change": item.get("what_to_change"),
                    "why_it_matters": item.get("why_it_matters"),
                },
                evidence={"priority": item.get("priority"), "area": item.get("area")},
                acceptance_criteria=item.get("qa_check")
                or "Review the product/category draft action before any live Odoo rollout.",
                snapshot=snapshot,
                sync_run=sync_run,
            )

    async def prepare_drafts(
        self, *, audit: Audit, connection: OdooConnection
    ) -> Dict[str, Any]:
        plan = await OdooDeliveryService.build_plan(self.db, audit)
        sync_run = self._latest_sync_run(
            self.db,
            audit_id=audit.id,
            connection_id=connection.id,
        )
        snapshots = self._snapshots_for_audit(
            self.db,
            audit_id=audit.id,
            connection_id=connection.id,
        )

        for fix_item in list(audit.fix_plan or []):
            if not isinstance(fix_item, dict):
                continue
            if OdooDeliveryService._is_performance_fix(fix_item):
                continue
            self._prepare_fix_action(
                audit=audit,
                connection=connection,
                sync_run=sync_run,
                snapshots=snapshots,
                fix_item=fix_item,
            )

        await self._prepare_article_drafts(
            audit=audit,
            connection=connection,
            sync_run=sync_run,
            plan=plan,
        )
        self._prepare_ecommerce_drafts(
            audit=audit,
            connection=connection,
            sync_run=sync_run,
            plan=plan,
            snapshots=snapshots,
        )

        self.db.commit()
        return self.grouped_drafts(audit_id=audit.id, connection_id=connection.id)

    def grouped_drafts(self, *, audit_id: int, connection_id: str) -> Dict[str, Any]:
        actions = (
            self.db.query(OdooDraftAction)
            .options(
                load_only(
                    OdooDraftAction.id,
                    OdooDraftAction.action_key,
                    OdooDraftAction.draft_type,
                    OdooDraftAction.status,
                    OdooDraftAction.title,
                    OdooDraftAction.target_model,
                    OdooDraftAction.target_record_id,
                    OdooDraftAction.target_path,
                    OdooDraftAction.external_record_id,
                    OdooDraftAction.draft_payload,
                    OdooDraftAction.evidence,
                    OdooDraftAction.acceptance_criteria,
                    OdooDraftAction.error_message,
                    OdooDraftAction.updated_at,
                )
            )
            .filter(
                OdooDraftAction.audit_id == audit_id,
                OdooDraftAction.connection_id == connection_id,
            )
            .order_by(OdooDraftAction.updated_at.desc())
            .all()
        )
        grouped = {
            "native_created": [],
            "draft": [],
            "manual_review": [],
            "failed": [],
        }
        for action in actions:
            row = {
                "id": action.id,
                "action_key": action.action_key,
                "draft_type": action.draft_type,
                "status": action.status,
                "title": action.title,
                "target_model": action.target_model,
                "target_record_id": action.target_record_id,
                "target_path": action.target_path,
                "external_record_id": action.external_record_id,
                "draft_payload": action.draft_payload,
                "evidence": action.evidence,
                "acceptance_criteria": action.acceptance_criteria,
                "error_message": action.error_message,
                "updated_at": (
                    action.updated_at.isoformat() if action.updated_at else None
                ),
            }
            bucket = (
                grouped[action.status] if action.status in grouped else grouped["draft"]
            )
            bucket.append(row)

        grouped["summary"] = {
            "native_draft_count": len(grouped["native_created"]),
            "draft_count": len(grouped["draft"]),
            "manual_review_count": len(grouped["manual_review"]),
            "failed_count": len(grouped["failed"]),
            "last_prepared_at": datetime.now(timezone.utc).isoformat(),
        }
        return grouped
