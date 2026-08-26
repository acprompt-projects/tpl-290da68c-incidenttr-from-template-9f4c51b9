import os
import logging
from .models import Incident, IncidentSeverity

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
PAGERDUTY_ROUTING_KEY = os.getenv("PAGERDUTY_ROUTING_KEY", "")


async def _send_slack(incident: Incident):
    if not SLACK_WEBHOOK_URL:
        logger.info("Slack webhook not configured, skipping notification for %s", incident.id)
        return
    import httpx
    payload = {
        "text": f":rotating_light: *[{incident.severity.value.upper()}]* {incident.title}\n"
                f"> ID: `{incident.id}` | Status: {incident.status.value} | Alerts: {incident.alert_count}\n"
                f"> {incident.description or ''}"
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
    logger.info("Slack notification sent for incident %s", incident.id)


async def _send_pagerduty(incident: Incident):
    if not PAGERDUTY_ROUTING_KEY:
        logger.info("PagerDuty routing key not configured, skipping for %s", incident.id)
        return
    if incident.severity not in (IncidentSeverity.HIGH, IncidentSeverity.CRITICAL):
        return
    import httpx
    payload = {
        "routing_key": PAGERDUTY_ROUTING_KEY,
        "event_action": "trigger",
        "payload": {
            "summary": incident.title,
            "severity": incident.severity.value,
            "source": incident.source,
            "component": incident.rule_id,
            "group": incident.fingerprint,
            "custom_details": {"alert_count": incident.alert_count, "description": incident.description},
        },
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://events.pagerduty.com/v2/enqueue",
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
    logger.info("PagerDuty notification sent for incident %s", incident.id)


async def dispatch_notifications(incident: Incident):
    errors = []
    for fn in (_send_slack, _send_pagerduty):
        try:
            await fn(incident)
        except Exception as exc:
            logger.exception("Notification failed for incident %s", incident.id)
            errors.append(str(exc))
    if errors:
        logger.warning("Some notifications failed for %s: %s", incident.id, "; ".join(errors))