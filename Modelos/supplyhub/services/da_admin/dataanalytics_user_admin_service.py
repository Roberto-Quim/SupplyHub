"""
dataanalytics_user_admin_service.py — Administración de usuarios de DataAnalytics.

Responsabilidad:
    CRUD de DataAnalytics.dbo.Usuarios y lectura de dbo.Perfiles para el
    módulo "Administrar usuarios". Búsqueda de candidatos por nómina
    (reutilizando get_payroll_worker_data) o por correo.

Seguridad:
    - Todas las consultas usan parámetros (?), nunca concatenación de input.
    - Escrituras hacen commit() en éxito y rollback() en excepción.
    - La conexión siempre se cierra (finally).
    - Si DATAANALYTICS_ENABLED=False, las funciones de lectura devuelven
      vacío y las de escritura no hacen nada (el sistema sigue como antes).
    - Nunca imprime contraseñas ni datos sensibles en logs.
"""

import logging
import os
import re

logger = logging.getLogger('supplyhub')

# Perfiles autorizados para administrar usuarios (comparación case-insensitive)
_ADMIN_PROFILE_NAMES = frozenset({'ti', 'administrador', 'admin'})

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

IDENTIFIER_NOMINA = 'nomina'
IDENTIFIER_CORREO = 'correo'

# Acceso por defecto cuando no se especifica (3 = 'base de datos' en dbo.Acceso).
# La columna dbo.Usuarios.IdAcceso permite NULL con default 3; aquí lo normalizamos.
_DEFAULT_ID_ACCESO = 3

# SELECT de lectura de usuarios — incluye perfil (dbo.Perfiles) y acceso (dbo.Acceso).
# LEFT JOIN para no descartar filas con IdAcceso/IdPerfil NULL.
_USER_SELECT = (
    'SELECT u.IdUsuario, u.NoNomina, u.Correo, u.IdPerfil, p.Perfil, '
    '       u.Activo, u.FechaAdd, u.FechaUpd, '
    '       u.IdAcceso, ac.Acceso '
    'FROM dbo.Usuarios u '
    'LEFT JOIN dbo.Perfiles p ON u.IdPerfil = p.IdPerfil '
    'LEFT JOIN dbo.Acceso ac ON ac.IdAcceso = u.IdAcceso '
)


# ---------------------------------------------------------------------------
# Helpers de estado / detección
# ---------------------------------------------------------------------------

def _is_enabled() -> bool:
    from django.conf import settings
    return settings.DATAANALYTICS_ENABLED


def _is_missing_database_object_error(exc: Exception) -> bool:
    """
    True si la excepción es "objeto de BD inexistente" en SQL Server, caso ESPERADO
    durante la migración a SPs (antes de ejecutar 015): NO es un bug.
      - Procedimiento inexistente: 'Could not find stored procedure' · error 2812
      - Tabla/objeto inexistente:  'Invalid object name' · error 208 · SQLSTATE 42S02
    """
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


def _is_missing_stored_procedure_error(exc: Exception) -> bool:
    """
    True SOLO si el SP no existe ('Could not find stored procedure' / error 2812).
    Para ESCRITURAS solo se hace fallback en este caso (el error ocurre al enlazar
    el EXEC, antes de ejecutar nada → es seguro reintentar con SQL directo). Otros
    errores (incluida tabla faltante) NO disparan fallback: se propagan → rollback.
    """
    texto = str(exc).lower()
    return ('could not find stored procedure' in texto) or ('2812' in texto)


def _sp_or_direct_execute(cur, sp_sql, sp_params, direct_sql, direct_params, sp_name):
    """
    Ejecuta el SP de lectura; si el SP/objeto aún no existe en la BD (2812/208/...),
    cae a la query directa equivalente en el MISMO cursor (fallback temporal). Otros
    errores se propagan al llamador (que mantiene su logger.exception y retorno). Deja
    el cursor listo para fetchone()/fetchall(). Parámetros con ? (nunca concatenados).
    """
    try:
        if sp_params is None:
            cur.execute(sp_sql)
        else:
            cur.execute(sp_sql, sp_params)
    except Exception as exc:
        if _is_missing_database_object_error(exc):
            logger.warning('UserAdmin: SP %s no existe todavía; usando query directa.', sp_name)
            if direct_params is None:
                cur.execute(direct_sql)
            else:
                cur.execute(direct_sql, direct_params)
        else:
            raise


