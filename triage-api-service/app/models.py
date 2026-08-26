from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class IncidentSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    OPEN = "open"
    TRIAGING = "triaging"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class IncidentCreate(BaseModel):
    alert_id: str
    source: str = "rules-engine"
    rule_id: str
    fingerprint: str
    title: str
    description: Optional[str] = None
    labels: Optional[dict[str, str]] = None
    alert_count: Optional[int] = None


class IncidentUpdate(BaseModel):
    severity: Optional[IncidentSeverity] = None
    status: Optional[IncidentStatus] = None
    assigned_to: Optional[str] = None
    notes: Optional[str] = None


class Incident(BaseModel):
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex[:12])
    alert_id: str
    source: str
    rule_id: str
    fingerprint: str
    title: str
    description: Optional[str] = None
    labels: Optional[dict[str, str]] = None
    severity: IncidentSeverity = IncidentSeverity.MEDIUM
    status: IncidentStatus = IncidentStatus.OPEN
    assigned_to: Optional[str] = None
    notes: Optional[str] = None
    alert_count: int = 1
    dedupe_key: str = ""
    correlated_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))