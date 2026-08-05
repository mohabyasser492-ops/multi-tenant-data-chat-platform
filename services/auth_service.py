from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
)
from models.tenant import Tenant
from models.user import User


class InvalidCredentialsError(ValueError):
    """Raised when authentication credentials are invalid."""


async def authenticate_user(
    *,
    session: AsyncSession,
    tenant_code: str,
    email: str,
    password: str,
) -> User:
    normalized_tenant_code = tenant_code.strip().lower()
    normalized_email = email.strip().lower()

    result = await session.execute(
        select(User)
        .join(
            Tenant,
            User.tenant_id == Tenant.id,
        )
        .where(
            Tenant.code == normalized_tenant_code,
            Tenant.status == "active",
            User.email == normalized_email,
            User.status == "active",
        )
    )

    user = result.scalar_one_or_none()

    if (
        user is None
        or user.password_hash is None
        or not verify_password(password, user.password_hash)
    ):
        raise InvalidCredentialsError("Invalid tenant code, email, or password.")

    return user


def create_authentication_tokens(
    user: User,
) -> tuple[str, str]:
    access_token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
    )
    refresh_token = create_refresh_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
    )

    return access_token, refresh_token
