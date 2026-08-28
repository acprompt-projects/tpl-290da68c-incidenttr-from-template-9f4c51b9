import { useState, useEffect, useCallback } from "react";
import { fetchIncidents, fetchIncident, acknowledgeIncident, resolveIncident } from "./api";

const SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"];
const STATUS_OPTIONS = ["new", "acknowledged", "investigating", "resolved", "closed"];

const SEV_COLORS = {
  critical: { bg: "#fee2e2", border: "#dc2626", text: "#991b1b" },
  high:     { bg: "#ffedd5", border: "#ea580c", text: "#9a3412" },
  medium:   { bg: "#fef9c3", border: "#ca8a04", text: "#854d0e" },
  low:      { bg: "#dcfce7", border: "#16a34a", text: "#166534" },
  info:     { bg: "#dbeafe", border: "#2563eb", text: "#1e40af" },
};

function Badge({ value, palette }) {
  const c = palette[value] || palette.info;
  return (
    <span style={{
      display: "inline-block", padding: "2px 10px", borderRadius: 999,
      fontSize: 12, fontWeight: 600, border: `1px solid ${c.border}`,
      background: c.bg, color: c.text,
    }}>{value}</span>
  );
}

function formatTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function App() {
  const [incidents, setIncidents] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sevFilter, setSevFilter] = useState(null);
  const [statusFilter, setStatusFilter] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const data = await fetchIncidents({ severity: sevFilter, status: statusFilter });
      setIncidents(Array.isArray(data) ? data : data.items ?? []);
    } catch (e) { setError(e.message); }
    setLoading(false);
  }, [sevFilter, statusFilter]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!selectedId) { setDetail(null); return; }
    fetchIncident(selectedId).then(setDetail).catch(() => setDetail(null));
  }, [selectedId]);

  const handleAction = async (fn) => {
    await fn(selectedId);
    setDetail(await fetchIncident(selectedId));
    load();
  };

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", maxWidth: 1280, margin: "0 auto", padding: 24 }}>
      <h1 style={{ fontSize: 24, marginBottom: 4 }}>Incident Triage Dashboard</h1>
      <p style={{ color: "#6b7280", marginTop: 0, marginBottom: 20 }}>
        Real-time incident management &amp; notification tracking
      </p>

      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 16 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: "#374151" }}>Severity:</span>
        <button onClick={() => setSevFilter(null)} style={pillBtn(!sevFilter)}>All</button>
        {SEVERITY_ORDER.map(s => (
          <button key={s} onClick={() => setSevFilter(sevFilter === s ? null : s)} style={pillBtn(sevFilter === s, SEV_COLORS[s])}>
            {s}
          </button>
        ))}
        <span style={{ marginLeft: 16, fontSize: 13, fontWeight: 600, color: "#374151" }}>Status:</span>
        <select value={statusFilter || ""} onChange={e => setStatusFilter(e.target.value || null)}
          style={{ padding: "4px 8px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13 }}>
          <option value="">All</option>
          {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <button onClick={load} style={{ marginLeft: "auto", ...pillBtn(false) }}>↻ Refresh</button>
      </div>

      {error && <div style={{ color: "#dc2626", marginBottom: 12 }}>Error: {error}</div>}

      <div style={{ display: "flex", gap: 20 }}>
        <div style={{ flex: 2, overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: "2px solid #e5e7eb", textAlign: "left" }}>
                <th style={th}>ID</th><th style={th}>Title</th><th style={th}>Severity</th>
                <th style={th}>Status</th><th style={th}>Service</th><th style={th}>Created</th>
              </tr>
            </thead>
            <tbody>
              {loading && incidents.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>Loading…</td></tr>
              )}
              {!loading && incidents.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>No incidents found</td></tr>
              )}
              {incidents.map(inc => (
                <tr key={inc.id} onClick={() => setSelectedId(inc.id)} style={{
                  cursor: "pointer", background: selectedId === inc.id ? "#eff6ff" : "transparent",
                  borderBottom: "1px solid #f3f4f6",
                }}>
                  <td style={td}><code style={{ fontSize: 11 }}>{inc.id?.slice(0,8)}</code></td>
                  <td style={{ ...td, fontWeight: 500 }}>{inc.title}</td>
                  <td style={td}><Badge value={inc.severity} palette={SEV_COLORS} /></td>
                  <td style={td}>{inc.status}</td>
                  <td style={td}>{inc.service || inc.source || "—"}</td>
                  <td style={td}>{formatTime(inc.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {detail && (
          <div style={{ flex: 1, background: "#f9fafb", borderRadius: 8, padding: 16, border: "1px solid #e5e7eb", alignSelf: "flex-start" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h2 style={{ fontSize: 16, margin: 0 }}>Incident Detail</h2>
              <button onClick={() => setSelectedId(null)} style={{ border: "none", background: "none", cursor: "pointer", fontSize: 18 }}>✕</button>
            </div>
            <p style={{ fontWeight: 600, marginTop: 0 }}>{detail.title}</p>
            <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              <Badge value={detail.severity} palette={SEV_COLORS} />
              <Badge value={detail.status} palette={STATUS_COLORS} />
            </div>
            <dl style={{ fontSize: 13, lineHeight: 1.8, margin: 0 }}>
              <dt style={{ fontWeight: 600, display: "inline" }}>ID:</dt><dd style={{ display: "inline", marginLeft: 4 }}>{detail.id}</dd><br/>
              <dt style={{ fontWeight: 600, display: "inline" }}>Service:</dt><dd style={{ display: "inline", marginLeft: 4 }}>{detail.service || detail.source || "—"}</dd><br/>
              <dt style={{ fontWeight: 600, display: "inline" }}>Created:</dt><dd style={{ display: "inline", marginLeft: 4 }}>{formatTime(detail.created_at)}</dd><br/>
              <dt style={{ fontWeight: 600, display: "inline" }}>Alerts:</dt><dd style={{ display: "inline", marginLeft: 4 }}>{detail.alert_count ?? detail.correlated_alerts?.length ?? "—"}</dd>
            </dl>
            {detail.description && (
              <p style={{ fontSize: 13, color: "#4b5563", marginTop: 12, padding: 8, background: "#fff", borderRadius: 4, border: "1px solid #e5e7eb" }}>
                {detail.description}
              </p>
            )}
            {detail.notifications && (
              <div style={{ marginTop: 12, fontSize: 12 }}>
                <strong>Notifications:</strong>
                <ul style={{ margin: "4px 0", paddingLeft: 20, color: "#6b7280" }}>
                  {detail.notifications.map((n, i) => <li key={i}>{n.channel}: {n.status}</li>)}
                </ul>
              </div>
            )}
            <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
              {detail.status !== "acknowledged" && detail.status !== "resolved" && detail.status !== "closed" && (
                <button onClick={() => handleAction(acknowledgeIncident)} style={actionBtn("#ea580c")}>Acknowledge</button>
              )}
              {detail.status !== "resolved" && detail.status !== "closed" && (
                <button onClick={() => handleAction(resolveIncident)} style={actionBtn("#16a34a")}>Resolve</button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const STATUS_COLORS = {
  new: { bg: "#dbeafe", border: "#3b82f6", text: "#1e40af" },
  acknowledged: { bg: "#fef3c7", border: "#f59e0b", text: "#92400e" },
  investigating: { bg: "#ede9fe", border: "#8b5cf6", text: "#5b21b6" },
  resolved: { bg: "#dcfce7", border: "#22c55e", text: "#166534" },
  closed: { bg: "#f3f4f6", border: "#9ca3af", text: "#374151" },
};

const th = { padding: "8px 6px", color: "#6b7280", fontWeight: 600, fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em" };
const td = { padding: "8px 6px" };

function pillBtn(active, color) {
  return {
    padding: "3px 12px", borderRadius: 999, fontSize: 13, cursor: "pointer",
    border: active ? `1.5px solid ${color?.border || "#2563eb"}` : "1.5px solid #d1d5db",
    background: active ? (color?.bg || "#dbeafe") : "#fff",
    color: active ? (color?.text || "#1e40af") : "#374151",
    fontWeight: active ? 600 : 400,
  };
}

function actionBtn(color) {
  return {
    padding: "6px 16px", borderRadius: 6, fontSize: 13, fontWeight: 600,
    border: "none", background: color, color: "#fff", cursor: "pointer",
  };
}