import logging
from typing import Any, Dict, List

import aiohttp
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.external_resilience import run_external_call
from ..models import RankTracking

logger = logging.getLogger(__name__)


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

        for kw in keywords:
            position, top_results = await self._get_position_and_top_results(kw, domain)

            ranking = RankTracking(
                audit_id=audit_id,
                keyword=kw,
                position=position,
                url=f"https://{domain}" if position > 0 else "Not Ranked",
                device="desktop",
                location="Global",
                top_results=top_results,
            )
            self.db.add(ranking)
            created_rankings.append(ranking)

        self.db.commit()
        for r in created_rankings:
            self.db.refresh(r)

        return created_rankings

    def get_rankings(self, audit_id: int) -> List[RankTracking]:
        return (
            self.db.query(RankTracking).filter(RankTracking.audit_id == audit_id).all()
        )
