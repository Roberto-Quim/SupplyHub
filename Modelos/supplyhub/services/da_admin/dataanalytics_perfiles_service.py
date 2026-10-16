"""
dataanalytics_perfiles_service.py — CRUD de Perfiles y asignaciones de submódulos.

Responsabilidad:
    Administración de dbo.Perfiles y dbo.PerfilModulos (modelo jerárquico).

Reglas de negocio:
    - La creación/edición de un perfil y sus asignaciones ocurre en una sola
      transacción: si falla una asignación no queda el perfil a medias.
    - No se permiten asignaciones duplicadas (UNIQUE IdPerfil, IdSubModulo).
    - La activación/desactivación es lógica (Activo=0/1), no física.

Seguridad:
    - Consultas parametrizadas (?), nunca concatenación de input.
    - Escrituras con commit() en éxito y rollback() en excepción.
    - Conexión siempre cerrada (finally).
"""

import logging
import os

logger = logging.getLogger('supplyhub')


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
            logger.warning('Perfiles: SP %s no existe todavía; usando query directa.', sp_name)
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
# Lectura
# ──────────────────────────────────────────────────────────────

def list_profiles_full() -> list[dict]:
    """
    Lista todos los perfiles con su conteo de submódulos asignados.
    Incluye perfiles activos e inactivos.
    """
    if not _is_enabled():
        return []
    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        _sp_or_direct_execute(
            cur,
            'EXEC dbo.GetPerfilesAdminReadDAsp', None,
            'SELECT p.IdPerfil, p.Perfil, p.Activo, p.FechaAdd, p.FechaUpd, '
            '       COUNT(pm.IdPerfilModulo) AS NumSubmodulos '
            'FROM dbo.Perfiles p '
            'LEFT JOIN dbo.PerfilModulos pm '
            '       ON pm.IdPerfil = p.IdPerfil AND pm.Activo = 1 '
            'GROUP BY p.IdPerfil, p.Perfil, p.Activo, p.FechaAdd, p.FechaUpd '
            'ORDER BY p.Perfil',
            None,
            'GetPerfilesAdminReadDAsp',
        )
        return [_row_to_perfil(r) for r in cur.fetchall()]
    except Exception:
        logger.exception('Perfiles: error al listar perfiles.')
        raise RuntimeError('No se pudo consultar DataAnalytics.') from None
    finally:
        _safe_close(conn)


def get_profile_with_submodulos(id_perfil: int) -> dict | None:
    """
    Devuelve un perfil con sus asignaciones de submódulos.
    Retorna None si no existe o DataAnalytics deshabilitado.
    """
    if not _is_enabled() or not id_perfil:
        return None
    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()

        # Datos del perfil
        _sp_or_direct_execute(
            cur,
            'EXEC dbo.GetPerfilByIdReadDAsp ?', (int(id_perfil),),
            'SELECT IdPerfil, Perfil, Activo, FechaAdd, FechaUpd '
            'FROM dbo.Perfiles WHERE IdPerfil = ?',
            (int(id_perfil),),
            'GetPerfilByIdReadDAsp',
        )
        row = cur.fetchone()
        if not row:
            return None
        perfil = _row_to_perfil_simple(row)

        # Asignaciones actuales
        _sp_or_direct_execute(
            cur,
            'EXEC dbo.GetPerfilSubmodulosDAsp ?', (int(id_perfil),),
            'SELECT pm.IdSubModulo, s.SubModulo, s.Ruta, '
            '       m.Modulo, pm.Activo '
            'FROM dbo.PerfilModulos pm '
            'INNER JOIN dbo.Submodulo s ON s.IdSubModulo = pm.IdSubModulo '
            'INNER JOIN dbo.Modulos   m ON m.IdModulo    = s.IdModulo '
            'WHERE pm.IdPerfil = ? '
            'ORDER BY m.Orden, s.Orden',
            (int(id_perfil),),
            'GetPerfilSubmodulosDAsp',
        )
        perfil['asignaciones'] = [
            {
                'id_submodulo': int(r[0]),
                'submodulo':    str(r[1]).strip() if r[1] else '',
                'ruta':         str(r[2]).strip() if r[2] else '',
                'modulo':       str(r[3]).strip() if r[3] else '',
                'activo':       bool(r[4]),
            }
            for r in cur.fetchall()
        ]
        return perfil
    except Exception:
        logger.exception('Perfiles: error al obtener perfil (IdPerfil=%s).', id_perfil)
        return None
    finally:
        _safe_close(conn)


