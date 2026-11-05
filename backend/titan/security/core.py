"""Authentication, password hashing, RBAC and secret management."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional

from ..config import settings

# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------


def hash_password(password: str, *, salt: Optional[bytes] = None) -> str:
    """scrypt hash, encoded as `scrypt$n$r$p$salt_b64$hash_b64`."""
    salt = salt or os.urandom(16)
    dk = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=settings.scrypt_n,
        r=settings.scrypt_r,
        p=settings.scrypt_p,
        dklen=32,
    )
    return "scrypt${}${}${}${}${}".format(
        settings.scrypt_n,
        settings.scrypt_r,
        settings.scrypt_p,
        base64.b64encode(salt).decode(),
        base64.b64encode(dk).decode(),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, hash_b64 = encoded.split("$")
        if scheme != "scrypt":
            return False
        dk = hashlib.scrypt(
            password.encode("utf-8"),
            salt=base64.b64decode(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=32,
        )
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT (HS256, implemented in-repo so no external dependency is required)
# ---------------------------------------------------------------------------


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64u_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def create_jwt(claims: Dict[str, Any], *, ttl_seconds: Optional[int] = None) -> str:
    now = int(time.time())
    payload = dict(claims)
    payload.setdefault("iat", now)
    payload.setdefault("iss", "titan-omega-infinity")
    payload["exp"] = now + (ttl_seconds if ttl_seconds is not None else settings.jwt_ttl_seconds)
    header = {"alg": settings.jwt_algorithm, "typ": "JWT"}
    signing_input = (
        _b64u(json.dumps(header, separators=(",", ":"), sort_keys=True).encode())
        + "."
        + _b64u(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    )
    sig = hmac.new(settings.jwt_secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return signing_input + "." + _b64u(sig)


def decode_jwt(token: str) -> Dict[str, Any]:
    """Raises ValueError on any structural, signature or expiry problem."""
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
    except ValueError as exc:
        raise ValueError("malformed token") from exc
    signing_input = f"{header_b64}.{payload_b64}".encode()
    expected = hmac.new(settings.jwt_secret.encode(), signing_input, hashlib.sha256).digest()
    try:
        provided = _b64u_decode(sig_b64)
    except Exception as exc:
        raise ValueError("malformed signature") from exc
    if not hmac.compare_digest(expected, provided):
        raise ValueError("invalid signature")
    try:
        payload = json.loads(_b64u_decode(payload_b64))
    except Exception as exc:
        raise ValueError("malformed payload") from exc
    if payload.get("iss") != "titan-omega-infinity":
        raise ValueError("invalid issuer")
    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("token expired")
    return payload


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------


def generate_api_key() -> str:
    return "tk_" + secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------

ROLE_SCOPES: Dict[str, set] = {
    "owner": {"*"},
    "admin": {
        "read", "write", "agents", "research", "skills", "workflows",
        "projects", "models", "memory", "build", "admin", "security",
    },
    "researcher": {"read", "write", "research", "agents", "skills", "memory", "models", "workflows"},
    "developer": {"read", "write", "projects", "build", "agents", "skills", "memory",
                  "workflows", "models", "research", "translation"},
    "viewer": {"read"},
}


@dataclass
class Principal:
    """Authenticated actor attached to every request."""

    user_id: str
    org_id: str
    role: str
    scopes: set = field(default_factory=set)

    def has_scope(self, scope: str) -> bool:
        if "*" in self.scopes:
            return True
        if scope in self.scopes:
            return True
        # a scope implies its "read" sibling
        return scope == "read" and "read" in self.scopes

    def require(self, scope: str) -> None:
        if not self.has_scope(scope):
            raise PermissionError(f"role '{self.role}' lacks scope '{scope}'")


def scopes_for_role(role: str) -> set:
    return set(ROLE_SCOPES.get(role, set()))


# ---------------------------------------------------------------------------
# Secret management
# ---------------------------------------------------------------------------

_SECRET_KEY_RE = None


class SecretStore:
    """Server-side secret resolution.

    Order: explicit override -> environment -> encrypted file (0600).
    Secrets are never returned through any HTTP API; callers only learn
    whether a secret is configured and where it came from.
    """

    def __init__(self) -> None:
        self._overrides: Dict[str, str] = {}

    def set_override(self, key: str, value: str) -> None:
        self._overrides[key] = value

    def resolve(self, key: str) -> Optional[str]:
        if key in self._overrides:
            return self._overrides[key]
        env_value = os.environ.get(key)
        if env_value:
            return env_value
        for candidate in (key.upper(), key.lower()):
            if candidate in settings.provider_keys:
                return settings.provider_keys[candidate]
        return None

    def status(self, key: str) -> Dict[str, str]:
        if key in self._overrides:
            return {"configured": True, "source": "override"}
        if os.environ.get(key):
            return {"configured": True, "source": "env"}
        if key.upper() in settings.provider_keys or key.lower() in settings.provider_keys:
            return {"configured": True, "source": "settings"}
        return {"configured": False, "source": "missing"}

    def list_configured(self) -> list:
        keys = set(os.environ.keys())
        keys.update(settings.provider_keys.keys())
        return sorted(k for k in keys if "KEY" in k.upper() or "TOKEN" in k.upper() or "SECRET" in k.upper())


secret_store = SecretStore()


# ---------------------------------------------------------------------------
# Log / output redaction
# ---------------------------------------------------------------------------

REDACTION_PLACEHOLDER = "[REDACTED]"


def redact(text: str, extra_secrets: Optional[Iterable[str]] = None) -> str:
    """Remove secret-looking substrings from text that may be logged."""
    if not text:
        return text
    out = text
    candidates = list(extra_secrets or [])
    candidates.extend(v for v in secret_store.list_configured() if (secret_store.resolve(v) or ""))
    for name in candidates:
        value = secret_store.resolve(name) if isinstance(name, str) else None
        if value and len(value) >= 8 and value in out:
            out = out.replace(value, REDACTION_PLACEHOLDER)
    # generic provider-key shapes
    import re

    out = re.sub(r"\b(sk-[A-Za-z0-9_\-]{12,})\b", REDACTION_PLACEHOLDER, out)
    out = re.sub(r"\b(gh[pousr]_[A-Za-z0-9]{16,})\b", REDACTION_PLACEHOLDER, out)
    out = re.sub(r"\bAIza[0-9A-Za-z_\-]{20,}\b", REDACTION_PLACEHOLDER, out)
    out = re.sub(r'(?i)(api[_-]?key"\s*:\s*")([^"]{8,})(")', r"\1" + REDACTION_PLACEHOLDER + r"\3", out)
    return out
