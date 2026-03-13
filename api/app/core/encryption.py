"""
Field-level encryption for sensitive data at rest.

Uses Fernet symmetric encryption (AES-128-CBC with HMAC-SHA256)
derived from the ENGINE_SECRET_KEY.

Usage:
    from app.core.encryption import encrypt_value, decrypt_value

    encrypted = encrypt_value("my-secret-token")
    plaintext = decrypt_value(encrypted)
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _get_fernet() -> Fernet:
    """Derive a Fernet key from ENGINE_SECRET_KEY."""
    # Derive a 32-byte key using SHA-256, then base64-encode for Fernet
    key_bytes = hashlib.sha256(settings.engine_secret_key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value. Returns base64-encoded ciphertext."""
    if not plaintext:
        return plaintext
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt an encrypted value. Returns plaintext string."""
    if not ciphertext:
        return ciphertext
    f = _get_fernet()
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        # Value may not be encrypted (migration in progress)
        return ciphertext
