from services.audit_service import (
    sanitize_audit_metadata,
)


def test_sensitive_values_are_redacted() -> None:
    metadata = {
        "password": "unsafe-password",
        "access_token": "unsafe-token",
        "action": "query",
    }

    sanitized = sanitize_audit_metadata(metadata)

    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["access_token"] == "[REDACTED]"
    assert sanitized["action"] == "query"


def test_nested_sensitive_values_are_redacted() -> None:
    metadata = {
        "connection": {
            "host": "localhost",
            "password": "unsafe-password",
        }
    }

    sanitized = sanitize_audit_metadata(metadata)

    assert sanitized["connection"]["host"] == ("localhost")
    assert sanitized["connection"]["password"] == ("[REDACTED]")


def test_sensitive_values_inside_lists_are_redacted() -> None:
    metadata = {
        "items": [
            {
                "token": "unsafe-token",
                "status": "completed",
            }
        ]
    }

    sanitized = sanitize_audit_metadata(metadata)

    assert sanitized["items"][0]["token"] == ("[REDACTED]")
    assert sanitized["items"][0]["status"] == ("completed")


def test_empty_metadata_returns_empty_dictionary() -> None:
    assert sanitize_audit_metadata(None) == {}
    assert sanitize_audit_metadata({}) == {}
