"""
dataanalytics_modulos_service.py — CRUD de Módulos y Submódulos.

Responsabilidad:
    Administración de dbo.Modulos y dbo.Submodulo.

Reglas de negocio:
    - No se permiten módulos ni submódulos con nombre duplicado en el mismo nivel.
    - La activación/desactivación es lógica (Activo=0/1), no física.
    - El módulo padre debe existir y estar activo para crear submódulos.
    - No se valida unicidad de Ruta (dos submódulos de distintos módulos pueden
      compartir ruta; la unicidad se gestiona a nivel de aplicación).

Seguridad:
    - Consultas parametrizadas (?), nunca concatenación de input.
    - Escrituras con commit() en éxito y rollback() en excepción.
"""

import logging
import os

logger = logging.getLogger('supplyhub')

# Nota (Ing. Juan Carlos Bermúdez, jun-2026): queda CANCELADA la regla anterior
# de "solo Administración". Pueden crearse más módulos padre y más submódulos.
# Los módulos padre (p. ej. Administración, Dashboards) no tienen ruta navegable
# propia; si el esquema exige Ruta NOT NULL se usa el valor técnico '#'.


def _is_enabled() -> bool:
    from django.conf import settings
    return settings.DATAANALYTICS_ENABLED


def _get_conn():
    from supplyhub.connectors.dataanalytics_connection import get_dataanalytics_conn
    return get_dataanalytics_conn()


def _safe_close(conn) -> None:
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


def _safe_rollback(conn) -> None:
    if conn is not None:
        try:
            conn.rollback()
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────
# Migración a Stored Procedures (fase 6): SOLO lecturas, SP-first con fallback.
# El SP se intenta primero; si aún no existe (2812/208/42S02) se cae a la query
# directa equivalente. Un error real se propaga (no se oculta). Ver 018.
# ──────────────────────────────────────────────────────────────

def _is_missing_database_object_error(exc: Exception) -> bool:
    """True si es 'objeto de BD inexistente' (SP/tabla): 2812/208/42S02. Caso esperado
    durante la migración, no un bug."""
    texto = str(exc).lower()
    if 'could not find stored procedure' in texto:
        return True
    if '2812' in texto:
        return True
    if 'invalid object name' in texto:
        return True
    if '42s02' in texto:
        return True
    if '208' in texto and 'object name' in texto:
        return True
    return False


def _sp_or_direct_execute(cur, sp_sql, sp_params, direct_sql, direct_params, sp_name):
    """Ejecuta el SP de lectura; si no existe (2812/208/...), cae a la query directa en el
    MISMO cursor. Otros errores se propagan. Parámetros con ? (nunca concatenados)."""
    try:
        if sp_params is None:
            cur.execute(sp_sql)
        else:
            cur.execute(sp_sql, sp_params)
    except Exception as exc:
        if _is_missing_database_object_error(exc):
            logger.warning('Modulos: SP %s no existe todavía; usando query directa.', sp_name)
            if direct_params is None:
                cur.execute(direct_sql)
            else:
                cur.execute(direct_sql, direct_params)
        else:
            raise


def _is_missing_stored_procedure_error(exc: Exception) -> bool:
    """
    True SOLO si el SP no existe ('Could not find stored procedure' / error 2812).
    Para ESCRITURAS solo se hace fallback en este caso (el error ocurre al enlazar el
    EXEC, antes de ejecutar nada → es seguro reintentar con SQL directo). Cualquier otro
    error (incluida una validación que el SP rechaza con RAISERROR) NO dispara fallback:
    se propaga → rollback del llamador.
    """
    texto = str(exc).lower()
    return ('could not find stored procedure' in texto) or ('2812' in texto)


# ──────────────────────────────────────────────────────────────
# Lectura — Módulos
# ──────────────────────────────────────────────────────────────

