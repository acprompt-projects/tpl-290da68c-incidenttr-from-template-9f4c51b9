import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Severity(Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class Category(Enum):
    INFRA = "infra"
    APP = "app"
    SECURITY = "security"
    NETWORK = "network"


@dataclass
class TriageLabel:
    severity: Severity
    category: Category
    confidence: float
    reasoning: str
    escalation_target: Optional[str] = None


@dataclass
class Incident:
    title: str
    description: str
    source: str
    tags: list[str] = field(default_factory=list)
    affected_services: list[str] = field(default_factory=list)
    alert_count: int = 1
    error_rate_pct: float = 0.0
    latency_ms: float = 0.0
    is_customer_facing: bool = False


# ── configurable thresholds ──────────────────────────────────────────
THRESHOLDS = {
    "error_rate_critical": 25.0,
    "error_rate_high": 10.0,
    "error_rate_medium": 5.0,
    "latency_critical_ms": 5000.0,
    "latency_high_ms": 2000.0,
    "latency_medium_ms": 1000.0,
    "alert_burst_threshold": 10,
    "customer_facing_severity_bump": True,
}

CATEGORY_KEYWORDS = {
    Category.INFRA: [
        r"\bcpu\b", r"\bmemory\b", r"\bram\b", r"\bdisk\b", r"\bstorage\b",
        r"\biops\b", r"\bnode\b", r"\bserver\b", r"\bhost\b", r"\bvm\b",
        r"\bpod\b", r"\bk8s\b", r"\bkubernetes\b", r"\bcluster\b",
        r"\bprovisioning\b", r"\bcapacity\b", r"\bresource", r"\boom\b",
        r"\bkilled\b", r"\bevicted\b",
    ],
    Category.APP: [
        r"\bexception\b", r"\berror\b", r"\btraceback\b", r"\b5xx\b",
        r"\bcrash\b", r"\bpanic\b", r"\btimeout\b", r"\bdeploy\b",
        r"\brelease\b", r"\brollback\b", r"\bbug\b", r"\bdefect\b",
        r"\bhttp\s?5\d{2}\b", r"\bresponse\s?code\b", r"\buptime\b",
        r"\bhealth\s?check\b",
    ],
    Category.SECURITY: [
        r"\bauth(oriz|entic)?\b", r"\bunauthorized\b", r"\bforbidden\b",
        r"\bcredential\b", r"\btoken\b", r"\bvulnerability\b", r"\bcve\b",
        r"\bbreach\b", r"\bmalware\b", r"\bintrusion\b", r"\bfirewall\b",
        r"\bddos\b", r"\bexfiltrat", r"\bcompliance\b", r"\bencrypt",
        r"\bssl\b", r"\btls\b", r"\bcert(ificate)?\b", r"\baccess\s?denied\b",
    ],
    Category.NETWORK: [
        r"\blatency\b", r"\bpacket\s?loss\b", r"\bdns\b", r"\bconnectivity\b",
        r"\brouting\b", r"\bgateway\b", r"\bload\s?balancer\b", r"\btcp\b",
        r"\budp\b", r"\bhandshake\b", r"\bssl\s?handshake\b", r"\btls\s?handshake\b",
        r"\brefused\b", r"\bunreachable\b", r"\bttl\b", r"\bbandwidth\b",
        r"\bthroughput\b", r"\bping\b",
    ],
}


def _match_category(incident: Incident) -> tuple[Category, float]:
    text = f"{incident.title} {incident.description} {' '.join(incident.tags)}".lower()
    scores: dict[Category, int] = {cat: 0 for cat in Category}
    total_matches = 0
    for cat, patterns in CATEGORY_KEYWORDS.items():
        for pat in patterns:
            hits = len(re.findall(pat, text))
            if hits:
                scores[cat] += hits
                total_matches += hits
    if total_matches == 0:
        return Category.APP, 0.3
    best = max(scores, key=lambda c: scores[c])
    confidence = scores[best] / total_matches if total_matches else 0.0
    return best, round(min(confidence + 0.2, 1.0), 2)


def _determine_severity(incident: Incident, category: Category) -> tuple[Severity, str]:
    reasons = []
    th = THRESHOLDS

    if incident.error_rate_pct >= th["error_rate_critical"]:
        return Severity.P1, f"error_rate {incident.error_rate_pct}% >= critical {th['error_rate_critical']}%"

    if incident.latency_ms >= th["latency_critical_ms"]:
        return Severity.P1, f"latency {incident.latency_ms}ms >= critical {th['latency_critical_ms']}ms"

    score = 0
    if incident.error_rate_pct >= th["error_rate_high"]:
        score += 3
        reasons.append(f"error_rate {incident.error_rate_pct}% >= high")
    elif incident.error_rate_pct >= th["error_rate_medium"]:
        score += 2
        reasons.append(f"error_rate {incident.error_rate_pct}% >= medium")

    if incident.latency_ms >= th["latency_high_ms"]:
        score += 2
        reasons.append(f"latency {incident.latency_ms}ms >= high")
    elif incident.latency_ms >= th["latency_medium_ms"]:
        score += 1
        reasons.append(f"latency {incident.latency_ms}ms >= medium")

    if incident.alert_count >= th["alert_burst_threshold"]:
        score += 2
        reasons.append(f"alert_burst {incident.alert_count} >= {th['alert_burst_threshold']}")

    if incident.is_customer_facing and th["customer_facing_severity_bump"]:
        score += 1
        reasons.append("customer_facing bump")

    if category == Category.SECURITY:
        score += 1
        reasons.append("security category bump")

    if score >= 5:
        severity = Severity.P1
    elif score >= 3:
        severity = Severity.P2
    elif score >= 1:
        severity = Severity.P3
    else:
        severity = Severity.P4

    return severity, "; ".join(reasons) if reasons else "below all threshold thresholds"


ESCALATION_MAP = {
    Severity.P1: "pagerduty",
    Severity.P2: "pagerduty",
    Severity.P3: "slack",
    Severity.P4: "slack",
}


def classify(incident: Incident) -> TriageLabel:
    category, cat_confidence = _match_category(incident)
    severity, reasoning = _determine_severity(incident, category)
    confidence = round(cat_confidence * (0.95 if severity != Severity.P4 else 0.7), 2)
    return TriageLabel(
        severity=severity,
        category=category,
        confidence=confidence,
        reasoning=reasoning,
        escalation_target=ESCALATION_MAP[severity],
    )