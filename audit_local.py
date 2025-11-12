#!/usr/bin/env python3
# audit_local.py
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re, json, logging
from dateutil import parser as dateparser
from utils import now_iso, save_json

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("audit_local")

# Headers para simular un navegador y evitar 403 Forbidden
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}


async def fetch_text(session, url, timeout=20):
    try:
        # Pasamos los headers en la sesión, así que no es necesario pasarlos aquí
        async with session.get(url, timeout=timeout) as resp:
            text = await resp.text(errors="ignore")
            return resp.status, text, resp.headers.get("content-type", "")
    except Exception as e:
        logger.error("fetch_text error: %s", e)
        return None, None, None


def snippet(el, maxlen=200):
    if not el:
        return ""
    txt = " ".join(el.stripped_strings)
    return txt[:maxlen] + ("…" if len(txt) > maxlen else "")


def analyze_structure(soup):
    h1s = soup.find_all("h1")
    h1_status = "pass" if len(h1s) == 1 else ("warn" if len(h1s) > 1 else "fail")
    h1_details = {"count": len(h1s), "example": snippet(h1s[0]) if h1s else ""}

    headers = soup.find_all(re.compile("^h[1-6]$"))
    header_hierarchy_issues = []
    last_level = 0
    last_header_tag = None  # Guardar el tag anterior

    for h in headers:
        level = int(h.name[1])
        if last_level and (level - last_level) > 1:
            # MODIFICADO: Añadir snippets de HTML
            header_hierarchy_issues.append(
                {
                    "prev_level": last_level,
                    "current_level": level,
                    "text": snippet(h),
                    "prev_tag_html": str(last_header_tag),  # NUEVO
                    "current_tag_html": str(h),  # NUEVO
                }
            )
        last_level = level
        last_header_tag = h  # NUEVO: Actualizar el tag anterior

    lists = soup.find_all(["ul", "ol"])
    tables = soup.find_all("table")
    semantic_tags = ["article", "section", "nav", "main", "aside", "figure"]
    semantic_found = {t: bool(soup.find(t)) for t in semantic_tags}
    semantic_score = round(
        sum(1 for v in semantic_found.values() if v) / len(semantic_tags) * 100, 1
    )

    return {
        "h1_check": {"status": h1_status, "details": h1_details},
        "header_hierarchy": {
            "issues": header_hierarchy_issues
        },  # AHORA CONTIENE SNIPPETS
        "list_usage": {"count": len(lists)},
        "table_usage": {"count": len(tables)},
        "semantic_html": {"score_percent": semantic_score, "found": semantic_found},
    }


def analyze_content(soup):
    paragraphs = soup.find_all("p")
    long_paragraphs = [p for p in paragraphs if len(" ".join(p.stripped_strings)) > 400]
    faqs = []
    for h in soup.find_all(re.compile("^h[2-3]$")):
        txt = " ".join(h.stripped_strings).strip()
        if txt.endswith("?"):
            nxt = h.find_next_sibling(["p", "div", "ul", "ol"])
            faqs.append({"question": txt, "answer_snippet": snippet(nxt)})
    sampled = [
        " ".join(h.stripped_strings).lower()
        for h in soup.find_all(re.compile("^h[2-3]$"))[:10]
    ]
    conv_hits = sum(
        1
        for s in sampled
        if any(
            tok in s
            for tok in ["how", "what", "why", "you", "?", "cómo", "qué", "por qué"]
        )
    )
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
                p.text.strip().startswith(tuple(["In summary", "TL;DR", "Resumen"]))
                for p in paragraphs[:3]
            )
            else "warn"
        },
    }


def analyze_eeat(soup, page_url):
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
                el.get("content", "") if el.name == "meta" else el.get_text(strip=True)
            )
            break
    date_candidates = []
    t = soup.find("time")
    if t and t.get("datetime"):
        date_candidates.append(t.get("datetime"))
    meta_date = soup.find("meta", {"property": "article:published_time"})
    if meta_date and meta_date.get("content"):
        date_candidates.append(meta_date.get("content"))
    text = " ".join(
        [s.get_text(separator=" ") for s in soup.find_all(["p", "span", "div"])][:60]
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
            parsed_dates.append(dateparser.parse(d, fuzzy=True).isoformat())
        except Exception:
            pass
    external_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if (
            href.startswith("http")
            and urlparse(href).netloc != urlparse(page_url).netloc
        ):
            external_links.append(href)
    authoritative = [u for u in external_links if re.search(r"\.(gov|edu|org)\b", u)]
    transparency = {
        "about": bool(soup.find("a", href=re.compile(r"about", re.I))),
        "contact": bool(soup.find("a", href=re.compile(r"contact", re.I))),
        "privacy": bool(soup.find("a", href=re.compile(r"privacy", re.I))),
    }
    return {
        "author_presence": {"status": "pass" if author else "fail", "details": author},
        "citations_and_sources": {
            "external_links": len(external_links),
            "authoritative_links": len(authoritative),
        },
        "content_freshness": {"dates_found": parsed_dates},
        "transparency_signals": transparency,
    }


# <<< MODIFICADO: AHORA GUARDA EL JSON-LD CRUDO (RAW)
def analyze_schema(soup):
    jsonld_list = []
    raw_jsonld_blocks = []  # <<< NUEVO: Guardar el texto crudo

    for script in soup.find_all("script", type=lambda x: x and "ld+json" in x.lower()):
        try:
            txt = script.string or script.get_text()
            if not txt:
                continue

            raw_jsonld_blocks.append(txt.strip())  # <<< NUEVO: Guardar el bloque crudo
            parsed = json.loads(txt)

            if isinstance(parsed, list):
                jsonld_list.extend(parsed)
            else:
                jsonld_list.append(parsed)
        except Exception:
            continue

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
        "raw_jsonld": raw_jsonld_blocks,  # <<< NUEVO: Devolver los bloques crudos
        "recommendations": "Add FAQPage, Article, Author JSON-LD where relevant"
        if not jsonld_list
        else "Review and enrich types if needed",
    }