def list_modulos(solo_activos: bool = False) -> list[dict]:
    """Lista módulos con conteo de submódulos, ordenados por Orden."""
    if not _is_enabled():
        return []
    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        filtro = 'WHERE m.Activo = 1' if solo_activos else ''
        _sp_or_direct_execute(
            cur,
            'EXEC dbo.GetModulosAdminReadDAsp ?', (1 if solo_activos else 0,),
            f'SELECT m.IdModulo, COALESCE(m.Modulo, \'\') AS Modulo, '
            f'       m.Ruta, m.Orden, m.Activo, m.FechaAdd, m.FechaUpd, '
            f'       COUNT(s.IdSubModulo) AS NumSubmodulos '
            f'FROM dbo.Modulos m '
            f'LEFT JOIN dbo.Submodulo s ON s.IdModulo = m.IdModulo AND s.Activo = 1 '
            f'{filtro} '
            f'GROUP BY m.IdModulo, m.Modulo, m.Ruta, m.Orden, m.Activo, '
            f'         m.FechaAdd, m.FechaUpd '
            f'ORDER BY m.Orden, m.IdModulo',
            None,
            'GetModulosAdminReadDAsp',
        )
        return [_row_to_modulo(r) for r in cur.fetchall()]
    except Exception:
        logger.exception('Modulos: error al listar módulos.')
        raise RuntimeError('No se pudo consultar DataAnalytics.') from None
    finally:
        _safe_close(conn)


def get_modulo(id_modulo: int) -> dict | None:
    """Devuelve un módulo por IdModulo, o None."""
    if not _is_enabled() or not id_modulo:
        return None
    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        _sp_or_direct_execute(
            cur,
            'EXEC dbo.GetModuloByIdReadDAsp ?', (int(id_modulo),),
            'SELECT IdModulo, COALESCE(Modulo, \'\') AS Modulo, '
            '       Ruta, Orden, Activo, FechaAdd, FechaUpd '
            'FROM dbo.Modulos WHERE IdModulo = ?',
            (int(id_modulo),),
            'GetModuloByIdReadDAsp',
        )
        row = cur.fetchone()
        return _row_to_modulo_simple(row) if row else None
    except Exception:
        logger.exception('Modulos: error al obtener módulo (IdModulo=%s).', id_modulo)
        return None
    finally:
        _safe_close(conn)


# ──────────────────────────────────────────────────────────────
# Lectura — Submódulos
# ──────────────────────────────────────────────────────────────

def list_submodulos(id_modulo: int | None = None, solo_activos: bool = False) -> list[dict]:
    """
    Lista submódulos, opcionalmente filtrados por módulo padre.
    Incluye nombre del módulo padre.
    """
    if not _is_enabled():
        return []
    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        condiciones = []
        params = []
        if id_modulo:
            condiciones.append('s.IdModulo = ?')
            params.append(int(id_modulo))
        if solo_activos:
            condiciones.append('s.Activo = 1')
        where = ('WHERE ' + ' AND '.join(condiciones)) if condiciones else ''
        _sp_or_direct_execute(
            cur,
            'EXEC dbo.GetSubmodulosAdminReadDAsp ?, ?',
            (int(id_modulo) if id_modulo else None, 1 if solo_activos else 0),
            f'SELECT s.IdSubModulo, s.IdModulo, s.SubModulo, s.Ruta, s.Orden, '
            f'       s.Activo, s.FechaAdd, s.FechaUpd, '
            f'       COALESCE(m.Modulo, \'\') AS Modulo '
            f'FROM dbo.Submodulo s '
            f'INNER JOIN dbo.Modulos m ON m.IdModulo = s.IdModulo '
            f'{where} '
            f'ORDER BY m.Orden, s.Orden, s.IdSubModulo',
            params,
            'GetSubmodulosAdminReadDAsp',
        )
        return [_row_to_submodulo(r) for r in cur.fetchall()]
    except Exception:
        logger.exception('Modulos: error al listar submódulos.')
        raise RuntimeError('No se pudo consultar DataAnalytics.') from None
    finally:
        _safe_close(conn)


