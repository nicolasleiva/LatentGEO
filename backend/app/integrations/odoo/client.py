from __future__ import annotations

from typing import Any, Dict, Iterable, Optional
from urllib.parse import urljoin

import httpx


class OdooAPIError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 500,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


class OdooJSON2Client:
    def __init__(
        self,
        *,
        base_url: str,
        database: str,
        api_key: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = str(base_url or "").rstrip("/")
        self.database = str(database or "").strip()
        self.api_key = str(api_key or "").strip()
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={
                "Authorization": f"bearer {self.api_key}",
                "X-Odoo-Database": self.database,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "OdooJSON2Client":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    @staticmethod
    def _coerce_json(response: httpx.Response) -> Any:
        if not response.text:
            return None
        try:
            return response.json()
        except Exception:
            return {"raw": response.text}

    @staticmethod
    def _error_message(payload: Any, fallback: str) -> str:
        if isinstance(payload, dict):
            for key in ("message", "detail", "error", "name"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return fallback

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        response = await self._client.request(method, path, **kwargs)
        payload = self._coerce_json(response)
        if response.status_code >= 400:
            raise OdooAPIError(
                self._error_message(
                    payload,
                    f"Odoo request failed with status {response.status_code}",
                ),
                status_code=response.status_code,
                payload=payload if isinstance(payload, dict) else {"raw": payload},
            )
        return payload

    async def get_version_info(self) -> Dict[str, Any]:
        for path in ("/web/webclient/version_info", "/web/version"):
            try:
                payload = await self._request("GET", path)
            except OdooAPIError:
                continue
            if isinstance(payload, dict):
                return payload
        return {}

    async def call(
        self, model: str, method: str, payload: Optional[Dict[str, Any]] = None
    ) -> Any:
        safe_model = str(model or "").strip()
        safe_method = str(method or "").strip()
        if not safe_model or not safe_method:
            raise OdooAPIError("Invalid Odoo model or method", status_code=400)
        return await self._request(
            "POST",
            f"/json/2/{safe_model}/{safe_method}",
            json=payload or {},
        )

    async def fields_get(
        self,
        model: str,
        *,
        attributes: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if attributes:
            payload["attributes"] = list(attributes)
        result = await self.call(model, "fields_get", payload)
        return result if isinstance(result, dict) else {}

    async def search_read(
        self,
        model: str,
        *,
        domain: Optional[list] = None,
        fields: Optional[Iterable[str]] = None,
        limit: Optional[int] = None,
        order: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        payload: Dict[str, Any] = {"domain": domain or []}
        if fields:
            payload["fields"] = list(fields)
        if limit is not None:
            payload["limit"] = int(limit)
        if order:
            payload["order"] = order
        if context:
            payload["context"] = context
        result = await self.call(model, "search_read", payload)
        return result if isinstance(result, list) else []

    async def search_count(self, model: str, *, domain: Optional[list] = None) -> int:
        result = await self.call(model, "search_count", {"domain": domain or []})
        try:
            return int(result)
        except Exception:
            return 0

    async def create(self, model: str, *, vals: Dict[str, Any]) -> Any:
        return await self.call(model, "create", {"vals": vals})

    async def write(
        self, model: str, *, ids: list[int] | list[str], vals: Dict[str, Any]
    ) -> Any:
        return await self.call(model, "write", {"ids": ids, "vals": vals})

    def absolute_url(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        raw = str(value).strip()
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw
        return urljoin(f"{self.base_url}/", raw.lstrip("/"))
