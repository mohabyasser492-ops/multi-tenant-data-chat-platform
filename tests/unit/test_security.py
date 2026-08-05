import uuid
from datetime import timedelta

import pytest

from core.constants import TokenType
from core.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_password_does_not_store_plain_text() -> None:
    password = "StrongPassword123!"

    password_hash = hash_password(password)

    assert password_hash != password
    assert password_hash.startswith("$argon2")
    assert verify_password(password, password_hash) is True


def test_verify_password_rejects_wrong_password() -> None:
    password_hash = hash_password("CorrectPassword123!")

    assert (
        verify_password(
            "WrongPassword123!",
            password_hash,
        )
        is False
    )


def test_hash_password_rejects_empty_password() -> None:
    with pytest.raises(
        ValueError,
        match="Password cannot be empty",
    ):
        hash_password("")


def test_create_and_decode_access_token() -> None:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    token = create_access_token(
        user_id=user_id,
        tenant_id=tenant_id,
    )

    payload = decode_token(
        token,
        expected_type=TokenType.ACCESS,
    )

    assert payload.sub == user_id
    assert payload.tenant_id == tenant_id
    assert payload.type == TokenType.ACCESS
    assert payload.exp > payload.iat


def test_create_and_decode_refresh_token() -> None:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    token = create_refresh_token(
        user_id=user_id,
        tenant_id=tenant_id,
    )

    payload = decode_token(
        token,
        expected_type=TokenType.REFRESH,
    )

    assert payload.sub == user_id
    assert payload.tenant_id == tenant_id
    assert payload.type == TokenType.REFRESH


def test_refresh_token_cannot_be_used_as_access_token() -> None:
    token = create_refresh_token(
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
    )

    with pytest.raises(
        InvalidTokenError,
        match="Token type is invalid",
    ):
        decode_token(
            token,
            expected_type=TokenType.ACCESS,
        )


def test_access_token_cannot_be_used_as_refresh_token() -> None:
    token = create_access_token(
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
    )

    with pytest.raises(
        InvalidTokenError,
        match="Token type is invalid",
    ):
        decode_token(
            token,
            expected_type=TokenType.REFRESH,
        )


def test_decode_token_rejects_invalid_token() -> None:
    with pytest.raises(
        InvalidTokenError,
        match="Token is invalid or expired",
    ):
        decode_token(
            "not-a-valid-jwt",
            expected_type=TokenType.ACCESS,
        )


def test_decode_token_rejects_expired_token() -> None:
    token = create_token(
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(
        InvalidTokenError,
        match="Token is invalid or expired",
    ):
        decode_token(
            token,
            expected_type=TokenType.ACCESS,
        )


def test_additional_claims_cannot_replace_protected_claims() -> None:
    with pytest.raises(
        ValueError,
        match="cannot override protected token claims",
    ):
        create_token(
            user_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            token_type=TokenType.ACCESS,
            expires_delta=timedelta(minutes=5),
            additional_claims={
                "tenant_id": str(uuid.uuid4()),
            },
        )
