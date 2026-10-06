import httpx
from typing import Optional, Dict, Any
from app.config import settings
from app.core.logging import logger


async def send_ops_alert(
    message: str,
    severity: str = "warning",
    context: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Sends an operational alert to Slack webhook and logs structured event.
    Severities: 'critical', 'warning', 'info'
    """
    emoji = "🚨" if severity == "critical" else ("⚠️" if severity == "warning" else "ℹ️")
    formatted_header = f"{emoji} *[DEPOII ENGINE {severity.upper()}]*"

    log_msg = f"OPS ALERT [{severity.upper()}]: {message} | Context: {context or {}}"
    if severity == "critical":
        logger.critical(log_msg)
    else:
        logger.warning(log_msg)

    webhook_url = settings.SLACK_ALERT_WEBHOOK
    if not webhook_url:
        return True  # Logged cleanly, no external webhook configured

    payload = {
        "text": f"{formatted_header}\n{message}",
        "attachments": [
            {
                "color": "#DC2626" if severity == "critical" else "#F59E0B",
                "fields": [
                    {"title": k, "value": str(v), "short": True}
                    for k, v in (context or {}).items()
                ],
            }
        ] if context else [],
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(webhook_url, json=payload)
            return resp.status_code == 200
    except Exception as err:
        logger.error(f"[Alerting] Failed to dispatch Slack webhook: {err}")
        return False
