#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prompt_loader.py - Servicio de Carga de Prompts JSON v2.0

Carga y gestiona prompts en formato JSON desde backend/app/prompts/v2.0/
Proporciona:
- Carga de configuración maestra
- Carga de prompts individuales por nombre
- Validación de schemas
- Caché en memoria
- Fallback a versiones anteriores si es necesario
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)


class PromptLoader:
    """
    Loader de Prompts JSON v2.0 Enterprise

    Carga prompts estructurados en JSON desde el directorio v2.0
    con soporte para caché, validación y fallback.
    """

    # Directorio base de prompts v2.0
    PROMPTS_DIR = Path(__file__).parent.parent / "prompts" / "v2.0"

    # Nombres de prompts disponibles
    AVAILABLE_PROMPTS = {
        "config": "config.json",
        "external_analysis": "external_analysis.json",
        "pagespeed_analysis": "pagespeed_analysis.json",
        "executive_summary": "executive_summary.json",
        "report_generation": "report_generation.json",
        "competitor_intelligence": "competitor_intelligence.json",
        "product_intelligence": "product_intelligence.json",
        "content_strategy": "content_strategy.json",
        "fix_plan_generation": "fix_plan_generation.json",
    }

    def __init__(self):
        """Inicializa el loader y verifica el directorio de prompts."""
        self._cache: Dict[str, Any] = {}
        self._config: Optional[Dict] = None

        if not self.PROMPTS_DIR.exists():
            logger.error(f"Prompts directory not found: {self.PROMPTS_DIR}")
            raise FileNotFoundError(f"Prompts directory not found: {self.PROMPTS_DIR}")

        logger.info(f"PromptLoader initialized with directory: {self.PROMPTS_DIR}")

    def load_config(self) -> Dict[str, Any]:
        """
        Carga la configuración maestra de prompts.

        Returns:
            Dict con configuración completa
        """
        if self._config is None:
            self._config = self._load_json_file("config.json")
            logger.info(
                f"Loaded prompt config v{self._config.get('version', 'unknown')}"
            )
        return self._config

    def load_prompt(self, prompt_name: str) -> Dict[str, Any]:
        """
        Carga un prompt específico por nombre.

        Args:
            prompt_name: Nombre del prompt (ej: 'external_analysis')

        Returns:
            Dict con el prompt completo

        Raises:
            ValueError: Si el prompt no existe
        """
        if prompt_name in self._cache:
            logger.debug(f"Returning cached prompt: {prompt_name}")
            return self._cache[prompt_name]

        if prompt_name not in self.AVAILABLE_PROMPTS:
            available = ", ".join(self.AVAILABLE_PROMPTS.keys())
            raise ValueError(f"Unknown prompt: {prompt_name}. Available: {available}")

        filename = self.AVAILABLE_PROMPTS[prompt_name]
        prompt_data = self._load_json_file(filename)

        # Validar estructura mínima
        self._validate_prompt_structure(prompt_data, prompt_name)

        # Guardar en caché
        self._cache[prompt_name] = prompt_data
        logger.info(
            f"Loaded and cached prompt: {prompt_name} v{prompt_data.get('version', 'unknown')}"
        )

        return prompt_data

    def get_system_prompt(self, prompt_name: str) -> str:
        """
        Obtiene el system prompt de un prompt específico.

        Args:
            prompt_name: Nombre del prompt

        Returns:
            String con el system prompt
        """
        prompt_data = self.load_prompt(prompt_name)
        return prompt_data.get("system_prompt", "")

    def get_user_template(self, prompt_name: str) -> str:
        """
        Obtiene el user template de un prompt específico.

        Args:
            prompt_name: Nombre del prompt

        Returns:
            String con el user template
        """
        prompt_data = self.load_prompt(prompt_name)
        return prompt_data.get("user_template", "")

    def get_output_schema(self, prompt_name: str) -> Optional[Dict]:
        """
        Obtiene el schema de salida de un prompt.

        Args:
            prompt_name: Nombre del prompt

        Returns:
            Dict con el schema o None
        """
        prompt_data = self.load_prompt(prompt_name)
        return prompt_data.get("output_schema")

    def get_instructions(self, prompt_name: str) -> list:
        """
        Obtiene las instrucciones de un prompt.

        Args:
            prompt_name: Nombre del prompt

        Returns:
            Lista de instrucciones
        """
        prompt_data = self.load_prompt(prompt_name)
        return prompt_data.get("instructions", [])

    def get_quality_gates(self, prompt_name: str) -> Dict:
        """
        Obtiene los quality gates de un prompt.

        Args:
            prompt_name: Nombre del prompt

        Returns:
            Dict con quality gates
        """
        prompt_data = self.load_prompt(prompt_name)
        return prompt_data.get("quality_gates", {})

    def get_delimiter(self) -> str:
        """
        Obtiene el delimitador estándar para separar reporte de fix_plan.

        Returns:
            String del delimitador
        """
        config = self.load_config()
        return (
            config.get("configuration", {})
            .get("output_settings", {})
            .get("delimiter", "---START_FIX_PLAN---")
        )

    def list_available_prompts(self) -> list:
        """
        Lista todos los prompts disponibles.

        Returns:
            Lista de nombres de prompts
        """
        return list(self.AVAILABLE_PROMPTS.keys())

    def clear_cache(self):
        """Limpia el caché de prompts."""
        self._cache.clear()
        self._config = None
        logger.info("Prompt cache cleared")

    def _load_json_file(self, filename: str) -> Dict[str, Any]:
        """
        Carga un archivo JSON del directorio de prompts.

        Args:
            filename: Nombre del archivo

        Returns:
            Dict con el contenido del JSON

        Raises:
            FileNotFoundError: Si el archivo no existe
            json.JSONDecodeError: Si el JSON es inválido
        """
        filepath = self.PROMPTS_DIR / filename

        if not filepath.exists():
            logger.error(f"Prompt file not found: {filepath}")
            raise FileNotFoundError(f"Prompt file not found: {filepath}")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {filename}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
            raise

    def _validate_prompt_structure(self, prompt_data: Dict, prompt_name: str):
        """
        Valida que el prompt tenga la estructura mínima requerida.

        Args:
            prompt_data: Datos del prompt
            prompt_name: Nombre del prompt

        Raises:
            ValueError: Si la estructura es inválida
        """
        required_fields = ["version", "name", "system_prompt"]
        missing = [field for field in required_fields if field not in prompt_data]

        if missing:
            logger.warning(f"Prompt {prompt_name} missing fields: {missing}")

        # Verificar que system_prompt no esté vacío
        if not prompt_data.get("system_prompt", "").strip():
            logger.error(f"Prompt {prompt_name} has empty system_prompt")
            raise ValueError(f"Prompt {prompt_name} has empty system_prompt")


# Instancia singleton para uso global
prompt_loader = PromptLoader()


def get_prompt_loader() -> PromptLoader:
    """
    Obtiene la instancia singleton del PromptLoader.

    Returns:
        PromptLoader instance
    """
    return prompt_loader


def load_prompt(prompt_name: str) -> Dict[str, Any]:
    """
    Función helper para cargar un prompt.

    Args:
        prompt_name: Nombre del prompt

    Returns:
        Dict con el prompt
    """
    return prompt_loader.load_prompt(prompt_name)


def get_system_prompt(prompt_name: str) -> str:
    """
    Función helper para obtener system prompt.

    Args:
        prompt_name: Nombre del prompt

    Returns:
        System prompt string
    """
    return prompt_loader.get_system_prompt(prompt_name)


def get_user_template(prompt_name: str) -> str:
    """
    Función helper para obtener user template.

    Args:
        prompt_name: Nombre del prompt

    Returns:
        User template string
    """
    return prompt_loader.get_user_template(prompt_name)
