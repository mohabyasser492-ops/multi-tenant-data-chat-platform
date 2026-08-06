from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.constants import TokenType
from core.security import InvalidTokenError, decode_token
from db.session import get_db_session
from models.tenant import Tenant
from models.user import User

bearer_scheme = HTTPBearer(
    scheme_name="Bearer Authentication",
    description="Enter the access token returned by POST /api/auth/login.",
)

BearerCredentials = Annotated[
    HTTPAuthorizationCredentials,
    Depends(bearer_scheme),
]

DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_db_session),
]


async def get_current_user(
    credentials: BearerCredentials,
    session: DatabaseSession,
) -> User:
    token = credentials.credentials

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