def is_valid_email(value: str) -> bool:
    """True si value tiene formato de correo válido."""
    return bool(_EMAIL_RE.match((value or '').strip()))


def detect_identifier_type(identifier: str) -> str:
    """
    Detecta si el identificador es un correo o un número de nómina.
    - Contiene '@' → correo
    - Solo dígitos → nómina
    - Default → nómina (se valida después)
    """
    ident = (identifier or '').strip()
    if '@' in ident:
        return IDENTIFIER_CORREO
    return IDENTIFIER_NOMINA


def profile_can_manage(id_perfil: int) -> bool:
    """
    True si el IdPerfil corresponde a un perfil con permiso de administración
    (TI o Administrador). Resuelve el nombre desde dbo.Perfiles.
    """
    if not id_perfil:
        return False
    name = get_profile_name(id_perfil)
    return bool(name) and name.strip().lower() in _ADMIN_PROFILE_NAMES


# ---------------------------------------------------------------------------
# Jerarquía TI > Administrador > Usuario (helpers centralizados)
#
# Regla (Ing. Juan Carlos Bermúdez, jun-2026):
#   - TI: puede modificar cualquier usuario/perfil (incluido TI) y a sí mismo.
#   - Administrador: NO puede crear/editar/activar/desactivar usuarios TI, NO
#     puede asignar el perfil TI, NI editar/activar/desactivar/cambiar permisos
#     del perfil TI. Sí puede administrar Administrador y Usuario, y a sí mismo.
#   - El perfil objetivo SIEMPRE se resuelve desde la BD, nunca desde el POST.
# ---------------------------------------------------------------------------

PERFIL_TI = 'ti'


def is_ti_profile(id_perfil) -> bool:
    """True si el IdPerfil corresponde al perfil TI (resuelto desde BD)."""
    if not id_perfil:
        return False
    try:
        return get_profile_name(int(id_perfil)).strip().lower() == PERFIL_TI
    except (ValueError, TypeError):
        return False


def _actor_kind(actor_id_perfil) -> str:
    """'ti' | 'administrador' | 'otro' a partir del perfil del actor en sesión."""
    name = get_profile_name(actor_id_perfil).strip().lower() if actor_id_perfil else ''
    if name == 'ti':
        return 'ti'
    if name in ('administrador', 'admin'):
        return 'administrador'
    return 'otro'


def get_user_profile_id(id_usuario) -> int | None:
    """IdPerfil actual del usuario (desde dbo.Usuarios), o None."""
    if not _is_enabled() or not id_usuario:
        return None
    conn = None
    try:
        from supplyhub.connectors.dataanalytics_connection import get_dataanalytics_conn
        conn = get_dataanalytics_conn()
        cur = conn.cursor()
        _sp_or_direct_execute(
            cur,
            'EXEC dbo.GetUsuarioPerfilIdDAsp ?', (int(id_usuario),),
            'SELECT IdPerfil FROM dbo.Usuarios WHERE IdUsuario = ?', (int(id_usuario),),
            'GetUsuarioPerfilIdDAsp',
        )
        row = cur.fetchone()
        return int(row[0]) if (row and row[0] is not None) else None
    except Exception:
        logger.exception('UserAdmin: error al leer perfil de usuario (IdUsuario=%s).', id_usuario)
        return None
    finally:
        _safe_close(conn)


def can_actor_assign_profile(actor_id_perfil, target_id_perfil) -> bool:
    """¿Puede el actor ASIGNAR el perfil target a un usuario? Administrador no asigna TI."""
    kind = _actor_kind(actor_id_perfil)
    if kind == 'ti':
        return True
    if kind == 'administrador':
        return bool(get_profile_name(target_id_perfil)) and not is_ti_profile(target_id_perfil)
    return False


