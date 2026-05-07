"""
MCP Dependency Manager - Auto-install pip packages for generated skills

When LLM generates skills with external dependencies (yfinance, requests, etc.),
this manager automatically installs them in the container.
"""
import subprocess
import re
from typing import List, Set, Dict
from pathlib import Path
from logging_config import get_logger

logger = get_logger(__name__)


class MCPDependencyManager:
    """
    Manages Python dependencies for MCP skill plugins.

    Features:
    - Extract imports from skill code
    - Auto-install missing packages via pip
    - Cache installed packages
    - Handle conflicts safely
    """

    def __init__(self):
        self._installed_cache: Set[str] = set()
        self._import_to_package_map = {
            # Common mappings
            'yfinance': 'yfinance',
            'requests': 'requests',
            'pandas': 'pandas',
            'numpy': 'numpy',
            'BeautifulSoup': 'beautifulsoup4',
            'bs4': 'beautifulsoup4',
            'PIL': 'Pillow',
            'matplotlib': 'matplotlib',
            'seaborn': 'seaborn',
            'sqlalchemy': 'sqlalchemy',
            'asyncpg': 'asyncpg',
            'httpx': 'httpx',
            'aiohttp': 'aiohttp',
            'pydantic': 'pydantic',
            'redis': 'redis',
            'celery': 'celery',
            'openai': 'openai',
            'anthropic': 'anthropic',
        }

    def extract_imports(self, skill_code: str) -> Set[str]:
        """
        Extract import statements from skill code.

        Args:
            skill_code: Python code to analyze

        Returns:
            Set of imported module names
        """
        imports = set()

        # Match: import xyz, import xyz as abc, from xyz import ...
        patterns = [
            r'^import\s+(\w+)',
            r'^from\s+(\w+)',
            r'^import\s+(\w+\.\w+)',  # import package.module
        ]

        for line in skill_code.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    import_name = match.group(1)
                    # Get top-level package
                    top_level = import_name.split('.')[0]
                    imports.add(top_level)

        # Filter out standard library
        imports = self._filter_stdlib(imports)
        return imports

    def _filter_stdlib(self, imports: Set[str]) -> Set[str]:
        """Remove Python standard library modules."""
        stdlib_modules = {
            'os', 'sys', 're', 'json', 'datetime', 'pathlib', 'typing',
            'asyncio', 'collections', 'itertools', 'functools', 'uuid',
            'logging', 'math', 'random', 'hashlib', 'base64', 'time',
            'inspect', 'importlib', 'traceback', 'threading', 'multiprocessing',
        }

        # Also filter out project modules
        project_modules = {
            'canonical_skills', 'logging_config', 'database', 'models',
            'llm_fallback', 'mcp_manager', 'infrastructure'
        }

        return imports - stdlib_modules - project_modules

    def map_imports_to_packages(self, imports: Set[str]) -> Set[str]:
        """
        Map import names to pip package names.

        Args:
            imports: Set of import names

        Returns:
            Set of pip package names
        """
        packages = set()

        for imp in imports:
            # Try direct mapping first
            if imp in self._import_to_package_map:
                packages.add(self._import_to_package_map[imp])
            else:
                # Default: import name == package name
                packages.add(imp)

        return packages

    async def install_dependencies(
        self,
        skill_code: str,
        skill_id: str
    ) -> Dict[str, any]:
        """
        Extract and install dependencies for a skill.

        Args:
            skill_code: Python skill code
            skill_id: Skill identifier

        Returns:
            {
                "success": bool,
                "installed": List[str],
                "failed": List[str],
                "skipped": List[str]
            }
        """
        # Step 1: Extract imports
        imports = self.extract_imports(skill_code)

        if not imports:
            logger.info(
                "mcp_no_external_deps",
                skill_id=skill_id
            )
            return {
                "success": True,
                "installed": [],
                "failed": [],
                "skipped": []
            }

        logger.info(
            "mcp_deps_found",
            skill_id=skill_id,
            imports=list(imports)
        )

        # Step 2: Map to packages
        packages = self.map_imports_to_packages(imports)

        # Step 3: Filter already installed
        to_install = packages - self._installed_cache

        if not to_install:
            logger.info(
                "mcp_deps_already_installed",
                skill_id=skill_id,
                packages=list(packages)
            )
            return {
                "success": True,
                "installed": [],
                "failed": [],
                "skipped": list(packages)
            }

        # Step 4: Install packages
        installed = []
        failed = []

        for package in to_install:
            try:
                logger.info(
                    "mcp_installing_package",
                    package=package,
                    skill_id=skill_id
                )

                result = subprocess.run(
                    ['pip', 'install', package, '-q'],
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                if result.returncode == 0:
                    installed.append(package)
                    self._installed_cache.add(package)
                    logger.info(
                        "mcp_package_installed",
                        package=package
                    )
                else:
                    failed.append(package)
                    logger.warning(
                        "mcp_package_install_failed",
                        package=package,
                        error=result.stderr
                    )

            except subprocess.TimeoutExpired:
                failed.append(package)
                logger.error(
                    "mcp_package_install_timeout",
                    package=package
                )
            except Exception as e:
                failed.append(package)
                logger.error(
                    "mcp_package_install_error",
                    package=package,
                    error=str(e)
                )

        result = {
            "success": len(failed) == 0,
            "installed": installed,
            "failed": failed,
            "skipped": list(packages - to_install)
        }

        logger.info(
            "mcp_deps_install_complete",
            skill_id=skill_id,
            result=result
        )

        return result

    def check_installed(self, package_name: str) -> bool:
        """Check if package is already installed."""
        try:
            result = subprocess.run(
                ['pip', 'show', package_name],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False


# Singleton instance
mcp_dependency_manager = MCPDependencyManager()
