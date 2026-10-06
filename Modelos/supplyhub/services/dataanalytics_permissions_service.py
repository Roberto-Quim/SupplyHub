"""Lectura de rutas permitidas por perfil desde DataAnalytics.

Paso 2 deja lista la capa de autorización jerárquica; el Paso 3 la conectará al
menú HUB/Administración y a guards específicos por submódulo.
"""
from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger("supplyhub")


def get_allowed_routes(id_perfil: int) -> set[str] | None:
    """Retorna rutas permitidas.

    - DATAANALYTICS_ENABLED=False -> None (modo local/dev, sin matriz corporativa).
    - DataAnalytics activo y sin perfil/error -> set() (fail-closed).
    """
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
            str(row[0]).strip()
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
    return route in allowed