def can_actor_modify_user(actor_id_perfil, target_user_id) -> bool:
    """¿Puede el actor editar/activar/desactivar al usuario target? Resuelve perfil desde BD."""
    kind = _actor_kind(actor_id_perfil)
    if kind == 'ti':
        return True
    if kind == 'administrador':
        target = get_user_profile_id(target_user_id)
        return bool(target) and bool(get_profile_name(target)) and not is_ti_profile(target)
    return False


def can_actor_modify_profile(actor_id_perfil, target_profile_id) -> bool:
    """¿Puede el actor editar/activar/desactivar/cambiar permisos del perfil target?"""
    kind = _actor_kind(actor_id_perfil)
    if kind == 'ti':
        return True
    if kind == 'administrador':
        return bool(get_profile_name(target_profile_id)) and not is_ti_profile(target_profile_id)
    return False


def can_actor_create_profile(actor_id_perfil, nuevo_nombre: str) -> bool:
    """¿Puede el actor CREAR un perfil con ese nombre? Administrador no crea TI."""
    kind = _actor_kind(actor_id_perfil)
    if kind == 'ti':
        return True
    if kind == 'administrador':
        return (nuevo_nombre or '').strip().lower() != PERFIL_TI
    return False


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------

def get_profile_name(id_perfil: int) -> str:
    """Devuelve el nombre del perfil para un IdPerfil, o '' si no existe."""
    if not _is_enabled() or not id_perfil:
        return ''
    conn = None
    try:
        from supplyhub.connectors.dataanalytics_connection import get_dataanalytics_conn
        conn = get_dataanalytics_conn()
        cur = conn.cursor()
        _sp_or_direct_execute(
            cur,
            'EXEC dbo.GetPerfilNombreDAsp ?', (int(id_perfil),),
            'SELECT Perfil FROM dbo.Perfiles WHERE IdPerfil = ?', (int(id_perfil),),
            'GetPerfilNombreDAsp',
        )
        row = cur.fetchone()
        return str(row[0]).strip() if (row and row[0] is not None) else ''
    except Exception:
        logger.exception('UserAdmin: error al leer nombre de perfil (IdPerfil=%s).', id_perfil)
        return ''
    finally:
        _safe_close(conn)


def list_profiles() -> list[dict]:
    """Lista perfiles activos (Activo=1) para el dropdown."""
    if not _is_enabled():
        return []
    conn = None
    try:
        from supplyhub.connectors.dataanalytics_connection import get_dataanalytics_conn
        conn = get_dataanalytics_conn()
        cur = conn.cursor()
        _sp_or_direct_execute(
            cur,
            'EXEC dbo.GetPerfilesCatalogoDAsp', None,
            'SELECT IdPerfil, Perfil FROM dbo.Perfiles WHERE Activo = 1 ORDER BY Perfil', None,
            'GetPerfilesCatalogoDAsp',
        )
        return [
            {'id_perfil': int(r[0]), 'perfil': str(r[1]).strip() if r[1] else ''}
            for r in cur.fetchall()
        ]
    except Exception:
        logger.exception('UserAdmin: error al listar perfiles.')
        raise RuntimeError('No se pudo consultar DataAnalytics.') from None
    finally:
        _safe_close(conn)


def list_acceso() -> list[dict]:
    """Lista los tipos de acceso activos (dbo.Acceso) para el dropdown 'Acceso'."""
    if not _is_enabled():
        return []
    conn = None
    try:
        from supplyhub.connectors.dataanalytics_connection import get_dataanalytics_conn
        conn = get_dataanalytics_conn()
        cur = conn.cursor()
        _sp_or_direct_execute(
            cur,
            'EXEC dbo.GetAccesosCatalogoDAsp', None,
            'SELECT IdAcceso, Acceso FROM dbo.Acceso WHERE Activo = 1 ORDER BY IdAcceso', None,
            'GetAccesosCatalogoDAsp',
        )
        return [
            {'id_acceso': int(r[0]), 'acceso': str(r[1]).strip() if r[1] else ''}
            for r in cur.fetchall()
        ]
    except Exception:
        logger.exception('UserAdmin: error al listar accesos.')
        raise RuntimeError('No se pudo consultar DataAnalytics.') from None
    finally:
        _safe_close(conn)


