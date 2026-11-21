"""
Skill Manager and Base Skill Definition for Multi-AI Orchestrator.

Provides the abstract BaseSkill contract and dynamic SkillManager
with role-based access control, tool schema generation, and model mapping.
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from core.security_guard import SecurityGuard

logger = logging.getLogger(__name__)


class BaseSkill(ABC):
    """
    Abstract base class for all orchestrator skills.

    Each concrete skill encapsulates an autonomous tool, declaring its
    required security permissions, parameters schema, and asynchronous execution logic.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier name for the skill."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description explaining the skill's capabilities."""
        ...

    @property
    @abstractmethod
    def required_permissions(self) -> list[str]:
        """List of security permissions required by this skill."""
        ...

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """
        JSON schema defining input parameters for this skill.
        Can be overridden by subclasses to define specific inputs.
        """
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    @abstractmethod
    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the skill logic asynchronously.

        Args:
            params: Dictionary of input arguments matching parameters_schema.

        Returns:
            dict[str, Any]: Resulting payload or status from the operation.
        """
        ...

    def to_tool_schema(self) -> dict[str, Any]:
        """
        Export skill definition as an OpenAI-compatible function tool schema.

        Returns:
            dict[str, Any]: Formatted tool definition for AI model function calling.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }


class SkillManager:
    """
    Dynamic skill registry, model-to-skill mapper, and secured execution dispatcher.
    """

    def __init__(self, security_guard: SecurityGuard | None = None) -> None:
        """
        Initialize SkillManager with a reference to the central SecurityGuard.

        Args:
            security_guard: Optional SecurityGuard instance. If None, uses singleton.
        """
        self._skills: dict[str, BaseSkill] = {}
        self._security: SecurityGuard = (
            security_guard if security_guard is not None else SecurityGuard()
        )
        self._model_mappings: dict[str, list[str]] = {}  # model_id -> [skill_names]
        self._global_skills: set[str] = set()  # Skills available to all models

    @property
    def skills(self) -> dict[str, BaseSkill]:
        """Dictionary of currently registered skills."""
        return self._skills

    def register_skill(self, skill: BaseSkill) -> None:
        """
        Register a new skill instance in the registry.

        Args:
            skill: An instance of a BaseSkill subclass.

        Raises:
            TypeError: If skill is not an instance of BaseSkill.
        """
        if not isinstance(skill, BaseSkill):
            raise TypeError(f"Skill must be an instance of BaseSkill, got {type(skill).__name__}")
        self._skills[skill.name] = skill
        logger.info("Registered skill '%s'", skill.name)

    def unregister_skill(self, name: str) -> None:
        """
        Remove a skill from registry and associated mappings.

        Args:
            name: Identifier name of the skill to remove.
        """
        if name in self._skills:
            del self._skills[name]
        self._global_skills.discard(name)
        for model_id in self._model_mappings:
            if name in self._model_mappings[model_id]:
                self._model_mappings[model_id].remove(name)
        logger.info("Unregistered skill '%s'", name)

    def discover_and_load(self, skills_dir: str = "./skills/") -> int:
        """
        Dynamically discover and load BaseSkill classes from a directory.

        Args:
            skills_dir: Directory path containing Python skill modules.

        Returns:
            int: Total count of newly loaded and registered skills.
        """
        dir_path = Path(skills_dir).resolve()
        if not dir_path.exists() or not dir_path.is_dir():
            logger.warning("Skills directory does not exist: %s", dir_path)
            return 0

        loaded_count = 0
        for file_path in dir_path.glob("*.py"):
            if file_path.name.startswith("_") or file_path.name == "__init__.py":
                continue

            module_name = f"skills.{file_path.stem}"
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec is None or spec.loader is None:
                    continue

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(obj, BaseSkill)
                        and obj is not BaseSkill
                        and not inspect.isabstract(obj)
                    ):
                        try:
                            skill_instance = obj()
                            self.register_skill(skill_instance)
                            loaded_count += 1
                        except Exception as inst_err:
                            logger.error(
                                "Failed to instantiate skill class %s: %s",
                                obj.__name__,
                                inst_err,
                            )
            except Exception as mod_err:
                logger.error("Failed to load skill module from %s: %s", file_path, mod_err)

        return loaded_count

    async def execute_skill(self, skill_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a registered skill with security permission enforcement.

        Args:
            skill_name: Name of the skill to execute.
            params: Parameters dictionary required for skill execution.

        Returns:
            dict[str, Any]: Output dictionary formatted as:
                {'success': bool, 'result': Any, 'error': Optional[str]}
        """
        skill = self._skills.get(skill_name)
        if skill is None:
            return {
                "success": False,
                "result": None,
                "error": f"Skill '{skill_name}' is not registered.",
            }

        target_path = params.get("path") or params.get("cwd")

        # Verify all permissions declared by the skill
        for perm in skill.required_permissions:
            allowed, reason = self._security.check_permission(perm, target_path=target_path)
            if not allowed:
                return {
                    "success": False,
                    "result": None,
                    "error": f"Permission denied for '{perm}': {reason}",
                }

        try:
            result = await skill.execute(params)
            return {
                "success": True,
                "result": result,
                "error": None,
            }
        except Exception as exc:
            logger.exception("Error executing skill '%s': %s", skill_name, exc)
            return {
                "success": False,
                "result": None,
                "error": str(exc),
            }

    def get_skills_for_model(self, model_id: str) -> list[BaseSkill]:
        """
        Retrieve list of skills available for a specified AI model.

        Combines model-specific mapped skills and global skills.

        Args:
            model_id: Identifier of the AI model.

        Returns:
            list[BaseSkill]: Available skill instances.
        """
        mapped_names = set(self._model_mappings.get(model_id, []))
        accessible_names = mapped_names | self._global_skills

        return [
            self._skills[name]
            for name in accessible_names
            if name in self._skills
        ]

    def get_all_tool_schemas(self) -> list[dict[str, Any]]:
        """
        Export OpenAI-compatible function calling schemas for all registered skills.

        Returns:
            list[dict]: Tool schemas list for injection into LLM prompts.
        """
        return [skill.to_tool_schema() for skill in self._skills.values()]

    def map_skill_to_model(self, skill_name: str, model_id: str) -> None:
        """
        Associate a skill with a specific AI model.

        Args:
            skill_name: Name of registered skill.
            model_id: Identifier for target model.
        """
        if model_id not in self._model_mappings:
            self._model_mappings[model_id] = []
        if skill_name not in self._model_mappings[model_id]:
            self._model_mappings[model_id].append(skill_name)

    def set_global_skill(self, skill_name: str) -> None:
        """
        Mark a skill as globally available to all models.

        Args:
            skill_name: Name of registered skill.
        """
        self._global_skills.add(skill_name)

    def list_skills(self) -> list[dict[str, Any]]:
        """
        List all registered skills with metadata and availability mappings.

        Returns:
            list[dict[str, Any]]: Metadata descriptions for each skill.
        """
        result = []
        for name, skill in self._skills.items():
            mapped_models = [
                mid for mid, skills in self._model_mappings.items() if name in skills
            ]
            result.append({
                "name": skill.name,
                "description": skill.description,
                "required_permissions": skill.required_permissions,
                "is_global": name in self._global_skills,
                "mapped_models": mapped_models,
                "schema": skill.to_tool_schema(),
            })
        return result
