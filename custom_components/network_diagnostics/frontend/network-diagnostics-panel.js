class NetworkDiagnosticsPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._data = null;
    this._loading = false;
    this._lastLoad = 0;
    this._error = null;
  }

  set hass(value) {
    this._hass = value;
    const now = Date.now();
    if (!this._loading && now - this._lastLoad > 5000) this._load();
  }

  get hass() { return this._hass; }

  set panel(value) { this._panel = value; }
  set narrow(value) { this._narrow = value; this._render(); }
  set route(value) { this._route = value; }

  connectedCallback() { this._render(); if (this._hass) this._load(); }

  async _call(type) {
    if (!this._hass) return null;
    return this._hass.connection.sendMessagePromise({ type });
  }

  async _load() {
    if (this._loading || !this._hass) return;
    this._loading = true;
    try {
      this._data = await this._call("network_diagnostics/get_snapshot");
      this._error = null;
      this._lastLoad = Date.now();
    } catch (err) {
      this._error = String(err?.message || err);
    } finally {
      this._loading = false;
      this._render();
    }
  }

  async _analyze() {
    if (this._loading) return;
    this._loading = true;
    this._render();
    try {
      this._data = await this._call("network_diagnostics/analyze");
      this._error = null;
      this._lastLoad = Date.now();
    } catch (err) {
      this._error = String(err?.message || err);
    } finally {
      this._loading = false;
      this._render();
    }
  }

  _escape(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  _list(title, items, cls = "") {
    if (!items?.length) return "";
    return `<section class="detail ${cls}"><h3>${this._escape(title)}</h3><ul>${items.map(x => `<li>${this._escape(x)}</li>`).join("")}</ul></section>`;
  }

  _rootCauses(causes) {
    if (!causes?.length) return `<div class="empty">No supported root-cause hypothesis is active.</div>`;
    return causes.map(cause => {
      const path = cause.causal_path?.length ? cause.causal_path.map(x => this._escape(x)).join(" → ") : "—";
      return `<div class="cause">
        <div class="cause-head"><strong>${this._escape(cause.name)}</strong><span class="pill">${this._escape(cause.confidence)}</span></div>
        <div class="muted">Causal path: ${path}</div>
        ${cause.affected?.length ? `<div class="muted">Affected: ${cause.affected.map(x => this._escape(x)).join(", ")}</div>` : ""}
        ${this._list("Supports this cause", cause.supporting || [], "good")}
        ${this._list("Evidence against broader alternatives", cause.contradicting || [], "warn")}
        ${this._list("Downstream effects", cause.downstream || [])}
      </div>`;
    }).join("");
  }

  _monitorRows(current) {
    const rows = current?.observations || [];
    if (!rows.length) return `<div class="empty">No recognized Uptime Kuma monitors yet.</div>`;
    return `<div class="monitor-grid">
      ${rows.map(row => {
        const state = row.status === true ? "UP" : row.status === false ? "DOWN" : String(row.raw_status || "UNKNOWN").toUpperCase();
        const stateClass = row.status === true ? "good" : row.status === false ? "bad" : "warn";
        const latency = row.response_ms == null ? "—" : `${Math.round(row.response_ms)} ms`;
        const group = row.group ? ` · ${this._escape(row.group)}` : "";
        const target = row.target ? ` · ${this._escape(row.target)}` : "";
        const monitorType = row.monitor_type ? ` · ${this._escape(row.monitor_type)}` : "";
        return `<div class="monitor-row">
          <div><strong>${this._escape(row.label || row.name)}</strong><div class="muted">${this._escape(row.role)}${group}${monitorType}${target}</div></div>
          <div class="latency">${latency}</div>
          <div class="pill ${stateClass}">${this._escape(state)}</div>
        </div>`;
      }).join("")}
    </div>`;
  }

  _incidentRows(data) {
    const incidents = data?.recent_incidents || [];
    if (!incidents.length) return `<div class="empty">No completed incidents have been recorded yet.</div>`;
    return incidents.map(item => {
      const transitions = (item.transitions || []).map(t => `<div class="transition">
        <div><strong>${this._escape(t.diagnosis)}</strong> <span class="pill">${this._escape(t.confidence)}</span></div>
        <div class="muted">${this._escape(t.at)}</div>
        <div>${this._escape(t.summary || "")}</div>
      </div>`).join("");
      return `<details class="incident-detail">
        <summary>
          <span><strong>${this._escape(item.current_diagnosis)}</strong><span class="muted">${this._escape(item.started_at)}${item.duration_seconds != null ? ` · ${item.duration_seconds}s` : ""}</span></span>
          <span class="pill">${this._escape(item.confidence)}</span>
        </summary>
        <div class="incident-body">
          <div>${this._escape(item.summary || "")}</div>
          <div class="muted">Incident ${this._escape(item.id)} · fingerprint ${this._escape(item.fingerprint || "none")}${item.ended_at ? ` · ended ${this._escape(item.ended_at)}` : ""}</div>
          ${transitions ? `<h3>Diagnosis timeline</h3>${transitions}` : ""}
        </div>
      </details>`;
    }).join("");
  }

  _render() {
    if (!this.shadowRoot) return;
    const data = this._data;
    const current = data?.current;
    const d = current?.diagnosis;
    const discovery = data?.discovery || {};
    const diagnosis = d?.diagnosis || (this._loading ? "Analyzing…" : "Initializing");
    const confidence = d?.confidence || "unknown";
    const statusClass = diagnosis === "Healthy" ? "good" : diagnosis === "Monitoring incomplete" ? "warn" : diagnosis === "Initializing" ? "" : "bad";
    const active = data?.active_incident;
    const providerFresh = current?.provider_freshness?.fresh;
    const providerLabel = providerFresh === true ? "fresh" : providerFresh === false ? "stale/unavailable" : "unknown";

    this.shadowRoot.innerHTML = `
      <style>
        :host { display:block; min-height:100%; background:var(--primary-background-color); color:var(--primary-text-color); font-family:var(--paper-font-body1_-_font-family, sans-serif); }
        * { box-sizing:border-box; }
        .top { position:sticky; top:0; z-index:2; background:var(--app-header-background-color, var(--primary-background-color)); color:var(--app-header-text-color, var(--primary-text-color)); padding:16px 20px; border-bottom:1px solid var(--divider-color); display:flex; align-items:center; justify-content:space-between; gap:12px; }
        .top h1 { margin:0; font-size:22px; }
        button { border:0; border-radius:10px; padding:10px 14px; background:var(--primary-color); color:var(--text-primary-color, white); font-weight:600; cursor:pointer; }
        button[disabled] { opacity:.6; cursor:default; }
        .wrap { max-width:1280px; margin:0 auto; padding:20px; display:grid; gap:16px; }
        .hero { display:grid; grid-template-columns:2fr 1fr 1fr; gap:12px; }
        .card { background:var(--card-background-color); border-radius:14px; padding:16px; box-shadow:var(--ha-card-box-shadow, 0 2px 8px rgba(0,0,0,.08)); }
        .big { font-size:28px; font-weight:700; margin:6px 0; }
        .muted { color:var(--secondary-text-color); font-size:13px; margin-top:3px; }
        .pill { display:inline-block; border-radius:999px; padding:5px 9px; background:var(--secondary-background-color); font-size:12px; font-weight:700; }
        .pill.good, .accent.good { color:var(--success-color, #2e7d32); }
        .pill.bad, .accent.bad { color:var(--error-color, #d32f2f); }
        .pill.warn, .accent.warn { color:var(--warning-color, #ed6c02); }
        .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
        h2 { margin:0 0 12px; font-size:18px; } h3 { margin:0 0 8px; font-size:15px; }
        ul { margin:0; padding-left:20px; } li { margin:5px 0; }
        .detail { margin-top:14px; }
        .cause { padding:10px 0; border-top:1px solid var(--divider-color); }
        .cause:first-child { border-top:0; }
        .cause-head { display:flex; align-items:center; justify-content:space-between; gap:12px; }
        .monitor-grid { display:grid; gap:8px; }
        .monitor-row { display:grid; grid-template-columns:1fr auto auto; align-items:center; gap:12px; padding:10px 0; border-top:1px solid var(--divider-color); }
        .monitor-row:first-child { border-top:0; }
        .latency { min-width:70px; text-align:right; font-variant-numeric:tabular-nums; }
        .empty { color:var(--secondary-text-color); padding:8px 0; }
        .error { background:rgba(211,47,47,.1); color:var(--error-color); padding:10px 12px; border-radius:10px; }
        .active { border-left:4px solid var(--error-color); }
        .incident-detail { border-top:1px solid var(--divider-color); padding:8px 0; }
        .incident-detail:first-child { border-top:0; }
        .incident-detail summary { cursor:pointer; display:flex; justify-content:space-between; align-items:center; gap:12px; padding:6px 0; }
        .incident-detail summary .muted { display:block; }
        .incident-body { padding:8px 0 8px 12px; display:grid; gap:10px; }
        .transition { border-left:3px solid var(--divider-color); padding:6px 10px; display:grid; gap:3px; }
        @media (max-width:850px) { .hero, .grid2 { grid-template-columns:1fr; } .monitor-row { grid-template-columns:1fr auto; } .latency { display:none; } .wrap { padding:12px; } }
      </style>
      <div class="top"><h1>Network Diagnostics</h1><button ${this._loading ? "disabled" : ""} id="analyze">${this._loading ? "Analyzing…" : "Analyze now"}</button></div>
      <main class="wrap">
        ${this._error ? `<div class="error">${this._escape(this._error)}</div>` : ""}
        <section class="hero">
          <div class="card"><div class="muted">Current diagnosis</div><div class="big accent ${statusClass}">${this._escape(diagnosis)}</div><div>${this._escape(d?.summary || "Waiting for the first analysis pass.")}</div>${current?.at ? `<div class="muted">Analyzed ${this._escape(current.at)}</div>` : ""}</div>
          <div class="card"><div class="muted">Evidence strength</div><div class="big">${this._escape(confidence)}</div><div class="muted">No pseudo-probability is shown.</div></div>
          <div class="card"><div class="muted">Coverage</div><div class="big">${d?.coverage_gaps?.length ? "Partial" : "Complete"}</div><div class="muted">Profile: ${this._escape(discovery.profile || "generic")}</div></div>
        </section>

        ${active ? `<section class="card active"><h2>Active incident</h2><strong>${this._escape(active.current_diagnosis)}</strong><div class="muted">Started ${this._escape(active.started_at)} · fingerprint ${this._escape(active.fingerprint)}</div><p>${this._escape(active.summary)}</p></section>` : ""}

        <section class="grid2">
          <div class="card"><h2>Root-cause analysis</h2>
            ${this._rootCauses(d?.root_causes || [])}
            ${this._list("Supporting evidence", d?.evidence || [], "good")}
            ${this._list("Contradicting alternatives", d?.contradictions || [], "warn")}
            ${this._list("Downstream effects", d?.downstream || [])}
            ${this._list("Monitoring gaps", d?.monitoring_gaps || [], "bad")}
            ${this._list("Coverage gaps", d?.coverage_gaps || [], "warn")}
            ${this._list("Known limitations", discovery.limitations || [], "warn")}
          </div>
          <div class="card"><h2>Discovery</h2>
            <div><strong>${discovery.bindings?.length || 0}</strong> recognized Kuma monitors</div>
            <div class="muted">Network Diagnostics automatically re-discovers monitors about once per minute and listens to the official Uptime Kuma coordinator; it does not poll Kuma itself.</div>
            <div class="detail"><strong>Provider feed:</strong> ${providerLabel}</div>
            ${this._list("Setup blockers", discovery.required_gaps || [], "bad")}
            ${this._list("Unassigned monitors", discovery.unassigned_monitors || [])}
            ${this._list("Disabled status entities", discovery.disabled_status_monitors || [], "warn")}
          </div>
        </section>

        <section class="card"><h2>Current monitor evidence</h2>${this._monitorRows(current)}</section>
        <section class="card"><h2>Recent incidents</h2>${this._incidentRows(data)}</section>
      </main>`;
    const button = this.shadowRoot.getElementById("analyze");
    if (button) button.addEventListener("click", () => this._analyze());
  }
}

if (!customElements.get("network-diagnostics-panel")) {
  customElements.define("network-diagnostics-panel", NetworkDiagnosticsPanel);
}