def list_users() -> list[dict]:
    """Lista todos los usuarios con su perfil y acceso, más recientes primero."""
    if not _is_enabled():
        return []
    conn = None
    try:
        from supplyhub.connectors.dataanalytics_connection import get_dataanalytics_conn
        conn = get_dataanalytics_conn()
        cur = conn.cursor()
        _sp_or_direct_execute(
            cur,
            'EXEC dbo.GetUsuariosAdminDAsp', None,
            _USER_SELECT + 'ORDER BY u.IdUsuario DESC', None,
            'GetUsuariosAdminDAsp',
        )
        return [_row_to_user(r) for r in cur.fetchall()]
    except Exception:
        logger.exception('UserAdmin: error al listar usuarios.')
        raise RuntimeError('No se pudo consultar DataAnalytics.') from None
    finally:
        _safe_close(conn)


def get_user_by_id(id_usuario: int) -> dict | None:
    """Devuelve un usuario por IdUsuario, o None."""
    if not _is_enabled() or not id_usuario:
        return None
    conn = None
    try:
        from supplyhub.connectors.dataanalytics_connection import get_dataanalytics_conn
        conn = get_dataanalytics_conn()
        cur = conn.cursor()
        _sp_or_direct_execute(
            cur,
            'EXEC dbo.GetUsuarioAdminByIdDAsp ?', (int(id_usuario),),
            _USER_SELECT + 'WHERE u.IdUsuario = ?', (int(id_usuario),),
            'GetUsuarioAdminByIdDAsp',
        )
        row = cur.fetchone()
        return _row_to_user(row) if row else None
    except Exception:
        logger.exception('UserAdmin: error al obtener usuario (IdUsuario=%s).', id_usuario)
        return None
    finally:
        _safe_close(conn)


def find_user_in_dataanalytics(identifier: str) -> dict | None:
    """
    Busca un usuario existente en dbo.Usuarios por NoNomina o Correo.
    Detecta el tipo automáticamente. Devuelve dict o None.
    """
    if not _is_enabled():
        return None
    ident = (identifier or '').strip()
    if not ident:
        return None

    tipo = detect_identifier_type(ident)
    conn = None
    try:
        from supplyhub.connectors.dataanalytics_connection import get_dataanalytics_conn
        conn = get_dataanalytics_conn()
        cur = conn.cursor()
        if tipo == IDENTIFIER_CORREO:
            cur.execute(
                _USER_SELECT + 'WHERE LOWER(LTRIM(RTRIM(u.Correo))) = LOWER(?)',
                (ident,),
            )
        else:
            cur.execute(
                _USER_SELECT + 'WHERE LTRIM(RTRIM(u.NoNomina)) = ?',
                (ident,),
            )
        row = cur.fetchone()
        return _row_to_user(row) if row else None
    except Exception:
        logger.exception('UserAdmin: error al buscar usuario en DataAnalytics (tipo=%s).', tipo)
        return None
    finally:
        _safe_close(conn)


def search_candidate(identifier: str) -> dict:
    """
    Busca un candidato para alta/edición.

    Returns dict con:
        tipo:            'nomina' | 'correo'
        identifier:      valor normalizado
        exists_in_da:    bool — ya existe en dbo.Usuarios
        da_user:         dict | None — el usuario en DataAnalytics si existe
        source_data:     dict | None — datos del trabajador desde SSO (solo nómina)
        can_create:      bool — se permite crear si no existe
        message:         str  — aviso para la UI
    """
    ident = (identifier or '').strip()
    result = {
        'tipo': None, 'identifier': ident, 'exists_in_da': False,
        'da_user': None, 'source_data': None, 'can_create': False, 'message': '',
    }
    if not ident:
        result['message'] = 'Ingresa un número de nómina o correo.'
        return result

    tipo = detect_identifier_type(ident)
    result['tipo'] = tipo

    # 1. ¿Ya existe en DataAnalytics?
    da_user = find_user_in_dataanalytics(ident)
    if da_user:
        result['exists_in_da'] = True
        result['da_user']      = da_user
        result['can_create']   = False
        result['message']      = 'Usuario ya existe. Puedes actualizar perfil o activar/desactivar.'
        # Enriquecer con SSO si es nómina (solo informativo)
        if tipo == IDENTIFIER_NOMINA:
            result['source_data'] = _fetch_sso_worker(ident)
        return result

    # 2. No existe: buscar candidato en fuente autorizada
    if tipo == IDENTIFIER_NOMINA:
        worker = _fetch_sso_worker(ident)
        if worker:
            result['source_data'] = worker
            result['can_create']  = True
            result['message']     = 'Trabajador encontrado en fuente SSO. Asigna perfil y guarda.'
        else:
            result['can_create']  = False
            result['message']     = 'Nómina no encontrada en fuente autorizada.'
    else:  # correo
        if is_valid_email(ident):
            result['can_create'] = True
            result['message']    = (
                'Correo no encontrado en fuente autorizada. '
                'Puedes darlo de alta confirmando la acción.'
            )
        else:
            result['can_create'] = False
            result['message']    = 'Correo con formato inválido.'

    return result


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------

