from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class EncryptionError(ValueError):
    """Raised when a secret cannot be encrypted or decrypted safely."""


class CredentialEncryption:
    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode())
        except (TypeError, ValueError) as exc:
            raise EncryptionError("The credential encryption key is invalid.") from exc

    def encrypt(self, value: str) -> str:
        if not value:
            raise EncryptionError("The secret value cannot be empty.")

        try:
            return self._fernet.encrypt(value.encode()).decode()
        except (TypeError, ValueError) as exc:
            raise EncryptionError("The secret value could not be encrypted.") from exc

    def decrypt(self, encrypted_value: str) -> str:
        if not encrypted_value:
            raise EncryptionError("The encrypted value cannot be empty.")

        try:
            return self._fernet.decrypt(encrypted_value.encode()).decode()
        except (InvalidToken, TypeError, ValueError) as exc:
            raise EncryptionError(
                "The encrypted value is invalid or corrupted."
            ) from exc


credential_encryption = CredentialEncryption(settings.fernet_key)


def encrypt_secret(value: str) -> str:
    return credential_encryption.encrypt(value)


def decrypt_secret(encrypted_value: str) -> str:
    return credential_encryption.decrypt(encrypted_value)
