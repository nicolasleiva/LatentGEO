#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crawler_service.py - Servicio de rastreo web modular

Envuelve la funcionalidad del crawler.py original en una clase de servicio
para ser utilizada por los endpoints de la API.

Proporciona:
- Rastreo asincrónico de sitios web
- Normalización de URLs
- Procesamiento de HTML
- Manejo robusto de errores
"""

import asyncio
import aiohttp
import logging
import sys
from urllib.parse import urljoin, urlparse, ParseResult
from bs4 import BeautifulSoup
import urllib.robotparser
from typing import Optional, Set, List

logger = logging.getLogger(__name__)

# Headers para simular navegador
HEADERS_DESKTOP = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/91.0.4472.124 Safari/537.36"
}

HEADERS_MOBILE = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/91.0.4472.120 Mobile Safari/537.36"
}

# Extensiones a ignorar
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


class CrawlerService:
    """
    Servicio de rastreo web.

    Proporciona métodos para rastrear sitios web, normalizar URLs,
    procesar HTML y extraer enlaces.
    """

    @staticmethod
    def strip_www(hostname: Optional[str]) -> Optional[str]:
        """
        Elimina 'www.' del hostname.

        Args:
            hostname: Nombre del host (ej: www.google.com)

        Returns:
            Hostname sin www (ej: google.com)
        """
        if not hostname:
            return None
        return hostname.lower().lstrip("www.")

    @staticmethod
    def normalize_url(
        url: str, base_root: str, allow_subdomains: bool = False
    ) -> Optional[str]:
        """
        Normaliza y valida una URL.

        Args:
            url: URL a normalizar
            base_root: Dominio raíz (sin www, minúsculas)
            allow_subdomains: Si True, permite subdominios

        Returns:
            URL normalizada o None si es inválida

        Example:
            >>> normalize_url('https://www.google.com/search?q=test', 'google.com')
            'https://google.com/search'
        """
        try:
            # Comprobar espacios
            if " " in url:
                logger.warning(f"URL con espacio detectada: {url}")
                return None

            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return None

            hostname = parsed.hostname
            if not hostname:
                return None

            hostname_norm = CrawlerService.strip_www(hostname)

            # Validar que sea del mismo dominio
            if allow_subdomains:
                if not hostname_norm.endswith(base_root):
                    return None
            else:
                if hostname_norm != base_root:
                    return None

            # Ignorar extensiones de archivo
            if any(parsed.path.lower().endswith(ext) for ext in BAD_EXTENSIONS):
                return None

            # Reconstruir URL normalizada
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

        except Exception as e:
            logger.error(f"Error normalizando URL {url}: {e}")
            return None

    @staticmethod
    async def process_page(
        html: str, current_url: str, base_root: str, allow_subdomains: bool = False
    ) -> Set[str]:
        """
        Procesa una página HTML y extrae enlaces válidos.

        Args:
            html: Contenido HTML
            current_url: URL actual (para resolver URLs relativas)
            base_root: Dominio raíz
            allow_subdomains: Si permite subdominios

        Returns:
            Set de URLs encontradas y normalizadas
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            found_links = set()

            for a_tag in soup.find_all("a", href=True):
                link_href = a_tag.get("href")

                if not link_href:
                    continue

                link_href = link_href.strip()

                # Omitir links relativos con espacios (CMS mal configurados)
                if " " in link_href and not link_href.startswith(
                    ("http", "https", "tel:", "mailto:")
                ):
                    logger.warning(f"Omitiendo link relativo con espacios: {link_href}")
                    continue

                full_url = urljoin(current_url, link_href)
                normalized = CrawlerService.normalize_url(
                    full_url, base_root, allow_subdomains
                )

                if normalized:
                    found_links.add(normalized)

            return found_links

        except Exception as e:
            logger.error(f"Error procesando página {current_url}: {e}")
            return set()

    @staticmethod
    async def fetch_robots(base_url: str, mobile: bool = True) -> urllib.robotparser.RobotFileParser:
        """
        Descarga y parsea robots.txt del sitio.

        Args:
            base_url: URL base del sitio

        Returns:
            RobotFileParser con reglas o vacío si no disponible
        """
        try:
            parsed = urlparse(base_url)
            robots_url = f"{parsed.scheme}://{parsed.hostname}/robots.txt"
            rp = urllib.robotparser.RobotFileParser()
            headers = HEADERS_MOBILE if mobile else HEADERS_DESKTOP

            async with aiohttp.ClientSession(headers=headers) as s:
                async with s.get(
                    robots_url, timeout=aiohttp.ClientTimeout(total=5)
                ) as r:
                    if r.status == 200:
                        text = await r.text()
                        rp.parse(text.splitlines())
                    else:
                        rp = urllib.robotparser.RobotFileParser()

        except Exception as e:
            logger.warning(f"No se pudo descargar robots.txt: {e}")
            rp = urllib.robotparser.RobotFileParser()

        return rp

    @staticmethod
    async def crawl_site(
        base_url: str,
        max_pages: int = 1000,
        allow_subdomains: bool = False,
        callback: Optional[callable] = None,
        mobile_first: bool = True,
    ) -> List[str]:
        """
        Rastrea un sitio web completo de forma asincrónica.

        Args:
            base_url: URL inicial del rastreo
            max_pages: Máximo de páginas a rastrear
            allow_subdomains: Si permite rastrear subdominios
            callback: Función callable(url, status) para reportar progreso

        Returns:
            Lista de URLs encontradas (ordenada)

        Raises:
            ValueError: Si la URL base es inválida

        Example:
            >>> urls = await crawl_site('https://example.com', max_pages=50)
            >>> len(urls)
            35
        """
        queue = asyncio.Queue()
        visited = set()

        try:
            # Validar URL base
            parsed_base = urlparse(base_url)
            base_hostname = CrawlerService.strip_www(parsed_base.hostname)

            if not base_hostname:
                raise ValueError("No se pudo extraer el hostname de la URL base")

            # Normalizar URL de inicio
            start_url = CrawlerService.normalize_url(
                base_url, base_hostname, allow_subdomains=allow_subdomains
            )

            if not start_url:
                raise ValueError("La URL base no es válida para el rastreo")

            # Descargar robots.txt
            rp = await CrawlerService.fetch_robots(base_url, mobile_first)

            await queue.put(start_url)
            visited.add(start_url)

            logger.info(f"Iniciando rastreo: {base_hostname} (max_pages={max_pages})")
            if callback:
                callback(start_url, "starting")

        except ValueError as e:
            logger.error(f"Error validando URL: {e}")
            raise

        # Configurar sesión con limites de concurrencia
        timeout = aiohttp.ClientTimeout(total=10)
        connector = aiohttp.TCPConnector(limit=10)
        headers = HEADERS_MOBILE if mobile_first else HEADERS_DESKTOP

        async with aiohttp.ClientSession(
            headers=headers, timeout=timeout, connector=connector
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
                            async with session.get(url) as resp:
                                if (
                                    resp.status == 200
                                    and "text/html"
                                    in resp.headers.get("content-type", "")
                                ):
                                    try:
                                        html = await resp.text()
                                    except Exception:
                                        raw = await resp.read()
                                        html = raw.decode(errors="ignore")

                                    # Procesar página
                                    new_links = await CrawlerService.process_page(
                                        html,
                                        url,
                                        base_hostname,
                                        allow_subdomains=allow_subdomains,
                                    )

                                    async with lock:
                                        pages_count += 1

                                    # Agregar nuevos links a la cola
                                    for link in new_links:
                                        if (
                                            link not in visited
                                            and len(visited) < max_pages
                                        ):
                                            visited.add(link)
                                            await queue.put(link)
                                            logger.info(f"Encontrado: {link}")
                                            if callback:
                                                callback(link, "found")

                                else:
                                    logger.debug(
                                        f"Ignorado [status {resp.status}] {url}"
                                    )
                                    if callback:
                                        callback(url, "skipped")

                        except Exception as e:
                            logger.error(f"Error procesando {url}: {e}")
                            if callback:
                                callback(url, "error")

                        finally:
                            queue.task_done()
                            await asyncio.sleep(0.01)  # Cortesía

                    except asyncio.CancelledError:
                        break

            # Crear workers
            num_workers = 5
            for _ in range(num_workers):
                tasks.append(asyncio.create_task(worker()))

            # Esperar a que terminen
            await queue.join()

            # Cancelar workers
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(f"Rastreo finalizado. {len(visited)} URLs encontradas.")
        if callback:
            callback(None, f"completed:{len(visited)}")

        return sorted(visited)

    @staticmethod
    async def get_page_content(url: str, timeout: int = 10, mobile: bool = True) -> Optional[str]:
        """
        Obtiene el contenido HTML de una página.

        Args:
            url: URL a descargar
            timeout: Timeout en segundos

        Returns:
            Contenido HTML o None si falla
        """
        try:
            timeout_config = aiohttp.ClientTimeout(total=timeout)
            headers = HEADERS_MOBILE if mobile else HEADERS_DESKTOP
            async with aiohttp.ClientSession(
                headers=headers, timeout=timeout_config
            ) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        try:
                            return await resp.text()
                        except Exception:
                            raw = await resp.read()
                            return raw.decode(errors="ignore")
                    else:
                        logger.warning(f"Error descargando {url}: status {resp.status}")
                        return None

        except Exception as e:
            logger.error(f"Error descargando {url}: {e}")
            return None


# Función de compatibilidad con código anterior
async def crawl_site(
    base_url: str, max_pages: int = 1000, allow_subdomains: bool = False
) -> List[str]:
    """
    Función wrapper para compatibilidad con código existente.

    Llama directamente al método estático del servicio.
    """
    return await CrawlerService.crawl_site(base_url, max_pages, allow_subdomains)