def _normaliza_id_acceso(id_acceso) -> int:
    """Convierte id_acceso a int; vacío/None/ inválido → default 3 ('base de datos')."""
    try:
        v = int(str(id_acceso).strip())
        return v if v > 0 else _DEFAULT_ID_ACCESO
    except (ValueError, TypeError, AttributeError):
        return _DEFAULT_ID_ACCESO


# IdAcceso (mapea con dbo.Acceso): 1=Correo, 2=Directorio Activo, 3=Base de Datos.
_ACCESO_CORREO = 1
_ACCESO_AD     = 2
_ACCESO_BD     = 3


def acceso_validacion_error(id_acceso, no_nomina, correo) -> str:
    """
    Valida que estén presentes los campos requeridos según el método de acceso.

    Reglas (Requerimiento 2):
        - IdAcceso = 1 (Correo Electrónico) → requiere Correo.
        - IdAcceso = 2 (Directorio Activo)  → requiere Correo y/o NoNomina.
        - IdAcceso = 3 (Base de Datos)      → requiere NoNomina.

    Returns:
        '' si es válido, o un mensaje de error legible para la UI.
    """
    acceso = _normaliza_id_acceso(id_acceso)
    nom = (no_nomina or '').strip()
    cor = (correo or '').strip()

    if acceso == _ACCESO_CORREO and not cor:
        return 'El acceso por Correo Electrónico requiere un Correo.'
    if acceso == _ACCESO_BD and not nom:
        return 'El acceso por Base de Datos requiere un Número de Nómina.'
    if acceso == _ACCESO_AD and not (cor or nom):
        return 'El acceso por Directorio Activo requiere Correo y/o Número de Nómina.'
    return ''


def _ensure_planta_inicial_safe(id_usuario, no_nomina, correo) -> None:
    """
    Asignación AUTOMÁTICA de planta inicial tras un alta/actualización (Fase 2).
    Es un paso NO FATAL: cualquier error se registra y NO rompe el alta del usuario.
    """
    try:
        from supplyhub.services.da_admin.dataanalytics_usuario_plantas_service import (
            ensure_usuario_planta_inicial,
        )
        ensure_usuario_planta_inicial(id_usuario, no_nomina=no_nomina, correo=correo)
    except Exception:
        logger.exception(
            'UserAdmin: fallo NO FATAL en asignación de planta inicial (IdUsuario=%s).',
            id_usuario,
        )