def get_submodulo(id_submodulo: int) -> dict | None:
    """Devuelve un submódulo por IdSubModulo, o None."""
    if not _is_enabled() or not id_submodulo:
        return None
    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        _sp_or_direct_execute(
            cur,
            'EXEC dbo.GetSubmoduloByIdReadDAsp ?', (int(id_submodulo),),
            'SELECT s.IdSubModulo, s.IdModulo, s.SubModulo, s.Ruta, s.Orden, '
            '       s.Activo, s.FechaAdd, s.FechaUpd, '
            '       COALESCE(m.Modulo, \'\') AS Modulo '
            'FROM dbo.Submodulo s '
            'INNER JOIN dbo.Modulos m ON m.IdModulo = s.IdModulo '
            'WHERE s.IdSubModulo = ?',
            (int(id_submodulo),),
            'GetSubmoduloByIdReadDAsp',
        )
        row = cur.fetchone()
        return _row_to_submodulo(row) if row else None
    except Exception:
        logger.exception('Modulos: error al obtener submódulo (IdSubModulo=%s).', id_submodulo)
        return None
    finally:
        _safe_close(conn)


# ──────────────────────────────────────────────────────────────
# Escritura — Módulos
# ──────────────────────────────────────────────────────────────

def create_modulo(nombre: str, ruta: str | None, orden: int) -> tuple[int, str]:
    """
    Crea un módulo padre nuevo. Los módulos padre no navegan: si no se entrega
    ruta, se guarda el valor técnico no navegable '#'.

    Returns:
        (id_modulo, '') en éxito.
        (0, mensaje_error) si falla.
    """
    if not _is_enabled():
        return 0, 'DataAnalytics no está habilitado.'

    nombre = (nombre or '').strip()
    if not nombre:
        return 0, 'El nombre del módulo es requerido.'

    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()

        # Verificar nombre duplicado
        cur.execute(
            'SELECT COUNT(*) FROM dbo.Modulos '
            'WHERE LTRIM(RTRIM(COALESCE(Modulo, \'\'))) = ?',
            (nombre,),
        )
        if cur.fetchone()[0] > 0:
            return 0, f'Ya existe un módulo con el nombre "{nombre}".'

        # Los módulos padre no navegan; Ruta NOT NULL → valor técnico '#'.
        ruta_val = (ruta or '').strip() or '#'
        # Alta vía SP (fallback temporal: INSERT OUTPUT directo). La validación de
        # nombre duplicado ya se hizo arriba en Python; el SP solo inserta.
        try:
            cur.execute('EXEC dbo.AddOrUpdModuloAdminDAsp ?, ?, ?, ?',
                        (None, nombre, ruta_val, int(orden)))
            row = cur.fetchone()
        except Exception as exc:
            if _is_missing_stored_procedure_error(exc):
                logger.warning('Modulos: SP AddOrUpdModuloAdminDAsp no existe todavía; usando SQL directo.')
                cur.execute(
                    'INSERT INTO dbo.Modulos (Modulo, Ruta, Orden, Activo, FechaAdd, FechaUpd) '
                    'OUTPUT INSERTED.IdModulo '
                    'VALUES (?, ?, ?, 1, GETDATE(), GETDATE())',
                    (nombre, ruta_val, int(orden)),
                )
                row = cur.fetchone()
            else:
                raise
        if not row or row[0] is None:
            raise RuntimeError('No se obtuvo IdModulo tras insertar.')
        id_modulo = int(row[0])
        conn.commit()
        logger.info('Modulos: módulo creado (IdModulo=%s, nombre=%s).', id_modulo, nombre)
        return id_modulo, ''
    except Exception as exc:
        _safe_rollback(conn)
        logger.exception('Modulos: error al crear módulo "%s".', nombre)
        return 0, 'No se pudo guardar. Revisa los datos y la conexión con DataAnalytics.'
    finally:
        _safe_close(conn)


