#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reusable competitor domain filters.
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse


BLOCKED_COMPETITOR_DOMAINS = {
    "instagram.com",
    "facebook.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
    "reddit.com",
    "quora.com",
    "youtube.com",
    "youtu.be",
    "linkedin.com",
    "wikipedia.org",
    "medium.com",
}

INSTITUTIONAL_TLDS = {
    ".gov",
    ".edu",
    ".mil",
    ".int",
}

ECOMMERCE_ORG_ALLOWLIST = set()


def normalize_domain(url_or_domain: str) -> str:
    raw = str(url_or_domain or "").strip().lower()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    try:
        parsed = urlparse(raw)
    except Exception:
        return ""
    domain = (parsed.netloc or parsed.path or "").split("/")[0].split(":")[0].strip(".")
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _matches_domain(candidate: str, blocked: str) -> bool:
    return candidate == blocked or candidate.endswith(f".{blocked}")


def is_blocked_competitor_domain(domain: str) -> bool:
    normalized = normalize_domain(domain)
    if not normalized:
        return True
    if "." not in normalized:
        return True
    if any(normalized.endswith(tld) for tld in INSTITUTIONAL_TLDS):
        return True
    for blocked in BLOCKED_COMPETITOR_DOMAINS:
        if _matches_domain(normalized, blocked):
            return True
    return False


def is_valid_competitor_domain(domain: str, vertical_hint: Optional[str] = None) -> bool:
    normalized = normalize_domain(domain)
    if not normalized:
        return False
    if is_blocked_competitor_domain(normalized):
        return False

    vertical = str(vertical_hint or "").strip().lower()
    if vertical in {"ecommerce", "retail"}:
        if normalized.endswith(".org") and normalized not in ECOMMERCE_ORG_ALLOWLIST:
            return False

    return True


def infer_vertical_hint(*labels: Optional[str]) -> Optional[str]:
    text = " ".join(str(label or "").lower() for label in labels if label)
    if not text:
        return None
    ecommerce_tokens = {
        "ecommerce",
        "e-commerce",
        "tienda",
        "store",
        "retail",
        "shop",
        "pharmacy",
        "marketplace",
        "producto",
        "product",
    }
    if any(token in text for token in ecommerce_tokens):
        return "ecommerce"
    return "other"