def upsert_user(no_nomina: str | None, correo: str | None, id_perfil: int,
                id_acceso=None, actor_id_perfil=None, system: bool = False) -> tuple[int, bool]:
    """
    Inserta o actualiza un usuario en dbo.Usuarios.

    Reglas:
        - Busca existente por NoNomina (si viene) o por Correo.
        - id_acceso: si no se proporciona o viene vacío, aplica el default 3.
        - Si existe: actualiza IdPerfil, id_acceso, completa NoNomina/Correo si faltan,
          Activo=1, FechaUpd=GETDATE().
        - Si no existe: inserta con id_acceso, Activo=1, FechaAdd/FechaUpd=GETDATE().

    Returns:
        (id_usuario, created) — created=True si fue alta nueva.
        (0, False) si DataAnalytics está deshabilitado o falla.
    """
    if not _is_enabled():
        return 0, False
    if not id_perfil:
        logger.warning('UserAdmin: upsert sin IdPerfil — abortado.')
        return 0, False

    # Jerarquía (FAIL-CLOSED en la vía pública): el actor debe poder asignar el
    # perfil objetivo. system=True es la ÚNICA vía interna explícita (siembra /
    # migración) que omite la jerarquía. Sin actor válido (None/ajeno) la vía
    # pública DENIEGA — no basta con que el controlador normalmente pase el actor.
    if not system and not can_actor_assign_profile(actor_id_perfil, id_perfil):
        logger.warning('UserAdmin: actor sin permiso para asignar el perfil objetivo — abortado.')
        return 0, False

    nomina = (no_nomina or '').strip() or None
    email  = (correo or '').strip() or None
    acceso = _normaliza_id_acceso(id_acceso)
    if not nomina and not email:
        logger.warning('UserAdmin: upsert sin nómina ni correo — abortado.')
        return 0, False

    # Validar campos requeridos según el método de acceso (Requerimiento 2).
    # Solo si id_acceso viene explícito (el alta del admin siempre lo envía);
    # si no se especifica, se conserva el comportamiento previo (default 3).
    if id_acceso is not None and str(id_acceso).strip() != '':
        val_error = acceso_validacion_error(acceso, nomina, email)
        if val_error:
            logger.warning('UserAdmin: upsert con campos faltantes para IdAcceso=%s — abortado.', acceso)
            return 0, False

    conn = None
    try:
        from supplyhub.connectors.dataanalytics_connection import get_dataanalytics_conn
        conn = get_dataanalytics_conn()
        cur = conn.cursor()

        # Buscar existente (parametrizado)
        existing_id = None
        if nomina:
            cur.execute(
                'SELECT IdUsuario FROM dbo.Usuarios WHERE LTRIM(RTRIM(NoNomina)) = ?',
                (nomina,),
            )
            r = cur.fetchone()
            if r:
                existing_id = int(r[0])
        if existing_id is None and email:
            cur.execute(
                'SELECT IdUsuario FROM dbo.Usuarios '
                'WHERE LOWER(LTRIM(RTRIM(Correo))) = LOWER(?)',
                (email,),
            )
            r = cur.fetchone()
            if r:
                existing_id = int(r[0])

        # Jerarquía: si se edita un usuario existente, el actor debe poder
        # modificar al usuario objetivo (Administrador no puede tocar TI).
        if existing_id is not None and not system \
           and not can_actor_modify_user(actor_id_perfil, existing_id):
            logger.warning('UserAdmin: actor sin permiso para modificar al usuario objetivo — abortado.')
            return 0, False

        # La operación de DATOS (update/insert) se delega al SP AddOrUpdUsuarioAdminDAsp.
        # La AUTORIZACIÓN/JERARQUÍA ya se validó arriba en Python (existing_id y actor).
        # El SP recibe @IdUsuario para decidir update vs insert (no re-resuelve jerarquía).
        if existing_id is not None:
            # Actualizar vía SP (fallback temporal: UPDATE COALESCE directo). Sin fetch.
            try:
                cur.execute(
                    'EXEC dbo.AddOrUpdUsuarioAdminDAsp ?, ?, ?, ?, ?',
                    (int(existing_id), nomina, email, int(id_perfil), acceso),
                )
            except Exception as exc:
                if _is_missing_stored_procedure_error(exc):
                    logger.warning('UserAdmin: SP AddOrUpdUsuarioAdminDAsp no existe todavía; usando SQL directo.')
                    cur.execute(
                        'UPDATE dbo.Usuarios SET '
                        '  IdPerfil = ?, '
                        '  IdAcceso = ?, '
                        '  NoNomina = COALESCE(?, NoNomina), '
                        '  Correo   = COALESCE(?, Correo), '
                        '  Activo   = 1, '
                        '  FechaUpd = GETDATE() '
                        'WHERE IdUsuario = ?',
                        (int(id_perfil), acceso, nomina, email, int(existing_id)),
                    )
                else:
                    raise
            conn.commit()
            logger.info('UserAdmin: usuario actualizado (IdUsuario=%s, id_acceso=%s).',
                        existing_id, acceso)
            # Fase 2: planta inicial automática (solo vía pública; no fatal).
            if not system:
                _ensure_planta_inicial_safe(existing_id, nomina, email)
            return existing_id, False

        # Insertar nuevo vía SP (fallback: INSERT con OUTPUT INSERTED.IdUsuario directo).
        new_id = 0
        try:
            cur.execute(
                'EXEC dbo.AddOrUpdUsuarioAdminDAsp ?, ?, ?, ?, ?',
                (None, nomina, email, int(id_perfil), acceso),
            )
            row = cur.fetchone()
            new_id = int(row[0]) if (row and row[0] is not None) else 0
        except Exception as exc:
            if _is_missing_stored_procedure_error(exc):
                logger.warning('UserAdmin: SP AddOrUpdUsuarioAdminDAsp no existe todavía; usando SQL directo.')
                cur.execute(
                    'INSERT INTO dbo.Usuarios (IdPerfil, NoNomina, Correo, IdAcceso, Activo, FechaAdd, FechaUpd) '
                    'OUTPUT INSERTED.IdUsuario '
                    'VALUES (?, ?, ?, ?, 1, GETDATE(), GETDATE())',
                    (int(id_perfil), nomina, email, acceso),
                )
                row = cur.fetchone()
                new_id = int(row[0]) if (row and row[0] is not None) else 0
            else:
                raise
        conn.commit()
        logger.info('UserAdmin: usuario creado (IdUsuario=%s).', new_id)
        # Fase 2: planta inicial automática (solo vía pública; no fatal).
        if not system and new_id:
            _ensure_planta_inicial_safe(new_id, nomina, email)
        return new_id, True

    except Exception:
        _safe_rollback(conn)
        logger.exception('UserAdmin: error en upsert_user — rollback aplicado.')
        return 0, False
    finally:
        _safe_close(conn)


