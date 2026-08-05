from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.config import settings
from app.dependencies import CurrentUser, DatabaseSession
from core.constants import TokenType
from core.security import (
    InvalidTokenError,
    create_access_token,
    decode_token,
)
from models.tenant import Tenant
from models.user import User
from schemas.auth import (
    AccessTokenResponse,
    AuthenticatedUserResponse,
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from services.auth_service import (
    InvalidCredentialsError,
    authenticate_user,
    create_authentication_tokens,
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate a tenant user",
)
async def login(
    request: LoginRequest,
    session: DatabaseSession,
) -> TokenResponse:
    try:
        user = await authenticate_user(
            session=session,
            tenant_code=request.tenant_code,
            email=str(request.email),
            password=request.password,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid tenant code, email, or password.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    access_token, refresh_token = create_authentication_tokens(user)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Create a new access token",
)
async def refresh_access_token(
    request: RefreshTokenRequest,
    session: DatabaseSession,
) -> AccessTokenResponse:
    try:
        payload = decode_token(
            request.refresh_token,
            expected_type=TokenType.REFRESH,
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
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
            detail="Refresh token user is unavailable.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
    )

    return AccessTokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get(
    "/me",
    response_model=AuthenticatedUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the authenticated user",
)
async def get_authenticated_user(
    current_user: CurrentUser,
) -> AuthenticatedUserResponse:
    return AuthenticatedUserResponse.model_validate(current_user)
