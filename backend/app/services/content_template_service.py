#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
content_template_service.py - Plantillas de Contenido Optimizadas para GEO

Genera templates de contenido que maximizan la visibilidad en LLMs.
"""

import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class ContentTemplateService:
    """
    Servicio para generar plantillas de contenido optimizadas para GEO.
    
    Los LLMs prefieren:
    - Respuestas directas y estructuradas
    - Formato conversacional
    - Datos verificables
    - Estructura clara (listas, pasos, comparaciones)
    """
    
    # Templates base por tipo de contenido
    TEMPLATES = {
        'guide': {
            'name': 'Guía Completa',
            'description': 'Contenido educativo paso a paso optimizado para LLMs',
            'structure': [
                '# {title}\n\n',
                '## ¿Qué es {topic}?\n\n{intro}\n\n',
                '## ¿Por qué es importante {topic}?\n\n{importance}\n\n',
                '## Cómo {action} paso a paso\n\n{steps}\n\n',
                '## Mejores prácticas\n\n{best_practices}\n\n',
                '## Errores comunes a evitar\n\n{common_mistakes}\n\n',
                '## Preguntas frecuentes\n\n{faqs}\n\n',
                '## Conclusión\n\n{conclusion}'
            ],
            'llm_optimization': [
                'Usar lenguaje conversacional',
                'Incluir ejemplos concretos',
                'Responder preguntas antes de que se hagan',
                'Estructura clara con headings'
            ]
        },
        'comparison': {
            'name': 'Comparativa',
            'description': 'Comparación objetiva optimizada para queries de "vs" o "mejor"',
            'structure': [
                '# {product_a} vs {product_b}: ¿Cuál es mejor?\n\n',
                '## Resumen ejecutivo\n\n{summary}\n\n',
                '## Comparación rápida\n\n{quick_comparison_table}\n\n',
                '## {product_a}: Características principales\n\n{product_a_features}\n\n',
                '## {product_b}: Características principales\n\n{product_b_features}\n\n',
                '## Ventajas y desventajas\n\n{pros_cons}\n\n',
                '## ¿Cuál elegir según tu necesidad?\n\n{recommendations}\n\n',
                '## Veredicto final\n\n{verdict}'
            ],
            'llm_optimization': [
                'Ser objetivo y balanceado',
                'Incluir tabla comparativa',
                'Dar recomendaciones claras por caso de uso',
                'Mencionar precios y alternativas'
            ]
        },
        'faq': {
            'name': 'Página de Preguntas Frecuentes',
            'description': 'FAQ optimizado para capturar queries de preguntas',
            'structure': [
                '# Preguntas Frecuentes sobre {topic}\n\n',
                '{faq_items}\n\n',
                '## ¿Tienes más preguntas?\n\n{call_to_action}'
            ],
            'llm_optimization': [
                'Una pregunta = una respuesta concisa',
                'Usar Schema.org FAQPage',
                'Respuestas de 50-100 palabras',
                'Lenguaje natural y directo'
            ]
        },
        'listicle': {
            'name': 'Lista Top N',
            'description': 'Lista numerada optimizada para queries "mejores" o "top"',
            'structure': [
                '# Las {number} mejores {items} en {year}\n\n',
                '## Metodología\n\n{methodology}\n\n',
                '{list_items}\n\n',
                '## Cómo elegir el mejor {item} para ti\n\n{buying_guide}\n\n',
                '## Conclusión\n\n{conclusion}'
            ],
            'llm_optimization': [
                'Empezar con el mejor (no guardar para el final)',
                'Incluir criterios de selección',
                'Pros y contras de cada item',
                'Actualizar fecha regularmente'
            ]
        },
        'tutorial': {
            'name': 'Tutorial Práctico',
            'description': 'Tutorial paso a paso con Schema HowTo',
            'structure': [
                '# Cómo {action}: Tutorial completo\n\n',
                '## Lo que necesitas\n\n{requirements}\n\n',
                '## Tiempo requerido: {time}\n\n',
                '## Nivel de dificultad: {difficulty}\n\n',
                '## Pasos\n\n{steps}\n\n',
                '## Tips profesionales\n\n{pro_tips}\n\n',
                '## Solución de problemas\n\n{troubleshooting}'
            ],
            'llm_optimization': [
                'Pasos numerados y claros',
                'Incluir tiempo estimado',
                'Screenshots o código de ejemplo',
                'Usar Schema HowTo'
            ]
        }
    }
    
    @staticmethod
    async def generate_template(
        template_type: str,
        topic: str,
        keywords: List[str],
        llm_function: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Genera una plantilla de contenido personalizada.
        
        Args:
            template_type: Tipo de template (guide, comparison, faq, etc)
            topic: Tema principal
            keywords: Keywords relevantes
            llm_function: LLM para generar contenido de ejemplo
        
        Returns:
            Template completo con estructura y contenido de ejemplo
        """
        logger.info(f"Generando template tipo '{template_type}' para '{topic}'")
        
        # Obtener template base
        template = ContentTemplateService.TEMPLATES.get(template_type)
        
        if not template:
            raise ValueError(f"Template type '{template_type}' no existe")
        
        # Generar estructura personalizada
        personalized_structure = ContentTemplateService._personalize_structure(
            template['structure'],
            topic,
            keywords
        )
        
        # Generar contenido de ejemplo con LLM
        example_content = None
        if llm_function:
            example_content = await ContentTemplateService._generate_example_content(
                template_type,
                topic,
                keywords,
                llm_function
            )
        
        return {
            'template_type': template_type,
            'name': template['name'],
            'description': template['description'],
            'structure': personalized_structure,
            'optimization_tips': template['llm_optimization'],
            'example_content': example_content,
            'implementation_guide': ContentTemplateService._generate_implementation_guide(
                template_type
            )
        }
    
    @staticmethod
    def _personalize_structure(
        structure: List[str],
        topic: str,
        keywords: List[str]
    ) -> List[str]:
        """Personaliza la estructura del template."""
        personalized = []
        
        for section in structure:
            # Reemplazar placeholders
            section = section.replace('{topic}', topic)
            section = section.replace('{title}', f"Guía Completa de {topic}")
            section = section.replace('{year}', '2024')
            
            # Usar keywords si están disponibles
            if keywords:
                section = section.replace('{items}', keywords[0])
                section = section.replace('{item}', keywords[0].rstrip('s'))
            
            personalized.append(section)
        
        return personalized
    
    @staticmethod
    async def _generate_example_content(
        template_type: str,
        topic: str,
        keywords: List[str],
        llm_function: callable
    ) -> str:
        """Genera contenido de ejemplo usando LLM."""
        keywords_str = ", ".join(keywords[:3])
        
        prompts = {
            'guide': f"""Escribe una introducción optimizada para LLMs sobre "{topic}".

Keywords: {keywords_str}

La introducción debe:
- Explicar qué es de forma clara
- Por qué es importante
- Quién se beneficia
- Máximo 150 palabras

Solo escribe el texto, sin formato adicional.""",

            'comparison': f"""Crea un resumen ejecutivo comparando las principales opciones de "{topic}".

Keywords: {keywords_str}

Incluye:
- Cuál es mejor para cada caso de uso
- Diferencias clave
- Precio aproximado
- Máximo 100 palabras""",

            'faq': f"""Genera 5 preguntas frecuentes sobre "{topic}" con respuestas concisas.

Keywords: {keywords_str}

Formato:
**P: [Pregunta]**
R: [Respuesta de 50 palabras]

---""",

            'listicle': f"""Crea una metodología de selección para "{topic}".

Keywords: {keywords_str}

Explica en 80 palabras los criterios que usaste para elegir los mejores.""",

            'tutorial': f"""Lista los requisitos necesarios para "{topic}".

Keywords: {keywords_str}

Formato de lista:
- [Requisito 1]
- [Requisito 2]
- [Requisito 3]"""
        }
        
        prompt = prompts.get(template_type, prompts['guide'])
        
        try:
            example = await llm_function(prompt)
            return example.strip()
        except Exception as e:
            logger.error(f"Error generando ejemplo: {e}")
            return ""
    
    @staticmethod
    def _generate_implementation_guide(template_type: str) -> List[str]:
        """Genera guía de implementación."""
        guides = {
            'guide': [
                "1. Investiga el tema a fondo antes de escribir",
                "2. Usa ejemplos reales y específicos",
                "3. Incluye screenshots o diagramas si es posible",
                "4. Actualiza regularmente con nueva información",
                "5. Agrega Schema.org Article para mejor indexación"
            ],
            'comparison': [
                "1. Sé objetivo - menciona pros y contras de cada opción",
                "2. Incluye tabla comparativa HTML",
                "3. Actualiza precios regularmente",
                "4. Agrega sección 'Última actualización'",
                "5. Usa Schema.org Table para la comparación"
            ],
            'faq': [
                "1. Una pregunta por sección H2",
                "2. Respuestas entre 50-150 palabras",
                "3. Usar Schema.org FAQPage",
                "4. Incluir variaciones de la pregunta en el texto",
                "5. Actualizar con nuevas preguntas comunes"
            ],
            'listicle': [
                "1. Empezar con #1 (no guardar el mejor para el final)",
                "2. Incluir criterios de selección claros",
                "3. Mínimo 200 palabras por item",
                "4. Incluir pros y contras de cada uno",
                "5. Agregar fecha de actualización visible"
            ],
            'tutorial': [
                "1. Probar el tutorial tú mismo antes de publicar",
                "2. Screenshots en cada paso importante",
                "3. Código copiable si aplica",
                "4. Sección de troubleshooting",
                "5. Usar Schema.org HowTo"
            ]
        }
        
        return guides.get(template_type, guides['guide'])
    
    @staticmethod
    def get_all_templates() -> List[Dict[str, str]]:
        """Obtiene lista de todos los templates disponibles."""
        return [
            {
                'type': key,
                'name': template['name'],
                'description': template['description'],
                'best_for': ContentTemplateService._get_best_use_case(key)
            }
            for key, template in ContentTemplateService.TEMPLATES.items()
        ]
    
    @staticmethod
    def _get_best_use_case(template_type: str) -> str:
        """Describe el mejor caso de uso para cada template."""
        use_cases = {
            'guide': 'Contenido educativo, recursos de aprendizaje',
            'comparison': 'Queries "vs", "mejor", "comparar"',
            'faq': 'Capturar preguntas directas, soporte',
            'listicle': 'Queries "top", "mejores", rankings',
            'tutorial': 'Queries "cómo hacer", instrucciones paso a paso'
        }
        return use_cases.get(template_type, '')
    
    @staticmethod
    def analyze_content_for_geo(content: str) -> Dict[str, Any]:
        """
        Analiza contenido existente y sugiere mejoras para GEO.
        
        Args:
            content: Contenido a analizar
        
        Returns:
            Análisis con sugerencias de mejora
        """
        analysis = {
            'score': 0,
            'strengths': [],
            'improvements': [],
            'recommended_structure': None
        }
        
        content_lower = content.lower()
        
        # Verificar estructura
        has_headings = '##' in content or '<h2' in content_lower
        has_lists = ('- ' in content or '* ' in content or 
                    '<ul' in content_lower or '<ol' in content_lower)
        has_faqs = '?' in content and (content.count('?') > 3)
        
        if has_headings:
            analysis['strengths'].append('Usa headings para estructura')
            analysis['score'] += 20
        else:
            analysis['improvements'].append('Agregar headings (H2, H3) para mejor estructura')
        
        if has_lists:
            analysis['strengths'].append('Incluye listas (fáciles de procesar para LLMs)')
            analysis['score'] += 15
        else:
            analysis['improvements'].append('Convertir parágrafos largos en listas cuando sea posible')
        
        # Verificar longitud de párrafos
        paragraphs = content.split('\n\n')
        long_paragraphs = [p for p in paragraphs if len(p.split()) > 100]
        
        if len(long_paragraphs) > 3:
            analysis['improvements'].append('Dividir párrafos largos (máx 80-100 palabras)')
        else:
            analysis['strengths'].append('Párrafos de longitud adecuada')
            analysis['score'] += 15
        
        # Verificar tono conversacional
        conversational_markers = ['puedes', 'debes', 'necesitas', 'te recomiendo', '¿']
        if any(marker in content_lower for marker in conversational_markers):
            analysis['strengths'].append('Tono conversacional (bueno para LLMs)')
            analysis['score'] += 20
        else:
            analysis['improvements'].append('Usar tono más conversacional (tú/usted)')
        
        # Recomendar estructura
        if has_faqs:
            analysis['recommended_structure'] = 'faq'
        elif 'paso' in content_lower or 'primero' in content_lower:
            analysis['recommended_structure'] = 'tutorial'
        elif 'mejor' in content_lower or 'top' in content_lower:
            analysis['recommended_structure'] = 'listicle'
        else:
            analysis['recommended_structure'] = 'guide'
        
        # Score final
        analysis['score'] = min(100, analysis['score'])
        
        return analysis
