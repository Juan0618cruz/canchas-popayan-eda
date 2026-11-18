"""
Security utilities:
  - Password hashing / verification (bcrypt via passlib)
  - JWT creation / decoding (python-jose)
  - One-time reset-token generation
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return a bcrypt hash of *password* (truncated to 72 bytes max)."""
    if isinstance(password, str):
        # Bcrypt tiene un límite estricto de 72 bytes
        password_bytes = password.encode("utf-8")[:72]
        password = password_bytes.decode("utf-8", errors="ignore")
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return **True** if *plain_password* matches *hashed_password*."""
    if isinstance(plain_password, str):
        plain_password_bytes = plain_password.encode("utf-8")[:72]
        plain_password = plain_password_bytes.decode("utf-8", errors="ignore")
    return _pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def create_jwt_token(data: dict[str, Any], expires_minutes: int | None = None) -> str:
    """
    Create a signed JWT containing *data* as the payload.

    Args:
        data: Arbitrary claims to embed (must be JSON-serialisable).
        expires_minutes: Override the default expiry from settings.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire_minutes = expires_minutes if expires_minutes is not None else settings.JWT_EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    to_encode["exp"] = expire
    to_encode["iat"] = datetime.now(timezone.utc)

    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_jwt_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT.

    Args:
        token: Encoded JWT string.

    Returns:
        Decoded payload as a dict.

    Raises:
        jose.JWTError: If the token is invalid or expired.
    """
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


# ---------------------------------------------------------------------------
# Reset token / Código numérico de recuperación (6 dígitos)
# ---------------------------------------------------------------------------

def generate_reset_token() -> str:
    """
    Retorna un código numérico aleatorio de 6 dígitos (ej. '482915'),
    criptográficamente seguro para facilitar su tipeo por el usuario.
    """
    return f"{secrets.randbelow(900000) + 100000}"
