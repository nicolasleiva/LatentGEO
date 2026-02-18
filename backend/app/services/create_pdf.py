#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# create_pdf.py (v2.21-minimal-final-6-annex-pages)
# Código en inglés; comentarios en español.
# Ajustes:
# - Corregido crash 'Not enough horizontal space'
# - Actualizado a la API moderna de fpdf2 (XPos/YPos) para eliminar warnings
# - Añadido pdf.add_page() antes de cada Anexo para forzar saltos de página

import glob
import json
import logging
import math
import os
import re
import sys
import traceback
from datetime import datetime

# --- INICIO DE LA CORRECCIÓN ---
# Definir FPDF_AVAILABLE para que otros scripts puedan importarlo
try:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    FPDF_AVAILABLE = True
except Exception as e:
    logging.warning(
        f"Librería FPDF (fpdf2) no encontrada: {e}. El script puede correr, pero no generará PDFs."
    )
    FPDF_AVAILABLE = False

    # Clases "Dummy" para evitar que el resto del archivo falle al ser importado
    class FPDF:
        def __init__(self, *args, **kwargs):
            pass

        def add_page(self, *args, **kwargs):
            pass

        def set_font(self, *args, **kwargs):
            pass

        def set_margins(self, *args, **kwargs):
            pass

        def set_auto_page_break(self, *args, **kwargs):
            pass

        def alias_nb_pages(self, *args, **kwargs):
            pass

        def output(self, *args, **kwargs):
            logging.error("Llamada a 'output' de PDF fallida. FPDF no está instalado.")
            pass

        def __getattr__(self, name):
            def dummy_method(*args, **kwargs):
                pass

            return dummy_method

    class XPos:
        pass

    class YPos:
        pass


# --- FIN DE LA CORRECCIÓN ---


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
# -------------------- Configurable --------------------
BASE_FONT_SIZE = 11
MONO_FONT_SIZE = 6
TABLE_FONT_SIZE = 9
LINE_HEIGHT = 5.0
JSON_LINE_HEIGHT = 4.5
JSON_PADDING = 4
HEADING_FONT_SIZE = 16

PAGE_MARGIN_MM = 16
HEADER_HEIGHT_MM = 14
CONTENT_PADDING_TOP = 6

TOC_TITLE = "Table of Contents"
REPORT_TITLE_PREFIX = "GEO Audit Report"
FOOTER_LEFT = ""
FOOTER_RIGHT = "Audit"
PREPARED_BY_LABEL = "Prepared by"

# Colores sobrios
ACCENT_COLOR = (60, 60, 60)
HEADER_BG = (250, 250, 250)
JSON_BOX_FILL = (250, 250, 250)
JSON_BOX_BORDER = (220, 220, 220)

# Rutas de fuentes (priorizar local, fallback a raíz del proyecto)
_base_dir = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(_base_dir, "fonts")
if not os.path.exists(FONT_DIR) or not os.listdir(FONT_DIR):
    # Intentar buscar en la raíz del proyecto (3 niveles arriba si está en backend/app/services)
    _root_fonts = os.path.abspath(os.path.join(_base_dir, "..", "..", "..", "fonts"))
    if os.path.exists(_root_fonts):
        FONT_DIR = _root_fonts

FONT_REGULAR_PATH = os.path.join(FONT_DIR, "Roboto-VariableFont_wdth,wght.ttf")
FONT_BOLD_PATH = os.path.join(FONT_DIR, "Roboto-VariableFont_wdth,wght.ttf")
FONT_ITALIC_PATH = os.path.join(FONT_DIR, "Roboto-Italic-VariableFont_wdth,wght.ttf")
FONT_MONO_PATH = os.path.join(FONT_DIR, "RobotoMono-VariableFont_wght.ttf")
# ---------------------------------------------------------------------------


def clean_string_for_pdf(text):
    """Asegura que el string esté en formato amigable para PDF."""
    if not isinstance(text, str):
        text = str(text)
    # Reemplazar caracteres Unicode problemáticos
    replacements = {
        "•": "-",
        "–": "-",
        "—": "-",
        "'": "'",
        "“": '"',
        "”": '"',
        "…": "...",
        "→": "->",
        "←": "<-",
        "↑": "^",
        "↓": "v",
        "✓": "[OK]",
        "✗": "[X]",
        "★": "*",
        "©": "(c)",
        "®": "(R)",
        "™": "(TM)",
        "📚": "[LIBRO]",
        "📊": "[GRAFICO]",
        "📈": "[TENDENCIA]",
        "🔍": "[BUSCAR]",
        "✅": "[OK]",
        "❌": "[X]",
        "⚠️": "[ALERTA]",
        "💡": "[IDEA]",
        "🎯": "[OBJETIVO]",
        "🚀": "[COHETE]",
        "\u251c": "|-",  # ├
        "\u2500": "-",  # ─
        "\u2514": "|_",  # └
        "\u2502": "|",  # │
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[\U0001F300-\U0001F9FF]", "", text)

    return (
        text.replace("\r", "")
        .replace("\\r", "")
        .replace("\\n", "\n")
        .replace("\\t", "    ")
    )


def summarize_fix_plan(fix_plan_data, top_n=3):
    """Genera un resumen simple del fix_plan (fallback útil en auditorías)."""
    if not fix_plan_data:
        return {"counts": {}, "top": [], "pages_affected": 0}
    try:
        if isinstance(fix_plan_data, dict):
            items = fix_plan_data.get("items") or fix_plan_data.get("issues") or []
        elif isinstance(fix_plan_data, list):
            items = fix_plan_data
        else:
            return {"counts": {}, "top": [], "pages_affected": 0}

        counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0}
        by_page = {}
        for it in items:
            if not isinstance(it, dict):
                continue
            p = it.get("priority") or it.get("severity") or "UNKNOWN"
            counts[p] = counts.get(p, 0) + 1
            page = it.get("page_path") or it.get("url") or "global"
            by_page.setdefault(page, 0)
            by_page[page] += 1

        top = [it for it in items if isinstance(it, dict)][:top_n]
        top_summaries = []
        for it in top:
            t = it.get("description") or it.get("issue_code") or json.dumps(it)
            top_summaries.append(str(t)[:120])
        return {"counts": counts, "top": top_summaries, "pages_affected": len(by_page)}
    except Exception:
        logger.exception("Error al resumir fix_plan_data")
        return {"counts": {}, "top": [], "pages_affected": 0}


