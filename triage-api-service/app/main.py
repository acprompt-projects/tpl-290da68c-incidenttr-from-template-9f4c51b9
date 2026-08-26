from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from .models import IncidentCreate, IncidentUpdate, Incident, IncidentSeverity
from .store import IncidentStore
from .notifier import dispatch_notifications

store = IncidentStore()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await store.init()
    yield


app = FastAPI(title="Incident Triage Service", version="1.0.0", lifespan=lifespan)


def _classify_severity(payload: IncidentCreate) -> IncidentSeverity:
    """Rule-based severity classification (placeholder for ML model integration)."""
    score = 0
    if payload.source == "rules-engine":
        score += 1
    if payload.labels:
        score += sum(1 for k, v in payload.labels.items() if "critical" in v.lower() or "critical" in k.lower())
    if payload.alert_count and payload.alert_count >= 5:
        score += 2
    if score >= 3:
        return IncidentSeverity.CRITICAL
    if score >= 2:
        return IncidentSeverity.HIGH
    if score >= 1:
        return IncidentSeverity.MEDIUM
    return IncidentSeverity.LOW


def _dedupe_key(payload: IncidentCreate) -> str:
    return f"{payload.source}:{payload.rule_id}:{payload.fingerprint}"


@app.post("/incidents", response_model=Incident, status_code=201)
async def create_incident(payload: IncidentCreate):
    dedupe = _dedupe_key(payload)
    existing = await store.find_by_dedupe(dedupe)
    if existing:
        existing.alert_count += 1
        existing.correlated_ids.append(payload.alert_id)
        await store.save(existing)
        return existing

    severity = _classify_severity(payload)
    incident = Incident(
        alert_id=payload.alert_id,
        source=payload.source,
        rule_id=payload.rule_id,
        fingerprint=payload.fingerprint,
        title=payload.title,
        description=payload.description,
        labels=payload.labels,
        severity=severity,
        alert_count=payload.alert_count or 1,
        dedupe_key=dedupe,
        correlated_ids=[payload.alert_id],
    )
    await store.save(incident)
    await dispatch_notifications(incident)
    return incident


@app.get("/incidents/{incident_id}", response_model=Incident)
async def get_incident(incident_id: str):
    incident = await store.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@app.patch("/incidents/{incident_id}/triage", response_model=Incident)
async def update_triage(incident_id: str, update: IncidentUpdate):
    incident = await store.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if update.severity is not None:
        incident.severity = update.severity
    if update.status is not None:
        incident.status = update.status
    if update.assigned_to is not None:
        incident.assigned_to = update.assigned_to
    if update.notes is not None:
        incident.notes = update.notes
    await store.save(incident)
    return incident