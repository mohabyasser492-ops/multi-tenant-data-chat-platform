from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.constants import TokenType
from core.security import InvalidTokenError, decode_token
from db.session import get_db_session
from models.tenant import Tenant
from models.user import User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
)

DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_db_session),
]

AccessToken = Annotated[
    str,
    Depends(oauth2_scheme),
]


async def get_current_user(
    token: AccessToken,
    session: DatabaseSession,
) -> User:
    try:
        payload = decode_token(
            token,
            expected_type=TokenType.ACCESS,
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    result = await session.execute(
        select(User)
        .join(
            Tenant,
            User.tenant_id == Tenant.id,
        )
        .where(
            User.id == payload.sub,
            User.tenant_id == payload.tenant_id,
            User.status == "active",
            Tenant.status == "active",
        )
    )

    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user is unavailable.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


CurrentUser = Annotated[
    User,
    Depends(get_current_user),
]
