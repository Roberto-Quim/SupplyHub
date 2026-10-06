from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

_PREFIXES = ("fernet:", "enc:")
_KEY_ENV_PRIMARY = "APP_CONFIG_ENCRYPTION_KEY"
_KEY_ENV_FALLBACK = "APP_ENCRYPTION_KEY"


def is_encrypted_value(value: Any) -> bool:
    if value is None:
        return False
    value = str(value).strip()
    return any(value.startswith(prefix) for prefix in _PREFIXES)


def _strip_prefix(value: str) -> str:
    value = str(value).strip()
    for prefix in _PREFIXES:
        if value.startswith(prefix):
            return value[len(prefix):].strip()
    return value


@lru_cache(maxsize=1)
def _get_config_fernet():
    key = (
        os.environ.get(_KEY_ENV_PRIMARY, "").strip()
        or os.environ.get(_KEY_ENV_FALLBACK, "").strip()
    )
    if not key:
        raise RuntimeError(
            "Se encontró una variable cifrada, pero falta "
            f"{_KEY_ENV_PRIMARY} o {_KEY_ENV_FALLBACK}. "
            "La llave debe vivir fuera del repositorio."
        )

    try:
        from cryptography.fernet import Fernet
        return Fernet(key.encode("utf-8"))
    except Exception as exc:
        raise RuntimeError("La llave de cifrado de configuración no es Fernet válida.") from exc


def decrypt_value(value: Any) -> Any:
    if value is None or not isinstance(value, str) or not is_encrypted_value(value):
        return value

    token = _strip_prefix(value)
    try:
        return _get_config_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        raise RuntimeError(
            "No se pudo descifrar una variable de entorno; verifica APP_CONFIG_ENCRYPTION_KEY."
        ) from exc


def get_env_value(key: str, default: Any = "", *, strip: bool = True) -> Any:
    raw = os.environ.get(key, default)
    if raw is None:
        raw = ""
    value = decrypt_value(raw)
    if strip and isinstance(value, str):
        return value.strip()
    return value


def get_env_bool(key: str, default: str = "False") -> bool:
    return str(get_env_value(key, default)).strip().lower() in {"1", "true", "yes", "on"}


def get_env_int(key: str, default: int = 0) -> int:
    try:
        return int(get_env_value(key, str(default)))
    except (TypeError, ValueError):
        return default