def list_all_submodulos_for_assignment() -> list[dict]:
    """
    Lista todos los submódulos activos agrupados por módulo,
    para el formulario de asignación de perfiles.
    """
    if not _is_enabled():
        return []
    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        _sp_or_direct_execute(
            cur,
            'EXEC dbo.GetSubmodulosAsignablesReadDAsp', None,
            'SELECT s.IdSubModulo, s.SubModulo, s.Ruta, s.Orden, s.Activo, '
            '       m.IdModulo, COALESCE(m.Modulo, \'\') AS Modulo, m.Orden AS ModuloOrden '
            'FROM dbo.Submodulo s '
            'INNER JOIN dbo.Modulos m ON m.IdModulo = s.IdModulo '
            'WHERE s.Activo = 1 AND m.Activo = 1 '
            'ORDER BY m.Orden, s.Orden',
            None,
            'GetSubmodulosAsignablesReadDAsp',
        )
        # Agrupar por módulo
        modulos: dict[int, dict] = {}
        for row in cur.fetchall():
            id_sub, nombre_sub, ruta, orden_sub, activo_sub, id_mod, nombre_mod, orden_mod = row
            if id_mod not in modulos:
                modulos[id_mod] = {
                    'id_modulo': int(id_mod),
                    'modulo':    str(nombre_mod).strip() if nombre_mod else '',
                    'orden':     int(orden_mod) if orden_mod is not None else 0,
                    'submodulos': [],
                }
            modulos[id_mod]['submodulos'].append({
                'id_submodulo': int(id_sub),
                'submodulo':    str(nombre_sub).strip() if nombre_sub else '',
                'ruta':         str(ruta).strip() if ruta else '',
                'orden':        int(orden_sub) if orden_sub is not None else 0,
                'activo':       bool(activo_sub),
            })
        return list(modulos.values())
    except Exception:
        logger.exception('Perfiles: error al listar submódulos para asignación.')
        raise RuntimeError('No se pudo consultar DataAnalytics.') from None
    finally:
        _safe_close(conn)


# ──────────────────────────────────────────────────────────────
# Escritura transaccional
# ──────────────────────────────────────────────────────────────

