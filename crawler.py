#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crawler.py - Un rastreador asíncrono de sitios web (versión mejorada).
v1.1 (URL Robustness Fix)
- FIX: Añadido .strip() a los href.
- FIX: Añadida comprobación para omitir URLs con espacios.
- CHG: Chequeo de robots.txt comentado para permitir el rastreo.
"""

import asyncio
import aiohttp
import logging
import argparse
import sys
from urllib.parse import urljoin, urlparse, ParseResult
from bs4 import BeautifulSoup
import urllib.robotparser

# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("crawler_v1_1")  # v1.1

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/91.0.4472.124 Safari/537.36"
}

BAD_EXTENSIONS = [
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".svg",
    ".webp",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".rar",
    ".gz",
    ".tar",
    ".css",
    ".js",
    ".xml",
    ".rss",
]


def strip_www(hostname: str | None) -> str | None:
    if not hostname:
        return None
    return hostname.lower().lstrip("www.")


def normalize_url(
    url: str, base_root: str, allow_subdomains: bool = False
) -> str | None:
    """Limpia, normaliza y valida una URL. base_root debe ser sin www y en minúsculas."""
    try:
        # <<< FIX 2.3: Comprobación final de espacios
        if " " in url:
            logger.warning(f"URL con espacio detectada y omitida: {url}")
            return None

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return None

        hostname = parsed.hostname
        if not hostname:
            return None

        hostname_norm = strip_www(hostname)
        # Permitimos sólo mismo dominio o subdominios si allow_subdomains True
        if allow_subdomains:
            if not hostname_norm.endswith(base_root):
                return None
        else:
            if hostname_norm != base_root:
                return None

        # Ignorar extensiones de archivo
        if any(parsed.path.lower().endswith(ext) for ext in BAD_EXTENSIONS):
            return None

        # Reconstruir sin query ni fragmento; netloc sin puerto por defecto
        normalized = ParseResult(
            scheme=parsed.scheme.lower(),
            netloc=hostname_norm,
            path=parsed.path or "/",
            params="",
            query="",
            fragment="",
        ).geturl()

        # Evitar duplicados con / final
        if normalized.endswith("/") and len(normalized) > 1:
            normalized = normalized[:-1]

        return normalized

    except Exception:
        return None


async def process_page(
    html: str, current_url: str, base_root: str, allow_subdomains: bool = False
) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    found_links = set()

    for a_tag in soup.find_all("a", href=True):
        link_href = a_tag.get("href")

        # --- 🟢 FIX v1.1 (Robustez) ---
        if not link_href:  # Comprobar si href está vacío
            continue

        link_href = link_href.strip()  # FIX 2.1: Limpiar espacios

        # FIX 2.2: Omitir links relativos con espacios (comunes en CMS mal configurados)
        if " " in link_href and not link_href.startswith(
            ("http", "https", "tel:", "mailto:")
        ):
            logger.warning(f"Omitiendo link relativo con espacios: {link_href}")
            continue
        # --- 🟢 FIN FIX ---

        full_url = urljoin(current_url, link_href)
        normalized = normalize_url(
            full_url, base_root, allow_subdomains=allow_subdomains
        )
        if normalized:
            found_links.add(normalized)
    return found_links


async def fetch_robots(base_url: str) -> urllib.robotparser.RobotFileParser:
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.hostname}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    try:
        async with aiohttp.ClientSession(headers=HEADERS) as s:
            async with s.get(robots_url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status == 200:
                    text = await r.text()
                    rp.parse(text.splitlines())
                else:
                    rp = (
                        urllib.robotparser.RobotFileParser()
                    )  # vacío = permite por defecto
    except Exception:
        rp = urllib.robotparser.RobotFileParser()
    return rp


async def crawl_site(
    base_url: str, max_pages: int = 1000, allow_subdomains: bool = False
) -> list[str]:
    queue = asyncio.Queue()
    visited = set()

    try:
        parsed_base = urlparse(base_url)
        base_hostname = strip_www(parsed_base.hostname)
        if not base_hostname:
            logger.error("No se pudo extraer el hostname de la URL base.")
            return []
    except Exception as e:
        logger.error(f"Error al parsear la URL base: {e}")
        return []

    start_url = normalize_url(
        base_url, base_hostname, allow_subdomains=allow_subdomains
    )
    if not start_url:
        logger.error("La URL base no es válida para el rastreo.")
        return []

    # robots
    rp = await fetch_robots(base_url)

    await queue.put(start_url)
    visited.add(start_url)

    logger.info(f"Iniciando rastreo para: {base_hostname} (max_pages={max_pages})")

    timeout = aiohttp.ClientTimeout(total=10)
    connector = aiohttp.TCPConnector(limit=10)  # controlar concurrencia TCP
    async with aiohttp.ClientSession(
        headers=HEADERS, timeout=timeout, connector=connector
    ) as session:
        tasks = []
        pages_count = 0
        lock = asyncio.Lock()

        async def worker():
            nonlocal pages_count
            while True:
                try:
                    url = await queue.get()
                    try:
                        # --- 🟢 FIX: robots.txt check (DESACTIVADO PARA GENERACIÓN GEO) ---
                        # if hasattr(rp, 'can_fetch') and not rp.can_fetch(HEADERS["User-Agent"], url):
                        #     logger.info(f"Bloqueado por robots.txt: {url}")
                        #     continue
                        # --- 🟢 FIN FIX ---

                        async with session.get(url) as resp:
                            if resp.status == 200 and "text/html" in resp.headers.get(
                                "content-type", ""
                            ):
                                try:
                                    html = await resp.text()
                                except Exception:
                                    raw = await resp.read()
                                    html = raw.decode(errors="ignore")

                                new_links = await process_page(
                                    html,
                                    url,
                                    base_hostname,
                                    allow_subdomains=allow_subdomains,
                                )

                                async with lock:
                                    pages_count += 1
                                for link in new_links:
                                    if link not in visited and len(visited) < max_pages:
                                        visited.add(link)
                                        await queue.put(link)
                                        logger.info(f"Encontrado: {link}")

                            else:
                                logger.debug(f"Ignorado [status {resp.status}] {url}")

                    except Exception as e:
                        logger.error(f"Error procesando {url}: {e}")
                    finally:
                        queue.task_done()
                        # pequeña espera para ser cortés (ajustable)
                        await asyncio.sleep(0.01)
                except asyncio.CancelledError:
                    break

        num_workers = 5
        for _ in range(num_workers):
            tasks.append(asyncio.create_task(worker()))

        await queue.join()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    logger.info(f"Rastreo finalizado. {len(visited)} URLs encontradas.")
    return sorted(visited)


async def main():
    parser = argparse.ArgumentParser(description="Rastreador asincrónico mejorado")
    parser.add_argument("url", help="URL base")
    parser.add_argument("--max", type=int, default=500, help="Max páginas a rastrear")
    args = parser.parse_args()

    urls = await crawl_site(args.url, max_pages=args.max)
    print("\n--- URLs Encontradas ---")
    for u in urls:
        print(u)
    print(f"\nTotal: {len(urls)} páginas.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Rastreo interrumpido.")
        sys.exit(0)
