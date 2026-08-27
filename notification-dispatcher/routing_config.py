"""
Default routing configuration for the notification dispatcher.
Override via environment variables or inject custom RoutingRule lists.
"""
import os
from dispatcher import Channel, Severity, RoutingRule, RateLimit, DEFAULT_ROUTING_RULES


def load_routing_rules_from_env() -> list:
    """Build routing rules from environment variables.

    Expected env vars (all optional, falls back to DEFAULT_ROUTING_RULES):
      SLACK_SEVERITIES   - comma-separated severities for Slack (default: critical,high,medium)
      SLACK_CATEGORIES   - comma-separated categories or empty for all
      SLACK_RATE_LIMIT   - max calls per period (default: 30)
      SLACK_RATE_PERIOD  - period in seconds (default: 60)

      PD_SEVERITIES      - comma-separated severities for PagerDuty (default: critical,high)
      PD_CATEGORIES      - comma-separated categories or empty for all
      PD_RATE_LIMIT      - max calls per period (default: 10)
      PD_RATE_PERIOD     - period in seconds (default: 60)

      EMAIL_SEVERITIES   - comma-separated severities for Email (default: medium,low,info)
      EMAIL_CATEGORIES   - comma-separated categories or empty for all
      EMAIL_RATE_LIMIT   - max calls per period (default: 60)
      EMAIL_RATE_PERIOD  - period in seconds (default: 60)
    """
    if not os.getenv("SLACK_SEVERITIES") and not os.getenv("PD_SEVERITIES"):
        return list(DEFAULT_ROUTING_RULES)

    def _parse_severities(val: str) -> list:
        return [Severity(s.strip().lower()) for s in val.split(",") if s.strip()]

    def _parse_categories(val: str) -> list:
        return [c.strip() for c in val.split(",") if c.strip()]

    rules = []

    slack_sevs = _parse_severities(os.getenv("SLACK_SEVERITIES", "critical,high,medium"))
    slack_cats = _parse_categories(os.getenv("SLACK_CATEGORIES", ""))
    rules.append(RoutingRule(
        channel=Channel.SLACK,
        severities=slack_sevs,
        categories=slack_cats,
        rate_limit=RateLimit(
            max_calls=int(os.getenv("SLACK_RATE_LIMIT", "30")),
            period_seconds=int(os.getenv("SLACK_RATE_PERIOD", "60")),
        ),
    ))

    pd_sevs = _parse_severities(os.getenv("PD_SEVERITIES", "critical,high"))
    pd_cats = _parse_categories(os.getenv("PD_CATEGORIES", ""))
    rules.append(RoutingRule(
        channel=Channel.PAGERDUTY,
        severities=pd_sevs,
        categories=pd_cats,
        rate_limit=RateLimit(
            max_calls=int(os.getenv("PD_RATE_LIMIT", "10")),
            period_seconds=int(os.getenv("PD_RATE_PERIOD", "60")),
        ),
    ))

    email_sevs = _parse_severities(os.getenv("EMAIL_SEVERITIES", "medium,low,info"))
    email_cats = _parse_categories(os.getenv("EMAIL_CATEGORIES", ""))
    rules.append(RoutingRule(
        channel=Channel.EMAIL,
        severities=email_sevs,
        categories=email_cats,
        rate_limit=RateLimit(
            max_calls=int(os.getenv("EMAIL_RATE_LIMIT", "60")),
            period_seconds=int(os.getenv("EMAIL_RATE_PERIOD", "60")),
        ),
    ))

    return rules