class PDFReport(FPDF):
    """Clase PDF con utilidades para el reporte profesional y minimalista."""

    def __init__(self, *args, metadata=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._fonts_added = set()
        self.setup_fonts()
        self.set_auto_page_break(True, margin=PAGE_MARGIN_MM)
        self.alias_nb_pages()
        self._toc_entries = []
        self._toc_page_no = None
        self._toc_page_count = 0
        self.metadata = metadata if isinstance(metadata, dict) else {}
        self.footer_left = str(self.metadata.get("footer_left") or FOOTER_LEFT)
        self.footer_right = str(self.metadata.get("footer_right") or FOOTER_RIGHT)
        self.report_title_prefix = str(
            self.metadata.get("report_title_prefix") or REPORT_TITLE_PREFIX
        )
        self.prepared_by = str(self.metadata.get("prepared_by") or "Auditor GEO")

        # Ajustes de márgenes consistentes
        self.set_margins(PAGE_MARGIN_MM, PAGE_MARGIN_MM, PAGE_MARGIN_MM)
        self.set_auto_page_break(auto=True, margin=PAGE_MARGIN_MM)

    def setup_fonts(self):
        """Intenta cargar fuentes locales; si no, usa las internas."""
        try:
            # FIX: Removido parámetro 'uni=True' (obsoleto)
            if os.path.exists(FONT_REGULAR_PATH):
                self.add_font("Roboto", "", FONT_REGULAR_PATH)
                self._fonts_added.add("Roboto")
            if os.path.exists(FONT_BOLD_PATH):
                self.add_font("Roboto", "B", FONT_BOLD_PATH)
                self._fonts_added.add("Roboto-B")
            if os.path.exists(FONT_ITALIC_PATH):
                self.add_font("Roboto", "I", FONT_ITALIC_PATH)
                self._fonts_added.add("Roboto-I")
            if os.path.exists(FONT_MONO_PATH):
                self.add_font("RobotoMono", "", FONT_MONO_PATH)
                self._fonts_added.add("RobotoMono")
            family = "Roboto" if "Roboto" in self._fonts_added else "helvetica"
            self.set_font(family, "", BASE_FONT_SIZE)
        except Exception:
            self.set_font("helvetica", "", BASE_FONT_SIZE)

    def header(self):
        """Encabezado sobrio: título corto en una línea y una regla."""
        # No mostrar encabezado en portada ni página TOC para mantener limpieza
        if self.page_no() == 1 or self._is_toc_page():
            return

        fam = "Roboto" if "Roboto" in self._fonts_added else "helvetica"
        self.set_y(PAGE_MARGIN_MM - 6)
        self.set_font(fam, "B" if ("Roboto-B" in self._fonts_added) else "", 10)
        title_short = self.report_title_prefix
        width = self.w - self.l_margin - self.r_margin
        self.set_text_color(*ACCENT_COLOR)
        # FIX: Reemplazado 'ln=1' por 'new_x/new_y'
        self.cell(
            width,
            HEADER_HEIGHT_MM / 2,
            title_short,
            0,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            align="L",
        )
        self.set_line_width(0.35)
        y_line = self.get_y() + 2
        self.line(self.l_margin, y_line, self.w - self.r_margin, y_line)
        self.ln(CONTENT_PADDING_TOP)

    def footer(self):
        """Pie de página con información de autor y paginación."""
        self.set_y(-12)
        fam = "Roboto" if "Roboto" in self._fonts_added else "helvetica"
        style = "I" if ("Roboto-I" in self._fonts_added or fam == "helvetica") else ""
        self.set_font(fam, style, 8)
        self.set_text_color(100)
        # Escribir autor a la izquierda y número de página a la derecha
        self.set_x(self.l_margin)
        # FIX: Reemplazado 'ln=0' por 'new_x/new_y'
        self.cell(
            0, 6, self.footer_left, 0, new_x=XPos.RIGHT, new_y=YPos.TOP, align="L"
        )
        self.set_x(self.l_margin)
        # FIX: Reemplazado 'ln=0' por 'new_x/new_y'
        self.cell(
            0,
            6,
            f"{self.footer_right}   |   Page {self.page_no()} / {{nb}}",
            0,
            new_x=XPos.RIGHT,
            new_y=YPos.TOP,
            align="R",
        )

    # -------------------- TOC / Bookmarks --------------------
    def _register_section(self, title, level, link_id=None):
        """Registra una entrada de TOC (evita duplicados)."""
        for e in self._toc_entries:
            try:
                if e.get("title") == title and int(e.get("level", 0)) == int(level):
                    if not e.get("link") and link_id:
                        e["link"] = link_id
                    return e.get("link")
            except Exception:  # nosec B112
                continue
        entry = {"title": title, "level": level, "link": link_id}
        self._toc_entries.append(entry)
        return link_id

    def _add_bookmark_compat(self, title, level=0, y=None, register=True):
        """Compatibilidad multi-versiones para bookmarks / outline."""
        try:
            link_id = self.add_link()
        except Exception:
            link_id = None
        if register:
            self._register_section(title, level, link_id=link_id)
        try:
            if link_id is not None:
                self.set_link(link_id, page=self.page_no())
        except Exception:  # nosec B110
            pass
        return link_id

    def begin_section(self, title, level=0, render_title=True):
        """
        Inicio de sección:
        - si estamos en la página del TOC, crea nueva página;
        """
        need_new_page = False
        if self._is_toc_page():
            need_new_page = True

        # (Lógica de salto automático eliminada para permitir el salto manual en create_comprehensive_pdf)

        if need_new_page:
            self.add_page()

        link_id = self._add_bookmark_compat(title, level=level, register=True)
        fam = "Roboto" if "Roboto" in self._fonts_added else "helvetica"
        style = "B" if ("Roboto-B" in self._fonts_added) else ""
        self.set_font(fam, style, HEADING_FONT_SIZE)

        if render_title:
            # Asegurar espacio para el título (10mm celda + 2mm 'ln(2)')
            self.ensure_space(12)

            self.set_x(self.l_margin)
            self.cell(0, 10, title, 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
            self.ln(2)

        self.set_font(fam, "", BASE_FONT_SIZE)
        if link_id is not None:
            try:
                self.set_link(link_id, page=self.page_no())
            except Exception:  # nosec B110
                pass

    # -------------------- Cover (Centrado) --------------------
    def create_cover_page(self, title, url, date_str, version=None):
        """Crea una portada centrada (título + metadatos) y registro en TOC."""
        self.add_page()
        fam = "Roboto" if "Roboto" in self._fonts_added else "helvetica"

        left = self.l_margin
        usable_w = self.w - self.l_margin - self.r_margin

        center_y = self.h / 2.0
        y_start = center_y - 36
        if y_start < PAGE_MARGIN_MM:
            y_start = PAGE_MARGIN_MM + 20

        self.set_xy(left, y_start)

        self.set_text_color(36, 36, 36)
        self.set_font(fam, "B" if ("Roboto-B" in self._fonts_added) else "", 26)
        for line in str(title).splitlines():
            self.multi_cell(usable_w, 12, line.strip(), 0, "C")
        self.ln(6)

        self.set_font(fam, "", 11)
        if url:
            self.multi_cell(usable_w, 7, f"{url}", 0, "C")
        if date_str:
            self.multi_cell(usable_w, 7, f"Audit Date: {date_str}", 0, "C")
        if version:
            self.multi_cell(usable_w, 7, f"Script Version: {version}", 0, "C")

        self.ln(16)

        footer_block_y = self.h - PAGE_MARGIN_MM - 40
        try:
            self.set_xy(left, footer_block_y)
            self.set_font(fam, "B" if ("Roboto-B" in self._fonts_added) else "", 11)
            self.multi_cell(
                usable_w, 7, f"{PREPARED_BY_LABEL}: {self.prepared_by}", 0, "C"
            )
            self.set_font(fam, "", 9)
            if self.footer_left:
                self.multi_cell(usable_w, 6, self.footer_left, 0, "C")
        except Exception:  # nosec B110
            pass

        try:
            self._register_section("Cover", 0, link_id=None)
        except Exception:  # nosec B110
            pass

    # -------------------- Contenido: markdown y tablas --------------------
    def clean_latin1(self, text):
        """Reemplaza caracteres Unicode no soportados por Latin-1."""
        if not isinstance(text, str):
            return str(text)

        replacements = {
            "\u201c": '"',
            "\u201d": '"',  # comillas curvas
            "\u2018": "'",
            "\u2019": "'",  # comillas simples curvas
            "\u2013": "-",
            "\u2014": "-",  # guiones
            "\u2265": ">=",
            "\u2264": "<=",  # mayor/menor igual
            "\u2026": "...",  # elipsis
            "\u2022": "-",  # duplicados por seguridad
        }
        for k, v in replacements.items():
            text = text.replace(k, v)

        # Fallback final: intentar codificar en latin-1, reemplazando errores
        try:
            text.encode("latin-1")
            return text
        except UnicodeEncodeError:
            # Reemplazar caracteres restantes por '?' o similar
            return text.encode("latin-1", "replace").decode("latin-1")

    def _sanitize_for_current_font(self, text):
        """
        Sanitiza texto para el backend de fuente activo.
        - Siempre limpia caracteres problemáticos comunes.
        - Si se usa helvetica (sin Roboto Unicode), fuerza latin-1 safe.
        """
        cleaned = clean_string_for_pdf(text or "")
        if "Roboto" not in self._fonts_added:
            cleaned = self.clean_latin1(cleaned)
        return cleaned

    def _strip_markdown_bold(self, text):
        """Elimina marcadores de negrita markdown (**texto** / __texto__)."""
        if not text:
            return text
        cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
        cleaned = re.sub(r"__(.*?)__", r"\1", cleaned)
        cleaned = cleaned.replace("**", "").replace("__", "")
        return cleaned

    def _is_toc_page(self, page_no=None):
        if self._toc_page_no is None or self._toc_page_count <= 0:
            return False
        current = page_no if page_no is not None else self.page_no()
        return (
            self._toc_page_no
            <= current
            <= (self._toc_page_no + self._toc_page_count - 1)
        )

    def _toc_header_start_y(self):
        return self.t_margin + HEADER_HEIGHT_MM + 10

    def _toc_entries_start_y(self):
        return self._toc_header_start_y() + (LINE_HEIGHT * 1.6) + 6

    def estimate_toc_pages(self, entry_count: int) -> int:
        if entry_count <= 0:
            return 1
        available = self.h - self.b_margin - self._toc_entries_start_y()
        lines_per_page = max(1, int(available // LINE_HEIGHT))
        return max(1, int(math.ceil(entry_count / lines_per_page)))

    def write_markdown_text(self, text):
        """Render simple de markdown básico y tablas estilo markdown.
        Mantiene sangrías y márgenes consistentes con la portada y TOC.
        """
        text = self._sanitize_for_current_font(text)

        fam = "Roboto" if "Roboto" in self._fonts_added else "helvetica"
        self.set_font(fam, "", BASE_FONT_SIZE)

        page_width = self.w - self.l_margin - self.r_margin
        table_line_height = max((TABLE_FONT_SIZE * 1.3) / self.k, 3.5)

        in_table = False
        table_headers = []
        table_aligns = []
        table_col_widths = []

        # Si estamos todavía en la página del TOC, decidir si crear page de contenido.
        try:
            current_is_toc = self._is_toc_page()
        except Exception:
            current_is_toc = False

        if current_is_toc:
            # encontrar primer non-empty line
            first_non_empty = None
            for line in text.splitlines():
                if line.strip():
                    first_non_empty = line.strip()
                    break
            if first_non_empty:
                # si primer bloque NO es H1, crear página de contenido ahora
                if not re.match(r"^(#{1})\s+", first_non_empty):
                    self.add_page()
            else:
                return

        for line in text.splitlines():
            cleaned_line = self._strip_markdown_bold(line)
            line_stripped = cleaned_line.strip()

            # Tablas markdown simples
            if line_stripped.startswith("|") and line_stripped.endswith("|"):
                cells = [
                    self._strip_markdown_bold(c.strip())
                    for c in line_stripped[1:-1].split("|")
                ]
                num_cols = len(cells)

                if all(bool(re.match(r"^:?-+:?$", c.strip())) for c in cells):
                    # inicio de tabla: definir alineaciones y anchos
                    in_table = True
                    table_aligns = []
                    if table_headers:
                        guessed_widths = []
                        for h in table_headers:
                            guessed_widths.append(
                                max(
                                    30,
                                    min(
                                        (self.get_string_width(h) + 2 * 3),
                                        page_width * 0.5,
                                    ),
                                )
                            )
                        total_guess = sum(guessed_widths)
                        if total_guess < page_width:
                            table_col_widths = [
                                (w / total_guess) * page_width for w in guessed_widths
                            ]
                        else:
                            table_col_widths = [page_width / num_cols] * num_cols
                    else:
                        table_col_widths = [page_width / max(1, num_cols)] * num_cols

                    for c in cells:
                        cs = c.strip()
                        if cs.startswith(":") and cs.endswith(":"):
                            table_aligns.append("C")
                        elif cs.endswith(":"):
                            table_aligns.append("R")
                        else:
                            table_aligns.append("L")

                    # render cabecera si existe
                    if table_headers:
                        self.ln(2)
                        self.set_font(fam, "B", TABLE_FONT_SIZE)
                        self.set_fill_color(245, 245, 245)
                        self.set_draw_color(210, 210, 210)
                        cell_heights = []
                        for i, header in enumerate(table_headers):
                            w = table_col_widths[i]
                            eff_w = max(6.0, w - 6)
                            text_width = max(1.0, self.get_string_width(header))
                            lines_est = max(1, math.ceil(text_width / eff_w))
                            cell_h = max(9, (lines_est * table_line_height) + 6)
                            cell_heights.append(cell_h)
                        max_h = max(cell_heights) if cell_heights else 9
                        self.ensure_space(max_h + 6)
                        start_x = self.get_x()
                        row_start_y = self.get_y()
                        for i, header in enumerate(table_headers):
                            w = table_col_widths[i]
                            align = table_aligns[i] if i < len(table_aligns) else "L"
                            try:
                                self.set_xy(start_x, row_start_y)
                                self.rect(start_x, row_start_y, w, max_h, style="DF")
                            except Exception:  # nosec B110
                                pass
                            self.set_xy(start_x + 3, row_start_y + 3)
                            self.multi_cell(
                                w - 6, table_line_height, header, border=0, align=align
                            )
                            start_x += w
                        try:
                            self.set_xy(self.l_margin, row_start_y + max_h + 4)
                        except Exception:
                            self.set_y(row_start_y + max_h + 4)
                elif in_table:
                    # filas de tabla
                    self.set_font(fam, "", TABLE_FONT_SIZE)
                    cell_heights = []
                    wrap_infos = []
                    for i, cell_text in enumerate(cells):
                        w = table_col_widths[min(i, len(table_col_widths) - 1)]
                        eff_w = max(6.0, w - 6)
                        text_width = max(1.0, self.get_string_width(cell_text))
                        lines_est = max(1, math.ceil(text_width / eff_w))
                        cell_h = max(9, (lines_est * table_line_height) + 6)
                        cell_heights.append(cell_h)
                        wrap_infos.append((cell_text, lines_est, eff_w))
                    row_h = max(cell_heights) if cell_heights else 9
                    self.ensure_space(row_h + 6)
                    start_x = self.get_x()
                    row_start_y = self.get_y()
                    self.set_draw_color(210, 210, 210)
                    for i, (cell_text, _, _) in enumerate(wrap_infos):
                        w = table_col_widths[min(i, len(table_col_widths) - 1)]
                        align = table_aligns[i] if i < len(table_aligns) else "L"
                        try:
                            self.rect(start_x, row_start_y, w, row_h)
                        except Exception:  # nosec B110
                            pass
                        try:
                            self.set_xy(start_x + 3, row_start_y + 3)
                            max_chars = int((w - 6) * 6)
                            text_to_print = (
                                cell_text
                                if len(cell_text) <= max_chars
                                else (cell_text[: max_chars - 3] + "...")
                            )
                            self.multi_cell(
                                w - 6,
                                table_line_height,
                                text_to_print,
                                border=0,
                                align=align,
                            )
                        except Exception:
                            try:
                                self.set_xy(start_x + 3, row_start_y + 3)
                                self.multi_cell(
                                    w - 6,
                                    table_line_height,
                                    cell_text[:300],
                                    border=0,
                                    align=align,
                                )
                            except Exception:  # nosec B110
                                pass
                        start_x += w
                    try:
                        self.set_xy(self.l_margin, row_start_y + row_h + 4)
                    except Exception:
                        self.set_y(row_start_y + row_h + 4)
                else:
                    table_headers = cells

            else:
                # salir de modo tabla
                if in_table:
                    in_table = False
                    table_headers = []
                    table_aligns = []
                    table_col_widths = []
                    self.ln(4)

                self.set_font(fam, "", BASE_FONT_SIZE)
                if not line.strip():
                    self.ln(4)
                    continue

                # Detect headings h1..h4
                m = re.match(r"^\s*(#{1,4})\s+(.*)", line)
                if m:
                    hashes = len(m.group(1))
                    title = self._strip_markdown_bold(m.group(2).strip())
                    level = min(hashes, 4)
                    try:
                        if level == 1:
                            self.begin_section(title, level=1, render_title=True)
                        else:
                            # Render subordinate headings (H2, H3, H4)
                            if level == 2:
                                self.ln(2)
                                self.set_font(fam, "B", 14)
                                self.set_x(self.l_margin)
                                self.multi_cell(0, LINE_HEIGHT * 1.4, title, 0, "L")
                                self.ln(1)
                            elif level == 3:
                                self.ln(1)
                                self.set_font(fam, "B", 12)
                                self.set_x(self.l_margin)
                                self.multi_cell(0, LINE_HEIGHT * 1.2, title, 0, "L")
                                self.ln(1)
                            else:
                                self.set_font(fam, "B", 11)
                                self.set_x(self.l_margin + 6)
                                self.multi_cell(0, LINE_HEIGHT, title, 0, "L")
                                self.ln(1)

                            try:
                                # Ensure subordinate headings are registered in TOC
                                link_id = self._add_bookmark_compat(
                                    title, level=level, register=True
                                )
                                if link_id is not None:
                                    self.set_link(link_id, page=self.page_no())
                            except Exception as e:
                                logger.debug(
                                    f"Error registering sub-heading {title}: {e}"
                                )

                        self.set_font(fam, "", BASE_FONT_SIZE)
                    except Exception as e:
                        logger.warning(f"Error rendering heading {title}: {e}")
                        self.multi_cell(0, LINE_HEIGHT, title, 0, "L")
                    continue

                # texto plano
                self.set_x(self.l_margin)
                self.multi_cell(0, LINE_HEIGHT, cleaned_line, 0, "L")

    # -------------------- JSON rendering (mejorada) --------------------
    def write_json_raw(self, data):
        """
        Renderiza JSON completo de forma robusta, dividiendo en páginas si es necesario.
        Evita páginas en blanco y bloques cortados incorrectamente.
        """
        # Configurar fuente monoespaciada
        mono = (
            "RobotoMono"
            if "RobotoMono" in self._fonts_added
            else ("Roboto" if "Roboto" in self._fonts_added else "helvetica")
        )
        font_size = 7
        line_height = 3.5  # mm por línea

        self.set_font(mono, "", font_size)
        self.set_fill_color(*JSON_BOX_FILL)
        self.set_draw_color(*JSON_BOX_BORDER)

        # Serializar y limpiar
        try:
            text = json.dumps(data, indent=2, ensure_ascii=False)
        except Exception:
            text = str(data)

        text = clean_string_for_pdf(text)
        lines = text.splitlines()

        if not lines:
            lines = ["(No data)"]

        # Iterar sobre las líneas e imprimir paginando manualmente
        i = 0
        total_lines = len(lines)

        while i < total_lines:
            # Calcular espacio disponible en la página actual
            current_y = self.get_y()
            page_height = self.h
            bottom_margin = self.b_margin
            space_left = page_height - bottom_margin - current_y

            # Si queda muy poco espacio (menos de 15mm), saltar de página
            # Pero solo si no estamos ya al principio de una página (para evitar bucles)
            if space_left < 15 and current_y > (self.t_margin + 20):
                self.add_page()
                current_y = self.get_y()
                space_left = page_height - bottom_margin - current_y

            # Calcular cuántas líneas caben en el espacio restante
            # Restamos 1 línea de margen de seguridad
            lines_that_fit = int(space_left / line_height) - 1

            if lines_that_fit <= 0:
                self.add_page()
                continue

            # Determinar el chunk a imprimir
            end_i = min(i + lines_that_fit, total_lines)
            chunk = lines[i:end_i]

            if not chunk:
                break

            chunk_text = "\n".join(chunk)

            # Imprimir el bloque
            # Usamos multi_cell. Como ya calculamos que cabe, no debería saltar de página automáticamente
            # salvo error de cálculo menor.
            # FIX: Asegurar posición X en margen izquierdo para evitar error de espacio horizontal
            self.set_x(self.l_margin)
            self.multi_cell(0, line_height, chunk_text, border=1, fill=True, align="L")

            # Avanzar índice
            i = end_i

        # Restaurar fuente normal al finalizar
        fam = "Roboto" if "Roboto" in self._fonts_added else "helvetica"
        self.set_font(fam, "", BASE_FONT_SIZE)
        self.ln(5)

    def write_json_summary_box(self, data, top_n=3, filename_hint=None):
        """Caja resumen de JSON (snippet) en estilo monoespaciado."""
        if data is None:
            self.set_font(
                "Roboto" if "Roboto" in self._fonts_added else "helvetica",
                "",
                BASE_FONT_SIZE,
            )
            self.multi_cell(0, JSON_LINE_HEIGHT, "(No data)", 0, "L")
            return
        try:
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            json_str = str(data)
        large = len(json_str) > 3000 or len(json_str.splitlines()) > 80
        snippet = ""
        if isinstance(data, dict):
            top_keys = list(data.keys())[:8]
            lines = []
            for k in top_keys:
                v = data.get(k)
                kv = f"{k}: {str(v)[:120]}"
                lines.append(kv)
            if "items" in data or "issues" in data:
                items = data.get("items") or data.get("issues") or []
                preview = [it for it in items if isinstance(it, dict)][:top_n]
                if preview:
                    lines.append("")
                    lines.append("Top issues:")
                    for it in preview:
                        if not it:
                            continue
                        val = it.get("description") or it.get("issue_code") or str(it)
                        lines.append(f" - {str(val)[:120]}")
            snippet = (
                "\n".join(lines) if lines else (json_str[:1200] if large else json_str)
            )
            if not snippet.strip():
                snippet = json_str[:1200]
        elif isinstance(data, list):
            snippet = f"Array length: {len(data)}\nExamples:"
            for it in data[:top_n]:
                if not it:
                    continue
                # Format based on filename_hint to handle different data types
                if filename_hint == "keywords.json":
                    val = f"{it.get('term', it.get('keyword', 'unknown'))}: {it.get('search_volume', it.get('volume', 0))} searches"
                elif filename_hint == "backlinks.json":
                    val = f"{it.get('source_url', 'unknown')} -> {it.get('target_url', 'unknown')}"
                elif filename_hint == "rankings.json":
                    val = f"{it.get('keyword', 'unknown')}: position {it.get('position', 'unknown')}"
                elif filename_hint == "llm_visibility.json":
                    val = f"{it.get('query', 'unknown')}: {'visible' if it.get('is_visible', it.get('mentioned', False)) else 'not visible'}"
                else:
                    val = it.get("description") if isinstance(it, dict) else str(it)
                snippet += f"\n - {str(val)[:120]}"
        else:
            snippet = str(data)[:800]

        mono = (
            "RobotoMono"
            if "RobotoMono" in self._fonts_added
            else ("Roboto" if "Roboto" in self._fonts_added else "helvetica")
        )
        self.set_font(mono, "", MONO_FONT_SIZE)
        self.set_fill_color(*JSON_BOX_FILL)
        self.set_draw_color(*JSON_BOX_BORDER)

        est_lines = max(3, len(snippet.splitlines()))
        est_h = est_lines * JSON_LINE_HEIGHT + JSON_PADDING
        self.ensure_space(est_h + 6)
        snippet = self._sanitize_for_current_font(snippet)
        self.multi_cell(0, JSON_LINE_HEIGHT, snippet, border=1, fill=True)
        if filename_hint:
            self.set_font(
                "Roboto" if "Roboto" in self._fonts_added else "helvetica",
                "I",
                MONO_FONT_SIZE - 1,
            )

            # --- INICIO FIX (v2): CRASH ---
            # Forzamos la posición X al margen izquierdo antes de dibujar.
            # Esto previene el FPDFException: Not enough horizontal space...
            self.set_x(self.l_margin)
            # --- FIN FIX (v2) ---

            # (Se usa multi_cell para word-wrap, como en v1)
            hint_text = self._sanitize_for_current_font(
                f"Ver anexo completo: {filename_hint}"
            )
            self.multi_cell(
                0,
                JSON_LINE_HEIGHT,
                hint_text,
                0,
                "L",
            )
        self.ln(4)

    # -------------------- Manual TOC render (más separación) --------------------
    def render_manual_toc(self):
        """Escribe el TOC en la página reservada (si existe)."""
        if self._toc_page_no is None:
            return

        # Si no hay entradas, escribir nota breve
        if not self._toc_entries:
            try:
                last_page = self.page_no()
                self.page = int(self._toc_page_no)
                # mayor separación vertical respecto del encabezado
                self.set_xy(self.l_margin, self.t_margin + HEADER_HEIGHT_MM + 10)
                self.set_font(
                    "Roboto" if "Roboto" in self._fonts_added else "helvetica", "B", 14
                )
                # FIX: Reemplazado 'ln=1' por 'new_x/new_y'
                self.cell(
                    0,
                    LINE_HEIGHT * 1.6,
                    TOC_TITLE,
                    0,
                    new_x=XPos.LMARGIN,
                    new_y=YPos.NEXT,
                    align="L",
                )
                self.ln(6)
                self.set_font(
                    "Roboto" if "Roboto" in self._fonts_added else "helvetica",
                    "",
                    BASE_FONT_SIZE,
                )
                self.multi_cell(
                    0,
                    LINE_HEIGHT,
                    "No table of contents was generated (no sections detected).",
                    0,
                    "L",
                )
                self.page = int(last_page)
            except Exception:  # nosec B110
                pass
            return

        try:
            last_page = self.page_no()
            toc_page = int(self._toc_page_no)
            toc_last_page = int(self._toc_page_no + max(1, self._toc_page_count) - 1)

            def render_toc_header(title_text):
                self.set_xy(self.l_margin, self._toc_header_start_y())
                self.set_font(
                    "Roboto" if "Roboto" in self._fonts_added else "helvetica",
                    "B",
                    14,
                )
                self.cell(
                    0,
                    LINE_HEIGHT * 1.6,
                    title_text,
                    0,
                    new_x=XPos.LMARGIN,
                    new_y=YPos.NEXT,
                    align="L",
                )
                self.ln(6)
                self.set_font(
                    "Roboto" if "Roboto" in self._fonts_added else "helvetica",
                    "",
                    BASE_FONT_SIZE,
                )

            self.page = toc_page
            render_toc_header(TOC_TITLE)

            bottom_limit = self.h - self.b_margin

            for entry in self._toc_entries:
                if not isinstance(entry, dict):
                    continue
                if (self.get_y() + LINE_HEIGHT) > bottom_limit:
                    toc_page += 1
                    if toc_page <= toc_last_page:
                        self.page = toc_page
                    else:
                        self.add_page()
                        toc_last_page = self.page_no()
                        toc_page = toc_last_page
                    render_toc_header(f"{TOC_TITLE} (cont.)")

                level = int(entry.get("level", 0) or 0)
                title = self._strip_markdown_bold(entry.get("title", "") or "")
                link = entry.get("link")
                indent_x = self.l_margin + (level * 6)
                self.set_x(indent_x)
                line_text = title
                try:
                    if link is not None:
                        self.cell(
                            0,
                            LINE_HEIGHT,
                            line_text,
                            0,
                            new_x=XPos.LMARGIN,
                            new_y=YPos.NEXT,
                            align="L",
                            link=link,
                        )
                    else:
                        self.cell(
                            0,
                            LINE_HEIGHT,
                            line_text,
                            0,
                            new_x=XPos.LMARGIN,
                            new_y=YPos.NEXT,
                            align="L",
                        )
                except Exception:
                    self.cell(
                        0,
                        LINE_HEIGHT,
                        line_text,
                        0,
                        new_x=XPos.LMARGIN,
                        new_y=YPos.NEXT,
                        align="L",
                    )

            self.page = int(last_page)
        except Exception:
            logger.exception("Error al renderizar TOC manual")

    # -------------------- Utilidades --------------------
    def ensure_space(self, needed_h):
        """Asegura que haya espacio suficiente en la página, si no añade página."""
        bottom_limit = self.h - self.b_margin
        current_y = self.get_y()
        top_limit = self.t_margin + HEADER_HEIGHT_MM
        if current_y < top_limit:
            try:
                self.set_y(top_limit)
                current_y = top_limit
            except Exception:  # nosec B110
                pass
        if (current_y + needed_h) > bottom_limit:
            self.add_page()
            try:
                self.set_xy(
                    self.l_margin,
                    self.t_margin + HEADER_HEIGHT_MM / 2 + CONTENT_PADDING_TOP,
                )
            except Exception:
                self.set_xy(self.l_margin, PAGE_MARGIN_MM + HEADER_HEIGHT_MM / 2)
            return True
        return False


# ---------------- Main generator (mejorado y minimalista) ----------------
def create_comprehensive_pdf(report_folder_path, metadata=None):
    """Genera el PDF consolidado a partir de la carpeta de reporte."""
    try:
        if not os.path.isdir(report_folder_path):
            logger.error("La carpeta no existe: %s", report_folder_path)
            return

        # Definir rutas
        pdf_file_name = (
            f"Reporte_Consolidado_{os.path.basename(report_folder_path)}.pdf"
        )
        pdf_file_path = os.path.join(report_folder_path, pdf_file_name)
        md_file = os.path.join(report_folder_path, "ag2_report.md")
        json_fix_plan_file = os.path.join(report_folder_path, "fix_plan.json")
        json_agg_summary_file = os.path.join(
            report_folder_path, "aggregated_summary.json"
        )
        json_pagespeed_file = os.path.join(report_folder_path, "pagespeed.json")
        json_keywords_file = os.path.join(report_folder_path, "keywords.json")
        json_backlinks_file = os.path.join(report_folder_path, "backlinks.json")
        json_rankings_file = os.path.join(report_folder_path, "rankings.json")
        json_llm_visibility_file = os.path.join(
            report_folder_path, "llm_visibility.json"
        )

        # DEBUG: Logs para páginas
        pages_dir = os.path.join(report_folder_path, "pages")
        page_json_files = sorted(glob.glob(os.path.join(pages_dir, "page_*.json")))
        if not page_json_files:
            # Legacy fallback: report_*.json
            page_json_files = sorted(
                glob.glob(os.path.join(pages_dir, "report_*.json"))
            )
        logger.info(f"DEBUG: Buscando reportes de páginas en: {pages_dir}")
        logger.info(
            f"DEBUG: Encontrados {len(page_json_files)} archivos: {[os.path.basename(f) for f in page_json_files]}"
        )

        # Leer Markdown
        markdown_text = ""
        if os.path.exists(md_file):
            with open(md_file, "r", encoding="utf-8") as f:
                markdown_text = f.read()

        # Leer Fix Plan
        try:
            with open(json_fix_plan_file, "r", encoding="utf-8") as f:
                fix_plan_data = json.load(f)
        except Exception:
            logger.warning("No se pudo leer fix_plan.json -> se usará lista vacía")
            fix_plan_data = []

        # Leer Aggregated Summary
        try:
            with open(json_agg_summary_file, "r", encoding="utf-8") as f:
                agg_summary_data = json.load(f)
        except Exception:
            logger.warning(
                "No se pudo leer aggregated_summary.json -> se usará diccionario vacío"
            )
            agg_summary_data = {}

        # Leer PageSpeed
        try:
            with open(json_pagespeed_file, "r", encoding="utf-8") as f:
                pagespeed_data = json.load(f)
        except Exception:
            logger.warning(
                "No se pudo leer pagespeed.json -> se usará diccionario vacío"
            )
            pagespeed_data = {}

        # Leer Keywords
        try:
            with open(json_keywords_file, "r", encoding="utf-8") as f:
                keywords_data = json.load(f)
        except Exception:
            keywords_data = []

        # Leer Backlinks
        try:
            with open(json_backlinks_file, "r", encoding="utf-8") as f:
                backlinks_data = json.load(f)
        except Exception:
            backlinks_data = []

        # Leer Rankings
        try:
            with open(json_rankings_file, "r", encoding="utf-8") as f:
                rankings_data = json.load(f)
        except Exception:
            rankings_data = []

        # Leer LLM Visibility
        try:
            with open(json_llm_visibility_file, "r", encoding="utf-8") as f:
                llm_visibility_data = json.load(f)
        except Exception:
            llm_visibility_data = []

        if fix_plan_data is None:
            fix_plan_data = []
        if agg_summary_data is None:
            agg_summary_data = {}

        # Inicializar PDF
        pdf = PDFReport(metadata=metadata)

        # Datos para portada
        url_base = "N/A"
        try:
            url_tmp = (
                agg_summary_data.get("url")
                if isinstance(agg_summary_data, dict)
                else None
            )
            url_base = (url_tmp or "N/A").replace("SITE-WIDE AGGREGATE: ", "")
        except Exception:
            url_base = "N/A"
        fecha_str = datetime.now().strftime("%Y-%m-%d")

        report_title_prefix = (
            str(metadata.get("report_title_prefix"))
            if isinstance(metadata, dict) and metadata.get("report_title_prefix")
            else REPORT_TITLE_PREFIX
        )

        # --- Cover ---
        pdf.create_cover_page(
            f"{report_title_prefix}\n{os.path.basename(report_folder_path)}",
            url_base,
            fecha_str,
            version="v9.2",
        )

        # --- Table of contents pages (placeholder, multi-page safe) ---
        def _estimate_markdown_toc_entries(markdown: str) -> int:
            if not markdown:
                return 0
            count = 0
            for line in markdown.splitlines():
                if re.match(r"^\s*#{1,4}\s+", line):
                    count += 1
            return count

        static_toc_entries = 0
        if not markdown_text:
            static_toc_entries += 1  # Executive Summary (Fallback)
        pagespeed_analysis_file = os.path.join(
            report_folder_path, "pagespeed_analysis.md"
        )
        if os.path.exists(pagespeed_analysis_file):
            static_toc_entries += 1

        # Appendices and data sections
        static_toc_entries += 1  # Appendix C
        static_toc_entries += 1  # Appendix D
        if pagespeed_data:
            static_toc_entries += 1  # D.1
        if keywords_data:
            static_toc_entries += 1  # D.2
        if backlinks_data:
            static_toc_entries += 1  # D.3
        if rankings_data:
            static_toc_entries += 1  # D.4
        if llm_visibility_data:
            static_toc_entries += 1  # D.5
        static_toc_entries += 1  # Appendix E
        static_toc_entries += 1  # Appendix F

        toc_entry_estimate = (
            _estimate_markdown_toc_entries(markdown_text) + static_toc_entries
        )
        toc_pages = pdf.estimate_toc_pages(toc_entry_estimate)
        for _ in range(max(1, toc_pages)):
            pdf.add_page()
        pdf._toc_page_no = pdf.page_no() - max(1, toc_pages) + 1
        pdf._toc_page_count = max(1, toc_pages)

        # --- Renderizar Markdown ---
        if markdown_text:
            pdf.write_markdown_text(markdown_text)
        else:
            # Fallback (executive summary)
            pdf.begin_section("Executive Summary (Fallback)", level=1)
            try:
                pages_audited = (
                    agg_summary_data.get("audited_pages_count", "N/A")
                    if agg_summary_data
                    else "N/A"
                )
            except Exception:
                pages_audited = "N/A"

            summarize_fix_plan(fix_plan_data, top_n=3)
            pdf.set_font(
                "Roboto" if "Roboto" in pdf._fonts_added else "helvetica", "B", 12
            )
            pdf.cell(
                0,
                LINE_HEIGHT * 1.8,
                "Executive Summary of Findings",
                0,
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
                align="L",
            )
            pdf.ln(2)

            pdf.set_font(
                "Roboto" if "Roboto" in pdf._fonts_added else "helvetica",
                "",
                BASE_FONT_SIZE,
            )
            pdf.multi_cell(0, LINE_HEIGHT, f"Total Audited Pages: {pages_audited}")
            pdf.ln(4)

        # --- PageSpeed analysis ---
        pagespeed_analysis_file = os.path.join(
            report_folder_path, "pagespeed_analysis.md"
        )
        if os.path.exists(pagespeed_analysis_file):
            try:
                with open(pagespeed_analysis_file, "r", encoding="utf-8") as f:
                    ps_analysis = f.read()
                pdf.add_page()
                pdf.begin_section("Performance Analysis (PageSpeed Insights)", level=1)
                pdf.write_markdown_text(ps_analysis)
            except Exception as e:
                logger.warning(f"Error leyendo análisis PageSpeed: {e}")

        # --- Appendix C: Action Plan ---
        pdf.add_page()
        pdf.begin_section("Appendix C: Action Plan (fix_plan.json)", level=1)
        if not fix_plan_data:
            pdf.set_font(
                "Roboto" if "Roboto" in pdf._fonts_added else "helvetica", "I", 10
            )
            pdf.multi_cell(
                0,
                5,
                "(No automated tasks were generated in the Action Plan. This may happen when no critical issues were detected or AI analysis failed.)",
            )
        else:
            pdf.write_json_raw(fix_plan_data)

        # --- Appendix D: Aggregated summary ---
        pdf.add_page()
        pdf.begin_section(
            "Appendix D: Aggregated Data Summary (aggregated_summary.json)", level=1
        )
        pdf.write_json_summary_box(
            agg_summary_data, top_n=4, filename_hint="aggregated_summary.json"
        )

        # --- Anexo D.1 (PageSpeed) ---
        if pagespeed_data:
            # Extract mobile data if it exists
            mobile_data = pagespeed_data.get("mobile", pagespeed_data)
            if mobile_data:

                def _format_ms(value):
                    if value is None:
                        return "N/A"
                    if isinstance(value, str):
                        raw = value.strip().lower()
                        if not raw:
                            return "N/A"
                        is_seconds = False
                        if raw.endswith("ms"):
                            raw = raw[:-2]
                        elif raw.endswith("s"):
                            raw = raw[:-1]
                            is_seconds = True
                        # extract numeric part only
                        match = re.search(r"[0-9]+(?:[\\.,][0-9]+)?", raw)
                        if not match:
                            return value
                        raw = match.group(0)
                        # remove thousands separators
                        raw = raw.replace(",", "")
                        try:
                            value = float(raw)
                            if is_seconds:
                                value = value * 1000
                        except Exception:
                            return value
                    try:
                        value_f = float(value)
                    except Exception:
                        return value
                    if value_f <= 0:
                        return "N/A"
                    return f"{value_f/1000:.2f}s ({int(round(value_f))} ms)"

                pdf.add_page()
                pdf.begin_section(
                    "Appendix D.1: PageSpeed Insights (pagespeed.json)", level=1
                )
                # Renderizar resumen de PageSpeed
                ps_summary = {
                    "Performance Score": mobile_data.get("performance_score", "N/A"),
                    "Accessibility Score": mobile_data.get(
                        "accessibility_score", "N/A"
                    ),
                    "Best Practices Score": mobile_data.get(
                        "best_practices_score", "N/A"
                    ),
                    "SEO Score": mobile_data.get("seo_score", "N/A"),
                    "Strategy": mobile_data.get("strategy", "N/A"),
                    "Core Web Vitals": {
                        "LCP": _format_ms(
                            mobile_data.get("core_web_vitals", {}).get("lcp", "N/A")
                        ),
                        "FID": _format_ms(
                            mobile_data.get("core_web_vitals", {}).get("fid", "N/A")
                        ),
                        "CLS": mobile_data.get("core_web_vitals", {}).get("cls", "N/A"),
                        "FCP": _format_ms(
                            mobile_data.get("core_web_vitals", {}).get("fcp", "N/A")
                        ),
                        "TTFB": _format_ms(
                            mobile_data.get("core_web_vitals", {}).get("ttfb", "N/A")
                        ),
                    },
                }
                pdf.write_json_summary_box(
                    ps_summary, top_n=5, filename_hint="pagespeed.json"
                )

        # --- Appendix D.2 (Keywords) ---
        if keywords_data:
            pdf.add_page()
            pdf.begin_section("Appendix D.2: Keyword Analysis (keywords.json)", level=1)
            pdf.write_json_summary_box(
                keywords_data, top_n=10, filename_hint="keywords.json"
            )

        # --- Appendix D.3 (Backlinks) ---
        if backlinks_data:
            pdf.add_page()
            pdf.begin_section(
                "Appendix D.3: Backlink Profile (backlinks.json)", level=1
            )
            pdf.write_json_summary_box(
                backlinks_data, top_n=10, filename_hint="backlinks.json"
            )

        # --- Appendix D.4 (Rankings) ---
        if rankings_data:
            pdf.add_page()
            pdf.begin_section(
                "Appendix D.4: Ranking Monitoring (rankings.json)", level=1
            )
            pdf.write_json_summary_box(
                rankings_data, top_n=10, filename_hint="rankings.json"
            )

        # --- Appendix D.5 (LLM Visibility) ---
        if llm_visibility_data:
            pdf.add_page()
            pdf.begin_section(
                "Appendix D.5: LLM Visibility (llm_visibility.json)", level=1
            )
            pdf.write_json_summary_box(
                llm_visibility_data, top_n=5, filename_hint="llm_visibility.json"
            )

        # --- Appendix E ---
        pdf.add_page()
        pdf.begin_section("Appendix E: Individual Page Reports (Summary)", level=1)

        if not page_json_files:
            pdf.set_font(
                "Roboto" if "Roboto" in pdf._fonts_added else "helvetica", "", 10
            )
            pdf.multi_cell(0, 5, "(No individual page reports found in 'pages' folder)")

        for i, page_file in enumerate(page_json_files):
            page_title = pdf._sanitize_for_current_font(
                f"File: {os.path.basename(page_file)}"
            )
            if i > 0:
                pdf.ln(4)
                pdf.set_draw_color(200, 200, 200)
                pdf.line(
                    pdf.get_x(),
                    pdf.get_y(),
                    pdf.get_x() + (pdf.w - pdf.l_margin - pdf.r_margin),
                    pdf.get_y(),
                )
                pdf.ln(4)

            pdf.set_font(
                "Roboto" if "Roboto" in pdf._fonts_added else "helvetica", "B", 11
            )
            pdf.cell(
                0, LINE_HEIGHT * 1.3, page_title, new_x=XPos.LMARGIN, new_y=YPos.NEXT
            )
            pdf.ln(6)

            try:
                with open(page_file, "r", encoding="utf-8") as f:
                    page_data = json.load(f)
                # DEBUG LOG
                logger.info(
                    f"DEBUG: Cargado {os.path.basename(page_file)}. Keys: {list(page_data.keys()) if isinstance(page_data, dict) else 'No dict'}"
                )
            except Exception as e:
                logger.error(f"DEBUG: Error cargando {page_file}: {e}")
                page_data = None

            pdf.write_json_summary_box(
                page_data,
                top_n=3,
                filename_hint=os.path.join("pages", os.path.basename(page_file)),
            )

        # --- Appendix F: Competitors ---
        pdf.add_page()
        pdf.begin_section("Appendix F: Detailed Competitor Analysis", level=1)

        # Buscar archivos JSON de competidores
        competitors_dir = os.path.join(report_folder_path, "competitors")
        competitor_json_files = []

        logger.info(f"DEBUG: Buscando competidores en: {competitors_dir}")

        if os.path.isdir(competitors_dir):
            competitor_json_files = sorted(
                glob.glob(os.path.join(competitors_dir, "competitor_*.json"))
            )
            logger.info(
                f"DEBUG: Encontrados {len(competitor_json_files)} competidores: {[os.path.basename(f) for f in competitor_json_files]}"
            )

        if not competitor_json_files:
            pdf.set_font(
                "Roboto" if "Roboto" in pdf._fonts_added else "helvetica", "", 10
            )
            pdf.multi_cell(
                0,
                5,
                "(No competitor reports found in 'competitors' folder)",
            )
        else:
            # Introducción del anexo
            pdf.set_font(
                "Roboto" if "Roboto" in pdf._fonts_added else "helvetica", "", 10
            )
            intro_text = (
                f"{len(competitor_json_files)} competitors identified during the audit "
                "were analyzed. The following section provides a detailed breakdown "
                "of each competitor, including GEO Score and comparison with the target site."
            )
            pdf.multi_cell(0, 5, intro_text)
            pdf.ln(6)

            # Tabla comparativa de GEO Scores
            pdf.set_font(
                "Roboto" if "Roboto" in pdf._fonts_added else "helvetica", "B", 11
            )
            pdf.cell(
                0,
                LINE_HEIGHT * 1.3,
                "Comparative GEO Score Table",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
            pdf.ln(4)

            # Cargar scores de todos los competidores
            # Cargar scores de todos los competidores
            competitor_map = {}
            for comp_file in competitor_json_files:
                try:
                    with open(comp_file, "r", encoding="utf-8") as f:
                        comp_data = json.load(f)

                        # 1. Try to get domain from field
                        raw_domain = comp_data.get("domain")

                        # 2. If missing, extract from URL
                        url = comp_data.get("url", "")

                        if not raw_domain and url:
                            from urllib.parse import urlparse

                            # Handle cases where url is just "mercadolibre.cl" without scheme
                            if "://" not in url:
                                url_for_parse = "http://" + url
                            else:
                                url_for_parse = url
                            raw_domain = urlparse(url_for_parse).netloc

                        if not raw_domain:
                            raw_domain = f"competitor_{len(competitor_map) + 1}"

                        # 3. Normalize: lowercase, strip, remove www.
                        normalized_key = raw_domain.lower().strip().replace("www.", "")

                        # 4. Display domain (keep original casing or nicely formatted?)
                        # We use raw_domain but maybe stripped of www for display
                        display_domain = raw_domain.replace("www.", "")

                        # 5. Deduplicate
                        # If exists, keep the one with higher score or more data
                        existing = competitor_map.get(normalized_key)
                        current_score = comp_data.get("geo_score", None)
                        if not isinstance(current_score, (int, float)):
                            current_score = None
                        if current_score is None or current_score == 0:
                            try:
                                from app.services.audit_service import CompetitorService

                                current_score = CompetitorService._calculate_geo_score(
                                    comp_data
                                )
                            except Exception:
                                current_score = current_score or 0

                        if existing:
                            logger.info(
                                f"Duplicate competitor found for key '{normalized_key}': {display_domain} vs {existing['domain']}"
                            )
                            if current_score > existing["geo_score"]:
                                # Update with better score
                                competitor_map[normalized_key] = {
                                    "domain": display_domain,
                                    "geo_score": current_score,
                                    "url": url,
                                    "audit_data": comp_data.get(
                                        "audit_data", {}
                                    ),  # Keep audit data if needed later
                                }
                        else:
                            competitor_map[normalized_key] = {
                                "domain": display_domain,
                                "geo_score": current_score,
                                "url": url,
                                "audit_data": comp_data.get("audit_data", {}),
                            }

                except Exception as e:
                    logger.error(f"Error loading competitor {comp_file}: {e}")

            competitor_scores = list(competitor_map.values())

            # Ordenar por GEO Score descendente
            competitor_scores.sort(key=lambda x: x["geo_score"], reverse=True)

            # Render table
            pdf.set_font(
                "Roboto" if "Roboto" in pdf._fonts_added else "helvetica", "B", 9
            )
            col_widths = [100, 40, 40]
            pdf.cell(col_widths[0], 6, "Competitor", border=1)
            pdf.cell(col_widths[1], 6, "GEO Score (%)", border=1, align="C")
            pdf.cell(
                col_widths[2],
                6,
                "Ranking",
                border=1,
                align="C",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )

            pdf.set_font(
                "Roboto" if "Roboto" in pdf._fonts_added else "helvetica", "", 9
            )
            for idx, comp in enumerate(competitor_scores, 1):
                domain_text = pdf.clean_latin1(
                    comp["domain"][:45]
                )  # Truncar si es muy largo
                pdf.cell(col_widths[0], 6, domain_text, border=1)
                pdf.cell(
                    col_widths[1], 6, f"{comp['geo_score']:.1f}%", border=1, align="C"
                )
                pdf.cell(
                    col_widths[2],
                    6,
                    f"#{idx}",
                    border=1,
                    align="C",
                    new_x=XPos.LMARGIN,
                    new_y=YPos.NEXT,
                )

            pdf.ln(8)

            # Individual competitor reports
            for i, comp_file in enumerate(competitor_json_files):
                try:
                    with open(comp_file, "r", encoding="utf-8") as f:
                        comp_data = json.load(f)

                    domain = comp_data.get("domain")
                    if not domain:
                        from urllib.parse import urlparse

                        domain = (
                            urlparse(url).netloc.replace("www.", "")
                            if url
                            else "Unknown"
                        )
                    geo_score = comp_data.get("geo_score", 0)
                    url = comp_data.get("url", "")
                    audit_data = comp_data.get("audit_data", {})

                    # Separador entre competidores
                    if i > 0:
                        pdf.ln(6)
                        pdf.set_draw_color(200, 200, 200)
                        pdf.line(
                            pdf.get_x(),
                            pdf.get_y(),
                            pdf.get_x() + (pdf.w - pdf.l_margin - pdf.r_margin),
                            pdf.get_y(),
                        )
                        pdf.ln(6)

                    # Competitor title
                    pdf.set_font(
                        "Roboto" if "Roboto" in pdf._fonts_added else "helvetica",
                        "B",
                        12,
                    )
                    comp_title = pdf.clean_latin1(f"Competitor: {domain}")
                    pdf.cell(
                        0,
                        LINE_HEIGHT * 1.5,
                        comp_title,
                        new_x=XPos.LMARGIN,
                        new_y=YPos.NEXT,
                    )
                    pdf.ln(2)

                    # URL and GEO Score
                    pdf.set_font(
                        "Roboto" if "Roboto" in pdf._fonts_added else "helvetica", "", 9
                    )
                    url_text = pdf.clean_latin1(f"URL: {url}")
                    pdf.cell(0, 5, url_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

                    # GEO Score with color coding
                    score_text = f"GEO Score: {geo_score:.1f}%"
                    if geo_score >= 85:
                        pdf.set_text_color(0, 128, 0)  # Green
                        interpretation = "(Excellent AI optimization)"
                    elif geo_score >= 70:
                        pdf.set_text_color(255, 140, 0)  # Orange
                        interpretation = "(Moderate optimization)"
                    else:
                        pdf.set_text_color(255, 0, 0)  # Red
                        interpretation = "(Low optimization)"

                    pdf.set_font(
                        "Roboto" if "Roboto" in pdf._fonts_added else "helvetica",
                        "B",
                        10,
                    )
                    pdf.cell(
                        0,
                        5,
                        f"{score_text} {interpretation}",
                        new_x=XPos.LMARGIN,
                        new_y=YPos.NEXT,
                    )
                    pdf.set_text_color(0, 0, 0)  # Reset color
                    pdf.ln(4)

                    # Strengths and weaknesses analysis
                    pdf.set_font(
                        "Roboto" if "Roboto" in pdf._fonts_added else "helvetica",
                        "B",
                        10,
                    )
                    pdf.cell(0, 5, "Strengths:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                    pdf.set_font(
                        "Roboto" if "Roboto" in pdf._fonts_added else "helvetica", "", 9
                    )

                    strengths = []
                    weaknesses = []

                    # Analyze structure
                    if (
                        audit_data.get("structure", {})
                        .get("h1_check", {})
                        .get("status")
                        == "pass"
                    ):
                        strengths.append("✓ H1 properly implemented")
                    else:
                        weaknesses.append("✗ Missing or incorrect H1")

                    # Analyze schema
                    schema_status = (
                        audit_data.get("schema", {})
                        .get("schema_presence", {})
                        .get("status")
                    )
                    if schema_status == "present":
                        schema_types = audit_data.get("schema", {}).get(
                            "schema_types", []
                        )
                        strengths.append(
                            f"✓ Schema.org implemented ({len(schema_types)} types)"
                        )
                    else:
                        weaknesses.append("✗ No Schema.org")

                    # Analyze E-E-A-T
                    author_status = (
                        audit_data.get("eeat", {})
                        .get("author_presence", {})
                        .get("status")
                    )
                    if author_status == "pass":
                        strengths.append("✓ Author information present")
                    else:
                        weaknesses.append("✗ No author information")

                    # Analyze semantic HTML
                    semantic_score = (
                        audit_data.get("structure", {})
                        .get("semantic_html", {})
                        .get("score_percent", 0)
                    )
                    if semantic_score >= 70:
                        strengths.append(
                            f"✓ Semantic HTML well implemented ({semantic_score}%)"
                        )
                    elif semantic_score >= 50:
                        weaknesses.append(
                            f"⚠ Semantic HTML is moderate ({semantic_score}%)"
                        )
                    else:
                        weaknesses.append(
                            f"✗ Semantic HTML is weak ({semantic_score}%)"
                        )

                    # Render strengths
                    for strength in strengths:
                        strength_text = pdf.clean_latin1(f"  {strength}")
                        pdf.cell(
                            0, 5, strength_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT
                        )

                    if not strengths:
                        pdf.cell(
                            0,
                            5,
                            "  (No significant strengths identified)",
                            new_x=XPos.LMARGIN,
                            new_y=YPos.NEXT,
                        )

                    pdf.ln(3)

                    # Render weaknesses
                    pdf.set_font(
                        "Roboto" if "Roboto" in pdf._fonts_added else "helvetica",
                        "B",
                        10,
                    )
                    pdf.cell(0, 5, "Weaknesses:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                    pdf.set_font(
                        "Roboto" if "Roboto" in pdf._fonts_added else "helvetica", "", 9
                    )

                    for weakness in weaknesses:
                        weakness_text = pdf.clean_latin1(f"  {weakness}")
                        pdf.cell(
                            0, 5, weakness_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT
                        )

                    if not weaknesses:
                        pdf.cell(
                            0,
                            5,
                            "  (No significant weaknesses identified)",
                            new_x=XPos.LMARGIN,
                            new_y=YPos.NEXT,
                        )

                    pdf.ln(4)

                    # Learning opportunities
                    if strengths:
                        pdf.set_font(
                            "Roboto" if "Roboto" in pdf._fonts_added else "helvetica",
                            "B",
                            10,
                        )
                        pdf.cell(
                            0,
                            5,
                            "Learning Opportunities:",
                            new_x=XPos.LMARGIN,
                            new_y=YPos.NEXT,
                        )
                        pdf.set_font(
                            "Roboto" if "Roboto" in pdf._fonts_added else "helvetica",
                            "I",
                            9,
                        )
                        opp_text = pdf.clean_latin1(
                            f"This competitor stands out in {len(strengths)} area(s). Consider adopting similar practices to improve your GEO Score."
                        )
                        pdf.multi_cell(0, 5, opp_text)

                except Exception as e:
                    logger.error(f"Error processing competitor {comp_file}: {e}")
                    pdf.set_font(
                        "Roboto" if "Roboto" in pdf._fonts_added else "helvetica", "", 9
                    )
                    pdf.cell(
                        0,
                        5,
                        f"Error loading competitor data: {os.path.basename(comp_file)}",
                        new_x=XPos.LMARGIN,
                        new_y=YPos.NEXT,
                    )

        # --- Rellenar TOC ---
        logger.info(
            "Rendering TOC (entries=%d) on page %s",
            len(pdf._toc_entries),
            pdf._toc_page_no,
        )
        pdf.render_manual_toc()

        # --- Guardar PDF ---
        try:
            pdf.output(pdf_file_path)
            logger.info("¡Éxito! PDF consolidado guardado en: %s", pdf_file_path)
        except Exception as e:
            logger.exception("Error al guardar PDF: %s", e)

    except Exception as e:
        logger.error("Falló la creación del PDF: %s", e)
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Uso: python create_pdf.py "ruta/a/la_carpeta_reporte"')
        sys.exit(1)
    report_folder = sys.argv[1]
    create_comprehensive_pdf(report_folder)
