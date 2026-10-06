"""Conector de autenticación por nómina.

Los nombres de SP se dejan configurables porque son infraestructura corporativa.
No se inventan nombres en código: para activar PAYROLL_AUTH_ENABLED deben estar
configurados PAYROLL_SP_VALIDATE y PAYROLL_SP_WORKER_DATA.
"""
from __future__ import annotations

import logging

from supplyhub.security.env import get_env_bool, get_env_int, get_env_value

logger = logging.getLogger("supplyhub")


def _connection():
    import pyodbc

    server = get_env_value("PAYROLL_DB_SERVER", "")
    port = get_env_int("PAYROLL_DB_PORT", 0)
    database = get_env_value("PAYROLL_DB_NAME", "")
    user = get_env_value("PAYROLL_DB_USER", "")
    password = get_env_value("PAYROLL_DB_PASSWORD", "", strip=False)
    driver = get_env_value("PAYROLL_DB_DRIVER", "ODBC Driver 18 for SQL Server")
    encrypt = "yes" if get_env_bool("PAYROLL_DB_ENCRYPT", "True") else "no"
    trust = "yes" if get_env_bool("PAYROLL_DB_TRUST_SERVER_CERTIFICATE", "False") else "no"

    if not server or not database or not user or not password:
        raise RuntimeError("Configuración PAYROLL_DB_* incompleta.")

    host = f"{server},{port}" if port else server
    conn_string = (
        f"DRIVER={{{driver}}};SERVER={host};DATABASE={database};"
        f"UID={user};PWD={password};Encrypt={encrypt};TrustServerCertificate={trust};"
    )
    return pyodbc.connect(conn_string, autocommit=False)


def validate_payroll_login(employee_number: str, password: str) -> str | None:
    sp = get_env_value("PAYROLL_SP_VALIDATE", "").strip()
    if not sp:
        logger.error("PAYROLL_AUTH_ENABLED sin PAYROLL_SP_VALIDATE configurado.")
        return None

    conn = None
    try:
        conn = _connection()
        cur = conn.cursor()
        # Contraseña enviada como parámetro; nunca se concatena ni se registra.
        cur.execute(f"EXEC {sp} ?, ?", (employee_number, password))
        row = cur.fetchone()
        if not row or row[0] is None:
            return None
        return str(row[0]).strip()
    except Exception:
        logger.exception("Error validando login por nómina; credenciales omitidas.")
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def get_payroll_worker_data(employee_number: str) -> dict:
    sp = get_env_value("PAYROLL_SP_WORKER_DATA", "").strip()
    if not sp:
        return {}

    conn = None
    try:
        conn = _connection()
        cur = conn.cursor()
        cur.execute(f"EXEC {sp} ?", (employee_number,))
        row = cur.fetchone()
        if row is None:
            return {}
        columns = [str(col[0]) for col in cur.description or []]
        return dict(zip(columns, row))
    except Exception:
        logger.exception("Error consultando datos de trabajador por nómina.")
        return {}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
