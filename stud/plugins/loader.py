import importlib.util
import sys
from pathlib import Path
from typing import Dict, Optional, Type

from ..core.exceptions import StudError
from .manifest import PLUGIN_MANIFEST_FILENAME, PluginManifest
from .sdk import Plugin, PluginContext


class PluginLoaderError(StudError):
    pass


class PluginLoader:
    def __init__(self, plugins_dir: Path):
        self.plugins_dir = Path(plugins_dir)
        self._loaded: Dict[str, Plugin] = {}
        self._contexts: Dict[str, PluginContext] = {}

    def _load_class(self, plugin_dir: Path, manifest: PluginManifest) -> Type[Plugin]:
        module_name, _, class_name = manifest.entry_point.partition(":")
        module_file = plugin_dir / (module_name.replace(".", "/") + ".py")

        if not module_file.exists():
            raise PluginLoaderError(f"entry point module not found: {module_file}")

        spec = importlib.util.spec_from_file_location(
            f"stud_plugin_{manifest.name}.{module_name}", module_file
        )
        if spec is None or spec.loader is None:
            raise PluginLoaderError(f"cannot load module: {module_file}")

        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)

        cls = getattr(mod, class_name, None)
        if cls is None:
            raise PluginLoaderError(f"class {class_name!r} not found in {module_file}")
        if not issubclass(cls, Plugin):
            raise PluginLoaderError(f"{class_name} is not a subclass of Plugin")
        return cls

    def load(self, plugin_dir: Path, config: Optional[dict] = None) -> Plugin:
        plugin_dir = Path(plugin_dir)
        manifest = PluginManifest.load(plugin_dir / PLUGIN_MANIFEST_FILENAME)

        if manifest.name in self._loaded:
            return self._loaded[manifest.name]

        cls = self._load_class(plugin_dir, manifest)
        plugin = cls()
        plugin.name = manifest.name
        plugin.version = manifest.version
        plugin.description = manifest.description

        ctx = PluginContext(plugin_name=manifest.name, config=config or {})
        plugin.setup(ctx)

        self._loaded[manifest.name] = plugin
        self._contexts[manifest.name] = ctx
        return plugin

    def discover(self, config: Optional[Dict[str, dict]] = None) -> Dict[str, Plugin]:
        if not self.plugins_dir.exists():
            return {}
        config = config or {}
        loaded: Dict[str, Plugin] = {}
        for plugin_dir in sorted(self.plugins_dir.iterdir()):
            manifest_file = plugin_dir / PLUGIN_MANIFEST_FILENAME
            if plugin_dir.is_dir() and manifest_file.exists():
                try:
                    plugin = self.load(plugin_dir, config=config.get(plugin_dir.name))
                    loaded[plugin.name] = plugin
                except (PluginLoaderError, Exception):
                    pass
        return loaded

    def unload(self, name: str) -> None:
        plugin = self._loaded.get(name)
        if plugin is None:
            return
        ctx = self._contexts.get(name)
        if ctx:
            plugin.teardown(ctx)
        del self._loaded[name]
        self._contexts.pop(name, None)

    def get(self, name: str) -> Optional[Plugin]:
        return self._loaded.get(name)

    def list(self):
        return list(self._loaded.values())
