"""Autorización de acceso de SupplyHub contra DataAnalytics.

Autenticación y autorización son capas distintas:
- proveedor (AD/nómina/Google) valida identidad;
- DataAnalytics valida usuario activo, perfil y método de acceso.
"""
from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger("supplyhub")

TIPO_NOMINA = 1
TIPO_CORREO = 2

METODO_CORREO = 1
METODO_AD = 2
METODO_NOMINA = 3

DENIED_MESSAGE = "Usuario sin permiso en SupplyHub."

SESSION_KEYS = (
    "sh_id_usuario",
    "sh_id_perfil",
    "sh_metodo_acceso",
    "sh_no_nomina",
    "sh_correo",
    "sh_display_name",
    "sh_identity_source",
)


def _fetch_row(cursor):
    row = cursor.fetchone()
    while row is None and cursor.nextset():
        row = cursor.fetchone()
    return row


def validate_user(
    tipo_acceso: int,
    *,
    no_nomina: str | None = None,
    correo: str | None = None,
    metodo_acceso: int | None = None,
) -> tuple[int, int]:
    if not settings.DATAANALYTICS_ENABLED:
        return 0, 0

    from supplyhub.connectors.dataanalytics_connection import get_dataanalytics_conn

    conn = None
    try:
        conn = get_dataanalytics_conn()
        cur = conn.cursor()
        if metodo_acceso is not None:
            sp = settings.DATAANALYTICS_SP_VALIDATE_METHOD
            # El nombre del SP viene de configuración controlada; valores de usuario son parámetros.
            cur.execute(f"EXEC {sp} ?, ?, ?", (metodo_acceso, no_nomina, correo))
        else:
            sp = settings.DATAANALYTICS_SP_VALIDATE
            sql = (
                "DECLARE @IdU INT = 0, @IdP INT = 0;"
                f"EXEC {sp} @TipoAcceso=?, @NoNomina=?, @Correo=?, "
                "@IdUsuario=@IdU OUTPUT, @IdPerfil=@IdP OUTPUT;"
                "SELECT @IdU, @IdP;"
            )
            cur.execute(sql, (tipo_acceso, no_nomina, correo))

        row = _fetch_row(cur)
        if not row:
            return 0, 0
        return int(row[0] or 0), int(row[1] or 0)
    except Exception:
        logger.exception("Error validando autorización DataAnalytics; acceso denegado.")
        return 0, 0
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def log_access(
    *,
    id_usuario: int = 0,
    no_nomina: str | None = None,
    correo: str | None = None,
    acceso: bool = False,
) -> bool:
    if not settings.DATAANALYTICS_ENABLED:
        return False

    from supplyhub.connectors.dataanalytics_connection import get_dataanalytics_conn

    conn = None
    try:
        conn = get_dataanalytics_conn()
        cur = conn.cursor()
        sp = settings.DATAANALYTICS_SP_ADD_ACCESS
        sql = (
            "DECLARE @R BIT = 0;"
            f"EXEC {sp} @IdUsuario=?, @NoNomina=?, @Correo=?, @Acceso=?, "
            "@Resultado=@R OUTPUT; SELECT @R;"
        )
        cur.execute(sql, (id_usuario, no_nomina, correo, 1 if acceso else 0))
        row = _fetch_row(cur)
        conn.commit()
        return bool(row and row[0])
    except Exception:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.exception("No fue posible registrar auditoría de acceso.")
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def authorize_and_log(
    tipo_acceso: int,
    *,
    no_nomina: str | None = None,
    correo: str | None = None,
    metodo_acceso: int | None = None,
) -> tuple[bool, int, int]:
    # Modo desarrollo: proveedor puede autenticarse sin DataAnalytics.
    if not settings.DATAANALYTICS_ENABLED:
        return True, 0, 0

    id_usuario, id_perfil = validate_user(
        tipo_acceso,
        no_nomina=no_nomina,
        correo=correo,
        metodo_acceso=metodo_acceso,
    )
    allowed = id_usuario > 0 and id_perfil > 0
    log_access(
        id_usuario=id_usuario,
        no_nomina=no_nomina,
        correo=correo,
        acceso=allowed,
    )
    return allowed, id_usuario, id_perfil


def store_session_identity(
    session,
    id_usuario: int,
    id_perfil: int,
    *,
    metodo_acceso: int,
    no_nomina: str = "",
    correo: str = "",
    display_name: str = "",
    source: str = "",
) -> None:
    clear_session_identity(session)
    session["sh_id_usuario"] = int(id_usuario or 0)
    session["sh_id_perfil"] = int(id_perfil or 0)
    session["sh_metodo_acceso"] = int(metodo_acceso or 0)
    session["sh_no_nomina"] = no_nomina or ""
    session["sh_correo"] = correo or ""
    session["sh_display_name"] = display_name or ""
    session["sh_identity_source"] = source or ""


def clear_session_identity(session) -> None:
    for key in SESSION_KEYS:
        session.pop(key, None)
    session.pop("payroll_worker", None)
