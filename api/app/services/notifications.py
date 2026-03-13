"""
Notification dispatch service.

Sends notifications to configured channels when events occur:
  - deploy_started, deploy_succeeded, deploy_failed
  - health_degraded, health_recovered
  - rollback_triggered
  - scan_failed

The health monitor already calls this for health events.
Pipeline stages call this on deploy events.
"""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.models.notification_config import NotificationConfig
from app.models.site import Site

logger = logging.getLogger(__name__)

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def validate_webhook_url(url: str) -> None:
    """Validate a webhook URL is safe to request.

    Blocks:
    - Non-HTTPS URLs
    - RFC1918, link-local, loopback addresses
    - URLs that resolve to internal IPs

    Raises ValueError if the URL is not safe.
    """
    parsed = urlparse(url)

    if parsed.scheme not in ("https",):
        raise ValueError(f"Webhook URLs must use HTTPS (got {parsed.scheme})")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid webhook URL: no hostname")

    # Resolve hostname and check against blocked networks
    try:
        addrs = socket.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in addrs:
            ip = ipaddress.ip_address(sockaddr[0])
            for network in _BLOCKED_NETWORKS:
                if ip in network:
                    raise ValueError(
                        "Webhook URL resolves to blocked internal address"
                    )
    except socket.gaierror:
        raise ValueError(f"Cannot resolve webhook hostname: {hostname}")


async def notify(
    db: Session,
    site_id,
    event: str,
    payload: dict,
) -> int:
    """Send notifications for an event on a site.

    Args:
        db: Database session
        site_id: UUID of the site
        event: Event name (e.g., "deploy_succeeded")
        payload: Event data to include in notification

    Returns:
        Number of notifications sent
    """
    configs = (
        db.query(NotificationConfig)
        .filter(
            NotificationConfig.site_id == site_id,
            NotificationConfig.enabled.is_(True),
        )
        .all()
    )

    sent = 0
    for config in configs:
        events = config.events or []
        if event not in events and "all" not in events:
            continue

        try:
            if config.type == "webhook":
                await _send_webhook(config, event, payload)
                sent += 1
            elif config.type == "slack":
                await _send_slack(config, event, payload)
                sent += 1
            elif config.type == "email":
                logger.info(f"Email notification to {config.target} (not implemented)")
                sent += 1
        except Exception as e:
            logger.error(
                f"Notification failed ({config.type} -> {config.target}): {e}"
            )

    return sent


async def _send_webhook(config: NotificationConfig, event: str, payload: dict):
    """Send a webhook POST with event data."""
    validate_webhook_url(config.target)
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            config.target,
            json={
                "event": event,
                "timestamp": payload.get("timestamp"),
                **payload,
            },
        )
    logger.info(f"Webhook sent to {config.target} for event {event}")


async def _send_slack(config: NotificationConfig, event: str, payload: dict):
    """Send a Slack incoming webhook message."""
    validate_webhook_url(config.target)
    # Map events to emoji and color
    emoji_map = {
        "deploy_started": ":rocket:",
        "deploy_succeeded": ":white_check_mark:",
        "deploy_failed": ":x:",
        "health_degraded": ":warning:",
        "health_recovered": ":green_heart:",
        "health_alert": ":rotating_light:",
        "rollback_triggered": ":rewind:",
        "scan_failed": ":shield:",
    }
    emoji = emoji_map.get(event, ":bell:")

    site_slug = payload.get("site_slug", "unknown")
    message = payload.get("message", event.replace("_", " ").title())

    text = f"{emoji} *{event.replace('_', ' ').title()}* | `{site_slug}`\n{message}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(config.target, json={"text": text})
    logger.info(f"Slack notification sent for {event} on {site_slug}")
