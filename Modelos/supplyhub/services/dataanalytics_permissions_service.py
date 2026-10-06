"""Autorización jerárquica de SupplyHub por rutas/submódulos."""
from __future__ import annotations

import logging
from urllib.parse import urlsplit

from django.conf import settings

logger = logging.getLogger("supplyhub")


def normalize_route(route: str) -> str:
    value = str(route or "").strip()
    if not value:
        return "/"
    if "://" in value:
        value = urlsplit(value).path
    value = value.split("?", 1)[0].split("#", 1)[0]
    if not value.startswith("/"):
        value = "/" + value
    if not value.endswith("/"):
        value += "/"
    return value


def get_allowed_routes(id_perfil: int) -> set[str] | None:
    """None = modo local; set vacío = fail-closed con DataAnalytics activo."""
    if not settings.DATAANALYTICS_ENABLED:
        return None
    if not id_perfil:
        return set()

    from supplyhub.connectors.dataanalytics_connection import get_dataanalytics_conn

    conn = None
    try:
        conn = get_dataanalytics_conn()
        cur = conn.cursor()
        sp = settings.DATAANALYTICS_SP_ALLOWED_ROUTES
        cur.execute(f"EXEC {sp} ?", (int(id_perfil),))
        return {
            normalize_route(row[0])
            for row in cur.fetchall()
            if row and row[0] is not None and str(row[0]).strip()
        }
    except Exception:
        logger.exception("No fue posible consultar permisos jerárquicos; acceso cerrado.")
        return set()
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def can_access_route(id_perfil: int, route: str) -> bool:
    allowed = get_allowed_routes(id_perfil)
    if allowed is None:
        return True
    return normalize_route(route) in allowed
