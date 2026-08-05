import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, ValidationError

from app.config import settings
from core.constants import TokenType

password_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
)


class TokenPayload(BaseModel):
    sub: uuid.UUID
    tenant_id: uuid.UUID
    type: TokenType
    iat: datetime
    exp: datetime


class InvalidTokenError(ValueError):
    """Raised when a JWT is missing, invalid, expired, or has the wrong type."""


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty.")

    return password_context.hash(password)


def verify_password(
    plain_password: str,
    password_hash: str,
) -> bool:
    if not plain_password or not password_hash:
        return False

    try:
        return password_context.verify(
            plain_password,
            password_hash,
        )
    except (TypeError, ValueError):
        return False


def create_token(
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    token_type: TokenType,
    expires_delta: timedelta,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    expires_at = now + expires_delta

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "type": token_type.value,
        "iat": now,
        "exp": expires_at,
    }

    if additional_claims:
        protected_claims = {
            "sub",
            "tenant_id",
            "type",
            "iat",
            "exp",
        }

        if protected_claims.intersection(additional_claims):
            raise ValueError(
                "Additional claims cannot override protected token claims."
            )

        payload.update(additional_claims)

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_access_token(
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> str:
    return create_token(
        user_id=user_id,
        tenant_id=tenant_id,
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> str:
    return create_token(
        user_id=user_id,
        tenant_id=tenant_id,
        token_type=TokenType.REFRESH,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(
    token: str,
    *,
    expected_type: TokenType | None = None,
) -> TokenPayload:
    if not token:
        raise InvalidTokenError("Token is required.")

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        token_payload = TokenPayload.model_validate(payload)

    except (JWTError, ValidationError, ValueError, TypeError) as exc:
        raise InvalidTokenError("Token is invalid or expired.") from exc

    if expected_type and token_payload.type != expected_type:
        raise InvalidTokenError("Token type is invalid.")

    return token_payload
