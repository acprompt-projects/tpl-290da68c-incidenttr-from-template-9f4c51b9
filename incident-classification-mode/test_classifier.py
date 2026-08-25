import pytest
from classifier import Incident, Severity, Category, classify, TriageLabel


def test_p1_critical_error_rate():
    inc = Incident(
        title="High error rate on payments",
        description="5xx errors spiking on payment service",
        source="prometheus",
        error_rate_pct=30.0,
        is_customer_facing=True,
    )
    result = classify(inc)
    assert result.severity is Severity.P1
    assert result.category is Category.APP
    assert result.escalation_target == "pagerduty"


def test_p1_critical_latency():
    inc = Incident(
        title="API latency spike",
        description="latency on gateway exceeding SLO",
        source="grafana",
        latency_ms=6000.0,
    )
    result = classify(inc)
    assert result.severity is Severity.P1
    assert result.category is Category.NETWORK
    assert result.confidence > 0


def test_security_category_with_bump():
    inc = Incident(
        title="Unauthorized access attempt",
        description="Multiple unauthorized requests detected on admin endpoint",
        source="ids",
        tags=["security", "auth"],
        error_rate_pct=3.0,
    )
    result = classify(inc)
    assert result.category is Category.SECURITY
    assert result.severity in (Severity.P2, Severity.P3)


def test_infra_oom_with_burst():
    inc = Incident(
        title="Pod OOM killed",
        description="k8s pod evicted due to memory limit",
        source="k8s",
        tags=["infra", "oom"],
        alert_count=12,
        is_customer_facing=True,
    )
    result = classify(inc)
    assert result.category is Category.INFRA
    assert result.severity in (Severity.P2, Severity.P3)
    assert result.escalation_target in ("pagerduty", "slack")


def test_p4_low_noise():
    inc = Incident(
        title="Minor log noise",
        description="Sporadic debug messages in logs",
        source="fluentd",
        tags=["app"],
        error_rate_pct=0.1,
        latency_ms=50.0,
        alert_count=1,
    )
    result = classify(inc)
    assert result.severity is Severity.P4
    assert result.escalation_target == "slack"


def test_triage_label_structure():
    inc = Incident(
        title="DNS resolution failure",
        description="dns timeouts across cluster",
        source="monitoring",
        tags=["network", "dns"],
    )
    result = classify(inc)
    assert isinstance(result, TriageLabel)
    assert isinstance(result.severity, Severity)
    assert isinstance(result.category, Category)
    assert 0.0 <= result.confidence <= 1.0
    assert isinstance(result.reasoning, str)
    assert result.reasoning