def update_modulo(id_modulo: int, nombre: str, ruta: str | None, orden: int) -> tuple[bool, str]:
    """Actualiza nombre, ruta y orden de un módulo."""
    if not _is_enabled():
        return False, 'DataAnalytics no está habilitado.'

    nombre = (nombre or '').strip()
    if not nombre:
        return False, 'El nombre del módulo es requerido.'

    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()

        cur.execute('SELECT COUNT(*) FROM dbo.Modulos WHERE IdModulo = ?', (int(id_modulo),))
        if cur.fetchone()[0] == 0:
            return False, 'El módulo no existe.'

        cur.execute(
            'SELECT COUNT(*) FROM dbo.Modulos '
            'WHERE LTRIM(RTRIM(COALESCE(Modulo, \'\'))) = ? AND IdModulo != ?',
            (nombre, int(id_modulo)),
        )
        if cur.fetchone()[0] > 0:
            return False, f'Ya existe otro módulo con el nombre "{nombre}".'

        ruta_val = (ruta or '').strip() or None
        # Edición vía SP (fallback temporal: UPDATE directo). Existencia y nombre
        # duplicado ya se validaron arriba en Python.
        try:
            cur.execute('EXEC dbo.AddOrUpdModuloAdminDAsp ?, ?, ?, ?',
                        (int(id_modulo), nombre, ruta_val, int(orden)))
        except Exception as exc:
            if _is_missing_stored_procedure_error(exc):
                logger.warning('Modulos: SP AddOrUpdModuloAdminDAsp no existe todavía; usando SQL directo.')
                cur.execute(
                    'UPDATE dbo.Modulos '
                    'SET Modulo = ?, Ruta = ?, Orden = ?, FechaUpd = GETDATE() '
                    'WHERE IdModulo = ?',
                    (nombre, ruta_val, int(orden), int(id_modulo)),
                )
            else:
                raise
        conn.commit()
        logger.info('Modulos: módulo actualizado (IdModulo=%s).', id_modulo)
        return True, ''
    except Exception as exc:
        _safe_rollback(conn)
        logger.exception('Modulos: error al actualizar módulo (IdModulo=%s).', id_modulo)
        return False, 'No se pudo guardar. Revisa los datos y la conexión con DataAnalytics.'
    finally:
        _safe_close(conn)


def set_modulo_active(id_modulo: int, active: bool) -> bool:
    """Activa o desactiva un módulo (lógico)."""
    if not _is_enabled() or not id_modulo:
        return False
    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        # Estado vía SP (fallback temporal: UPDATE Activo directo).
        try:
            cur.execute('EXEC dbo.UpdModuloActivoAdminDAsp ?, ?',
                        (int(id_modulo), 1 if active else 0))
        except Exception as exc:
            if _is_missing_stored_procedure_error(exc):
                logger.warning('Modulos: SP UpdModuloActivoAdminDAsp no existe todavía; usando SQL directo.')
                cur.execute(
                    'UPDATE dbo.Modulos SET Activo = ?, FechaUpd = GETDATE() WHERE IdModulo = ?',
                    (1 if active else 0, int(id_modulo)),
                )
            else:
                raise
        conn.commit()
        logger.info('Modulos: módulo %s (IdModulo=%s).',
                    'activado' if active else 'desactivado', id_modulo)
        return True
    except Exception:
        _safe_rollback(conn)
        logger.exception('Modulos: error al cambiar estado de módulo (IdModulo=%s).', id_modulo)
        return False
    finally:
        _safe_close(conn)


# ──────────────────────────────────────────────────────────────
# Escritura — Submódulos
# ──────────────────────────────────────────────────────────────

