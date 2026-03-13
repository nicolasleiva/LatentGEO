import logging
from typing import Any, Dict, List

import aiohttp
from sqlalchemy.exc import DBAPIError, DataError, InvalidRequestError
from sqlalchemy.orm.exc import UnmappedInstanceError
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.external_resilience import run_external_call
from ..models import RankTracking
from .audit_service import AuditService

logger = logging.getLogger(__name__)

_RANK_TRACKING_KEYWORD_MAX_LENGTH = 255
_RANK_TRACKING_URL_MAX_LENGTH = 500
_RANK_TRACKING_DEVICE_MAX_LENGTH = 20
_RANK_TRACKING_LOCATION_MAX_LENGTH = 50


def _normalize_limited_text(value: Any, max_length: int) -> tuple[str, bool]:
    normalized = " ".join(str(value or "").split()).strip()
    if not normalized:
        return "", False
    if len(normalized) <= max_length:
        return normalized, False
    return normalized[:max_length].rstrip(), True


class RankTrackerService:
    def __init__(self, db: Session):
        self.db = db
        self.serper_key = settings.SERPER_API_KEY

    async def _search_serper(
        self, query: str, *, num_results: int = 10
    ) -> List[Dict[str, Any]]:
        if not self.serper_key:
            logger.warning("SERPER_API_KEY not configured. Rank tracking skipped.")
            return []

        endpoint = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": self.serper_key,
            "Content-Type": "application/json",
        }
        all_items: List[Dict[str, Any]] = []
        seen_links = set()
        max_pages = max(1, (num_results + 9) // 10)

        try:
            async with aiohttp.ClientSession() as session:
                for page in range(max_pages):
                    if len(all_items) >= num_results:
                        break

                    payload = {"q": query, "num": 10, "page": page + 1}

                    async def _fetch_rank_page():
                        async with session.post(
                            endpoint,
                            json=payload,
                            headers=headers,
                            timeout=float(settings.SERPER_TIMEOUT_SECONDS),
                        ) as resp:
                            if resp.status == 200:
                                return resp.status, await resp.json()
                            return resp.status, await resp.text()

                    status_code, payload_body = await run_external_call(
                        "serper-rank-tracking",
                        _fetch_rank_page,
                        timeout_seconds=float(settings.SERPER_TIMEOUT_SECONDS),
                    )
                    if status_code != 200:
                        logger.error(
                            f"Serper rank search error {status_code}: {payload_body}"
                        )
                        break

                    data = payload_body if isinstance(payload_body, dict) else {}
                    organic = data.get("organic", [])
                    if not organic:
                        break

                    for entry in organic:
                        link = str(entry.get("link") or "").strip()
                        if not link or link in seen_links:
                            continue
                        seen_links.add(link)
                        all_items.append(
                            {
                                "title": entry.get("title", ""),
                                "link": link,
                                "snippet": entry.get("snippet", ""),
                            }
                        )
                        if len(all_items) >= num_results:
                            break
        except Exception as exc:
            logger.error(f"Rank search error: {exc}")
            return []

        return all_items[:num_results]

    async def _get_position_and_top_results(self, query: str, domain: str) -> tuple:
        """
        Returns position of domain and top 10 results.
        Returns: (position, top_results_list)
        """
        if not self.serper_key:
            return 0, []

        try:
            items = await self._search_serper(query, num_results=10)

            # Normalize domain for comparison
            clean_domain = (
                domain.replace("www.", "")
                .replace("https://", "")
                .replace("http://", "")
                .split("/")[0]
            )

            position = 0
            top_results = []

            for i, item in enumerate(items):
                link = item.get("link", "")
                title = item.get("title", "")

                # Extract domain from result URL
                try:
                    result_domain = (
                        link.replace("https://", "")
                        .replace("http://", "")
                        .replace("www.", "")
                        .split("/")[0]
                    )
                except Exception:
                    result_domain = "Unknown"

                top_results.append(
                    {
                        "position": i + 1,
                        "url": link,
                        "title": title,
                        "domain": result_domain,
                    }
                )

                if clean_domain in link and position == 0:
                    position = i + 1

            return position, top_results
        except Exception as e:
            logger.error(f"Rank Check Error: {e}")
            return 0, []

    async def track_rankings(
        self, audit_id: int, domain: str, keywords: List[str]
    ) -> List[RankTracking]:
        """
        Tracks rankings using Serper search results.
        """
        logger.info(f"Tracking rankings for audit {audit_id}, domain {domain}")

        created_rankings = []
        truncated_keywords = 0
        skipped_keywords = 0
        persistence_failures = 0

        for kw in keywords:
            keyword, keyword_truncated = _normalize_limited_text(
                kw, _RANK_TRACKING_KEYWORD_MAX_LENGTH
            )
            if keyword_truncated:
                truncated_keywords += 1
                logger.warning(
                    "Rank tracking keyword truncated for audit %s (original_length=%s)",
                    audit_id,
                    len(" ".join(str(kw or "").split()).strip()),
                )
            if not keyword:
                skipped_keywords += 1
                logger.warning(
                    "Skipping rank tracking keyword for audit %s because it is empty after normalization",
                    audit_id,
                )
                continue

            position, top_results = await self._get_position_and_top_results(
                keyword, domain
            )
            url_value, _ = _normalize_limited_text(
                f"https://{domain}" if position > 0 else "Not Ranked",
                _RANK_TRACKING_URL_MAX_LENGTH,
            )
            device_value, _ = _normalize_limited_text(
                "desktop",
                _RANK_TRACKING_DEVICE_MAX_LENGTH,
            )
            location_value, _ = _normalize_limited_text(
                "Global",
                _RANK_TRACKING_LOCATION_MAX_LENGTH,
            )

            ranking = RankTracking(
                audit_id=audit_id,
                keyword=keyword,
                position=position,
                url=url_value,
                device=device_value,
                location=location_value,
                top_results=top_results,
            )
            if not self._persist_ranking(ranking):
                persistence_failures += 1
                logger.warning(
                    "Rank tracking row could not be persisted for audit %s keyword=%r",
                    audit_id,
                    keyword,
                )
                continue
            created_rankings.append(ranking)

        self._persist_tracking_diagnostics(
            audit_id=audit_id,
            truncated_keywords=truncated_keywords,
            skipped_keywords=skipped_keywords,
            persistence_failures=persistence_failures,
        )
        self.db.commit()
        for r in created_rankings:
            self.db.refresh(r)

        return created_rankings

    def _persist_ranking(self, ranking: RankTracking) -> bool:
        savepoint = self.db.begin_nested()
        try:
            self.db.add(ranking)
            self.db.flush()
            savepoint.commit()
            return True
        except (DBAPIError, DataError, ValueError) as exc:
            savepoint.rollback()
            try:
                self.db.expunge(ranking)
            except (InvalidRequestError, UnmappedInstanceError):
                pass
            logger.warning("Rank tracking persistence error: %s", exc)
            return False

    def _persist_tracking_diagnostics(
        self,
        *,
        audit_id: int,
        truncated_keywords: int,
        skipped_keywords: int,
        persistence_failures: int,
    ) -> None:
        if truncated_keywords > 0:
            AuditService.append_runtime_diagnostic(
                self.db,
                audit_id,
                source="rank-tracking",
                stage="persist-rankings",
                severity="warning",
                code="rank_tracking_keyword_truncated",
                message=(
                    f"Rank tracking truncated {truncated_keywords} keyword values to fit database limits."
                ),
                commit=False,
            )
        if skipped_keywords > 0:
            AuditService.append_runtime_diagnostic(
                self.db,
                audit_id,
                source="rank-tracking",
                stage="persist-rankings",
                severity="warning",
                code="rank_tracking_keyword_skipped",
                message=(
                    f"Rank tracking skipped {skipped_keywords} empty keyword values after normalization."
                ),
                commit=False,
            )
        if persistence_failures > 0:
            AuditService.append_runtime_diagnostic(
                self.db,
                audit_id,
                source="rank-tracking",
                stage="persist-rankings",
                severity="warning",
                code="rank_tracking_row_persist_failed",
                message=(
                    f"Rank tracking could not persist {persistence_failures} rows and continued with the remaining results."
                ),
                commit=False,
            )

    def get_rankings(self, audit_id: int) -> List[RankTracking]:
        return (
            self.db.query(RankTracking).filter(RankTracking.audit_id == audit_id).all()
        )
