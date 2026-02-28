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
import gzip
import logging
import re
import urllib.robotparser
from typing import Callable, List, Optional, Set, Tuple
from urllib.parse import ParseResult, urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
from defusedxml import ElementTree as DefusedET

from ..core.config import settings
from ..core.security import is_safe_outbound_url, normalize_outbound_url

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
        hostname = hostname.lower()
        if hostname.startswith("www."):
            return hostname[4:]
        return hostname

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

            # Reconstruir URL normalizada - preservamos el hostname original (con o sin www)
            # para no romper sitios que dependen del subdominio www
            normalized = ParseResult(
                scheme=parsed.scheme.lower(),
                netloc=hostname.lower(),
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
                    # Filter out purely numeric paths (e.g. /452, /468) which are often low value
                    parsed_idx = urlparse(normalized)
                    if re.match(r"^/\d+/?$", parsed_idx.path):
                        # logger.debug(f"Skipping numeric path: {normalized}")
                        continue
                    found_links.add(normalized)

            return found_links

        except Exception as e:
            logger.error(f"Error procesando página {current_url}: {e}")
            return set()

    @staticmethod
    async def fetch_robots(
        base_url: str, mobile: bool = True
    ) -> urllib.robotparser.RobotFileParser:
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

            try:
                # Intento 1: SSL verificado
                async with aiohttp.ClientSession(headers=headers) as s:
                    async with s.get(
                        robots_url,
                        timeout=aiohttp.ClientTimeout(total=5),
                        allow_redirects=True,
                    ) as r:
                        if r.status == 200:
                            text = await r.text()
                            rp.parse(text.splitlines())
            except Exception as e:
                if not settings.ALLOW_INSECURE_SSL_FALLBACK:
                    logger.warning(
                        f"Error descargando robots.txt para {base_url}: {e}. Fallback SSL inseguro deshabilitado."
                    )
                else:
                    logger.warning(
                        f"Error descargando robots.txt para {base_url}: {e}. Reintentando sin SSL por configuración explícita..."
                    )
                    # Intento 2: SSL relajado
                    connector = aiohttp.TCPConnector(ssl=False)
                    async with aiohttp.ClientSession(
                        headers=headers, connector=connector
                    ) as s:
                        async with s.get(
                            robots_url,
                            timeout=aiohttp.ClientTimeout(total=5),
                            allow_redirects=True,
                        ) as r:
                            if r.status == 200:
                                text = await r.text()
                                rp.parse(text.splitlines())

        except Exception as e:
            logger.warning(f"No se pudo descargar robots.txt definitivamente: {e}")
            rp = urllib.robotparser.RobotFileParser()

        return rp

    @staticmethod
    def _parse_sitemap_xml(xml_text: str) -> Tuple[List[str], bool]:
        """
        Parsea XML de sitemap.

        Returns:
            (locs, is_index)
        """
        if not xml_text:
            return [], False
        try:
            root = DefusedET.fromstring(xml_text)
        except Exception:
            return [], False

        tag = root.tag.lower()
        is_index = tag.endswith("sitemapindex")
        locs = []
        for loc in root.findall(".//{*}loc"):
            if loc is not None and loc.text:
                locs.append(loc.text.strip())
        return locs, is_index

    @staticmethod
    async def _fetch_text_url(
        session: aiohttp.ClientSession,
        url: str,
        timeout: int = 10,
        allow_insecure_fallback: Optional[bool] = None,
    ) -> Optional[str]:
        if allow_insecure_fallback is None:
            allow_insecure_fallback = settings.ALLOW_INSECURE_SSL_FALLBACK
        try:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                if resp.status != 200:
                    return None
                raw = await resp.read()
                if not raw:
                    return None
                encoding = resp.headers.get("Content-Encoding", "").lower()
                content_type = resp.headers.get("Content-Type", "").lower()
                if (
                    "gzip" in encoding
                    or url.endswith(".gz")
                    or "application/x-gzip" in content_type
                ):
                    try:
                        raw = gzip.decompress(raw)
                    except Exception:  # nosec B110
                        pass
                try:
                    return raw.decode(errors="ignore")
                except Exception:
                    return None
        except Exception:
            if not allow_insecure_fallback:
                return None
            try:
                connector = aiohttp.TCPConnector(ssl=False)
                headers = session.headers if hasattr(session, "headers") else None
                async with aiohttp.ClientSession(
                    headers=headers, connector=connector
                ) as insecure_session:
                    async with insecure_session.get(
                        url, timeout=aiohttp.ClientTimeout(total=timeout)
                    ) as resp:
                        if resp.status != 200:
                            return None
                        raw = await resp.read()
                        if not raw:
                            return None
                        encoding = resp.headers.get("Content-Encoding", "").lower()
                        content_type = resp.headers.get("Content-Type", "").lower()
                        if (
                            "gzip" in encoding
                            or url.endswith(".gz")
                            or "application/x-gzip" in content_type
                        ):
                            try:
                                raw = gzip.decompress(raw)
                            except Exception:  # nosec B110
                                pass
                        try:
                            return raw.decode(errors="ignore")
                        except Exception:
                            return None
            except Exception:
                return None

    @staticmethod
    async def fetch_sitemap_urls(
        base_url: str,
        allow_subdomains: bool = False,
        max_urls: int = 500,
        mobile_first: bool = True,
    ) -> List[str]:
        """
        Descubre URLs desde sitemaps (robots.txt + sitemap.xml).
        """
        urls: List[str] = []
        if not base_url:
            return urls

        parsed = urlparse(base_url)
        if not parsed.scheme or not parsed.hostname:
            return urls

        base_root = CrawlerService.strip_www(parsed.hostname)
        if not base_root:
            return urls

        candidate_sitemaps = set()
        robots_url = f"{parsed.scheme}://{parsed.hostname}/robots.txt"
        candidate_sitemaps.add(f"{parsed.scheme}://{parsed.hostname}/sitemap.xml")
        candidate_sitemaps.add(f"{parsed.scheme}://{parsed.hostname}/sitemap.xml.gz")
        candidate_sitemaps.add(f"{parsed.scheme}://{parsed.hostname}/sitemap_index.xml")
        candidate_sitemaps.add(
            f"{parsed.scheme}://{parsed.hostname}/sitemap_index.xml.gz"
        )
        candidate_sitemaps.add(
            f"{parsed.scheme}://{parsed.hostname}/sitemap/sitemap.xml"
        )
        candidate_sitemaps.add(
            f"{parsed.scheme}://{parsed.hostname}/sitemap/sitemap-index.xml"
        )

        headers = HEADERS_MOBILE if mobile_first else HEADERS_DESKTOP

        async with aiohttp.ClientSession(headers=headers) as session:
            robots_text = await CrawlerService._fetch_text_url(
                session,
                robots_url,
                timeout=6,
                allow_insecure_fallback=settings.ALLOW_INSECURE_SSL_FALLBACK,
            )
            if robots_text:
                for line in robots_text.splitlines():
                    if line.lower().startswith("sitemap:"):
                        sitemap_url = line.split(":", 1)[-1].strip()
                        if sitemap_url:
                            candidate_sitemaps.add(sitemap_url)

            seen_sitemaps = set()
            while candidate_sitemaps and len(urls) < max_urls:
                sitemap_url = candidate_sitemaps.pop()
                if not sitemap_url or sitemap_url in seen_sitemaps:
                    continue
                seen_sitemaps.add(sitemap_url)

                xml_text = await CrawlerService._fetch_text_url(
                    session,
                    sitemap_url,
                    timeout=10,
                    allow_insecure_fallback=settings.ALLOW_INSECURE_SSL_FALLBACK,
                )
                if not xml_text:
                    continue

                locs, is_index = CrawlerService._parse_sitemap_xml(xml_text)
                if is_index:
                    for loc in locs:
                        if loc and loc not in seen_sitemaps:
                            candidate_sitemaps.add(loc)
                    continue

                for loc in locs:
                    normalized = CrawlerService.normalize_url(
                        loc, base_root, allow_subdomains=allow_subdomains
                    )
                    if normalized and normalized not in urls:
                        urls.append(normalized)
                        if len(urls) >= max_urls:
                            break

        return urls

    @staticmethod
    async def crawl_site(
        base_url: str,
        max_pages: int = 1000,
        allow_subdomains: bool = False,
        callback: Optional[Callable[[Optional[str], str], None]] = None,
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
        queue: asyncio.Queue[str] = asyncio.Queue()
        visited: Set[str] = set()

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
            try:
                from app.core.config import settings

                respect_robots = getattr(settings, "RESPECT_ROBOTS", False)
            except Exception:
                respect_robots = False

            await queue.put(start_url)
            visited.add(start_url)

            # Seed con URLs desde sitemap si están disponibles
            try:
                sitemap_urls = await CrawlerService.fetch_sitemap_urls(
                    base_url,
                    allow_subdomains=allow_subdomains,
                    max_urls=max_pages,
                    mobile_first=mobile_first,
                )
                for sm_url in sitemap_urls:
                    if len(visited) >= max_pages:
                        break
                    if sm_url not in visited:
                        visited.add(sm_url)
                        await queue.put(sm_url)
            except Exception as e:
                logger.warning(f"Error obteniendo sitemap para {base_url}: {e}")

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
                        html = None  # Initialize html to None
                        try:
                            # Intento normal
                            try:
                                if respect_robots and rp and hasattr(rp, "can_fetch"):
                                    if not rp.can_fetch("*", url):
                                        logger.debug(f"Bloqueado por robots.txt: {url}")
                                        if callback:
                                            callback(url, "blocked")
                                        continue

                                async with session.get(
                                    url, allow_redirects=True
                                ) as resp:
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
                                    else:
                                        logger.debug(
                                            f"Ignorado [status {resp.status}] {url}"
                                        )
                                        if callback:
                                            callback(url, "skipped")
                            except Exception as e:
                                if not settings.ALLOW_INSECURE_SSL_FALLBACK:
                                    logger.error(
                                        f"Error inicial en crawler para {url}: {e}. Fallback SSL inseguro deshabilitado."
                                    )
                                else:
                                    logger.warning(
                                        f"Error inicial en crawler para {url}: {e}. Reintentando sin SSL por configuración explícita..."
                                    )
                                    # Reintento sin SSL
                                    connector_no_ssl = aiohttp.TCPConnector(ssl=False)
                                    async with aiohttp.ClientSession(
                                        connector=connector_no_ssl, headers=headers
                                    ) as secure_session:
                                        async with secure_session.get(
                                            url, allow_redirects=True
                                        ) as resp:
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

                            if html:
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
                                    if link not in visited and len(visited) < max_pages:
                                        visited.add(link)
                                        await queue.put(link)
                                        logger.info(f"Encontrado: {link}")
                                        if callback:
                                            callback(link, "found")

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
    async def get_page_content(
        url: str, timeout: int = 10, mobile: bool = True
    ) -> Optional[str]:
        """
        Obtiene el contenido HTML de una página.

        Args:
            url: URL a descargar
            timeout: Timeout en segundos

        Returns:
            Contenido HTML o None si falla
        """
        try:
            current_url = normalize_outbound_url(url)
            if not current_url:
                logger.warning("URL inválida para descarga de contenido")
                return None

            timeout_config = aiohttp.ClientTimeout(total=timeout)
            headers = HEADERS_MOBILE if mobile else HEADERS_DESKTOP
            max_redirect_hops = 5

            async with aiohttp.ClientSession(
                headers=headers, timeout=timeout_config
            ) as session:
                for _ in range(max_redirect_hops + 1):
                    if not is_safe_outbound_url(current_url):
                        logger.warning(
                            "Bloqueado por política SSRF al descargar contenido: %s",
                            current_url,
                        )
                        return None

                    async with session.get(current_url, allow_redirects=False) as resp:
                        if resp.status in {301, 302, 303, 307, 308}:
                            location = resp.headers.get("Location")
                            if not location:
                                return None
                            next_url = normalize_outbound_url(
                                urljoin(str(resp.url), location)
                            )
                            if not next_url or not is_safe_outbound_url(next_url):
                                logger.warning(
                                    "Redirect bloqueado por política SSRF: %s -> %s",
                                    current_url,
                                    location,
                                )
                                return None
                            current_url = next_url
                            continue

                        if resp.status == 200:
                            try:
                                return await resp.text()
                            except Exception:
                                raw = await resp.read()
                                return raw.decode(errors="ignore")

                        logger.warning(
                            "Error descargando %s: status %s", current_url, resp.status
                        )
                        return None

                logger.warning(
                    "Demasiados redirects al descargar contenido: %s", current_url
                )
                return None

        except Exception:
            logger.exception("Error descargando contenido")
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
