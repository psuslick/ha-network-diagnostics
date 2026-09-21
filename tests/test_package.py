from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components" / "network_diagnostics"


def test_manifest_is_installable_privacy_safe_v031_service():
    manifest = json.loads((COMP / "manifest.json").read_text())
    assert manifest["version"] == "0.3.1"
    assert manifest["domain"] == "network_diagnostics"
    assert manifest["integration_type"] == "service"
    assert "uptime_kuma" in manifest["dependencies"]
    assert "REPLACE_WITH_" not in json.dumps(manifest)
    assert isinstance(manifest.get("codeowners", []), list)
    for owner in manifest.get("codeowners", []):
        assert owner.startswith("@")
    if "documentation" in manifest:
        assert manifest["documentation"].startswith("https://github.com/")
    if "issue_tracker" in manifest:
        assert manifest["issue_tracker"].startswith("https://github.com/")


def test_no_legacy_name_parser_or_private_kuma_runtime_dependency():
    assert not (COMP / "roles.py").exists()
    discovery = (COMP / "discovery.py").read_text()
    assert ".runtime_data" not in discovery


def test_config_flow_has_reconfigure_and_options_reload():
    text = (COMP / "config_flow.py").read_text()
    assert "async_step_reconfigure" in text
    assert "async_update_reload_and_abort" in text
    assert "OptionsFlowWithReload" in text


def test_unconfigured_setup_state_is_not_network_incident_or_monitoring_fault():
    classifier = (COMP / "classifier.py").read_text()
    runtime = (COMP / "runtime.py").read_text()
    sensor = (COMP / "sensor.py").read_text()
    assert 'SETUP_REQUIRED = "Setup required"' in classifier
    assert "if result.setup_required:" in runtime
    assert 'return "Not configured"' in sensor


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
    assert "One-time setup required" in js
    assert "Settings → Devices & services → Integrations → Network Diagnostics" in js


def test_success_contract_documents_single_raw_historian_and_live_regressions():
    criteria = (ROOT / "SUCCESS_CRITERIA.md").read_text()
    assert "One raw historian" in criteria
    assert "Uptime Kuma is authoritative" in criteria
    assert "Normal Integrations visibility" in criteria
    assert "Setup state is not a fault state" in criteria
    assert "Install artifact metadata must be immediately usable" in criteria


def test_source_has_no_vendor_specific_profile_module():
    combined = "\n".join(
        path.read_text(errors="replace")
        for path in COMP.rglob("*")
        if path.is_file() and path.suffix in {".py", ".json", ".js"}
    )
    for forbidden in ("LEGACY_VENDOR_PROFILE", "DEPLOYMENT_SENTINELS"):
        assert forbidden not in combined
