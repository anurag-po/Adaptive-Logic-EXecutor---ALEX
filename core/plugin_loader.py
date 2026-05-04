"""
ALEX -- Plugin Loader (Phase 3)
Auto-discovers action modules from the actions/ directory and builds
the dispatch table dynamically. No more manual mapping in router.py.

Drop a new actions/my_actions.py + add entries to knowledge.md
and they're automatically available.
"""

import os
import importlib
import inspect
import pkgutil

import config
from utils.helpers import get_logger

logger = get_logger()


class PluginLoader:
    """
    Scans the actions/ package for modules and discovers public functions.
    Cross-references with the knowledge.md registry to build dispatch table.
    """

    def __init__(self, registry_functions: dict[str, list[str]]):
        """
        Args:
            registry_functions: dict from RegistryValidator.get_all_functions()
                                mapping function_name -> [param_names]
        """
        self._registry = registry_functions
        self._dispatch: dict[str, callable] = {}
        self._skipped: list[str] = []

    def discover(self) -> dict[str, callable]:
        """
        Scan actions/ for modules, discover functions, and return
        a dispatch table of function_name -> callable.
        """
        actions_package = "actions"

        try:
            package = importlib.import_module(actions_package)
        except ImportError as e:
            logger.error(f"Cannot import actions package: {e}")
            return {}

        package_path = os.path.dirname(package.__file__)

        for importer, module_name, is_pkg in pkgutil.iter_modules([package_path]):
            if module_name.startswith("_"):
                continue  # Skip __init__, __pycache__, etc.

            full_module_name = f"{actions_package}.{module_name}"

            try:
                module = importlib.import_module(full_module_name)
                self._scan_module(module, module_name)
            except Exception as e:
                logger.warning(
                    f"Plugin load failed for {full_module_name}: {e}"
                )

        logger.info(
            f"Plugin loader: {len(self._dispatch)} functions discovered "
            f"from actions/ ({len(self._skipped)} skipped, not in registry)"
        )

        return self._dispatch

    def _scan_module(self, module, module_name: str):
        """
        Inspect a module for public callable functions and register
        those that exist in the knowledge.md registry.
        """
        for name, obj in inspect.getmembers(module, inspect.isfunction):
            # Skip private/internal functions
            if name.startswith("_"):
                continue

            # Skip functions imported from other modules (only module's own)
            if getattr(obj, "__module__", "") != module.__name__:
                continue

            # Check if this function is in the registry
            if name in self._registry:
                self._dispatch[name] = obj
            else:
                self._skipped.append(name)

    def get_dispatch_table(self) -> dict[str, callable]:
        """Return the discovered dispatch table."""
        return dict(self._dispatch)

    def get_skipped(self) -> list[str]:
        """Return functions found in modules but not in registry."""
        return list(self._skipped)
