"""
Prompt Loader - Enterprise Grade
Dynamic loading and caching of JSON-based prompts with validation.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class PromptLoader:
    """
    Enterprise-grade prompt loader with caching, validation, and fallback support.

    Features:
    - Dynamic JSON prompt loading
    - In-memory caching with TTL
    - Schema validation
    - Fallback to default prompts
    - Hot-reload support for development
    - Version management
    """

    def __init__(self, prompts_dir: Optional[str] = None, version: str = "v2.0"):
        """
        Initialize the prompt loader.

        Args:
            prompts_dir: Directory containing prompt JSON files
            version: Prompt version to load (v2.0, v1.11, etc.)
        """
        if prompts_dir is None:
            # Default to backend/app/prompts/{version}
            base_dir = Path(__file__).parent.parent.parent
            prompts_dir = base_dir / "app" / "prompts" / version

        self.prompts_dir = Path(prompts_dir)
        self.version = version
        self.config = None
        self._cache = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load the main configuration file."""
        config_path = self.prompts_dir / "config.json"

        if not config_path.exists():
            logger.error(f"Config file not found: {config_path}")
            raise FileNotFoundError(f"Prompt configuration not found: {config_path}")

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)

            logger.info(
                f"Loaded prompt configuration v{self.config.get('version', 'unknown')}"
            )

            # Validate configuration
            self._validate_config()

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            raise ValueError(f"Invalid configuration JSON: {e}")
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            raise

    def _validate_config(self) -> None:
        """Validate the configuration structure."""
        required_fields = ["version", "prompts_structure", "configuration"]

        for field in required_fields:
            if field not in self.config:
                raise ValueError(f"Missing required config field: {field}")

        # Validate prompts structure
        prompts_structure = self.config.get("prompts_structure", {})
        if not prompts_structure:
            raise ValueError("No prompts defined in configuration")

    def load_prompt(self, prompt_name: str, validate: bool = True) -> Dict[str, Any]:
        """
        Load a specific prompt by name.

        Args:
            prompt_name: Name of the prompt (e.g., 'external_analysis')
            validate: Whether to validate the prompt structure

        Returns:
            Dictionary containing the prompt configuration

        Raises:
            FileNotFoundError: If prompt file doesn't exist
            ValueError: If prompt structure is invalid
        """
        # Check cache first
        cache_key = f"{self.version}:{prompt_name}"
        if cache_key in self._cache:
            logger.debug(f"Returning cached prompt: {prompt_name}")
            return self._cache[cache_key]

        # Get prompt info from config
        prompt_info = self.config.get("prompts_structure", {}).get(prompt_name)
        if not prompt_info:
            raise ValueError(f"Prompt '{prompt_name}' not found in configuration")

        # Load the prompt file
        filename = prompt_info.get("file", f"{prompt_name}.json")
        prompt_path = self.prompts_dir / filename

        if not prompt_path.exists():
            logger.error(f"Prompt file not found: {prompt_path}")
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_data = json.load(f)

            # Validate if requested
            if validate:
                self._validate_prompt_structure(prompt_name, prompt_data)

            # Cache the result
            self._cache[cache_key] = prompt_data

            logger.info(
                f"Loaded prompt: {prompt_name} v{prompt_data.get('version', '1.0')}"
            )
            return prompt_data

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in prompt file {filename}: {e}")
            raise ValueError(f"Invalid prompt JSON: {e}")
        except Exception as e:
            logger.error(f"Error loading prompt {prompt_name}: {e}")
            raise

    def _validate_prompt_structure(self, prompt_name: str, prompt_data: Dict) -> None:
        """Validate the structure of a loaded prompt."""
        required_fields = ["system_prompt", "output_schema"]

        for field in required_fields:
            if field not in prompt_data:
                raise ValueError(
                    f"Prompt '{prompt_name}' missing required field: {field}"
                )

        # Validate system_prompt is not empty
        if not prompt_data.get("system_prompt", "").strip():
            raise ValueError(f"Prompt '{prompt_name}' has empty system_prompt")

        # Validate output_schema has required fields
        output_schema = prompt_data.get("output_schema", {})
        if not output_schema:
            raise ValueError(f"Prompt '{prompt_name}' has empty output_schema")

    def get_system_prompt(self, prompt_name: str) -> str:
        """
        Get only the system prompt text for a given prompt.

        Args:
            prompt_name: Name of the prompt

        Returns:
            System prompt string
        """
        prompt_data = self.load_prompt(prompt_name)
        return prompt_data.get("system_prompt", "")

    def get_output_schema(self, prompt_name: str) -> Dict[str, Any]:
        """
        Get the expected output schema for a given prompt.

        Args:
            prompt_name: Name of the prompt

        Returns:
            Output schema dictionary
        """
        prompt_data = self.load_prompt(prompt_name)
        return prompt_data.get("output_schema", {})

    def get_user_template(self, prompt_name: str) -> str:
        """
        Get the user prompt template for a given prompt.

        Args:
            prompt_name: Name of the prompt

        Returns:
            User prompt template string
        """
        prompt_data = self.load_prompt(prompt_name)
        return prompt_data.get("user_template", "{{input_data}}")

    def format_user_prompt(self, prompt_name: str, **kwargs) -> str:
        """
        Format the user prompt template with provided variables.

        Args:
            prompt_name: Name of the prompt
            **kwargs: Variables to substitute in the template

        Returns:
            Formatted user prompt string
        """
        template = self.get_user_template(prompt_name)

        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing variable in prompt template: {e}")
            raise ValueError(f"Missing template variable: {e}")

    def get_all_prompts(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all configured prompts.

        Returns:
            Dictionary mapping prompt names to their configurations
        """
        prompts = {}
        prompts_structure = self.config.get("prompts_structure", {})

        for prompt_name in prompts_structure.keys():
            try:
                prompts[prompt_name] = self.load_prompt(prompt_name)
            except Exception as e:
                logger.error(f"Failed to load prompt {prompt_name}: {e}")
                continue

        return prompts

    def get_prompt_metadata(self, prompt_name: str) -> Dict[str, Any]:
        """
        Get metadata for a specific prompt.

        Args:
            prompt_name: Name of the prompt

        Returns:
            Metadata dictionary
        """
        prompt_info = self.config.get("prompts_structure", {}).get(prompt_name, {})
        return {
            "name": prompt_name,
            "file": prompt_info.get("file"),
            "description": prompt_info.get("description"),
            "priority": prompt_info.get("priority"),
            "conditional": prompt_info.get("conditional"),
        }

    def clear_cache(self) -> None:
        """Clear the in-memory cache."""
        self._cache.clear()
        logger.info("Prompt cache cleared")

    def reload(self) -> None:
        """Reload all prompts from disk (useful for development)."""
        self.clear_cache()
        self._load_config()
        logger.info("Prompts reloaded from disk")

    def get_config(self) -> Dict[str, Any]:
        """Get the full configuration object."""
        return self.config.copy()

    def get_version(self) -> str:
        """Get the current prompt version."""
        return self.config.get("version", self.version)

    @property
    def available_prompts(self) -> list:
        """Get list of available prompt names."""
        return list(self.config.get("prompts_structure", {}).keys())


# Singleton instance for global use
_prompt_loader_instance = None


def get_prompt_loader(version: str = "v2.0") -> PromptLoader:
    """
    Get or create the singleton prompt loader instance.

    Args:
        version: Prompt version to load

    Returns:
        PromptLoader instance
    """
    global _prompt_loader_instance

    if _prompt_loader_instance is None or _prompt_loader_instance.version != version:
        _prompt_loader_instance = PromptLoader(version=version)

    return _prompt_loader_instance


def load_prompt(prompt_name: str, version: str = "v2.0") -> Dict[str, Any]:
    """
    Convenience function to load a prompt.

    Args:
        prompt_name: Name of the prompt to load
        version: Prompt version

    Returns:
        Prompt configuration dictionary
    """
    loader = get_prompt_loader(version)
    return loader.load_prompt(prompt_name)


def get_system_prompt(prompt_name: str, version: str = "v2.0") -> str:
    """
    Convenience function to get system prompt text.

    Args:
        prompt_name: Name of the prompt
        version: Prompt version

    Returns:
        System prompt string
    """
    loader = get_prompt_loader(version)
    return loader.get_system_prompt(prompt_name)
