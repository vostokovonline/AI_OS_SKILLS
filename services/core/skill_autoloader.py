"""
Auto-Load Skills from Canonical Skills Directory

Scans canonical_skills/ directory at startup and automatically
registers all skills with their manifests.

This makes skills autonomous - no manual registration required.

Author: Claude (Control Center v3.1)
Date: 2026-03-03
"""

import os
import importlib
import inspect
from pathlib import Path
from typing import List, Dict, Any
from logging_config import get_logger

logger = get_logger(__name__)


class SkillAutoLoader:
    """
    Automatically discovers and loads skills from canonical_skills/.

    Scans for:
    - Skill classes with manifest attribute
    - Standalone manifest variables
    - Registration functions
    """

    def __init__(self, skills_dir: str = None):
        if skills_dir is None:
            # Default to canonical_skills directory
            current_dir = Path(__file__).parent
            skills_dir = current_dir / "canonical_skills"

        self.skills_dir = Path(skills_dir)
        self.loaded_skills: Dict[str, Any] = {}

    def load_all_skills(self) -> int:
        """
        Load all skills from canonical_skills directory.

        Returns:
            Number of skills loaded
        """
        if not self.skills_dir.exists():
            logger.warning("skills_directory_not_found", path=str(self.skills_dir))
            return 0

        loaded_count = 0

        # Scan for Python files
        for py_file in self.skills_dir.glob("*.py"):
            # Skip __init__, base, and registry files
            if py_file.name.startswith("_") or py_file.name in ["base.py", "registry.py"]:
                continue

            try:
                # Import module
                module_name = f"canonical_skills.{py_file.stem}"
                module = importlib.import_module(module_name)

                # Find skills in module
                skills_found = self._extract_skills_from_module(module, py_file.stem)

                for skill_name, skill_data in skills_found.items():
                    self.loaded_skills[skill_name] = skill_data
                    loaded_count += 1

                    logger.info(
                        "skill_loaded",
                        skill_name=skill_name,
                        source=py_file.name
                    )

            except Exception as e:
                # Log but don't fail - continue with other files
                logger.warning(
                    "skill_load_skipped",
                    file=py_file.name,
                    error=str(e)[:200],  # Truncate long errors
                    action="skipped_file"
                )
                continue

        logger.info(
            "skills_autoload_completed",
            total_loaded=loaded_count,
            skills_dir=str(self.skills_dir)
        )

        return loaded_count

    def _extract_skills_from_module(self, module, filename: str) -> Dict[str, Any]:
        """
        Extract skill definitions from a module.

        Looks for:
        1. Classes with .manifest attribute
        2. Variables ending in _MANIFEST
        3. Functions ending in _skill
        """
        skills = {}

        # Check for manifest variables (e.g., TEXT_TO_FILE_MANIFEST)
        for attr_name in dir(module):
            if attr_name.endswith("_MANIFEST"):
                manifest = getattr(module, attr_name)

                # Check if it's a SkillManifest
                if hasattr(manifest, "name"):
                    skill_info = {
                        "type": "manifest",
                        "manifest": manifest,
                        "module": module.__name__,
                        "filename": filename
                    }

                    # Also look for corresponding function
                    func_name = attr_name.replace("_MANIFEST", "").lower()
                    if hasattr(module, func_name):
                        skill_info["function"] = getattr(module, func_name)

                    skills[manifest.name] = skill_info

        # Check for skill classes
        for attr_name in dir(module):
            if attr_name.endswith("Skill") and not attr_name.startswith("_"):
                skill_class = getattr(module, attr_name)

                if inspect.isclass(skill_class):
                    # Check if it has manifest
                    if hasattr(skill_class, "manifest"):
                        skills[skill_class.manifest.name] = {
                            "type": "class",
                            "class": skill_class,
                            "manifest": skill_class.manifest,
                            "module": module.__name__,
                            "filename": filename
                        }

        return skills

    def get_all_skills(self) -> List[Dict[str, Any]]:
        """
        Get all loaded skills in API-friendly format.

        Returns:
            List of skill info dictionaries
        """
        result = []

        # First try to get skills from auto-loader
        for skill_name, skill_data in self.loaded_skills.items():
            manifest = skill_data.get("manifest")

            if manifest is None:
                continue

            # Extract capabilities from manifest
            capabilities = []
            if hasattr(manifest, "inputs"):
                if hasattr(manifest.inputs, "required"):
                    capabilities.extend(manifest.inputs.required)
                if hasattr(manifest.inputs, "optional"):
                    capabilities.extend(manifest.inputs.optional)

            # Extract contracts
            contracts = {}
            if hasattr(manifest, "contracts"):
                contracts = manifest.contracts

            result.append({
                "skill_id": manifest.name,
                "version": getattr(manifest, "version", "1.0.0"),
                "author": getattr(manifest, "author", "system"),
                "description": getattr(manifest, "description", ""),
                "capabilities": capabilities,
                "contracts": contracts,
                "category": getattr(manifest, "category", "general"),
                "filename": skill_data.get("filename", "")
            })

        # If no skills from auto-loader, try to get from goal_executor_v2
        if not result:
            try:
                from goal_executor_v2 import goal_executor_v2
                if hasattr(goal_executor_v2, "skills"):
                    for skill_name in goal_executor_v2.skills.keys():
                        result.append({
                            "skill_id": skill_name,
                            "version": "1.0.0",
                            "author": "system",
                            "description": f"Auto-discovered skill: {skill_name}",
                            "capabilities": ["execute"],
                            "contracts": {},
                            "category": "auto_discovered",
                            "filename": "goal_executor_v2"
                        })
            except Exception as e:
                logger.warning("failed_to_get_skills_from_executor", error=str(e))

        return result

    def get_skill(self, skill_name: str) -> Dict[str, Any]:
        """
        Get specific skill info.

        Args:
            skill_name: Name of the skill

        Returns:
            Skill info dict or None
        """
        all_skills = self.get_all_skills()
        for skill in all_skills:
            if skill["skill_id"] == skill_name:
                return skill
        return None


# Global instance
skill_auto_loader = SkillAutoLoader()


def load_skills_on_startup():
    """
    Load all skills at system startup.

    Call this in main.py after app initialization.
    """
    count = skill_auto_loader.load_all_skills()
    logger.info("startup_skill_loading", count=count)
    return count
