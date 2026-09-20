"""Load pure integration modules without requiring a Home Assistant install."""

from __future__ import annotations

from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
CC = ROOT / "custom_components"
PKG = CC / "network_diagnostics"

custom_components = types.ModuleType("custom_components")
custom_components.__path__ = [str(CC)]
sys.modules.setdefault("custom_components", custom_components)

network_diagnostics = types.ModuleType("custom_components.network_diagnostics")
network_diagnostics.__path__ = [str(PKG)]
sys.modules.setdefault("custom_components.network_diagnostics", network_diagnostics)
