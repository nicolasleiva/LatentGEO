#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pdf_generator.py - Contiene la clase PDFReport

import os
import json
import math
import logging
import re
from datetime import datetime

try:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    FPDF_AVAILABLE = True
except ImportError:
    logging.warning("fpdf2 no está instalado. La generación de PDF fallará.")
    FPDF_AVAILABLE = False

    class FPDF:
        def __getattr__(self, name):
            def dummy_method(*args, **kwargs):
                logging.error("Llamada a método FPDF fallida. fpdf2 no está instalado.")
            return dummy_method

    class XPos: pass
    class YPos: pass


logger = logging.getLogger(__name__)

# --- Constantes de Estilo (movidas aquí para encapsulación) ---
BASE_FONT_SIZE = 11
TABLE_FONT_SIZE = 9
LINE_HEIGHT = 5.0
HEADING_FONT_SIZE = 16
PAGE_MARGIN_MM = 16
HEADER_HEIGHT_MM = 14
CONTENT_PADDING_TOP = 6
ACCENT_COLOR = (60, 60, 60)


class PDFReport(FPDF):
    """Clase PDF con utilidades para el reporte profesional y minimalista."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._fonts_added = set()
        self.setup_fonts()
        self.set_auto_page_break(True, margin=PAGE_MARGIN_MM)
        self.alias_nb_pages()
        self._toc_entries = []
        self._toc_page_no = None
        self.footer_left = "https://www.linkedin.com/in/nicolasleiva/"
        self.footer_right = "Nicolas Leiva"

        self.set_margins(PAGE_MARGIN_MM, PAGE_MARGIN_MM, PAGE_MARGIN_MM)
        self.set_auto_page_break(auto=True, margin=PAGE_MARGIN_MM)

    def setup_fonts(self):
        """Intenta cargar fuentes locales; si no, usa las internas."""
        # Esta lógica puede necesitar ajustes si las fuentes no están en una ruta accesible
        # Por simplicidad, usaremos helvetica si las fuentes no se encuentran.
        self.set_font("helvetica", "", BASE_FONT_SIZE)

    def header(self):
        """Encabezado sobrio: título corto en una línea y una regla."""
        if self.page_no() in (1, self._toc_page_no):
            return

        self.set_y(PAGE_MARGIN_MM - 6)
        self.set_font("helvetica", "B", 10)
        title_short = "Informe de Auditoría GEO"
        width = self.w - self.l_margin - self.r_margin
        self.set_text_color(*ACCENT_COLOR)
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
        self.set_font("helvetica", "I", 8)
        self.set_text_color(100)
        self.set_x(self.l_margin)
        self.cell(
            0, 6, self.footer_left, 0, new_x=XPos.RIGHT, new_y=YPos.TOP, align="L"
        )
        self.set_x(self.l_margin)
        self.cell(
            0,
            6,
            f"{self.footer_right}   |   Página {self.page_no()} / {{nb}}",
            0,
            new_x=XPos.RIGHT,
            new_y=YPos.TOP,
            align="R",
        )

    def create_cover_page(self, title, url, date_str, version=None):
        """Crea una portada centrada."""
        self.add_page()
        left = self.l_margin
        usable_w = self.w - self.l_margin - self.r_margin
        center_y = self.h / 2.0
        y_start = center_y - 36
        if y_start < PAGE_MARGIN_MM:
            y_start = PAGE_MARGIN_MM + 20

        self.set_xy(left, y_start)
        self.set_text_color(36, 36, 36)
        self.set_font("helvetica", "B", 26)
        for line in str(title).splitlines():
            self.multi_cell(usable_w, 12, line.strip(), 0, "C")
        self.ln(6)

        self.set_font("helvetica", "", 11)
        if url:
            self.multi_cell(usable_w, 7, f"{url}", 0, "C")
        if date_str:
            self.multi_cell(usable_w, 7, f"Fecha de auditoría: {date_str}", 0, "C")

    def write_markdown_text(self, text):
        """Render simple de markdown básico."""
        text = str(text or "").replace("\r", "")
        self.set_font("helvetica", "", BASE_FONT_SIZE)

        for line in text.splitlines():
            line_stripped = line.strip()

            if not line_stripped:
                self.ln(4)
                continue

            m = re.match(r"^(#{1,4})\s+(.*)", line)
            if m:
                hashes = len(m.group(1))
                title = m.group(2).strip()
                if hashes == 1:
                    self.set_font("helvetica", "B", 16)
                    self.multi_cell(0, LINE_HEIGHT * 1.6, title, 0, "L")
                    self.ln(4)
                elif hashes == 2:
                    self.set_font("helvetica", "B", 14)
                    self.multi_cell(0, LINE_HEIGHT * 1.4, title, 0, "L")
                    self.ln(2)
                else:
                    self.set_font("helvetica", "B", 12)
                    self.multi_cell(0, LINE_HEIGHT * 1.2, title, 0, "L")
                    self.ln(1)
                self.set_font("helvetica", "", BASE_FONT_SIZE)
            else:
                self.set_x(self.l_margin)
                self.multi_cell(0, LINE_HEIGHT, line, 0, "L")

    def ensure_space(self, needed_h):
        """Asegura que haya espacio suficiente en la página, si no añade página."""
        if (self.get_y() + needed_h) > (self.h - self.b_margin):
            self.add_page()
            return True
        return False

# El resto de la clase PDFReport de create_pdf.py iría aquí.
# Por brevedad, he incluido solo los métodos esenciales.
# Puedes copiar y pegar el resto de la clase `PDFReport` desde `create_pdf.py`
# a este nuevo archivo `pdf_generator.py`.