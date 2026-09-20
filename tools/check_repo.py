#!/usr/bin/env python3
"""Validate the Network Diagnostics repository without importing Home Assistant."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
from generate_source_manifest import build_manifest_lines

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "network_diagnostics"
PLACEHOLDER = "REPLACE_WITH_"
VERSION = "0.2.0"


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        fail(f"invalid JSON in {path.relative_to(ROOT)}: {err}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--allow-placeholders",
        action="store_true",
        help="Allow pre-repository manifest URL/codeowner placeholders.",
    )
    args = parser.parse_args()

    required = [
        ROOT / "README.md",
        ROOT / "ORBI_NEXTDNS_SETUP.md",
        ROOT / "DECISIONS_AND_HANDOFF.md",
        ROOT / "RELEASE_NOTES_v0.2.0.md",
        ROOT / "REPOSITORY_SETUP.md",
        ROOT / "CHANGELOG.md",
        ROOT / "STATUS.md",
        ROOT / "VALIDATION.txt",
        ROOT / "SOURCE_MANIFEST.sha256",
        ROOT / "LICENSE",
        ROOT / "hacs.json",
        ROOT / "pyproject.toml",
        ROOT / ".github" / "workflows" / "validate.yml",
        COMP / "manifest.json",
        COMP / "__init__.py",
        COMP / "config_flow.py",
        COMP / "runtime.py",
        COMP / "classifier.py",
        COMP / "discovery.py",
        COMP / "validation.py",
        COMP / "diagnostics.py",
        COMP / "system_health.py",
        COMP / "translations" / "en.json",
        COMP / "frontend" / "network-diagnostics-panel.js",
        COMP / "brand" / "icon.png",
        COMP / "brand" / "icon@2x.png",
    ]
    for path in required:
        if not path.is_file():
            fail(f"missing {path.relative_to(ROOT)}")

    # HACS allows only one integration directory in this repository shape.
    cc_root = ROOT / "custom_components"
    integration_dirs = sorted(path.name for path in cc_root.iterdir() if path.is_dir())
    if integration_dirs != ["network_diagnostics"]:
        fail(f"expected exactly custom_components/network_diagnostics; found {integration_dirs}")

    manifest = load_json(COMP / "manifest.json")
    if manifest.get("domain") != "network_diagnostics":
        fail("manifest domain mismatch")
    if manifest.get("name") != "Network Diagnostics":
        fail("manifest name mismatch")
    if manifest.get("version") != VERSION:
        fail(f"manifest version mismatch (expected {VERSION})")
    if manifest.get("config_flow") is not True:
        fail("manifest config_flow must be true")
    if manifest.get("single_config_entry") is not True:
        fail("manifest single_config_entry must be true")
    if manifest.get("iot_class") != "calculated":
        fail("manifest iot_class must be calculated")
    if manifest.get("integration_type") != "helper":
        fail("manifest integration_type must be helper")

    required_dependencies = {"frontend", "http", "panel_custom", "uptime_kuma", "websocket_api"}
    dependencies = set(manifest.get("dependencies", []))
    missing_deps = sorted(required_dependencies - dependencies)
    if missing_deps:
        fail(f"manifest missing dependencies: {', '.join(missing_deps)}")

    for key in ("documentation", "issue_tracker"):
        value = manifest.get(key)
        if not isinstance(value, str) or not value.startswith("https://github.com/"):
            fail(f"manifest {key} must be a GitHub HTTPS URL")
    codeowners = manifest.get("codeowners")
    if not isinstance(codeowners, list) or not codeowners or not all(
        isinstance(item, str) and item.startswith("@") for item in codeowners
    ):
        fail("manifest codeowners must contain at least one @owner")
    if not args.allow_placeholders and PLACEHOLDER in json.dumps(manifest):
        fail("manifest still contains repository placeholders; run tools/finalize_repo.py")

    hacs = load_json(ROOT / "hacs.json")
    if hacs.get("name") != "Network Diagnostics":
        fail("hacs.json name mismatch")
    if not re.fullmatch(r"\d{4}\.\d+\.\d+", str(hacs.get("homeassistant", ""))):
        fail("hacs.json homeassistant must be a Home Assistant version")

    config_flow_text = (COMP / "config_flow.py").read_text(encoding="utf-8")
    if "ConfigFlowResult" not in config_flow_text:
        fail("config_flow.py must use current ConfigFlowResult typing")
    if "homeassistant.data_entry_flow import FlowResult" in config_flow_text:
        fail("config_flow.py still imports legacy FlowResult typing")

    translations = load_json(COMP / "translations" / "en.json")
    if translations.get("title") != "Network Diagnostics":
        fail("translation title mismatch")
    if (COMP / "strings.json").exists():
        fail("custom integration should use translations/en.json, not strings.json")

    for path in COMP.rglob("*.py"):
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as err:
            fail(f"Python syntax error in {path.relative_to(ROOT)}: {err}")

    js = (COMP / "frontend" / "network-diagnostics-panel.js").read_text(encoding="utf-8")
    for required_string in (
        "network_diagnostics/get_snapshot",
        "network_diagnostics/analyze",
        'customElements.define("network-diagnostics-panel"',
    ):
        if required_string not in js:
            fail(f"panel JavaScript missing {required_string!r}")
    if "fetch(" in js or "XMLHttpRequest" in js:
        fail("panel must not make direct HTTP/XHR requests")

    # Verify brand assets are actual PNG files rather than placeholder text.
    png_magic = b"\x89PNG\r\n\x1a\n"
    for path in (COMP / "brand" / "icon.png", COMP / "brand" / "icon@2x.png"):
        if path.read_bytes()[:8] != png_magic:
            fail(f"{path.relative_to(ROOT)} is not a PNG")

    obsolete = [
        ROOT / "dashboard",
        ROOT / "RELEASE_NOTES_v0.1.0.md",
    ]
    for path in obsolete:
        if path.exists():
            fail(f"obsolete v0.1 artifact still present: {path.relative_to(ROOT)}")

    forbidden_paths = []
    for path in ROOT.rglob("*"):
        if path.is_dir() and path.name in {"__pycache__", ".pytest_cache"}:
            forbidden_paths.append(path)
        elif path.is_file() and (path.suffix in {".pyc", ".pyo"} or path.name == ".DS_Store"):
            forbidden_paths.append(path)
    if forbidden_paths:
        fail(
            "generated/cache files present: "
            + ", ".join(str(path.relative_to(ROOT)) for path in forbidden_paths[:20])
        )

    expected_manifest = "\n".join(build_manifest_lines()) + "\n"
    actual_manifest = (ROOT / "SOURCE_MANIFEST.sha256").read_text(encoding="utf-8")
    if actual_manifest != expected_manifest:
        fail("SOURCE_MANIFEST.sha256 is stale; run tools/generate_source_manifest.py")

    # Keep current docs from accidentally reverting to the old deployment model.
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if "sidebar panel" not in readme or "Network Diagnostics" not in readme:
        fail("README does not document the integration-owned sidebar panel")
    if "[ND:gateway]" not in readme or "[ND:mesh-child:" not in readme:
        fail("README does not document the generic Kuma naming contract")

    print("Repository checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