def _coerce_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _get_ti_profile_id(cur) -> int | None:
    """IdPerfil del perfil TI (trim + case-insensitive), o None si no existe."""
    cur.execute(
        "SELECT IdPerfil FROM dbo.Perfiles "
        "WHERE UPPER(LTRIM(RTRIM(COALESCE(Perfil, '')))) = 'TI'"
    )
    row = cur.fetchone()
    return int(row[0]) if (row and row[0] is not None) else None


def _ensure_ti_permission_for_submodule(cur, id_submodulo: int, ti_id: int | None = None) -> None:
    """
    Inserta o reactiva el permiso del PERFIL TI sobre el submódulo, usando la MISMA
    transacción del llamador (no hace commit aquí).

    Reglas:
      - El permiso es por PERFIL TI (IdPerfil), NO por usuario individual.
      - NO asigna a Administrador ni a Usuario.
      - No duplica: si ya existe activo no hace nada; si existe inactivo lo reactiva.
    """
    if ti_id is None:
        ti_id = _get_ti_profile_id(cur)
    if not ti_id:
        logger.warning('Modulos: no se encontró el perfil TI; no se auto-asignó permiso del submódulo %s.',
                       id_submodulo)
        return

    cur.execute(
        'SELECT IdPerfilModulo, Activo FROM dbo.PerfilModulos '
        'WHERE IdPerfil = ? AND IdSubModulo = ?',
        (int(ti_id), int(id_submodulo)),
    )
    row = cur.fetchone()
    if row is None:
        cur.execute(
            'INSERT INTO dbo.PerfilModulos (IdPerfil, IdSubModulo, Activo, FechaAdd, FechaUpd) '
            'VALUES (?, ?, 1, GETDATE(), GETDATE())',
            (int(ti_id), int(id_submodulo)),
        )
        logger.info('Modulos: permiso TI auto-asignado (IdPerfil=%s, IdSubModulo=%s).', ti_id, id_submodulo)
    elif not bool(row[1]):
        cur.execute(
            'UPDATE dbo.PerfilModulos SET Activo = 1, FechaUpd = GETDATE() '
            'WHERE IdPerfilModulo = ?',
            (int(row[0]),),
        )
        logger.info('Modulos: permiso TI reactivado (IdSubModulo=%s).', id_submodulo)
    # else: ya estaba activo → no se duplica.