def check_meta_robots(soup):
    m = soup.find("meta", attrs={"name": "robots"})
    return m["content"] if m and m.get("content") else ""


def build_fallback_markdown(
    url, structure, content, eeat, schema, meta_robots, status=200
):
    md = []
    md.append(f"# Informe de Auditoría GEO para {url}")
    md.append(f"*Generado:* {now_iso()} UTC")

    if status != 200:
        md.append(f"\n---\n**ADVERTENCIA: Falló la auditoría local**")
        md.append(f"**El servidor respondió con el código de estado: {status}**")
        md.append(
            "El análisis siguiente se basa en una página de error (ej. '403 Forbidden') y NO en el contenido real."
        )
        md.append(
            f"El H1 encontrado fue: {structure['h1_check']['details'].get('example', 'N/A')}"
        )
        md.append("\n---\n")
        return "\n".join(md)

    md.append("\n---\n")
    md.append("## 1. Análisis Estructural y Técnico")
    md.append(
        f"- **H1:** {structure['h1_check']['status']}, {structure['h1_check']['details']}"
    )
    # MODIFICADO: Mostrar snippets si existen
    md.append(f"- **Header issues:** {len(structure['header_hierarchy']['issues'])}")
    if structure["header_hierarchy"]["issues"]:
        ex = structure["header_hierarchy"]["issues"][0]
        md.append(
            f"  - *Ejemplo de error:* Se encontró `{ex.get('current_tag_html','N/A')}` después de `{ex.get('prev_tag_html','N/A')}`"
        )
    md.append(
        f"- **Listas:** {structure['list_usage']['count']}, **Tablas:** {structure['table_usage']['count']}"
    )
    md.append(
        f"- **HTML semántico score:** {structure['semantic_html']['score_percent']}%"
    )
    md.append("\n---\n")
    md.append("## 2. Análisis de Contenido y Semántica")
    md.append(f"- Fragment clarity score: {content['fragment_clarity']['score']}")
    md.append(f"- Conversational tone: {content['conversational_tone']['score']}/10")
    md.append(
        f"- FAQs detected: {len(content['question_targeting'].get('examples',[]))}"
    )
    md.append("\n---\n")
    md.append("## 3. Auditoría E-E-A-T")
    md.append(f"- Author presence: {eeat['author_presence']}")
    md.append(
        f"- Citations: external={eeat['citations_and_sources']['external_links']}, authoritative={eeat['citations_and_sources']['authoritative_links']}"
    )
    md.append("\n---\n")
    md.append("## 4. Schema.org")
    md.append(
        f"- JSON-LD found: {schema['schema_presence']['status']}, types: {schema['schema_types']}"
    )
    # <<< NUEVO: Mostrar el schema crudo en el fallback
    if schema["raw_jsonld"]:
        md.append("- **Schema Crudo Encontrado:**")
        md.append(
            f"```json\n{schema['raw_jsonld'][0]}\n```"
        )  # Muestra el primer bloque
    md.append("\n---\n")
    md.append("## Gobernanza / robots")
    md.append(f"- meta robots: \"{meta_robots or 'no encontrado'}\"")
    md.append("\n---\n")
    md.append("## Resumen ejecutivo (3 prioridades)")
    md.append(
        "1. Fix H1 and header hierarchy; 2. Add JSON-LD and author biographies; 3. Fragment content into Q&A blocks and lists."
    )
    return "\n".join(md)


async def run_local_audit(url, output_json="examples/sample_report.json"):
    if not urlparse(url).scheme:
        url = "https://" + url

    # Crear la sesión de AIOHTTP con los headers
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        status, html, ctype = await fetch_text(session, url)

        if status is None:
            status = 500  # Simular un error interno si la descarga falló

        soup = BeautifulSoup(html or "", "html.parser")

        # Correr análisis incluso si es una página de error, para reportar el H1 (ej. "403 Forbidden")
        structure = analyze_structure(soup)
        content = analyze_content(soup)
        eeat = analyze_eeat(soup, url)
        schema = analyze_schema(soup)
        meta_robots = check_meta_robots(soup)

        summary = {
            "url": url,
            "status": status,
            "content_type": ctype,
            "generated_at": now_iso(),
            "structure": structure,
            "content": content,
            "eeat": eeat,
            "schema": schema,  # <<< AHORA CONTIENE 'raw_jsonld'
            "meta_robots": meta_robots,
        }

        if status != 200:
            logger.warning(
                f"Failed to fetch {url} with status {status}. Results will be based on error page."
            )

        # Guardar el JSON ANTES de construir el fallback MD
        save_json(output_json, summary)

        md = build_fallback_markdown(
            url, structure, content, eeat, schema, meta_robots, status=status
        )
        return summary, md


if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else None
    out = sys.argv[2] if len(sys.argv) > 2 else "examples/sample_report.json"
    if not url:
        print("Usage: python audit_local.py <url> [output_json]")
    else:
        s, md = asyncio.run(run_local_audit(url, out))
        with open("examples/fallback_report.md", "w", encoding="utf-8") as f:
            f.write(md)
        print("Saved summary and fallback_report.md")
