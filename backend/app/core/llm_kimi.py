"""
LLM Service - Kimi 2.5 (NVIDIA NIM)
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List
from urllib.parse import urlparse

import httpx
from openai import AsyncOpenAI

from ..core.config import settings
from ..core.external_resilience import (
    ExternalCircuitOpenError,
    ExternalServiceTimeout,
    run_external_call,
)
from ..core.logger import get_logger

logger = get_logger(__name__)


class KimiSearchUnavailableError(RuntimeError):
    """Raised when Kimi Search is disabled or unsupported by provider/runtime."""


class KimiSearchError(RuntimeError):
    """Raised when Kimi Search fails while enabled."""


class KimiUnavailableError(RuntimeError):
    """Raised when Kimi (non-search) credentials are unavailable."""


class KimiGenerationError(RuntimeError):
    """Raised when Kimi (non-search) generation fails."""


def resolve_kimi_api_key() -> str | None:
    return (
        settings.NV_API_KEY_ANALYSIS or settings.NVIDIA_API_KEY or settings.NV_API_KEY
    )


def is_kimi_configured() -> bool:
    return bool(resolve_kimi_api_key())


def _get_api_key() -> str | None:
    return resolve_kimi_api_key()


def _safe_close_message(exc: Exception) -> bool:
    return "Event loop is closed" in str(exc)


def _classify_kimi_generation_error(exc: BaseException) -> tuple[str, str]:
    if isinstance(exc, ExternalServiceTimeout):
        return (
            "KIMI_TIMEOUT",
            "Kimi request timed out while waiting for provider response.",
        )
    if isinstance(exc, ExternalCircuitOpenError):
        return (
            "KIMI_CIRCUIT_OPEN",
            "Kimi circuit breaker is open due to repeated provider failures.",
        )

    timeout_errors = (
        asyncio.TimeoutError,
        TimeoutError,
        httpx.TimeoutException,
        httpx.ConnectTimeout,
        httpx.ReadTimeout,
        httpx.WriteTimeout,
        httpx.PoolTimeout,
    )
    if isinstance(exc, asyncio.CancelledError) or isinstance(exc, timeout_errors):
        return (
            "KIMI_TIMEOUT",
            "Kimi request timed out while waiting for provider response.",
        )

    network_errors = (
        httpx.NetworkError,
        httpx.TransportError,
        httpx.ConnectError,
        httpx.ReadError,
    )
    if isinstance(exc, network_errors):
        return (
            "KIMI_NETWORK_ERROR",
            "Kimi request failed due to a provider network transport error.",
        )

    if isinstance(exc, ValueError) and "empty response" in str(exc).lower():
        return ("KIMI_EMPTY_RESPONSE", "Kimi returned an empty response.")

    return ("KIMI_REQUEST_FAILED", "Kimi request failed unexpectedly.")


def _strip_markdown_fences(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return cleaned
    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```json", "```").replace("```", "").strip()
    return cleaned


def _extract_json_payload(raw_text: str) -> Dict[str, Any] | List[Any]:
    cleaned = _strip_markdown_fences(raw_text)
    if not cleaned:
        raise ValueError("Kimi search returned empty text.")

    try:
        return json.loads(cleaned)
    except Exception:  # nosec B110
        pass

    # Try to recover first object or array block from mixed text.
    first_obj = cleaned.find("{")
    last_obj = cleaned.rfind("}")
    if first_obj != -1 and last_obj > first_obj:
        candidate = cleaned[first_obj : last_obj + 1]
        try:
            return json.loads(candidate)
        except Exception:  # nosec B110
            pass

    first_arr = cleaned.find("[")
    last_arr = cleaned.rfind("]")
    if first_arr != -1 and last_arr > first_arr:
        candidate = cleaned[first_arr : last_arr + 1]
        return json.loads(candidate)

    raise ValueError("Unable to parse JSON payload from Kimi search response.")


def _extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    output = getattr(response, "output", None)
    if output is None and isinstance(response, dict):
        output = response.get("output")

    chunks: List[str] = []
    for item in output or []:
        content = getattr(item, "content", None)
        if content is None and isinstance(item, dict):
            content = item.get("content", [])
        for part in content or []:
            text = getattr(part, "text", None)
            if text is None and isinstance(part, dict):
                text = part.get("text")
            if text:
                chunks.append(str(text))
    return "\n".join(chunks).strip()


def _normalize_results(
    payload: Dict[str, Any] | List[Any], top_k: int
) -> List[Dict[str, Any]]:
    items: List[Any]
    if isinstance(payload, dict):
        items = payload.get("results") or payload.get("items") or []
    else:
        items = payload

    normalized: List[Dict[str, Any]] = []
    seen_urls = set()

    for idx, raw in enumerate(items or []):
        if not isinstance(raw, dict):
            continue
        url = str(raw.get("url") or raw.get("link") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        parsed = urlparse(url if "://" in url else f"https://{url}")
        domain = parsed.netloc.lower().replace("www.", "")
        if not domain:
            continue
        title = str(raw.get("title") or raw.get("name") or domain).strip()
        snippet = str(
            raw.get("snippet") or raw.get("description") or raw.get("summary") or ""
        ).strip()
        normalized.append(
            {
                "position": (
                    len(normalized) + 1
                    if not raw.get("position")
                    else int(raw["position"])
                ),
                "title": title,
                "url": url,
                "domain": domain,
                "snippet": snippet,
            }
        )
        if len(normalized) >= top_k:
            break

    # Re-index to avoid gaps or duplicated positions from the model response.
    for i, row in enumerate(normalized, start=1):
        row["position"] = i
    return normalized[:top_k]


async def kimi_function(
    system_prompt: str | None = None,
    user_prompt: str | None = None,
    max_tokens: int | None = None,
) -> str:
    """
    Run non-search prompts with Kimi 2.5.
    """
    api_key = _get_api_key()

    if not api_key:
        logger.error("No NVIDIA API key configured for KIMI")
        raise KimiUnavailableError(
            "Kimi provider is not configured. Set NV_API_KEY_ANALYSIS or NVIDIA_API_KEY or NV_API_KEY."
        )

    client = None
    try:
        provider_timeout = float(settings.NVIDIA_TIMEOUT_SECONDS)
        client = AsyncOpenAI(
            base_url=settings.NV_BASE_URL,
            api_key=api_key,
            timeout=provider_timeout,
            max_retries=2,
        )

        # Backward-compatible call style:
        # - preferred: kimi_function(system_prompt, user_prompt)
        # - legacy: kimi_function(user_prompt)
        if user_prompt is None:
            user_prompt = system_prompt or ""
            system_prompt = (
                "You are a reliable assistant. "
                "Return factual, production-safe output and avoid fabrication."
            )

        messages = [
            {"role": "system", "content": system_prompt or ""},
            {"role": "user", "content": user_prompt or ""},
        ]

        max_tokens_value = max_tokens or settings.NV_MAX_TOKENS
        logger.info(
            f"Llamando a KIMI (Modelo: {settings.NV_MODEL_ANALYSIS}). Max tokens: {max_tokens_value}"
        )
        completion = await run_external_call(
            "nvidia-kimi-generation",
            lambda: client.chat.completions.create(
                model=settings.NV_MODEL_ANALYSIS,
                messages=messages,
                temperature=0.0,
                top_p=1.0,
                max_tokens=max_tokens_value,
                stream=False,
            ),
            timeout_seconds=provider_timeout,
        )

        content = completion.choices[0].message.content
        if not content:
            raise ValueError("Empty response from LLM")
        return content.strip()

    except KimiUnavailableError:
        raise
    except asyncio.CancelledError as err:
        error_code, stable_message = _classify_kimi_generation_error(err)
        logger.warning(f"Error with KIMI [{error_code}]: {stable_message}")
        raise KimiGenerationError(f"{error_code}: {stable_message}") from err
    except Exception as err:
        error_code, stable_message = _classify_kimi_generation_error(err)
        logger.error(
            f"Error with KIMI [{error_code}]: {stable_message}. "
            f"Raw={type(err).__name__}: {err}"
        )
        raise KimiGenerationError(f"{error_code}: {stable_message}") from err
    finally:
        if client is not None:
            try:
                await client.close()
            except RuntimeError as close_err:
                if not _safe_close_message(close_err):
                    logger.warning(f"Error closing KIMI client: {close_err}")


async def kimi_search_serp(
    query: str,
    market: str,
    *,
    top_k: int = 10,
    language: str = "es",
) -> Dict[str, Any]:
    """
    Execute search for commerce query analysis.
    Provider is controlled by NV_KIMI_SEARCH_PROVIDER (kimi | serper | auto).
    """
    if not settings.NV_KIMI_SEARCH_ENABLED:
        raise KimiSearchUnavailableError(
            "Kimi Search is disabled. Set NV_KIMI_SEARCH_ENABLED=true to enable commerce query analysis."
        )

    provider = (settings.NV_KIMI_SEARCH_PROVIDER or "kimi").lower().strip()

    async def _serper_search() -> Dict[str, Any]:
        if not settings.SERPER_API_KEY:
            raise KimiSearchUnavailableError(
                "Serper search requires SERPER_API_KEY."
            )

        endpoint = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": settings.SERPER_API_KEY,
            "Content-Type": "application/json",
        }
        max_pages = (top_k + 9) // 10
        all_items: List[Dict[str, Any]] = []
        gl = (market or "").strip().lower()
        hl = (language or "").strip().lower()[:2]

        async with httpx.AsyncClient(
            timeout=float(settings.NV_KIMI_SEARCH_TIMEOUT)
        ) as client:
            for page in range(max_pages):
                if len(all_items) >= top_k:
                    break
                payload: Dict[str, Any] = {
                    "q": query,
                    "num": min(10, top_k - len(all_items)),
                    "page": page + 1,
                }
                if gl:
                    payload["gl"] = gl
                if hl:
                    payload["hl"] = hl

                resp = await run_external_call(
                    "serper-search",
                    lambda: client.post(endpoint, headers=headers, json=payload),
                    timeout_seconds=float(settings.SERPER_TIMEOUT_SECONDS),
                )
                if resp.status_code != 200:
                    raise KimiSearchError(
                        f"Serper error {resp.status_code}: {resp.text}"
                    )
                data = resp.json()
                items = data.get("organic", [])
                if not isinstance(items, list) or not items:
                    break
                for entry in items:
                    link = str(entry.get("link") or "").strip()
                    if not link:
                        continue
                    all_items.append(
                        {
                            "title": entry.get("title", ""),
                            "link": link,
                            "snippet": entry.get("snippet", ""),
                        }
                    )
                    if len(all_items) >= top_k:
                        break

        results = _normalize_results({"items": all_items[:top_k]}, top_k=top_k)
        if not results:
            raise KimiSearchError("Serper returned no parseable results.")

        evidence = [{"title": row["title"], "url": row["url"]} for row in results]
        return {
            "query": query,
            "market": market.upper(),
            "provider": "serper",
            "results": results,
            "evidence": evidence,
        }

    if provider in {"serper", "google"}:
        if provider == "google":
            logger.warning(
                "NV_KIMI_SEARCH_PROVIDER=google is deprecated. Using Serper instead."
            )
        return await _serper_search()

    api_key = _get_api_key()
    if not api_key:
        raise KimiSearchUnavailableError(
            "Kimi Search requires NV/NVIDIA API credentials."
        )

    prompt = (
        "Use web search and return ONLY JSON.\n"
        f"Query: {query}\n"
        f"Market: {market}\n"
        f"Language: {language}\n"
        f"Top K: {top_k}\n"
        "JSON schema:\n"
        "{"
        '"query":"string",'
        '"market":"string",'
        '"results":[{"position":1,"title":"string","url":"https://...","domain":"example.com","snippet":"string"}]'
        "}\n"
        "Rules: include only real web results with valid URLs. Do not invent domains."
    )
    system_prompt = "You are Kimi 2.5 Search. Always perform web search and return strict JSON only."

    client = None
    try:
        client = AsyncOpenAI(
            base_url=settings.NV_BASE_URL,
            api_key=api_key,
            timeout=float(settings.NV_KIMI_SEARCH_TIMEOUT),
            max_retries=1,
        )

        raw_text = ""

        # Attempt Responses API first.
        try:
            response = await run_external_call(
                "nvidia-kimi-search",
                lambda: client.responses.create(
                    model=settings.NV_KIMI_SEARCH_MODEL,
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    tools=[{"type": "web_search"}],
                    temperature=0.0,
                    top_p=1.0,
                    max_output_tokens=4096,
                ),
                timeout_seconds=float(settings.NV_KIMI_SEARCH_TIMEOUT),
            )
            raw_text = _extract_response_text(response)
        except Exception as response_exc:
            logger.warning(
                f"Kimi responses API search call failed, retrying via chat tools: {response_exc}"
            )
            completion = await run_external_call(
                "nvidia-kimi-search",
                lambda: client.chat.completions.create(
                    model=settings.NV_KIMI_SEARCH_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    tools=[{"type": "web_search"}],
                    temperature=0.0,
                    top_p=1.0,
                    max_tokens=4096,
                    stream=False,
                ),
                timeout_seconds=float(settings.NV_KIMI_SEARCH_TIMEOUT),
            )
            raw_text = (
                completion.choices[0].message.content
                if completion.choices and completion.choices[0].message.content
                else ""
            )

        payload = _extract_json_payload(raw_text)
        results = _normalize_results(payload, top_k=top_k)
        if not results:
            raise KimiSearchError("Kimi Search returned no parseable results.")

        evidence = [{"title": row["title"], "url": row["url"]} for row in results]
        return {
            "query": query,
            "market": market.upper(),
            "provider": "kimi-2.5-search",
            "results": results,
            "evidence": evidence,
        }
    except KimiSearchUnavailableError:
        raise
    except KimiSearchError:
        raise
    except Exception as exc:
        message = str(exc)
        lowered = message.lower()
        if any(
            marker in lowered
            for marker in ["web_search", "unknown tool", "unsupported", "responses"]
        ):
            if provider == "auto":
                return await _serper_search()
            raise KimiSearchUnavailableError(
                "Kimi Search is not available in this runtime/provider. Check model capability and account permissions."
            ) from exc
        raise KimiSearchError(f"Kimi Search request failed: {message}") from exc
    finally:
        if client is not None:
            try:
                await client.close()
            except RuntimeError as close_err:
                if not _safe_close_message(close_err):
                    logger.warning(f"Error closing KIMI client: {close_err}")


def get_llm_function():
    """
    Return default LLM function (Kimi).
    """
    return kimi_function