def update_user_profile(id_usuario: int, id_perfil: int, id_acceso=None,
                         actor_id_perfil=None, system: bool = False) -> bool:
    """
    Cambia el perfil de un usuario existente y, opcionalmente, su id_acceso.
    Actualiza FechaUpd. Si id_acceso es None, no toca esa columna.
    """
    if not _is_enabled() or not id_usuario or not id_perfil:
        return False
    # Jerarquía (FAIL-CLOSED en la vía pública): modificar al usuario objetivo y
    # asignar el perfil pedido. system=True es la única vía interna que omite.
    if not system and (
        not can_actor_modify_user(actor_id_perfil, id_usuario)
        or not can_actor_assign_profile(actor_id_perfil, id_perfil)
    ):
        logger.warning('UserAdmin: actor sin permiso para cambiar el perfil del usuario — abortado.')
        return False
    # @IdAcceso NULL → el SP/SQL solo actualiza IdPerfil (no toca IdAcceso), igual que hoy.
    acceso_param = (_normaliza_id_acceso(id_acceso)
                    if (id_acceso is not None and str(id_acceso).strip() != '') else None)

    conn = None
    try:
        from supplyhub.connectors.dataanalytics_connection import get_dataanalytics_conn
        conn = get_dataanalytics_conn()
        cur = conn.cursor()
        # Escritura vía SP (fallback temporal: UPDATE directo de dos variantes).
        try:
            cur.execute(
                'EXEC dbo.UpdUsuarioPerfilAccesoAdminDAsp ?, ?, ?',
                (int(id_usuario), int(id_perfil), acceso_param),
            )
        except Exception as exc:
            if _is_missing_stored_procedure_error(exc):
                logger.warning('UserAdmin: SP UpdUsuarioPerfilAccesoAdminDAsp no existe todavía; usando SQL directo.')
                if acceso_param is None:
                    cur.execute(
                        'UPDATE dbo.Usuarios SET IdPerfil = ?, FechaUpd = GETDATE() '
                        'WHERE IdUsuario = ?',
                        (int(id_perfil), int(id_usuario)),
                    )
                else:
                    cur.execute(
                        'UPDATE dbo.Usuarios SET IdPerfil = ?, IdAcceso = ?, FechaUpd = GETDATE() '
                        'WHERE IdUsuario = ?',
                        (int(id_perfil), acceso_param, int(id_usuario)),
                    )
            else:
                raise
        conn.commit()
        logger.info('UserAdmin: perfil actualizado (IdUsuario=%s, IdPerfil=%s, id_acceso=%s).',
                    id_usuario, id_perfil, id_acceso)
        return True
    except Exception:
        _safe_rollback(conn)
        logger.exception('UserAdmin: error en update_user_profile — rollback aplicado.')
        return False
    finally:
        _safe_close(conn)


