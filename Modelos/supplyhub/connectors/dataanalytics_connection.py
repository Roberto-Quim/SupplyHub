"""Conexión única de SupplyHub hacia DataAnalytics vía ODBC.

No registra ni expone contraseñas. Todos los valores provienen del entorno y
pueden estar cifrados con el mecanismo fernet: del proyecto.
"""
from __future__ import annotations

from supplyhub.security.env import get_env_bool, get_env_int, get_env_value


def get_dataanalytics_conn():
    try:
        import pyodbc
    except ImportError as exc:  # pragma: no cover - dependencia de infraestructura
        raise RuntimeError("pyodbc no está instalado.") from exc

    server = get_env_value("DATAANALYTICS_DB_SERVER", "")
    port = get_env_int("DATAANALYTICS_DB_PORT", 0)
    database = get_env_value("DATAANALYTICS_DB_NAME", "DataAnalytics")
    user = get_env_value("DATAANALYTICS_DB_USER", "")
    password = get_env_value("DATAANALYTICS_DB_PASSWORD", "", strip=False)
    driver = get_env_value("DATAANALYTICS_DB_DRIVER", "ODBC Driver 18 for SQL Server")
    encrypt = "yes" if get_env_bool("DATAANALYTICS_DB_ENCRYPT", "True") else "no"
    trust = "yes" if get_env_bool("DATAANALYTICS_DB_TRUST_SERVER_CERTIFICATE", "False") else "no"
    timeout = get_env_int("DATAANALYTICS_DB_TIMEOUT", 10)

    if not server or not database or not user or not password:
        raise RuntimeError(
            "Configuración DataAnalytics incompleta. Revisa DATAANALYTICS_DB_* en .env."
        )

    host = f"{server},{port}" if port else server
    connection_string = (
        f"DRIVER={{{driver}}};"
        f"SERVER={host};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        f"Encrypt={encrypt};"
        f"TrustServerCertificate={trust};"
        "Connection Timeout=" + str(timeout) + ";"
    )
    return pyodbc.connect(connection_string, autocommit=False)
