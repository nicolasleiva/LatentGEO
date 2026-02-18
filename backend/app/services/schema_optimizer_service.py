#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
schema_optimizer_service.py - Generador Automático de Schema.org para GEO

Genera Schema.org optimizado para LLMs basado en el contenido de la página.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SchemaOptimizerService:
    """
    Servicio para generar Schema.org optimizado para LLMs.

    Los LLMs entienden mejor el contenido estructurado.
    Schema.org ayuda a:
    - Identificar entidades claramente
    - Entender relaciones
    - Extraer información precisa

    """

    # Templates de Schema por tipo
    SCHEMA_TEMPLATES = {
        "Organization": {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": None,
            "url": None,
            "logo": None,
            "description": None,
            "sameAs": [],
            "contactPoint": {
                "@type": "ContactPoint",
                "contactType": "customer support",
            },
        },
        "Article": {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": None,
            "author": {"@type": "Person", "name": None},
            "datePublished": None,
            "dateModified": None,
            "publisher": {"@type": "Organization", "name": None},
            "description": None,
        },
        "Product": {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": None,
            "description": None,
            "brand": {"@type": "Brand", "name": None},
            "offers": {"@type": "Offer", "price": None, "priceCurrency": "USD"},
        },
        "FAQPage": {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [],
        },
        "HowTo": {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": None,
            "description": None,
            "step": [],
        },
    }

    @staticmethod
    async def generate_schema(
        html_content: str,
        url: str,
        page_type: Optional[str] = None,
        llm_function: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Genera Schema.org optimizado basado en el contenido de la página.

        Args:
            html_content: HTML de la página
            url: URL de la página
            page_type: Tipo de página (auto-detectado si None)
            llm_function: LLM para enriquecer schema

        Returns:
            Schema.org completo en JSON-LD
        """
        logger.info(f"Generando schema para {url}")

        # Parsear HTML
        soup = BeautifulSoup(html_content, "html.parser")

        # Auto-detectar tipo de página si no se especifica
        if not page_type:
            page_type = SchemaOptimizerService._detect_page_type(soup, url)

        # Generar schema base
        schema = SchemaOptimizerService._generate_base_schema(soup, url, page_type)

        # Enriquecer con LLM si está disponible
        if llm_function:
            schema = await SchemaOptimizerService._enrich_with_llm(
                schema, soup, llm_function
            )

        # Validar schema
        is_valid = SchemaOptimizerService._validate_schema(schema)

        logger.info(f"Schema generado: tipo={page_type}, válido={is_valid}")

        return {
            "schema": schema,
            "page_type": page_type,
            "is_valid": is_valid,
            "implementation_code": SchemaOptimizerService._generate_implementation_code(
                schema
            ),
        }

    @staticmethod
    def _detect_page_type(soup: BeautifulSoup, url: str) -> str:
        """Auto-detecta el tipo de página."""
        # Buscar señales en el contenido
        text_content = soup.get_text().lower()

        # FAQ Page
        if (
            "pregunta" in text_content
            or "faq" in text_content
            or len(soup.find_all(["dt", "dd"])) > 3
        ):
            return "FAQPage"

        # Article/Blog
        if soup.find("article") or "/blog/" in url or soup.find("time"):
            return "Article"

        # Product
        if (
            "precio" in text_content
            or "comprar" in text_content
            or soup.find(class_=lambda x: x and "price" in x.lower())
        ):
            return "Product"

        # HowTo
        if (
            "cómo" in text_content
            or "paso" in text_content
            or len(soup.find_all(["ol", "ul"])) > 2
        ):
            return "HowTo"

        # Default: Organization
        return "Organization"

    @staticmethod
    def _generate_base_schema(soup: BeautifulSoup, url: str, page_type: str) -> Dict:
        """Genera schema base extrayendo datos del HTML."""
        from urllib.parse import urlparse

        # Obtener template
        schema = SchemaOptimizerService.SCHEMA_TEMPLATES.get(page_type, {}).copy()

        # Datos comunes
        title = soup.find("title")
        meta_desc = soup.find("meta", attrs={"name": "description"})
        h1 = soup.find("h1")

        domain = urlparse(url).netloc.replace("www.", "")
        brand_name = domain.split(".")[0].title()

        # Organization
        if page_type == "Organization":
            schema["name"] = brand_name
            schema["url"] = url
            schema["description"] = meta_desc.get("content") if meta_desc else None

            # Buscar logo
            logo = soup.find("img", attrs={"alt": lambda x: x and "logo" in x.lower()})
            if logo and logo.get("src"):
                schema["logo"] = logo["src"]

        # Article
        elif page_type == "Article":
            schema["headline"] = title.get_text() if title else None
            schema["description"] = meta_desc.get("content") if meta_desc else None
            schema["publisher"]["name"] = brand_name

            # Buscar autor
            author = soup.find(class_=lambda x: x and "author" in x.lower())
            if author:
                schema["author"]["name"] = author.get_text().strip()

            # Fechas
            time_tag = soup.find("time")
            if time_tag and time_tag.get("datetime"):
                schema["datePublished"] = time_tag["datetime"]

        # Product
        elif page_type == "Product":
            schema["name"] = h1.get_text() if h1 else None
            schema["description"] = meta_desc.get("content") if meta_desc else None
            schema["brand"]["name"] = brand_name

            # Buscar precio
            price_el = soup.find(class_=lambda x: x and "price" in x.lower())
            if price_el:
                price_text = price_el.get_text().strip()
                # Extraer número
                import re

                price_match = re.search(r"[\d,\.]+", price_text)
                if price_match:
                    schema["offers"]["price"] = price_match.group()

        # FAQPage
        elif page_type == "FAQPage":
            faqs = []

            # Buscar dt/dd pairs
            dts = soup.find_all("dt")
            dds = soup.find_all("dd")

            for dt, dd in zip(dts, dds):
                faqs.append(
                    {
                        "@type": "Question",
                        "name": dt.get_text().strip(),
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": dd.get_text().strip(),
                        },
                    }
                )

            schema["mainEntity"] = faqs[:10]  # Máximo 10 FAQs

        # HowTo
        elif page_type == "HowTo":
            schema["name"] = title.get_text() if title else None
            schema["description"] = meta_desc.get("content") if meta_desc else None

            # Buscar pasos
            steps = []
            ol = soup.find("ol")
            if ol:
                lis = ol.find_all("li")
                for i, li in enumerate(lis[:10]):  # Máximo 10 pasos
                    steps.append(
                        {
                            "@type": "HowToStep",
                            "position": i + 1,
                            "name": f"Paso {i + 1}",
                            "text": li.get_text().strip(),
                        }
                    )

            schema["step"] = steps

        return schema

    @staticmethod
    async def _enrich_with_llm(
        schema: Dict, soup: BeautifulSoup, llm_function: callable
    ) -> Dict:
        """Enriquece schema usando LLM para mejorar descripciones."""
        try:
            # Extraer texto principal
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()

            main_text = soup.get_text(separator=" ", strip=True)[:1000]

            prompt = f"""Basado en este contenido de página web, mejora la descripción para Schema.org.

Contenido:
{main_text}

Genera UNA descripción optimizada para LLMs (máx 160 caracteres) que:
1. Sea clara y precisa
2. Incluya keywords relevantes
3. Describa el valor principal

Devuelve SOLO la descripción, sin formato adicional."""

            enhanced_desc = await llm_function(prompt)

            # Actualizar descripción en el schema
            if "description" in schema and enhanced_desc:
                schema["description"] = enhanced_desc.strip()[:160]

            return schema

        except Exception as e:
            logger.warning(f"Error enriqueciendo con LLM: {e}")
            return schema

    @staticmethod
    def _validate_schema(schema: Dict) -> bool:
        """Valida que el schema tenga los campos mínimos requeridos."""
        if not schema or "@type" not in schema:
            return False

        # Verificar campos requeridos según el tipo
        schema_type = schema.get("@type")

        required_fields = {
            "Organization": ["name", "url"],
            "Article": ["headline", "author"],
            "Product": ["name", "description"],
            "FAQPage": ["mainEntity"],
            "HowTo": ["name", "step"],
        }

        required = required_fields.get(schema_type, [])

        for field in required:
            if field not in schema or not schema[field]:
                return False

        return True

    @staticmethod
    def _generate_implementation_code(schema: Dict) -> str:
        """Genera código HTML para implementar el schema."""
        schema_json = json.dumps(schema, indent=2, ensure_ascii=False)

        return f"""<!-- Agregar en el <head> de tu página -->
<script type="application/ld+json">
{schema_json}
</script>"""

    @staticmethod
    def generate_multiple_schemas(html_content: str, url: str) -> List[Dict]:
        """
        Genera múltiples schemas si la página lo amerita.

        Por ejemplo: Organization + Article para un blog post
        """
        soup = BeautifulSoup(html_content, "html.parser")
        schemas = []

        # Siempre agregar Organization
        org_schema = SchemaOptimizerService._generate_base_schema(
            soup, url, "Organization"
        )
        schemas.append({"type": "Organization", "schema": org_schema})

        # Detectar tipo específico de página
        page_type = SchemaOptimizerService._detect_page_type(soup, url)

        if page_type != "Organization":
            specific_schema = SchemaOptimizerService._generate_base_schema(
                soup, url, page_type
            )
            schemas.append({"type": page_type, "schema": specific_schema})

        return schemas
