"""Password hashing + JWT — OWASP-aligned (see docs/auth-design.md).

Passwords: Argon2id (OWASP params m=19 MiB, t=2, p=1) via argon2-cffi, with a
stdlib scrypt fallback (N=2^17, r=8, p=1) if the wheel is unavailable.
Tokens: HS256, single issuer (the EEP); the algorithm is PINNED on decode.
Secrets come from the environment — never hard-coded into a deployed build.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time

import jwt  # PyJWT

# ---------------------------------------------------------------- passwords ---

try:  # Argon2id is the OWASP-preferred choice.
    from argon2 import PasswordHasher
    from argon2.exceptions import Argon2Error

    _PH = PasswordHasher(time_cost=2, memory_cost=19_456, parallelism=1)  # 19 MiB, t=2, p=1
    _ARGON2 = True
except Exception:  # pragma: no cover - exercised only when the wheel is missing
    _ARGON2 = False

# scrypt fallback (OWASP minimums). 128*N*r bytes ≈ 128 MiB, so raise maxmem.
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**17, 8, 1
_SCRYPT_MAXMEM = 256 * 1024 * 1024


def hash_password(password: str) -> str:
    """Return an encoded hash (algorithm + params + salt are embedded)."""
    if not password:
        raise ValueError("empty password")
    if _ARGON2:
        return _PH.hash(password)
    salt = os.urandom(16)
    dk = hashlib.scrypt(
        password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P,
        dklen=64, maxmem=_SCRYPT_MAXMEM,
    )
    return "scrypt${}${}${}${}${}".format(
        _SCRYPT_N, _SCRYPT_R, _SCRYPT_P,
        base64.b64encode(salt).decode(), base64.b64encode(dk).decode(),
    )


def verify_password(password: str, stored: str) -> bool:
    """Constant-time-ish verification against either hash format."""
    if not stored:
        return False
    if stored.startswith("$argon2"):
        if not _ARGON2:
            return False
        try:
            _PH.verify(stored, password)
            return True
        except Argon2Error:
            return False
    if stored.startswith("scrypt$"):
        try:
            _, n, r, p, salt_b64, dk_b64 = stored.split("$")
            salt = base64.b64decode(salt_b64)
            expected = base64.b64decode(dk_b64)
            dk = hashlib.scrypt(
                password.encode(), salt=salt, n=int(n), r=int(r), p=int(p),
                dklen=len(expected), maxmem=_SCRYPT_MAXMEM,
            )
            return hmac.compare_digest(dk, expected)
        except Exception:
            return False
    return False


# --------------------------------------------------------------------- JWT ---

_JWT_ALG = "HS256"


def _secret() -> str:
    # Must be overridden in any deployed build; the default is dev-only.
    return os.environ.get("JWT_SECRET", "dev-insecure-jwt-secret-change-me")


def jwt_ttl_seconds() -> int:
    return int(os.environ.get("JWT_TTL_HOURS", "8")) * 3600


def make_token(sub: str, role: str) -> str:
    now = int(time.time())
    payload = {"sub": sub, "role": role, "iat": now, "exp": now + jwt_ttl_seconds()}
    return jwt.encode(payload, _secret(), algorithm=_JWT_ALG)


def decode_token(token: str) -> dict | None:
    """Decode + verify. Algorithm is pinned (rejects alg:none / alg-confusion)."""
    try:
        return jwt.decode(token, _secret(), algorithms=[_JWT_ALG])
    except jwt.PyJWTError:
        return None
