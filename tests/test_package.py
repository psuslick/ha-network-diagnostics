from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "network_diagnostics"


def test_manifest_shape():
    manifest = json.loads((COMP / "manifest.json").read_text())
    assert manifest["domain"] == "network_diagnostics"
    assert manifest["version"] == "0.2.0"
    assert manifest["config_flow"] is True
    assert manifest["single_config_entry"] is True
    assert manifest["iot_class"] == "calculated"
    assert "uptime_kuma" in manifest["dependencies"]
    assert "panel_custom" in manifest["dependencies"]


def test_custom_integration_uses_translations_en_not_strings_json():
    assert (COMP / "translations" / "en.json").exists()
    assert not (COMP / "strings.json").exists()
    json.loads((COMP / "translations" / "en.json").read_text())


def test_expected_files_exist():
    for name in (
        "sensor.py",
        "binary_sensor.py",
        "event.py",
        "button.py",
        "diagnostics.py",
        "system_health.py",
        "config_flow.py",
        "discovery.py",
        "roles.py",
        "observations.py",
        "frontend.py",
        "websocket.py",
        "targets.py",
        "validation.py",
        "kuma_ids.py",
    ):
        assert (COMP / name).exists()
    assert (COMP / "frontend" / "network-diagnostics-panel.js").exists()


def test_config_flow_uses_current_config_flow_result_type():
    text = (COMP / "config_flow.py").read_text()
    assert "ConfigFlowResult" in text
    assert "homeassistant.data_entry_flow import FlowResult" not in text


def test_all_python_files_parse():
    for path in COMP.rglob("*.py"):
        ast.parse(path.read_text(), filename=str(path))


def test_no_direct_network_client_imports():
    banned = {"aiohttp", "requests", "httpx", "socket", "asyncio_dgram", "ping3"}
    for path in COMP.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(alias.name.split(".")[0] in banned for alias in node.names), path
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in banned, path


def test_panel_calls_only_local_websocket_contract():
    js = (COMP / "frontend" / "network-diagnostics-panel.js").read_text()
    assert "network_diagnostics/get_snapshot" in js
    assert "network_diagnostics/analyze" in js
    assert "fetch(" not in js
    assert "XMLHttpRequest" not in js


def test_hacs_json_parses():
    data = json.loads((ROOT / "hacs.json").read_text())
    assert data["name"] == "Network Diagnostics"
    assert data["homeassistant"] == "2026.9.0"
    assert "render_readme" not in data


def test_v02_has_integration_owned_panel_not_dashboard_artifact():
    assert not (ROOT / "dashboard").exists()
    assert not (ROOT / "RELEASE_NOTES_v0.1.0.md").exists()


def test_websocket_runtime_lookup_fails_closed_when_entry_not_loaded():
    text = (COMP / "websocket.py").read_text()
    assert 'getattr(entries[0], "runtime_data", None)' in text


def test_source_manifest_tooling_is_present():
    assert (ROOT / "tools" / "generate_source_manifest.py").exists()
    assert "write_manifest()" in (ROOT / "tools" / "finalize_repo.py").read_text()

