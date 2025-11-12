#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_local_service.py - Servicio de auditoría local

Envuelve la funcionalidad del audit_local.py original en una clase de servicio
para auditoría de páginas individuales.

Proporciona:
- Análisis de estructura HTML
- Análisis de contenido (claridad, tono)
- Auditoría E-E-A-T
- Extracción de Schema.org
- Validación de meta robots
- Generación de reportes markdown
"""

import asyncio
import aiohttp
import logging
import json
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Headers para simular navegador
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/91.0.4472.124 Safari/537.36"
}


class AuditLocalService:
    """
    Servicio de auditoría local de páginas web.

    Proporciona métodos para analizar estructura, contenido, EEAT,
    schema markup y generar reportes markdown.
    """

    @staticmethod
    def now_iso() -> str:
        """Retorna timestamp ISO 8601 actual."""
        return datetime.utcnow().isoformat() + "Z"

    @staticmethod
    def snippet(element: Optional[Any], maxlen: int = 200) -> str:
        """
        Extrae un snippet de texto de un elemento HTML.

        Args:
            element: Elemento BeautifulSoup
            maxlen: Longitud máxima

        Returns:
            Texto resumido
        """
        if not element:
            return ""
        txt = (
            " ".join(element.stripped_strings)
            if hasattr(element, "stripped_strings")
            else str(element)
        )
        return txt[:maxlen] + ("…" if len(txt) > maxlen else "")

    @staticmethod
    async def fetch_text(
        session: aiohttp.ClientSession, url: str, timeout: int = 20
    ) -> Tuple[Optional[int], Optional[str], str]:
        """
        Descarga el contenido de una URL.

        Args:
            session: Sesión aiohttp
            url: URL a descargar
            timeout: Timeout en segundos

        Returns:
            Tupla (status, html, content_type) o (None, None, "") si falla
        """
        try:
            async with session.get(url, timeout=timeout) as resp:
                text = await resp.text(errors="ignore")
                content_type = resp.headers.get("content-type", "")
                return resp.status, text, content_type
        except Exception as e:
            logger.error(f"Error descargando {url}: {e}")
            return None, None, ""

    @staticmethod
    def analyze_structure(soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Analiza la estructura técnica de una página.

        Verifica:
        - H1 (debe haber exactamente 1)
        - Jerarquía de headers
        - Uso de listas y tablas
        - HTML semántico

        Args:
            soup: BeautifulSoup de la página

        Returns:
            Diccionario con análisis de estructura
        """
        # Análisis de H1
        h1s = soup.find_all("h1")
        h1_status = "pass" if len(h1s) == 1 else ("warn" if len(h1s) > 1 else "fail")
        h1_details = {
            "count": len(h1s),
            "example": AuditLocalService.snippet(h1s[0]) if h1s else "",
        }

        # Análisis de jerarquía de headers
        headers = soup.find_all(re.compile("^h[1-6]$"))
        header_hierarchy_issues = []
        last_level = 0
        last_header_tag = None

        for h in headers:
            level = int(h.name[1])
            if last_level and (level - last_level) > 1:
                header_hierarchy_issues.append(
                    {
                        "prev_level": last_level,
                        "current_level": level,
                        "text": AuditLocalService.snippet(h),
                        "prev_tag_html": str(last_header_tag)
                        if last_header_tag
                        else "",
                        "current_tag_html": str(h),
                    }
                )
            last_level = level
            last_header_tag = h

        # Análisis de semántica
        lists = soup.find_all(["ul", "ol"])
        tables = soup.find_all("table")
        semantic_tags = ["article", "section", "nav", "main", "aside", "figure"]
        semantic_found = {t: bool(soup.find(t)) for t in semantic_tags}
        semantic_score = round(
            sum(1 for v in semantic_found.values() if v) / len(semantic_tags) * 100, 1
        )

        return {
            "h1_check": {"status": h1_status, "details": h1_details},
            "header_hierarchy": {"issues": header_hierarchy_issues},
            "list_usage": {"count": len(lists)},
            "table_usage": {"count": len(tables)},
            "semantic_html": {"score_percent": semantic_score, "found": semantic_found},
        }

    @staticmethod
    def analyze_content(soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Analiza el contenido de la página.

        Evalúa:
        - Claridad de fragmentos
        - Tono conversacional
        - Preguntas dirigidas (FAQs)
        - Estilo pirámide invertida

        Args:
            soup: BeautifulSoup de la página

        Returns:
            Diccionario con análisis de contenido
        """
        paragraphs = soup.find_all("p")
        long_paragraphs = [
            p for p in paragraphs if len(" ".join(p.stripped_strings)) > 400
        ]

        # Buscar FAQs
        faqs = []
        for h in soup.find_all(re.compile("^h[2-3]$")):
            txt = " ".join(h.stripped_strings).strip()
            if txt.endswith("?"):
                nxt = h.find_next_sibling(["p", "div", "ul", "ol"])
                faqs.append(
                    {"question": txt, "answer_snippet": AuditLocalService.snippet(nxt)}
                )

        # Evaluar tono conversacional
        sampled = [
            " ".join(h.stripped_strings).lower()
            for h in soup.find_all(re.compile("^h[2-3]$"))[:10]
        ]
        conv_tokens = ["how", "what", "why", "you", "?", "cómo", "qué", "por qué"]
        conv_hits = sum(1 for s in sampled if any(tok in s for tok in conv_tokens))
        conversational_score = round((conv_hits / max(1, len(sampled))) * 10, 1)

        return {
            "fragment_clarity": {
                "score": max(1, 10 - len(long_paragraphs)),
                "details": f"long_paragraphs={len(long_paragraphs)}",
            },
            "conversational_tone": {
                "score": conversational_score,
                "details": "higher is more conversational",
            },
            "question_targeting": {
                "status": "pass" if len(faqs) > 0 else "warn",
                "examples": faqs[:5],
            },
            "inverted_pyramid_style": {
                "status": "pass"
                if any(
                    p.text.strip().startswith(("In summary", "TL;DR", "Resumen"))
                    for p in paragraphs[:3]
                )
                else "warn"
            },
        }

    @staticmethod
    def analyze_eeat(soup: BeautifulSoup, page_url: str) -> Dict[str, Any]:
        """
        Analiza E-E-A-T (Expertise, Authoritativeness, Trustworthiness).

        Verifica:
        - Presencia de autor
        - Citas y fuentes
        - Frescura del contenido
        - Señales de transparencia

        Args:
            soup: BeautifulSoup de la página
            page_url: URL de la página

        Returns:
            Diccionario con análisis E-E-A-T
        """
        # Detectar autor
        author = ""
        for sel in [
            "meta[name='author']",
            "meta[property='article:author']",
            ".author",
            ".byline",
        ]:
            el = soup.select_one(sel)
            if el:
                author = (
                    el.get("content", "")
                    if el.name == "meta"
                    else el.get_text(strip=True)
                )
                break

        # Detectar fechas
        date_candidates = []
        t = soup.find("time")
        if t and t.get("datetime"):
            date_candidates.append(t.get("datetime"))

        meta_date = soup.find("meta", {"property": "article:published_time"})
        if meta_date and meta_date.get("content"):
            date_candidates.append(meta_date.get("content"))

        text = " ".join(
            [s.get_text(separator=" ") for s in soup.find_all(["p", "span", "div"])][
                :60
            ]
        )

        maybe_dates = re.findall(
            r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)[^\n]{0,40})\b",
            text,
            flags=re.I,
        )
        date_candidates.extend(maybe_dates[:3])
        parsed_dates = []
        for d in date_candidates:
            try:
                from dateutil import parser as dateparser

                parsed_dates.append(dateparser.parse(d, fuzzy=True).isoformat())
            except Exception:
                pass

        # Analizar enlaces externos
        external_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if (
                href.startswith("http")
                and urlparse(href).netloc != urlparse(page_url).netloc
            ):
                external_links.append(href)

        authoritative = [
            u for u in external_links if re.search(r"\.(gov|edu|org)\b", u)
        ]

        # Señales de transparencia
        transparency = {
            "about": bool(soup.find("a", href=re.compile(r"about", re.I))),
            "contact": bool(soup.find("a", href=re.compile(r"contact", re.I))),
            "privacy": bool(soup.find("a", href=re.compile(r"privacy", re.I))),
        }

        return {
            "author_presence": {
                "status": "pass" if author else "fail",
                "details": author,
            },
            "citations_and_sources": {
                "external_links": len(external_links),
                "authoritative_links": len(authoritative),
            },
            "content_freshness": {"dates_found": parsed_dates},
            "transparency_signals": transparency,
        }

    @staticmethod
    def analyze_schema(soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extrae y analiza Schema.org (JSON-LD).

        Args:
            soup: BeautifulSoup de la página

        Returns:
            Diccionario con análisis de schema
        """
        jsonld_list = []
        raw_jsonld_blocks = []

        for script in soup.find_all(
            "script", type=lambda x: x and "ld+json" in x.lower()
        ):
            try:
                txt = script.string or script.get_text()
                if not txt:
                    continue

                raw_jsonld_blocks.append(txt.strip())
                parsed = json.loads(txt)

                if isinstance(parsed, list):
                    jsonld_list.extend(parsed)
                else:
                    jsonld_list.append(parsed)
            except Exception:
                continue

        # Extraer tipos de schema
        types = []
        for block in jsonld_list:
            if isinstance(block, dict):
                t = block.get("@type") or block.get("type")
                if isinstance(t, list):
                    types.extend(t)
                elif t:
                    types.append(t)

        return {
            "schema_presence": {
                "status": "present" if len(jsonld_list) else "absent",
                "details": f"count={len(jsonld_list)}",
            },
            "schema_types": list(dict.fromkeys(types)),
            "raw_jsonld": raw_jsonld_blocks,
            "recommendations": (
                "Add FAQPage, Article, Author JSON-LD where relevant"
                if not jsonld_list
                else "Review and enrich types if needed"
            ),
        }

    @staticmethod
    def check_meta_robots(soup: BeautifulSoup) -> str:
        """
        Extrae el meta robots de la página.

        Args:
            soup: BeautifulSoup de la página

        Returns:
            Contenido del meta robots o string vacío
        """
        m = soup.find("meta", attrs={"name": "robots"})
        return m["content"] if m and m.get("content") else ""

    @staticmethod
    def build_fallback_markdown(
        url: str,
        structure: Dict,
        content: Dict,
        eeat: Dict,
        schema: Dict,
        meta_robots: str,
        status: int = 200,
    ) -> str:
        """
        Construye un reporte markdown desde los datos analizados.

        Args:
            url: URL auditada
            structure: Análisis de estructura
            content: Análisis de contenido
            eeat: Análisis E-E-A-T
            schema: Análisis de schema
            meta_robots: Meta robots content
            status: HTTP status code

        Returns:
            Markdown del reporte
        """
        md = []
        md.append(f"# Informe de Auditoría GEO para {url}")
        md.append(f"*Generado:* {AuditLocalService.now_iso()} UTC")

        if status != 200:
            md.append(f"\n---\n**ADVERTENCIA: Falló la auditoría local**")
            md.append(f"**El servidor respondió con el código de estado: {status}**")
            md.append(
                "El análisis siguiente se basa en una página de error "
                "(ej. '403 Forbidden') y NO en el contenido real."
            )
            md.append(
                f"El H1 encontrado fue: "
                f"{structure['h1_check']['details'].get('example', 'N/A')}"
            )
            md.append("\n---\n")
            return "\n".join(md)

        md.append("\n---\n")
        md.append("## 1. Análisis Estructural y Técnico")
        md.append(
            f"- **H1:** {structure['h1_check']['status']}, {structure['h1_check']['details']}"
        )

        md.append(
            f"- **Header issues:** {len(structure['header_hierarchy']['issues'])}"
        )
        if structure["header_hierarchy"]["issues"]:
            ex = structure["header_hierarchy"]["issues"][0]
            md.append(
                f"  - *Ejemplo de error:* Se encontró "
                f"`{ex.get('current_tag_html', 'N/A')}` "
                f"después de `{ex.get('prev_tag_html', 'N/A')}`"
            )

        md.append(
            f"- **Listas:** {structure['list_usage']['count']}, "
            f"**Tablas:** {structure['table_usage']['count']}"
        )
        md.append(
            f"- **HTML semántico score:** {structure['semantic_html']['score_percent']}%"
        )
        md.append("\n---\n")

        md.append("## 2. Análisis de Contenido y Semántica")
        md.append(f"- Fragment clarity score: {content['fragment_clarity']['score']}")
        md.append(
            f"- Conversational tone: {content['conversational_tone']['score']}/10"
        )
        md.append(
            f"- FAQs detected: {len(content['question_targeting'].get('examples', []))}"
        )

        md.append("\n---\n")
        md.append("## 3. Auditoría E-E-A-T")
        md.append(f"- Author presence: {eeat['author_presence']}")
        md.append(
            f"- Citations: "
            f"external={eeat['citations_and_sources']['external_links']}, "
            f"authoritative={eeat['citations_and_sources']['authoritative_links']}"
        )

        md.append("\n---\n")
        md.append("## 4. Schema.org")
        md.append(
            f"- JSON-LD found: {schema['schema_presence']['status']}, "
            f"types: {schema['schema_types']}"
        )

        if schema["raw_jsonld"]:
            md.append("- **Schema Crudo Encontrado:**")
            md.append(f"```json\n{schema['raw_jsonld'][0]}\n```")

        md.append("\n---\n")
        md.append("## Gobernanza / robots")
        md.append(f'- meta robots: "{meta_robots or "no encontrado"}"')

        md.append("\n---\n")
        md.append("## Resumen ejecutivo (3 prioridades)")
        md.append(
            "1. Fix H1 and header hierarchy; "
            "2. Add JSON-LD and author biographies; "
            "3. Fragment content into Q&A blocks and lists."
        )

        return "\n".join(md)

    @staticmethod
    async def run_local_audit(
        url: str, timeout: int = 20
    ) -> Tuple[Dict[str, Any], str]:
        """
        Ejecuta una auditoría local completa de una URL.

        Args:
            url: URL a auditar
            timeout: Timeout en segundos

        Returns:
            Tupla (summary_dict, markdown_report)

        Example:
            >>> summary, md = await run_local_audit('https://example.com')
            >>> print(summary['structure']['h1_check']['status'])
            pass
        """
        # Asegurar que URL tenga scheme
        if not urlparse(url).scheme:
            url = "https://" + url

        async with aiohttp.ClientSession(headers=HEADERS) as session:
            status, html, ctype = await AuditLocalService.fetch_text(
                session, url, timeout
            )

            if status is None:
                status = 500

            soup = BeautifulSoup(html or "", "html.parser")

            # Ejecutar análisis
            structure = AuditLocalService.analyze_structure(soup)
            content = AuditLocalService.analyze_content(soup)
            eeat = AuditLocalService.analyze_eeat(soup, url)
            schema = AuditLocalService.analyze_schema(soup)
            meta_robots = AuditLocalService.check_meta_robots(soup)

            summary = {
                "url": url,
                "status": status,
                "content_type": ctype,
                "generated_at": AuditLocalService.now_iso(),
                "structure": structure,
                "content": content,
                "eeat": eeat,
                "schema": schema,
                "meta_robots": meta_robots,
            }

            if status != 200:
                logger.warning(
                    f"Failed to fetch {url} with status {status}. "
                    "Results will be based on error page."
                )

            # Construir markdown
            md = AuditLocalService.build_fallback_markdown(
                url, structure, content, eeat, schema, meta_robots, status=status
            )

            return summary, md


# Funciones de compatibilidad
async def run_local_audit(url: str, timeout: int = 20) -> Tuple[Dict[str, Any], str]:
    """Wrapper para compatibilidad con código existente."""
    return await AuditLocalService.run_local_audit(url, timeout)
