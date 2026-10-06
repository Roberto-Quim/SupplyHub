"""Cifrado simétrico Fernet para datos persistentes sensibles de SupplyHub.

No usar para contraseñas de usuarios. Las contraseñas son responsabilidad del
proveedor de autenticación o del hasher de Django cuando corresponda.
"""
import os
from functools import lru_cache


def generate_encryption_key() -> str:
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode("utf-8")


def is_encryption_configured() -> bool:
    enabled = os.environ.get("APP_ENCRYPTION_ENABLED", "False").strip().lower() == "true"
    key = os.environ.get("APP_ENCRYPTION_KEY", "").strip()
    return enabled and bool(key)


@lru_cache(maxsize=1)
def _get_fernet():
    from cryptography.fernet import Fernet

    enabled = os.environ.get("APP_ENCRYPTION_ENABLED", "False").strip().lower() == "true"
    if not enabled:
        raise RuntimeError("APP_ENCRYPTION_ENABLED=False; el cifrado persistente está desactivado.")

    key = os.environ.get("APP_ENCRYPTION_KEY", "").strip()
    if not key:
        raise RuntimeError("APP_ENCRYPTION_KEY no está definida.")

    try:
        return Fernet(key.encode("utf-8"))
    except Exception as exc:
        raise RuntimeError("APP_ENCRYPTION_KEY no tiene formato Fernet válido.") from exc


def encrypt_text(plain_text: str) -> str:
    return _get_fernet().encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_text(cipher_text: str) -> str:
    return _get_fernet().decrypt(cipher_text.encode("utf-8")).decode("utf-8")
