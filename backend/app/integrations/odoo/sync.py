from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from ...models import Audit
from ...models.odoo import OdooConnection, OdooRecordSnapshot, OdooSyncRun
from .client import OdooAPIError
from .service import OdooConnectionService


class OdooSyncService:
    MODEL_CONFIG = {
        "website.page": {
            "fields": [
                "id",
                "name",
                "url",
                "website_published",
                "write_date",
                "website_meta_title",
                "website_meta_description",
                "seo_name",
            ],
            "path_fields": ("url",),
            "name_fields": ("name", "seo_name"),
            "published_fields": ("website_published",),
        },
        "blog.post": {
            "fields": [
                "id",
                "name",
                "subtitle",
                "website_url",
                "website_published",
                "write_date",
                "website_meta_title",
                "website_meta_description",
                "blog_id",
            ],
            "path_fields": ("website_url",),
            "name_fields": ("name", "subtitle"),
            "published_fields": ("website_published",),
        },
        "product.template": {
            "fields": [
                "id",
                "name",
                "website_url",
                "website_published",
                "is_published",
                "write_date",
                "website_meta_title",
                "website_meta_description",
                "description_sale",
                "description_ecommerce",
            ],
            "path_fields": ("website_url",),
            "name_fields": ("name",),
            "published_fields": ("is_published", "website_published"),
        },
        "product.public.category": {
            "fields": [
                "id",
                "name",
                "website_url",
                "website_published",
                "write_date",
                "website_meta_title",
                "website_meta_description",
                "website_description",
            ],
            "path_fields": ("website_url",),
            "name_fields": ("name",),
            "published_fields": ("website_published",),
        },
        "website.website": {
            "fields": ["id", "name", "domain"],
            "path_fields": tuple(),
            "name_fields": ("name", "domain"),
            "published_fields": tuple(),
        },
    }

    def __init__(self, db: Session):
        self.db = db
        self.connection_service = OdooConnectionService(db)

    @staticmethod
    def _normalize_path(value: Optional[str]) -> Optional[str]:
        raw = str(value or "").strip()
        if not raw:
            return None
        parsed = urlparse(raw if "://" in raw else f"https://placeholder{raw}")
        path = parsed.path or "/"
        return path if path.startswith("/") else f"/{path}"

    @staticmethod
    def _pick_first(record: Dict[str, Any], fields: Iterable[str]) -> Optional[Any]:
        for field in fields:
            value = record.get(field)
            if value not in (None, "", []):
                return value
        return None

    def _upsert_snapshot(
        self,
        *,
        connection: OdooConnection,
        audit: Audit,
        sync_run: OdooSyncRun,
        model_name: str,
        record: Dict[str, Any],
        fields_meta: Dict[str, Any],
        config: Dict[str, Any],
        base_url: str,
    ) -> OdooRecordSnapshot:
        odoo_record_id = str(record.get("id"))
        snapshot = (
            self.db.query(OdooRecordSnapshot)
            .filter(
                OdooRecordSnapshot.connection_id == connection.id,
                OdooRecordSnapshot.audit_id == audit.id,
                OdooRecordSnapshot.odoo_model == model_name,
                OdooRecordSnapshot.odoo_record_id == odoo_record_id,
            )
            .first()
        )
        if not snapshot:
            snapshot = OdooRecordSnapshot(
                connection_id=connection.id,
                audit_id=audit.id,
                odoo_model=model_name,
                odoo_record_id=odoo_record_id,
            )
            self.db.add(snapshot)

        path_value = self._pick_first(record, config.get("path_fields") or ())
        record_path = self._normalize_path(path_value)
        snapshot.sync_run_id = sync_run.id
        snapshot.record_path = record_path
        snapshot.record_url = (
            path_value
            if isinstance(path_value, str) and path_value.startswith("http")
            else f"{base_url.rstrip('/')}{record_path or ''}"
            if record_path
            else None
        )
        snapshot.record_name = str(
            self._pick_first(record, config.get("name_fields") or ()) or odoo_record_id
        )
        snapshot.is_published = bool(
            self._pick_first(record, config.get("published_fields") or ()) or False
        )
        snapshot.field_snapshot = record
        snapshot.write_capabilities = {
            "writable_fields": OdooConnectionService._writable_fields(fields_meta),
        }
        snapshot.capabilities = {
            "supports_metadata": any(
                field in fields_meta
                for field in (
                    "website_meta_title",
                    "website_meta_description",
                    "meta_title",
                    "meta_description",
                )
            ),
            "supports_content": any(
                field in fields_meta
                for field in (
                    "content",
                    "description_sale",
                    "description_ecommerce",
                    "website_description",
                    "subtitle",
                )
            ),
        }
        snapshot.external_updated_at = str(record.get("write_date") or "")
        snapshot.last_synced_at = datetime.now(timezone.utc)
        return snapshot

    async def sync_audit(
        self, *, audit: Audit, connection: OdooConnection
    ) -> Dict[str, Any]:
        sync_run = OdooSyncRun(
            connection_id=connection.id,
            audit_id=audit.id,
            status="running",
            started_at=datetime.now(timezone.utc),
            summary={},
            warnings=[],
        )
        self.db.add(sync_run)
        self.db.commit()
        self.db.refresh(sync_run)

        counts_by_model: Dict[str, int] = {}
        mapped_paths: set[str] = set()
        warnings: list[str] = []

        try:
            async with await self.connection_service.build_client(connection) as client:
                capabilities = connection.capabilities or {}
                model_capabilities = (
                    capabilities.get("models") if isinstance(capabilities, dict) else {}
                ) or {}

                for model_name, config in self.MODEL_CONFIG.items():
                    model_state = model_capabilities.get(model_name) or {}
                    if not model_state.get("available"):
                        continue

                    fields_meta = await client.fields_get(
                        model_name,
                        attributes=("type", "string", "readonly"),
                    )
                    query_fields = [
                        field for field in config["fields"] if field in fields_meta
                    ]
                    records = await client.search_read(
                        model_name,
                        fields=query_fields,
                        limit=250,
                        order="id desc",
                    )
                    counts_by_model[model_name] = len(records)
                    for record in records:
                        snapshot = self._upsert_snapshot(
                            connection=connection,
                            audit=audit,
                            sync_run=sync_run,
                            model_name=model_name,
                            record=record,
                            fields_meta=fields_meta,
                            config=config,
                            base_url=connection.base_url,
                        )
                        if snapshot.record_path:
                            mapped_paths.add(snapshot.record_path)

            audit_paths: set[str] = set()
            for page in list(audit.pages or []):
                normalized_path = self._normalize_path(
                    getattr(page, "path", None) or getattr(page, "url", None)
                )
                if normalized_path:
                    audit_paths.add(normalized_path)
            unmapped_paths = sorted(audit_paths - mapped_paths)
            mapped_audit_paths = sorted(audit_paths & mapped_paths)

            summary = {
                "status": "completed",
                "counts_by_model": counts_by_model,
                "mapped_audit_paths": mapped_audit_paths,
                "mapped_count": len(mapped_audit_paths),
                "unmapped_paths": unmapped_paths,
                "unmapped_count": len(unmapped_paths),
                "last_synced_at": datetime.now(timezone.utc).isoformat(),
            }
            sync_run.status = "completed"
            sync_run.summary = summary
            sync_run.warnings = warnings
            sync_run.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(sync_run)
            return summary
        except OdooAPIError as exc:
            sync_run.status = "failed"
            sync_run.error_message = str(exc)
            sync_run.summary = {"status": "failed", "counts_by_model": counts_by_model}
            sync_run.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            raise
