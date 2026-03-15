from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from sqlalchemy.orm import Session, load_only

from ...core.config import settings
from ...core.security import is_safe_outbound_url, validate_api_key, validate_email
from ...models.odoo import OdooConnection
from .auth import OdooAuth
from .client import OdooAPIError, OdooJSON2Client

_DEV_LIKE_ENVIRONMENTS = {"development", "dev", "local", "testing"}
_LOCAL_ODOO_PORTS = {80, 443, 8069}
_PUBLIC_ODOO_PORTS = {80, 443, 8069, 8443}


def _normalize_email(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def _normalize_base_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Odoo URL is required")

    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    scheme = (parsed.scheme or "https").lower()
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise ValueError("Invalid Odoo URL")

    is_local = hostname in {"localhost", "127.0.0.1"}
    if is_local:
        environment = str(getattr(settings, "ENVIRONMENT", "") or "").lower()
        if environment not in _DEV_LIKE_ENVIRONMENTS:
            raise ValueError(
                "Local Odoo URLs are only allowed in development-like environments"
            )
        if scheme not in {"http", "https"}:
            raise ValueError("Local Odoo URLs must use http or https")
        if parsed.port and parsed.port not in _LOCAL_ODOO_PORTS:
            raise ValueError("Unsupported local Odoo port")
    elif scheme != "https":
        raise ValueError("Odoo URL must use HTTPS outside localhost")

    if parsed.username or parsed.password:
        raise ValueError("Odoo URL must not include embedded credentials")

    netloc = hostname
    if parsed.port:
        netloc = f"{hostname}:{parsed.port}"

    normalized_url = parsed._replace(
        scheme=scheme,
        netloc=netloc,
        params="",
        query="",
        fragment="",
        path="",
    ).geturl()
    if not is_local and not is_safe_outbound_url(
        normalized_url,
        allowed_ports=_PUBLIC_ODOO_PORTS,
        allow_http=False,
    ):
        raise ValueError("Odoo URL is not allowed")
    return normalized_url


class OdooConnectionService:
    MODEL_CAPABILITY_MAP = {
        "website.website": {
            "label": "website",
            "sample_fields": ["id", "name", "domain"],
        },
        "website.page": {
            "label": "website_page",
            "sample_fields": ["id", "name", "url", "website_published", "write_date"],
        },
        "blog.blog": {
            "label": "website_blog_container",
            "sample_fields": ["id", "name", "website_id"],
        },
        "blog.post": {
            "label": "website_blog",
            "sample_fields": [
                "id",
                "name",
                "subtitle",
                "website_url",
                "website_published",
                "write_date",
            ],
        },
        "product.template": {
            "label": "product_template",
            "sample_fields": [
                "id",
                "name",
                "website_url",
                "is_published",
                "website_published",
                "write_date",
            ],
        },
        "product.public.category": {
            "label": "product_public_category",
            "sample_fields": [
                "id",
                "name",
                "website_url",
                "website_published",
                "write_date",
            ],
        },
        "social.media": {
            "label": "social_media",
            "sample_fields": ["id", "name", "media_type"],
        },
        "social.post": {
            "label": "social_post",
            "sample_fields": ["id", "message", "state"],
        },
    }

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _ensure_owned(
        connection: Optional[OdooConnection],
        *,
        owner_user_id: str,
        owner_email: Optional[str],
    ) -> OdooConnection:
        if not connection:
            raise ValueError("Odoo connection not found")
        if connection.owner_user_id and connection.owner_user_id == owner_user_id:
            return connection
        normalized_email = _normalize_email(owner_email)
        if (
            normalized_email
            and connection.owner_email
            and _normalize_email(connection.owner_email) == normalized_email
        ):
            return connection
        raise PermissionError("Odoo connection already belongs to another user")

    @staticmethod
    def _build_label(
        *,
        base_url: str,
        database: str,
        detected_user: Optional[Dict[str, Any]],
    ) -> str:
        parsed = urlparse(base_url)
        host = parsed.netloc or parsed.hostname or base_url
        user_hint = ""
        if isinstance(detected_user, dict):
            for key in ("name", "login", "email"):
                value = detected_user.get(key)
                if isinstance(value, str) and value.strip():
                    user_hint = value.strip()
                    break
        if user_hint:
            return f"{host} / {database} / {user_hint}"
        return f"{host} / {database}"

    @staticmethod
    def _writable_fields(fields_meta: Dict[str, Any]) -> list[str]:
        writable: list[str] = []
        for field_name, field_meta in (fields_meta or {}).items():
            if not isinstance(field_meta, dict):
                continue
            if field_meta.get("readonly"):
                continue
            writable.append(field_name)
        return sorted(writable)

    async def _detect_model_capability(
        self,
        client: OdooJSON2Client,
        *,
        model: str,
        sample_fields: list[str],
    ) -> Dict[str, Any]:
        try:
            fields_meta = await client.fields_get(
                model,
                attributes=("string", "type", "readonly", "required"),
            )
        except OdooAPIError as exc:
            return {
                "available": False,
                "error": str(exc),
                "status_code": exc.status_code,
            }

        available_fields = set(fields_meta.keys())
        readable_fields = [
            field for field in sample_fields if field in available_fields
        ]

        count = None
        if readable_fields:
            try:
                records = await client.search_read(
                    model,
                    fields=readable_fields,
                    limit=1,
                    order="id desc",
                )
                count = len(records)
            except OdooAPIError:
                count = None

        return {
            "available": True,
            "fields": sorted(list(available_fields)),
            "writable_fields": self._writable_fields(fields_meta),
            "sample_fields": readable_fields,
            "has_records_hint": bool(count),
        }

    async def _detect_user(
        self,
        client: OdooJSON2Client,
        *,
        expected_email: str,
    ) -> tuple[Optional[Dict[str, Any]], list[str]]:
        warnings: list[str] = []
        normalized_email = _normalize_email(expected_email) or ""

        try:
            user_fields = await client.fields_get(
                "res.users",
                attributes=("string", "type", "readonly"),
            )
        except OdooAPIError:
            warnings.append("Unable to inspect res.users for email validation.")
            return None, warnings

        preferred_fields = [
            field for field in ("id", "name", "login", "email") if field in user_fields
        ]
        if not preferred_fields:
            warnings.append(
                "User validation fields are not available in this Odoo instance."
            )
            return None, warnings

        for candidate_field in ("login", "email"):
            if candidate_field not in preferred_fields:
                continue
            try:
                users = await client.search_read(
                    "res.users",
                    domain=[[candidate_field, "=", normalized_email]],
                    fields=preferred_fields,
                    limit=1,
                )
            except OdooAPIError:
                continue
            if users:
                user = users[0]
                detected_email = _normalize_email(
                    user.get("email") or user.get("login")
                )
                if detected_email and detected_email != normalized_email:
                    warnings.append(
                        "API key is valid, but the detected Odoo user does not match the provided email."
                    )
                return {
                    "id": user.get("id"),
                    "name": user.get("name"),
                    "login": user.get("login"),
                    "email": user.get("email") or user.get("login"),
                }, warnings

        warnings.append(
            "API key is valid, but the provided email could not be verified against res.users."
        )
        return None, warnings

    async def inspect_connection(
        self,
        *,
        base_url: str,
        database: str,
        email: str,
        api_key: str,
    ) -> Dict[str, Any]:
        normalized_base_url = _normalize_base_url(base_url)
        normalized_email = _normalize_email(email)
        normalized_database = str(database or "").strip()

        if not normalized_database:
            raise ValueError("Odoo database is required")
        if not normalized_email or not validate_email(normalized_email):
            raise ValueError("Invalid Odoo email")
        if not validate_api_key(api_key):
            raise ValueError("Invalid Odoo API key")

        warnings: list[str] = []
        async with OdooJSON2Client(
            base_url=normalized_base_url,
            database=normalized_database,
            api_key=api_key,
            timeout_seconds=float(
                getattr(settings, "EXTERNAL_HTTP_TIMEOUT_SECONDS", 30.0) or 30.0
            ),
        ) as client:
            version_info = await client.get_version_info()
            detected_user, user_warnings = await self._detect_user(
                client,
                expected_email=normalized_email,
            )
            warnings.extend(user_warnings)

            capabilities: Dict[str, Any] = {"models": {}}
            for model_name, config in self.MODEL_CAPABILITY_MAP.items():
                capabilities["models"][model_name] = (
                    await self._detect_model_capability(
                        client,
                        model=model_name,
                        sample_fields=list(config["sample_fields"]),
                    )
                )

            model_state = capabilities["models"]
            capabilities["website"] = bool(
                model_state.get("website.page", {}).get("available")
                or model_state.get("website.website", {}).get("available")
            )
            capabilities["website_blog"] = bool(
                model_state.get("blog.post", {}).get("available")
            )
            capabilities["website_sale"] = bool(
                model_state.get("product.template", {}).get("available")
                or model_state.get("product.public.category", {}).get("available")
            )
            capabilities["social_marketing"] = bool(
                model_state.get("social.media", {}).get("available")
            )

            if not capabilities["website"]:
                warnings.append("Website models are not available or not accessible.")
            if not capabilities["website_blog"]:
                warnings.append(
                    "website_blog is not available; native article drafts will be skipped."
                )
            if not capabilities["website_sale"]:
                warnings.append(
                    "website_sale models are not available; ecommerce sync will be limited."
                )

        version_label = ""
        if isinstance(version_info, dict):
            version_label = (
                str(version_info.get("server_version") or "").strip()
                or str(version_info.get("server_version_info") or "").strip()
            )

        return {
            "ok": True,
            "normalized_base_url": normalized_base_url,
            "database": normalized_database,
            "detected_user": detected_user,
            "version": version_label or None,
            "capabilities": capabilities,
            "warnings": warnings,
        }

    async def create_or_update_connection(
        self,
        *,
        owner_user_id: str,
        owner_email: Optional[str],
        base_url: str,
        database: str,
        email: str,
        api_key: str,
        connection_id: Optional[str] = None,
    ) -> OdooConnection:
        inspection = await self.inspect_connection(
            base_url=base_url,
            database=database,
            email=email,
            api_key=api_key,
        )
        owner_email_normalized = _normalize_email(owner_email)
        expected_email = _normalize_email(email) or ""
        encrypted_api_key = OdooAuth.encrypt_api_key(api_key)

        connection: Optional[OdooConnection] = None
        if connection_id:
            candidate = (
                self.db.query(OdooConnection)
                .filter(
                    OdooConnection.id == connection_id,
                    OdooConnection.is_active.is_(True),
                )
                .first()
            )
            connection = self._ensure_owned(
                candidate,
                owner_user_id=owner_user_id,
                owner_email=owner_email_normalized,
            )
        else:
            connection = (
                self.db.query(OdooConnection)
                .filter(
                    OdooConnection.owner_user_id == owner_user_id,
                    OdooConnection.base_url == inspection["normalized_base_url"],
                    OdooConnection.database == database,
                    OdooConnection.expected_email == expected_email,
                    OdooConnection.is_active.is_(True),
                )
                .first()
            )

        if connection:
            connection.base_url = inspection["normalized_base_url"]
            connection.database = database
            connection.expected_email = expected_email
            connection.api_key = encrypted_api_key
            connection.odoo_version = inspection["version"]
            connection.capabilities = inspection["capabilities"]
            connection.warnings = inspection["warnings"]
            connection.detected_user = inspection["detected_user"]
            connection.label = self._build_label(
                base_url=inspection["normalized_base_url"],
                database=database,
                detected_user=inspection["detected_user"],
            )
            connection.owner_user_id = connection.owner_user_id or owner_user_id
            connection.owner_email = connection.owner_email or owner_email_normalized
            connection.last_validated_at = datetime.now(timezone.utc)
            connection.is_active = True
        else:
            connection = OdooConnection(
                owner_user_id=owner_user_id,
                owner_email=owner_email_normalized,
                base_url=inspection["normalized_base_url"],
                database=database,
                expected_email=expected_email,
                label=self._build_label(
                    base_url=inspection["normalized_base_url"],
                    database=database,
                    detected_user=inspection["detected_user"],
                ),
                api_key=encrypted_api_key,
                odoo_version=inspection["version"],
                capabilities=inspection["capabilities"],
                warnings=inspection["warnings"],
                detected_user=inspection["detected_user"],
                last_validated_at=datetime.now(timezone.utc),
            )
            self.db.add(connection)

        self.db.commit()
        self.db.refresh(connection)
        return connection

    def get_connection(self, connection_id: str) -> Optional[OdooConnection]:
        return (
            self.db.query(OdooConnection)
            .filter(
                OdooConnection.id == connection_id,
                OdooConnection.is_active.is_(True),
            )
            .first()
        )

    def list_connections(
        self, *, owner_user_id: str, owner_email: Optional[str]
    ) -> list[OdooConnection]:
        owner_email_normalized = _normalize_email(owner_email)
        query = (
            self.db.query(OdooConnection)
            .options(
                load_only(
                    OdooConnection.id,
                    OdooConnection.label,
                    OdooConnection.base_url,
                    OdooConnection.database,
                    OdooConnection.expected_email,
                    OdooConnection.odoo_version,
                    OdooConnection.capabilities,
                    OdooConnection.warnings,
                    OdooConnection.detected_user,
                    OdooConnection.last_validated_at,
                    OdooConnection.is_active,
                    OdooConnection.updated_at,
                )
            )
            .filter(OdooConnection.is_active.is_(True))
        )
        if owner_user_id:
            query = query.filter(
                (OdooConnection.owner_user_id == owner_user_id)
                | (OdooConnection.owner_email == owner_email_normalized)
            )
        elif owner_email_normalized:
            query = query.filter(OdooConnection.owner_email == owner_email_normalized)
        else:
            return []
        return query.order_by(OdooConnection.updated_at.desc()).all()

    async def build_client(self, connection: OdooConnection) -> OdooJSON2Client:
        api_key = OdooAuth.decrypt_api_key(connection.api_key)
        if not api_key:
            raise OdooAPIError(
                "Stored Odoo API key is invalid or corrupted.",
                status_code=400,
            )
        return OdooJSON2Client(
            base_url=connection.base_url,
            database=connection.database,
            api_key=api_key,
            timeout_seconds=float(
                getattr(settings, "EXTERNAL_HTTP_TIMEOUT_SECONDS", 30.0) or 30.0
            ),
        )