def create_submodulo(id_modulo: int, nombre: str, ruta: str | None,
                     orden: int, actor_id_perfil=None) -> tuple[int, str]:
    """
    Crea un submódulo hijo de id_modulo.

    Valida que:
        - El módulo padre exista y esté activo.
        - No haya otro submódulo con el mismo nombre bajo el mismo módulo.

    Auto-permiso TI (fix jun-2026): si `actor_id_perfil` corresponde al perfil TI,
    se inserta/reactiva automáticamente el permiso del PERFIL TI sobre el submódulo
    recién creado (en la misma transacción), para que aparezca en el menú BD-driven
    de TODOS los usuarios TI (no solo del que lo creó). NO se asigna a Administrador
    ni a Usuario.

    TODO (otro fix): el módulo de administración permite registrar rutas futuras.
    Si la Ruta del submódulo no existe aún en Django, aparecerá en el menú pero al
    entrar dará 404. Validar rutas existentes queda para una fase posterior.

    Returns:
        (id_submodulo, '') en éxito.
        (0, mensaje_error) si falla.
    """
    if not _is_enabled():
        return 0, 'DataAnalytics no está habilitado.'

    nombre = (nombre or '').strip()
    if not nombre:
        return 0, 'El nombre del submódulo es requerido.'

    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()

        # Verificar que el módulo padre existe y está activo
        cur.execute(
            'SELECT COUNT(*) FROM dbo.Modulos WHERE IdModulo = ? AND Activo = 1',
            (int(id_modulo),),
        )
        if cur.fetchone()[0] == 0:
            return 0, 'El módulo padre no existe o está inactivo.'

        # Verificar nombre duplicado bajo el mismo módulo
        cur.execute(
            'SELECT COUNT(*) FROM dbo.Submodulo '
            'WHERE IdModulo = ? AND LTRIM(RTRIM(SubModulo)) = ?',
            (int(id_modulo), nombre),
        )
        if cur.fetchone()[0] > 0:
            return 0, f'Ya existe un submódulo "{nombre}" bajo este módulo.'

        ruta_val = (ruta or '').strip() or None
        # Alta vía SP (fallback temporal: INSERT OUTPUT directo). El módulo padre y el
        # nombre duplicado ya se validaron arriba en Python; el SP solo inserta.
        try:
            cur.execute('EXEC dbo.AddOrUpdSubmoduloAdminDAsp ?, ?, ?, ?, ?',
                        (None, int(id_modulo), nombre, ruta_val, int(orden)))
            row = cur.fetchone()
        except Exception as exc:
            if _is_missing_stored_procedure_error(exc):
                logger.warning('Modulos: SP AddOrUpdSubmoduloAdminDAsp no existe todavía; usando SQL directo.')
                cur.execute(
                    'INSERT INTO dbo.Submodulo (IdModulo, SubModulo, Ruta, Orden, Activo, FechaAdd, FechaUpd) '
                    'OUTPUT INSERTED.IdSubModulo '
                    'VALUES (?, ?, ?, ?, 1, GETDATE(), GETDATE())',
                    (int(id_modulo), nombre, ruta_val, int(orden)),
                )
                row = cur.fetchone()
            else:
                raise
        if not row or row[0] is None:
            raise RuntimeError('No se obtuvo IdSubModulo tras insertar.')
        id_sub = int(row[0])

        # Auto-permiso TI: solo si el actor es del perfil TI (misma transacción).
        actor = _coerce_int(actor_id_perfil)
        if actor is not None:
            ti_id = _get_ti_profile_id(cur)
            if ti_id is not None and actor == ti_id:
                _ensure_ti_permission_for_submodule(cur, id_sub, ti_id=ti_id)

        conn.commit()
        logger.info('Modulos: submódulo creado (IdSubModulo=%s, nombre=%s).', id_sub, nombre)
        return id_sub, ''
    except Exception as exc:
        _safe_rollback(conn)
        logger.exception('Modulos: error al crear submódulo "%s".', nombre)
        return 0, 'No se pudo guardar. Revisa los datos y la conexión con DataAnalytics.'
    finally:
        _safe_close(conn)


def update_submodulo(id_submodulo: int, nombre: str, ruta: str | None,
                     orden: int) -> tuple[bool, str]:
    """Actualiza nombre, ruta y orden de un submódulo."""
    if not _is_enabled():
        return False, 'DataAnalytics no está habilitado.'

    nombre = (nombre or '').strip()
    if not nombre:
        return False, 'El nombre del submódulo es requerido.'

    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()

        # Obtener id_modulo del submódulo actual
        cur.execute(
            'SELECT IdModulo FROM dbo.Submodulo WHERE IdSubModulo = ?',
            (int(id_submodulo),),
        )
        row = cur.fetchone()
        if not row:
            return False, 'El submódulo no existe.'
        id_modulo = int(row[0])

        # Nombre duplicado en el mismo módulo
        cur.execute(
            'SELECT COUNT(*) FROM dbo.Submodulo '
            'WHERE IdModulo = ? AND LTRIM(RTRIM(SubModulo)) = ? AND IdSubModulo != ?',
            (id_modulo, nombre, int(id_submodulo)),
        )
        if cur.fetchone()[0] > 0:
            return False, f'Ya existe otro submódulo "{nombre}" bajo este módulo.'

        ruta_val = (ruta or '').strip() or None
        # Edición vía SP (fallback temporal: UPDATE directo). El submódulo no cambia de
        # módulo padre en edición (@IdModulo NULL). Existencia/duplicado ya validados arriba.
        try:
            cur.execute('EXEC dbo.AddOrUpdSubmoduloAdminDAsp ?, ?, ?, ?, ?',
                        (int(id_submodulo), None, nombre, ruta_val, int(orden)))
        except Exception as exc:
            if _is_missing_stored_procedure_error(exc):
                logger.warning('Modulos: SP AddOrUpdSubmoduloAdminDAsp no existe todavía; usando SQL directo.')
                cur.execute(
                    'UPDATE dbo.Submodulo '
                    'SET SubModulo = ?, Ruta = ?, Orden = ?, FechaUpd = GETDATE() '
                    'WHERE IdSubModulo = ?',
                    (nombre, ruta_val, int(orden), int(id_submodulo)),
                )
            else:
                raise
        conn.commit()
        logger.info('Modulos: submódulo actualizado (IdSubModulo=%s).', id_submodulo)
        return True, ''
    except Exception as exc:
        _safe_rollback(conn)
        logger.exception('Modulos: error al actualizar submódulo (IdSubModulo=%s).', id_submodulo)
        return False, 'No se pudo guardar. Revisa los datos y la conexión con DataAnalytics.'
    finally:
        _safe_close(conn)


