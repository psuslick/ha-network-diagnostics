from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "network_diagnostics"


def test_manifest_is_generic_v03():
    manifest = json.loads((COMP / "manifest.json").read_text())
    assert manifest["version"] == "0.3.0"
    assert manifest["domain"] == "network_diagnostics"
    assert "uptime_kuma" in manifest["dependencies"]
    assert manifest["documentation"].startswith("https://github.com/")
    assert manifest["issue_tracker"].startswith("https://github.com/")
    assert manifest["codeowners"] and all(owner.startswith("@") for owner in manifest["codeowners"])


def test_no_legacy_name_parser_or_private_kuma_runtime_dependency():
    assert not (COMP / "roles.py").exists()
    discovery = (COMP / "discovery.py").read_text()
    assert ".runtime_data" not in discovery


def test_config_flow_has_reconfigure_and_options_reload():
    text = (COMP / "config_flow.py").read_text()
    assert "async_step_reconfigure" in text
    assert "async_update_reload_and_abort" in text
    assert "OptionsFlowWithReload" in text


def test_runtime_does_not_persist_raw_baseline_samples():
    text = (COMP / "runtime.py").read_text()
    save_section = text[text.index("async def _async_save") :]
    assert '"samples"' not in save_section
    assert '"incidents"' in save_section


def test_custom_panel_uses_ha_websocket_not_direct_http():
    js = (COMP / "frontend" / "network-diagnostics-panel.js").read_text()
    assert "sendMessagePromise" in js
    assert "fetch(" not in js
    assert "XMLHttpRequest" not in js


def test_success_contract_documents_single_raw_historian():
    criteria = (ROOT / "SUCCESS_CRITERIA.md").read_text()
    assert "One raw historian" in criteria
    assert "Uptime Kuma is authoritative" in criteria


def test_source_has_no_vendor_specific_profile_module():
    combined = "\n".join(
        path.read_text(errors="replace")
        for path in COMP.rglob("*")
        if path.is_file() and path.suffix in {".py", ".json", ".js"}
    )
    for forbidden in ("LEGACY_VENDOR_PROFILE", "DEPLOYMENT_SENTINELS"):
        assert forbidden not in combined
