import hashlib
import json
import re
from datetime import datetime
from typing import Any

from sqlalchemy.inspection import inspect


def serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    if hasattr(value, "__mapper__"):
        return {
            column.key: serialize(getattr(value, column.key))
            for column in inspect(value).mapper.column_attrs
        }
    return value


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:90] or "item"


def content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=serialize)


def redact(text: str) -> str:
    # Defense in depth for common token shapes; never log request headers.
    return re.sub(r"(?i)(bearer\s+|sk-)[a-z0-9_\-.]{8,}", r"\1[REDACTED]", text)


def sanitize_argv(argv: list[str]) -> list[str]:
    sensitive_flags = {"--api-key", "--token", "--password", "--secret", "--access-token"}
    sanitized = []
    redact_next = False
    for argument in argv:
        if redact_next:
            sanitized.append("[REDACTED]")
            redact_next = False
            continue
        if argument in sensitive_flags:
            sanitized.append(argument)
            redact_next = True
            continue
        if any(argument.startswith(f"{flag}=") for flag in sensitive_flags):
            sanitized.append(argument.split("=", 1)[0] + "=[REDACTED]")
            continue
        sanitized.append(redact(argument))
    return sanitized