# Submódulos BASE del sistema: nunca se eliminan físicamente (solo activar/desactivar).
# Comparación normalizada (strip + lower).
_SUBMODULOS_PROTEGIDOS = {
    '/usuarios/',
    '/perfiles/',
    '/modulos/',
    '/auditorias/',
    '/tpt/',
    '/error-logs/',
}


def es_submodulo_protegido(ruta) -> bool:
    """True si la ruta corresponde a un submódulo base del sistema (no eliminable)."""
    return str(ruta or '').strip().lower() in _SUBMODULOS_PROTEGIDOS


def delete_submodulo(id_submodulo: int, actor_id_perfil=None) -> tuple[bool, str]:
    """
    Elimina FÍSICAMENTE un submódulo creado por error y sus permisos asociados.

    Seguridad:
      - Los submódulos BASE (_SUBMODULOS_PROTEGIDOS) NO se eliminan: se rechaza.
      - Borra primero dbo.PerfilModulos (permisos) y luego dbo.Submodulo, en UNA
        transacción. No toca módulos padre, perfiles ni otras tablas.
      - Ante cualquier error hace rollback y devuelve un mensaje controlado.

    El control de permisos (TI/Administrador con acceso a /modulos/) lo hace el
    controlador antes de llamar aquí; `actor_id_perfil` se acepta por consistencia.

    Returns (True, '') en éxito; (False, mensaje) si no se eliminó.
    """
    if not _is_enabled():
        return False, 'DataAnalytics no está habilitado.'

    sid = _coerce_int(id_submodulo)
    if not sid:
        return False, 'Submódulo inválido.'

    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()

        # Localizar el submódulo y su ruta (para validar protección).
        cur.execute('SELECT Ruta FROM dbo.Submodulo WHERE IdSubModulo = ?', (sid,))
        row = cur.fetchone()
        if not row:
            return False, 'El submódulo no existe.'
        ruta = str(row[0]).strip() if row[0] is not None else ''

        if es_submodulo_protegido(ruta):
            return False, 'Este submódulo es base del sistema y no puede eliminarse.'

        # Baja física vía SP (fallback temporal: DELETE directo PerfilModulos→Submodulo).
        # La existencia y la protección del submódulo ya se validaron arriba en Python; el
        # SP solo borra los permisos y luego el submódulo, en el mismo orden.
        try:
            cur.execute('EXEC dbo.DelSubmoduloAdminDAsp ?', (sid,))
        except Exception as exc:
            if _is_missing_stored_procedure_error(exc):
                logger.warning('Modulos: SP DelSubmoduloAdminDAsp no existe todavía; usando SQL directo.')
                # Transacción: primero los permisos, luego el submódulo.
                cur.execute('DELETE FROM dbo.PerfilModulos WHERE IdSubModulo = ?', (sid,))
                cur.execute('DELETE FROM dbo.Submodulo WHERE IdSubModulo = ?', (sid,))
            else:
                raise
        conn.commit()
        logger.info('Modulos: submódulo eliminado (IdSubModulo=%s, ruta=%s).', sid, ruta)
        return True, ''
    except Exception as exc:
        _safe_rollback(conn)
        logger.exception('Modulos: error al eliminar submódulo (IdSubModulo=%s) — rollback.', id_submodulo)
        return False, 'No se pudo guardar. Revisa los datos y la conexión con DataAnalytics.'
    finally:
        _safe_close(conn)