def create_profile(nombre: str, id_submodulos: list[int],
                   actor_id_perfil=None, system: bool = False) -> tuple[int, str]:
    """
    Crea un perfil nuevo y asigna sus submódulos en una sola transacción.

    Returns:
        (id_perfil, '') en éxito.
        (0, mensaje_error) en caso de error.
    """
    if not _is_enabled():
        return 0, 'DataAnalytics no está habilitado.'

    nombre = (nombre or '').strip()
    if not nombre:
        return 0, 'El nombre del perfil es requerido.'

    # Jerarquía (FAIL-CLOSED en la vía pública): Administrador no puede crear el
    # perfil TI; sin actor válido la vía pública DENIEGA. system=True (siembra)
    # es la única vía interna explícita que omite la jerarquía.
    if not system:
        from supplyhub.services.da_admin.dataanalytics_user_admin_service import can_actor_create_profile
        if not can_actor_create_profile(actor_id_perfil, nombre):
            return 0, 'No tienes permiso para crear un perfil con ese nombre.'

    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()

        # Verificar que no exista otro perfil con el mismo nombre
        cur.execute(
            'SELECT COUNT(*) FROM dbo.Perfiles WHERE LTRIM(RTRIM(Perfil)) = ?',
            (nombre,),
        )
        if cur.fetchone()[0] > 0:
            return 0, f'Ya existe un perfil con el nombre "{nombre}".'

        # Insertar perfil vía SP (fallback temporal: INSERT OUTPUT directo).
        # La AUTORIZACIÓN/JERARQUÍA y el chequeo de nombre duplicado ya se validaron
        # arriba en Python; el SP solo ejecuta la operación de datos ya autorizada.
        try:
            cur.execute('EXEC dbo.AddOrUpdPerfilAdminDAsp ?, ?', (None, nombre))
            row = cur.fetchone()
        except Exception as exc:
            if _is_missing_stored_procedure_error(exc):
                logger.warning('Perfiles: SP AddOrUpdPerfilAdminDAsp no existe todavía; usando SQL directo.')
                cur.execute(
                    'INSERT INTO dbo.Perfiles (Perfil, Activo, FechaAdd, FechaUpd) '
                    'OUTPUT INSERTED.IdPerfil '
                    'VALUES (?, 1, GETDATE(), GETDATE())',
                    (nombre,),
                )
                row = cur.fetchone()
            else:
                raise
        if not row or row[0] is None:
            raise RuntimeError('No se pudo obtener el IdPerfil del nuevo perfil.')
        id_perfil = int(row[0])

        # Asignaciones de submódulos vía SP (fallback: upsert directo).
        _set_perfil_submodulos(cur, id_perfil, id_submodulos)

        conn.commit()
        logger.info('Perfiles: perfil creado (IdPerfil=%s, nombre=%s).', id_perfil, nombre)
        return id_perfil, ''

    except Exception as exc:
        _safe_rollback(conn)
        logger.exception('Perfiles: error al crear perfil "%s" — rollback aplicado.', nombre)
        return 0, 'No se pudo guardar. Revisa los datos y la conexión con DataAnalytics.'
    finally:
        _safe_close(conn)


def update_profile(id_perfil: int, nombre: str, id_submodulos: list[int],
                   actor_id_perfil=None, system: bool = False) -> tuple[bool, str]:
    """
    Actualiza nombre y asignaciones de un perfil en una sola transacción.
    Las asignaciones antiguas se reemplazan por la lista nueva.

    Returns:
        (True, '') en éxito.
        (False, mensaje_error) en caso de error.
    """
    if not _is_enabled():
        return False, 'DataAnalytics no está habilitado.'

    # Jerarquía (FAIL-CLOSED en la vía pública): Administrador no puede
    # editar/cambiar permisos del perfil TI. system=True es la única vía interna
    # (siembra/migración). Sin actor válido la vía pública DENIEGA.
    if not system:
        from supplyhub.services.da_admin.dataanalytics_user_admin_service import can_actor_modify_profile
        if not can_actor_modify_profile(actor_id_perfil, id_perfil):
            return False, 'No tienes permiso para modificar este perfil.'

    nombre = (nombre or '').strip()
    if not nombre:
        return False, 'El nombre del perfil es requerido.'

    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()

        # Verificar que el perfil existe
        cur.execute('SELECT COUNT(*) FROM dbo.Perfiles WHERE IdPerfil = ?', (int(id_perfil),))
        if cur.fetchone()[0] == 0:
            return False, 'El perfil no existe.'

        # Verificar nombre duplicado (excluir el propio)
        cur.execute(
            'SELECT COUNT(*) FROM dbo.Perfiles '
            'WHERE LTRIM(RTRIM(Perfil)) = ? AND IdPerfil != ?',
            (nombre, int(id_perfil)),
        )
        if cur.fetchone()[0] > 0:
            return False, f'Ya existe otro perfil con el nombre "{nombre}".'

        # Actualizar nombre vía SP (fallback temporal: UPDATE directo). La jerarquía y
        # los chequeos de existencia/nombre duplicado ya se validaron arriba en Python.
        try:
            cur.execute('EXEC dbo.AddOrUpdPerfilAdminDAsp ?, ?', (int(id_perfil), nombre))
        except Exception as exc:
            if _is_missing_stored_procedure_error(exc):
                logger.warning('Perfiles: SP AddOrUpdPerfilAdminDAsp no existe todavía; usando SQL directo.')
                cur.execute(
                    'UPDATE dbo.Perfiles SET Perfil = ?, FechaUpd = GETDATE() WHERE IdPerfil = ?',
                    (nombre, int(id_perfil)),
                )
            else:
                raise

        # Reemplazar asignaciones vía SP (fallback: upsert directo).
        _set_perfil_submodulos(cur, id_perfil, id_submodulos)

        conn.commit()
        logger.info('Perfiles: perfil actualizado (IdPerfil=%s).', id_perfil)
        return True, ''

    except Exception as exc:
        _safe_rollback(conn)
        logger.exception('Perfiles: error al actualizar perfil (IdPerfil=%s) — rollback.', id_perfil)
        return False, 'No se pudo guardar. Revisa los datos y la conexión con DataAnalytics.'
    finally:
        _safe_close(conn)


