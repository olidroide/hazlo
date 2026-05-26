from __future__ import annotations

import pytest
from cryptography.fernet import Fernet, InvalidToken

from hazlo.infrastructure.crypto import decrypt_value, encrypt_value, get_fernet


@pytest.fixture
def fernet_key() -> str:
    return Fernet.generate_key().decode()


def test_get_fernet_returns_fernet_instance(fernet_key: str) -> None:
    result = get_fernet(fernet_key)
    assert isinstance(result, Fernet)


def test_encrypt_value_returns_different_string(fernet_key: str) -> None:
    encrypted = encrypt_value("hello", fernet_key)
    assert encrypted != "hello"
    assert isinstance(encrypted, str)


def test_encrypt_decrypt_roundtrip(fernet_key: str) -> None:
    original = "my-api-key-12345"
    encrypted = encrypt_value(original, fernet_key)
    decrypted = decrypt_value(encrypted, fernet_key)
    assert decrypted == original


def test_encrypt_value_deterministic(fernet_key: str) -> None:
    encrypted1 = encrypt_value("test", fernet_key)
    encrypted2 = encrypt_value("test", fernet_key)
    assert encrypted1 != encrypted2


def test_decrypt_value_different_key_fails(fernet_key: str) -> None:
    other_key = Fernet.generate_key().decode()
    encrypted = encrypt_value("secret", fernet_key)
    with pytest.raises(InvalidToken):
        decrypt_value(encrypted, other_key)


def test_encrypt_value_empty_string(fernet_key: str) -> None:
    encrypted = encrypt_value("", fernet_key)
    decrypted = decrypt_value(encrypted, fernet_key)
    assert decrypted == ""


def test_encrypt_decrypt_special_chars(fernet_key: str) -> None:
    original = "key!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
    encrypted = encrypt_value(original, fernet_key)
    decrypted = decrypt_value(encrypted, fernet_key)
    assert decrypted == original


def test_encrypt_decrypt_unicode(fernet_key: str) -> None:
    original = "clave-secreta-mañana-über"
    encrypted = encrypt_value(original, fernet_key)
    decrypted = decrypt_value(encrypted, fernet_key)
    assert decrypted == original


def test_encrypt_value_long_string(fernet_key: str) -> None:
    original = "x" * 10000
    encrypted = encrypt_value(original, fernet_key)
    decrypted = decrypt_value(encrypted, fernet_key)
    assert decrypted == original


def test_decrypt_value_tampered_data(fernet_key: str) -> None:
    encrypted = encrypt_value("secret", fernet_key)
    tampered = encrypted[:-5] + "XXXXX"
    with pytest.raises(InvalidToken):
        decrypt_value(tampered, fernet_key)