def set_submodulo_active(id_submodulo: int, active: bool) -> bool:
    """Activa o desactiva un submódulo (lógico)."""
    if not _is_enabled() or not id_submodulo:
        return False
    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        # Estado vía SP (fallback temporal: UPDATE Activo directo).
        try:
            cur.execute('EXEC dbo.UpdSubmoduloActivoAdminDAsp ?, ?',
                        (int(id_submodulo), 1 if active else 0))
        except Exception as exc:
            if _is_missing_stored_procedure_error(exc):
                logger.warning('Modulos: SP UpdSubmoduloActivoAdminDAsp no existe todavía; usando SQL directo.')
                cur.execute(
                    'UPDATE dbo.Submodulo SET Activo = ?, FechaUpd = GETDATE() WHERE IdSubModulo = ?',
                    (1 if active else 0, int(id_submodulo)),
                )
            else:
                raise
        conn.commit()
        logger.info('Modulos: submódulo %s (IdSubModulo=%s).',
                    'activado' if active else 'desactivado', id_submodulo)
        return True
    except Exception:
        _safe_rollback(conn)
        logger.exception('Modulos: error al cambiar estado submódulo (IdSubModulo=%s).', id_submodulo)
        return False
    finally:
        _safe_close(conn)


# ──────────────────────────────────────────────────────────────
# Helpers privados
# ──────────────────────────────────────────────────────────────

def _row_to_modulo(row) -> dict:
    return {
        'id_modulo':     int(row[0]) if row[0] is not None else 0,
        'modulo':        str(row[1]).strip() if row[1] else '',
        'ruta':          str(row[2]).strip() if row[2] else '',
        'orden':         int(row[3]) if row[3] is not None else 0,
        'activo':        bool(row[4]),
        'fecha_add':     str(row[5]) if row[5] else '',
        'fecha_upd':     str(row[6]) if row[6] else '',
        'num_submodulos': int(row[7]) if row[7] is not None else 0,
    }


def _row_to_modulo_simple(row) -> dict:
    return {
        'id_modulo': int(row[0]) if row[0] is not None else 0,
        'modulo':    str(row[1]).strip() if row[1] else '',
        'ruta':      str(row[2]).strip() if row[2] else '',
        'orden':     int(row[3]) if row[3] is not None else 0,
        'activo':    bool(row[4]),
        'fecha_add': str(row[5]) if row[5] else '',
        'fecha_upd': str(row[6]) if row[6] else '',
    }


def _row_to_submodulo(row) -> dict:
    return {
        'id_submodulo': int(row[0]) if row[0] is not None else 0,
        'id_modulo':    int(row[1]) if row[1] is not None else 0,
        'submodulo':    str(row[2]).strip() if row[2] else '',
        'ruta':         str(row[3]).strip() if row[3] else '',
        'orden':        int(row[4]) if row[4] is not None else 0,
        'activo':       bool(row[5]),
        'fecha_add':    str(row[6]) if row[6] else '',
        'fecha_upd':    str(row[7]) if row[7] else '',
        'modulo':       str(row[8]).strip() if row[8] else '',
    }
