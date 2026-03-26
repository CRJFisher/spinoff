"""Security functions: secret redaction, safety filter, HTML escaping."""

import html
import re

from spinoff.screen import strip_ansi

# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------

_SECRET_TOKEN_RE = re.compile(
    r"(sk-|pk_|Bearer |token=)([A-Za-z0-9_-]{8,})"
)

_SECRET_KV_RE = re.compile(
    r"(password|secret|key|token)(\s*[=:]\s*)\S+",
    re.IGNORECASE,
)

_DB_URI_RE = re.compile(
    r"(mongodb(\+srv)?|postgres(ql)?|mysql|redis|amqp|sqlite)://\S+",
    re.IGNORECASE,
)


def redact_secrets(text: str) -> str:
    """Replace secrets in text with [REDACTED] markers."""
    result = _SECRET_TOKEN_RE.sub(r"\1[REDACTED]", text)
    result = _SECRET_KV_RE.sub(r"\1\2[REDACTED]", result)
    result = _DB_URI_RE.sub("[REDACTED]", result)
    return result


# ---------------------------------------------------------------------------
# Safety filter for auto-approval
# ---------------------------------------------------------------------------

_DANGEROUS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"git\s+push\s+.*(-f|--force)\b"), "git force push"),
    (re.compile(r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+/"), "recursive delete at root"),
    (re.compile(r"\bsudo\b"), "privilege elevation (sudo)"),
    (re.compile(r"\bsu\s+-"), "privilege elevation (su)"),
    (re.compile(r"\bdoas\b"), "privilege elevation (doas)"),
    (re.compile(r"reset\s+--hard"), "git reset --hard"),
    (re.compile(r"checkout\s+\."), "git checkout ."),
    (re.compile(r"restore\s+\."), "git restore ."),
    (re.compile(r"clean\s+-[a-zA-Z]*f"), "git clean -f"),
    (re.compile(r"branch\s+-D\b"), "git branch -D"),
]

_NETWORK_TOOL_RE = re.compile(r"\b(curl|wget)\b", re.IGNORECASE)
_LOCALHOST_RE = re.compile(r"(localhost|127\.0\.0\.1|0\.0\.0\.0|\[?::1\]?)")


def is_safe_to_approve(screen_text: str) -> tuple[bool, str]:
    """Check if a WAITING_APPROVAL screen is safe for auto-approval.

    Returns (True, "") if safe, or (False, reason) if blocked.
    """
    text = strip_ansi(screen_text)

    for pattern, reason in _DANGEROUS_PATTERNS:
        if pattern.search(text):
            return False, reason

    # Network tool check: block non-localhost requests
    if _NETWORK_TOOL_RE.search(text) and not _LOCALHOST_RE.search(text):
        return False, "external network request"

    return True, ""


# ---------------------------------------------------------------------------
# HTML escaping
# ---------------------------------------------------------------------------

def safe_html(text: str) -> str:
    """Redact secrets then HTML-escape for safe insertion."""
    return html.escape(redact_secrets(text))