def set_profile_active(id_perfil: int, active: bool, actor_id_perfil=None,
                       system: bool = False) -> bool:
    """Activa o desactiva un perfil. No borra físicamente."""
    if not _is_enabled() or not id_perfil:
        return False
    # Jerarquía (FAIL-CLOSED en la vía pública): Administrador no puede
    # activar/desactivar el perfil TI. system=True es la única vía interna.
    if not system:
        from supplyhub.services.da_admin.dataanalytics_user_admin_service import can_actor_modify_profile
        if not can_actor_modify_profile(actor_id_perfil, id_perfil):
            return False
    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        # Estado del perfil vía SP (fallback temporal: UPDATE Activo directo). La
        # jerarquía ya se validó arriba en Python.
        try:
            cur.execute('EXEC dbo.UpdPerfilActivoAdminDAsp ?, ?',
                        (int(id_perfil), 1 if active else 0))
        except Exception as exc:
            if _is_missing_stored_procedure_error(exc):
                logger.warning('Perfiles: SP UpdPerfilActivoAdminDAsp no existe todavía; usando SQL directo.')
                cur.execute(
                    'UPDATE dbo.Perfiles SET Activo = ?, FechaUpd = GETDATE() WHERE IdPerfil = ?',
                    (1 if active else 0, int(id_perfil)),
                )
            else:
                raise
        conn.commit()
        logger.info('Perfiles: perfil %s (IdPerfil=%s).',
                    'activado' if active else 'desactivado', id_perfil)
        return True
    except Exception:
        _safe_rollback(conn)
        logger.exception('Perfiles: error al cambiar estado (IdPerfil=%s).', id_perfil)
        return False
    finally:
        _safe_close(conn)


# ──────────────────────────────────────────────────────────────
# Helpers privados
# ──────────────────────────────────────────────────────────────

def _set_perfil_submodulos(cur, id_perfil: int, id_submodulos: list[int]) -> None:
    """
    Reemplaza las asignaciones PerfilModulos del perfil (desactiva las removidas,
    reactiva las existentes, inserta las nuevas) vía SP `SetPerfilSubmodulosAdminDAsp`.

    SP-first: intenta EXEC y, SOLO si el SP no existe (2812), cae al upsert directo
    equivalente (`_upsert_asignaciones(..., reemplazar=True)`). Cualquier otro error
    (incluida la validación de submódulos inválidos/inactivos que el SP rechaza con
    RAISERROR, o el `ValueError` del fallback) se propaga → rollback del llamador.

    Las claves viajan como CSV de enteros en un parámetro (?), nunca concatenadas al SQL.
    """
    ids = [int(s) for s in (id_submodulos or [])]      # valida numérico (igual que hoy)
    csv = ','.join(str(s) for s in ids) or None
    try:
        cur.execute('EXEC dbo.SetPerfilSubmodulosAdminDAsp ?, ?', (int(id_perfil), csv))
    except Exception as exc:
        if _is_missing_stored_procedure_error(exc):
            logger.warning('Perfiles: SP SetPerfilSubmodulosAdminDAsp no existe todavía; usando SQL directo.')
            _upsert_asignaciones(cur, id_perfil, ids, reemplazar=True)
        else:
            raise


