import time
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from collections import defaultdict
import httpx

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Channel(str, Enum):
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    EMAIL = "email"


@dataclass
class Incident:
    id: str
    title: str
    severity: Severity
    category: str
    description: str
    metadata: Dict = field(default_factory=dict)


@dataclass
class RateLimit:
    max_calls: int
    period_seconds: int

    def __post_init__(self):
        self._timestamps: List[float] = []

    def allow(self) -> bool:
        now = time.monotonic()
        cutoff = now - self.period_seconds
        self._timestamps = [t for t in self._timestamps if t > cutoff]
        if len(self._timestamps) >= self.max_calls:
            return False
        self._timestamps.append(now)
        return True


@dataclass
class RoutingRule:
    channel: Channel
    severities: List[Severity]
    categories: List[str]  # empty means all categories
    rate_limit: RateLimit


DEFAULT_ROUTING_RULES: List[RoutingRule] = [
    RoutingRule(
        channel=Channel.PAGERDUTY,
        severities=[Severity.CRITICAL, Severity.HIGH],
        categories=[],
        rate_limit=RateLimit(max_calls=10, period_seconds=60),
    ),
    RoutingRule(
        channel=Channel.SLACK,
        severities=[Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM],
        categories=[],
        rate_limit=RateLimit(max_calls=30, period_seconds=60),
    ),
    RoutingRule(
        channel=Channel.EMAIL,
        severities=[Severity.MEDIUM, Severity.LOW, Severity.INFO],
        categories=[],
        rate_limit=RateLimit(max_calls=60, period_seconds=60),
    ),
    RoutingRule(
        channel=Channel.SLACK,
        severities=[Severity.CRITICAL],
        categories=["security"],
        rate_limit=RateLimit(max_calls=5, period_seconds=60),
    ),
]


class NotificationDispatcher:
    def __init__(
        self,
        routing_rules: Optional[List[RoutingRule]] = None,
        slack_webhook_url: Optional[str] = None,
        pagerduty_routing_key: Optional[str] = None,
        pagerduty_api_url: str = "https://events.pagerduty.com/v2/enqueue",
        email_from: Optional[str] = None,
        email_recipients: Optional[Dict[Severity, List[str]]] = None,
        http_client: Optional[httpx.Client] = None,
    ):
        self.routing_rules = routing_rules or list(DEFAULT_ROUTING_RULES)
        self.slack_webhook_url = slack_webhook_url
        self.pagerduty_routing_key = pagerduty_routing_key
        self.pagerduty_api_url = pagerduty_api_url
        self.email_from = email_from
        self.email_recipients = email_recipients or {}
        self._client = http_client or httpx.Client(timeout=10.0)
        self._channel_handlers: Dict[Channel, Callable] = {
            Channel.SLACK: self._send_slack,
            Channel.PAGERDUTY: self._send_pagerduty,
            Channel.EMAIL: self._send_email,
        }
        self._dispatch_log: List[Dict] = []

    def resolve_channels(self, incident: Incident) -> List[Channel]:
        channels = []
        for rule in self.routing_rules:
            if incident.severity not in rule.severities:
                continue
            if rule.categories and incident.category not in rule.categories:
                continue
            if not rule.rate_limit.allow():
                logger.warning(
                    "Rate limited channel %s for incident %s",
                    rule.channel.value,
                    incident.id,
                )
                continue
            if rule.channel not in channels:
                channels.append(rule.channel)
        return channels

    def dispatch(self, incident: Incident) -> Dict[str, bool]:
        channels = self.resolve_channels(incident)
        results: Dict[str, bool] = {}
        for channel in channels:
            handler = self._channel_handlers.get(channel)
            if not handler:
                logger.error("No handler for channel %s", channel.value)
                results[channel.value] = False
                continue
            try:
                success = handler(incident)
                results[channel.value] = success
                self._dispatch_log.append({
                    "incident_id": incident.id,
                    "channel": channel.value,
                    "success": success,
                    "timestamp": time.time(),
                })
            except Exception:
                logger.exception(
                    "Error dispatching incident %s to %s",
                    incident.id,
                    channel.value,
                )
                results[channel.value] = False
        return results

    def _send_slack(self, incident: Incident) -> bool:
        if not self.slack_webhook_url:
            logger.warning("Slack webhook URL not configured")
            return False
        emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}
        payload = {
            "text": (
                f"{emoji.get(incident.severity.value, '⚪')} *[{incident.severity.value.upper()}]* "
                f"{incident.title}\n> {incident.description}\n"
                f"> Category: {incident.category} | ID: {incident.id}"
            ),
        }
        resp = self._client.post(self.slack_webhook_url, json=payload)
        resp.raise_for_status()
        logger.info("Slack notification sent for incident %s", incident.id)
        return True

    def _send_pagerduty(self, incident: Incident) -> bool:
        if not self.pagerduty_routing_key:
            logger.warning("PagerDuty routing key not configured")
            return False
        severity_map = {
            Severity.CRITICAL: "critical",
            Severity.HIGH: "error",
            Severity.MEDIUM: "warning",
            Severity.LOW: "info",
            Severity.INFO: "info",
        }
        payload = {
            "routing_key": self.pagerduty_routing_key,
            "event_action": "trigger",
            "payload": {
                "summary": f"[{incident.severity.value.upper()}] {incident.title}",
                "severity": severity_map.get(incident.severity, "error"),
                "source": incident.metadata.get("source", "incident-triage"),
                "component": incident.category,
                "group": incident.metadata.get("group", ""),
                "class": incident.category,
                "custom_details": {
                    "incident_id": incident.id,
                    "description": incident.description,
                },
            },
        }
        resp = self._client.post(self.pagerduty_api_url, json=payload)
        resp.raise_for_status()
        logger.info("PagerDuty alert sent for incident %s", incident.id)
        return True

    def _send_email(self, incident: Incident) -> bool:
        recipients = self.email_recipients.get(incident.severity, [])
        if not recipients:
            logger.info("No email recipients for severity %s", incident.severity.value)
            return False
        logger.info(
            "Email notification for incident %s to %s (would send via SMTP)",
            incident.id,
            ", ".join(recipients),
        )
        self._dispatch_log.append({
            "incident_id": incident.id,
            "channel": "email",
            "recipients": recipients,
            "subject": f"[{incident.severity.value.upper()}] {incident.title}",
            "timestamp": time.time(),
        })
        return True

    def get_dispatch_log(self, incident_id: Optional[str] = None) -> List[Dict]:
        if incident_id:
            return [e for e in self._dispatch_log if e.get("incident_id") == incident_id]
        return list(self._dispatch_log)