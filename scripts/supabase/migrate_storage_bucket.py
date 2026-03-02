#!/usr/bin/env python3
"""
Migrate objects between Supabase Storage buckets and verify size+SHA256.

Required environment variables:
  SOURCE_SUPABASE_URL
  SOURCE_SUPABASE_SERVICE_ROLE_KEY
  TARGET_SUPABASE_URL
  TARGET_SUPABASE_SERVICE_ROLE_KEY

Optional:
  SOURCE_BUCKET (default: audit-reports)
  TARGET_BUCKET (default: audit-reports)
  PREFIX (default: "")
"""

from __future__ import annotations

import hashlib
import os
import sys
from dataclasses import dataclass
from typing import Iterator

import requests


@dataclass(frozen=True)
class SupabaseStorageClient:
    base_url: str
    service_role_key: str
    bucket: str

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.service_role_key}",
            "apikey": self.service_role_key,
        }

    def _list_page(self, prefix: str, offset: int, limit: int = 1000) -> list[dict]:
        url = f"{self.base_url}/storage/v1/object/list/{self.bucket}"
        payload = {
            "prefix": prefix,
            "limit": limit,
            "offset": offset,
            "sortBy": {"column": "name", "order": "asc"},
        }
        response = requests.post(url, headers=self._headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            return []
        return data

    def iter_paths(self, prefix: str) -> Iterator[str]:
        offset = 0
        while True:
            items = self._list_page(prefix=prefix, offset=offset)
            if not items:
                return
            for item in items:
                name = item.get("name")
                if not name:
                    continue
                item_id = item.get("id")
                if item_id is None:
                    continue
                # list endpoint returns only current level names; combine with prefix.
                path = f"{prefix.rstrip('/')}/{name}".lstrip("/") if prefix else name
                if "." not in name and item.get("metadata") is None:
                    # probable folder marker; recurse
                    yield from self.iter_paths(path)
                else:
                    yield path
            offset += len(items)

    def download(self, path: str) -> bytes:
        url = f"{self.base_url}/storage/v1/object/{self.bucket}/{path}"
        response = requests.get(url, headers=self._headers, timeout=120)
        response.raise_for_status()
        return response.content

    def upload(self, path: str, content: bytes) -> None:
        url = f"{self.base_url}/storage/v1/object/{self.bucket}/{path}"
        headers = {
            **self._headers,
            "x-upsert": "true",
            "content-type": "application/octet-stream",
        }
        response = requests.post(url, headers=headers, data=content, timeout=120)
        response.raise_for_status()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value.rstrip("/")


def main() -> int:
    try:
        source = SupabaseStorageClient(
            base_url=required_env("SOURCE_SUPABASE_URL"),
            service_role_key=required_env("SOURCE_SUPABASE_SERVICE_ROLE_KEY"),
            bucket=os.getenv("SOURCE_BUCKET", "audit-reports"),
        )
        target = SupabaseStorageClient(
            base_url=required_env("TARGET_SUPABASE_URL"),
            service_role_key=required_env("TARGET_SUPABASE_SERVICE_ROLE_KEY"),
            bucket=os.getenv("TARGET_BUCKET", "audit-reports"),
        )
    except Exception as exc:
        print(f"[error] {exc}")
        return 1

    prefix = os.getenv("PREFIX", "").strip().lstrip("/")
    print(
        f"[info] Migrating storage objects from {source.bucket} to {target.bucket}, prefix='{prefix}'"
    )

    migrated = 0
    for path in source.iter_paths(prefix):
        data = source.download(path)
        source_hash = sha256_bytes(data)
        source_size = len(data)
        target.upload(path, data)

        verify = target.download(path)
        target_hash = sha256_bytes(verify)
        target_size = len(verify)

        if source_hash != target_hash or source_size != target_size:
            print(f"[error] Verification failed for {path}")
            print(
                f"        source(size={source_size}, sha={source_hash}) "
                f"target(size={target_size}, sha={target_hash})"
            )
            return 2

        migrated += 1
        print(f"[ok] {path} ({source_size} bytes)")

    print(f"[done] Migrated objects: {migrated}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