def set_user_active(id_usuario: int, active: bool, actor_id_perfil=None,
                    system: bool = False) -> bool:
    """Activa o desactiva un usuario. Actualiza FechaUpd."""
    if not _is_enabled() or not id_usuario:
        return False
    # Jerarquía (FAIL-CLOSED en la vía pública): Administrador no puede
    # activar/desactivar usuarios TI. system=True es la única vía interna.
    if not system and not can_actor_modify_user(actor_id_perfil, id_usuario):
        logger.warning('UserAdmin: actor sin permiso para (des)activar al usuario — abortado.')
        return False
    activo_bit = 1 if active else 0
    conn = None
    try:
        from supplyhub.connectors.dataanalytics_connection import get_dataanalytics_conn
        conn = get_dataanalytics_conn()
        cur = conn.cursor()
        # Escritura vía SP (fallback temporal: UPDATE Activo directo).
        try:
            cur.execute(
                'EXEC dbo.UpdUsuarioActivoAdminDAsp ?, ?',
                (int(id_usuario), activo_bit),
            )
        except Exception as exc:
            if _is_missing_stored_procedure_error(exc):
                logger.warning('UserAdmin: SP UpdUsuarioActivoAdminDAsp no existe todavía; usando SQL directo.')
                cur.execute(
                    'UPDATE dbo.Usuarios SET Activo = ?, FechaUpd = GETDATE() '
                    'WHERE IdUsuario = ?',
                    (activo_bit, int(id_usuario)),
                )
            else:
                raise
        conn.commit()
        logger.info('UserAdmin: usuario %s (IdUsuario=%s).',
                    'activado' if active else 'desactivado', id_usuario)
        return True
    except Exception:
        _safe_rollback(conn)
        logger.exception('UserAdmin: error en set_user_active — rollback aplicado.')
        return False
    finally:
        _safe_close(conn)


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _fetch_sso_worker(no_nomina: str) -> dict | None:
    """Reutiliza el servicio de payroll para traer datos del trabajador por nómina."""
    try:
        from supplyhub.connectors.payroll_connection import get_payroll_worker_data
        return get_payroll_worker_data(no_nomina)
    except Exception:
        logger.exception('UserAdmin: error al consultar SSO worker data.')
        return None


def _row_to_user(row) -> dict:
    """
    Convierte una fila a dict de usuario.
    Columnas: IdUsuario, NoNomina, Correo, IdPerfil, Perfil, Activo, FechaAdd, FechaUpd,
              [id_acceso, acceso]. Las dos últimas son tolerantes (compat. hacia atrás).
    """
    def _s(v):
        return str(v).strip() if v is not None else ''
    n = len(row)
    return {
        'id_usuario': int(row[0]) if row[0] is not None else 0,
        'no_nomina':  _s(row[1]),
        'correo':     _s(row[2]),
        'id_perfil':  int(row[3]) if row[3] is not None else 0,
        'perfil':     _s(row[4]),
        'activo':     bool(row[5]),
        'fecha_add':  _s(row[6]),
        'fecha_upd':  _s(row[7]),
        'id_acceso':  int(row[8]) if (n > 8 and row[8] is not None) else _DEFAULT_ID_ACCESO,
        'acceso':     _s(row[9]) if n > 9 else '',
    }


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
