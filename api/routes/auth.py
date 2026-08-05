from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from db.session import get_db_session
from schemas.auth import LoginRequest, TokenResponse
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
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid authentication credentials",
            "content": {
                "application/json": {
                    "example": {"detail": ("Invalid tenant code, email, or password.")}
                }
            },
        }
    },
)
async def login(
    request: LoginRequest,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
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
