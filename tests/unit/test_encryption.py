import pytest
from cryptography.fernet import Fernet

from core.encryption import (
    CredentialEncryption,
    EncryptionError,
    decrypt_secret,
    encrypt_secret,
)


def test_encrypt_secret_does_not_return_plain_text() -> None:
    plain_text = "CustomerDatabasePassword123!"

    encrypted = encrypt_secret(plain_text)

    assert encrypted != plain_text
    assert plain_text not in encrypted


def test_encrypt_and_decrypt_secret() -> None:
    plain_text = "CustomerDatabasePassword123!"

    encrypted = encrypt_secret(plain_text)
    decrypted = decrypt_secret(encrypted)

    assert decrypted == plain_text


def test_same_value_produces_different_ciphertext() -> None:
    plain_text = "RepeatedSecret123!"

    first_encrypted = encrypt_secret(plain_text)
    second_encrypted = encrypt_secret(plain_text)

    assert first_encrypted != second_encrypted
    assert decrypt_secret(first_encrypted) == plain_text
    assert decrypt_secret(second_encrypted) == plain_text


def test_encrypt_rejects_empty_value() -> None:
    with pytest.raises(
        EncryptionError,
        match="secret value cannot be empty",
    ):
        encrypt_secret("")


def test_decrypt_rejects_empty_value() -> None:
    with pytest.raises(
        EncryptionError,
        match="encrypted value cannot be empty",
    ):
        decrypt_secret("")


def test_decrypt_rejects_invalid_ciphertext() -> None:
    with pytest.raises(
        EncryptionError,
        match="invalid or corrupted",
    ):
        decrypt_secret("not-valid-encrypted-data")


def test_wrong_key_cannot_decrypt_secret() -> None:
    first_service = CredentialEncryption(Fernet.generate_key().decode())
    second_service = CredentialEncryption(Fernet.generate_key().decode())

    encrypted = first_service.encrypt("ProtectedSecret123!")

    with pytest.raises(
        EncryptionError,
        match="invalid or corrupted",
    ):
        second_service.decrypt(encrypted)


def test_invalid_fernet_key_is_rejected() -> None:
    with pytest.raises(
        EncryptionError,
        match="encryption key is invalid",
    ):
        CredentialEncryption("invalid-key")
