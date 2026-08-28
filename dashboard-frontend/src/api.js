const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...opts.headers },
    ...opts,
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export function fetchIncidents(filters = {}) {
  const params = new URLSearchParams();
  if (filters.severity) params.set("severity", filters.severity);
  if (filters.status) params.set("status", filters.status);
  const qs = params.toString();
  return request(`/incidents${qs ? `?${qs}` : ""}`);
}

export function fetchIncident(id) {
  return request(`/incidents/${id}`);
}

export function updateIncidentStatus(id, status) {
  return request(`/incidents/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function acknowledgeIncident(id) {
  return updateIncidentStatus(id, "acknowledged");
}

export function resolveIncident(id) {
  return updateIncidentStatus(id, "resolved");
}