def _upsert_asignaciones(cur, id_perfil: int, id_submodulos: list[int],
                         reemplazar: bool = False) -> None:
    """
    Mantiene las asignaciones PerfilModulos para el perfil dado.

    Si reemplazar=True: desactiva las asignaciones no incluidas en la lista
    y activa/crea las incluidas. No borra físicamente.

    Lanza excepción si algún id_submodulo es inválido.
    """
    if not id_submodulos and not reemplazar:
        return

    # Validar que todos los IdSubModulo son válidos y activos
    if id_submodulos:
        placeholders = ','.join(['?'] * len(id_submodulos))
        cur.execute(
            f'SELECT COUNT(*) FROM dbo.Submodulo '
            f'WHERE IdSubModulo IN ({placeholders}) AND Activo = 1',
            [int(s) for s in id_submodulos],
        )
        validos = cur.fetchone()[0]
        if validos != len(id_submodulos):
            raise ValueError(
                f'Uno o más IdSubModulo no existen o están inactivos: {id_submodulos}'
            )

    if reemplazar:
        if id_submodulos:
            placeholders = ','.join(['?'] * len(id_submodulos))
            # Desactivar los que no están en la lista nueva
            cur.execute(
                f'UPDATE dbo.PerfilModulos SET Activo = 0, FechaUpd = GETDATE() '
                f'WHERE IdPerfil = ? AND IdSubModulo NOT IN ({placeholders})',
                [int(id_perfil)] + [int(s) for s in id_submodulos],
            )
        else:
            # Sin submódulos → desactivar todos
            cur.execute(
                'UPDATE dbo.PerfilModulos SET Activo = 0, FechaUpd = GETDATE() '
                'WHERE IdPerfil = ?',
                (int(id_perfil),),
            )

    # Upsert: activar los existentes y crear los nuevos
    for id_sub in id_submodulos:
        cur.execute(
            'SELECT IdPerfilModulo FROM dbo.PerfilModulos '
            'WHERE IdPerfil = ? AND IdSubModulo = ?',
            (int(id_perfil), int(id_sub)),
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                'UPDATE dbo.PerfilModulos SET Activo = 1, FechaUpd = GETDATE() '
                'WHERE IdPerfil = ? AND IdSubModulo = ?',
                (int(id_perfil), int(id_sub)),
            )
        else:
            cur.execute(
                'INSERT INTO dbo.PerfilModulos (IdPerfil, IdSubModulo, Activo, FechaAdd, FechaUpd) '
                'VALUES (?, ?, 1, GETDATE(), GETDATE())',
                (int(id_perfil), int(id_sub)),
            )


def _row_to_perfil(row) -> dict:
    """Convierte fila con conteo de submódulos a dict."""
    return {
        'id_perfil':     int(row[0]) if row[0] is not None else 0,
        'perfil':        str(row[1]).strip() if row[1] else '',
        'activo':        bool(row[2]),
        'fecha_add':     str(row[3]) if row[3] else '',
        'fecha_upd':     str(row[4]) if row[4] else '',
        'num_submodulos': int(row[5]) if row[5] is not None else 0,
    }


def _row_to_perfil_simple(row) -> dict:
    """Convierte fila básica de perfil a dict."""
    return {
        'id_perfil': int(row[0]) if row[0] is not None else 0,
        'perfil':    str(row[1]).strip() if row[1] else '',
        'activo':    bool(row[2]),
        'fecha_add': str(row[3]) if row[3] else '',
        'fecha_upd': str(row[4]) if row[4] else '',
    }
