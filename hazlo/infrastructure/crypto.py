from __future__ import annotations

from cryptography.fernet import Fernet


def get_fernet(secret_key: str) -> Fernet:
    """Create Fernet instance from base64-encoded secret key."""
    return Fernet(secret_key.encode() if isinstance(secret_key, str) else secret_key)


def encrypt_value(value: str, secret_key: str) -> str:
    """Encrypt a string value using Fernet symmetric encryption."""
    fernet = get_fernet(secret_key)
    return fernet.encrypt(value.encode()).decode()


def decrypt_value(encrypted_value: str, secret_key: str) -> str:
    """Decrypt a Fernet-encrypted string value."""
    fernet = get_fernet(secret_key)
    return fernet.decrypt(encrypted_value.encode()).decode()
