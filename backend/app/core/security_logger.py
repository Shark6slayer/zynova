import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

# Dedicated logger for security-relevant operational events
sec_logger = logging.getLogger("super_ai.security")

def sanitize_log_val(val: Any) -> Any:
    """Sanitizes values to prevent log injection (CRLF) and masking sensitive keys."""
    if val is None:
        return None
    if isinstance(val, (int, float, bool)):
        return val
    s = str(val).replace("\r\n", " ").replace("\r", " ").replace("\n", " ").strip()
    # Mask if looks like JWT or secret
    if len(s) > 64 and ("." in s or "Bearer" in s):
        return f"{s[:6]}...[REDACTED]...{s[-4:]}"
    return s[:256]

def log_security_event(
    event_code: str,
    action: str,
    status: str,
    actor_id: Optional[str] = None,
    client_ip: Optional[str] = None,
    resource: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
):
    """
    Logs structured security event without exposing credentials, tokens, or PII.
    Event codes:
      AUTH_SUCCESS, AUTH_FAILURE, AUTH_LOGOUT,
      TOKEN_REVOKED, TOKEN_REVOCATION_ATTEMPT,
      RATE_LIMIT_EXCEEDED, RATE_LIMIT_FAIL_CLOSED,
      MALWARE_SCAN_SUCCESS, MALWARE_SCAN_REJECTED,
      BOLA_ACCESS_DENIED, INACTIVE_USER_BLOCKED
    """
    sanitized_details = {}
    if details:
        for k, v in details.items():
            k_lower = k.lower()
            if any(secret_term in k_lower for secret_term in ["pass", "token", "secret", "card", "vpa", "auth"]):
                sanitized_details[k] = "[REDACTED]"
            else:
                sanitized_details[k] = sanitize_log_val(v)

    event_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_code": event_code,
        "action": action,
        "status": status,
        "actor_id": sanitize_log_val(actor_id) if actor_id else "anonymous",
        "client_ip": sanitize_log_val(client_ip) if client_ip else "unknown",
        "resource": sanitize_log_val(resource) if resource else None,
        "details": sanitized_details
    }

    log_line = json.dumps(event_payload)
    if status == "BLOCKED" or status == "FAILURE" or status == "ERROR":
        sec_logger.warning(log_line)
    else:
        sec_logger.info(log_line)
