"""Administración de asignaciones persona + método + perfil en dbo.Usuarios.

Cada alta crea una fila independiente. Duplicados del mismo método se rechazan;
la edición apunta a IdUsuario. El SP 028 serializa escrituras y valida colisiones.
"""
import logging
from supplyhub.services.da_admin import dataanalytics_user_admin_service as users

logger = logging.getLogger('supplyhub')


def _save(id_usuario, no_nomina, correo, id_perfil, id_acceso, actor_id_perfil):
    if not users._is_enabled():
        return 0, 'DataAnalytics no está habilitado.'
    try:
        profile, method = int(id_perfil), int(id_acceso)
    except (TypeError, ValueError):
        return 0, 'Selecciona un perfil y un método válidos.'
    if profile <= 0 or method not in (1, 2, 3):
        return 0, 'Selecciona un perfil y un método válidos.'
    if not users.can_actor_assign_profile(actor_id_perfil, profile):
        return 0, 'No tienes permiso para asignar ese perfil.'
    if id_usuario and not users.can_actor_modify_user(actor_id_perfil, id_usuario):
        return 0, 'No tienes permiso para modificar esta asignación.'
    nom = (no_nomina or '').strip() or None
    email = (correo or '').strip() or None
    if id_usuario:
        actual = users.get_user_by_id(id_usuario)
        if not actual:
            return 0, 'No se encontró la asignación.'
        nom, email = actual.get('no_nomina') or None, actual.get('correo') or None
    error = users.acceso_validacion_error(method, nom, email)
    if error:
        return 0, error
    if (nom and len(nom) > 10) or (email and (len(email) > 200 or not users.is_valid_email(email))):
        return 0, 'Revisa la nómina (máximo 10 caracteres) y el correo (máximo 200).'
    conn = None
    try:
        from supplyhub.connectors.dataanalytics_connection import get_dataanalytics_conn
        conn = get_dataanalytics_conn()
        cur = conn.cursor()
        cur.execute('EXEC dbo.GuardarUsuarioMetodoAdminDAsp ?, ?, ?, ?, ?, ?',
                    (id_usuario, nom, email, profile, method, int(actor_id_perfil)))
        row = cur.fetchone()
        if not row or not row[0]:
            raise RuntimeError('Sin IdUsuario de resultado')
        saved = int(row[0])
        conn.commit()
        if not id_usuario:
            users._ensure_planta_inicial_safe(saved, nom, email)
        return saved, ''
    except Exception as exc:
        users._safe_rollback(conn)
        logger.exception('No se pudo guardar la asignación de ingreso.')
        if '51012' in str(exc):
            return 0, 'Ya existe una asignación para esa persona y método. Edita la fila existente.'
        if users._is_missing_stored_procedure_error(exc):
            return 0, 'Falta instalar el script 028 de asignaciones por método en DataAnalytics.'
        return 0, 'No se pudo guardar. Revisa datos, permisos y conexión.'
    finally:
        users._safe_close(conn)


def create_assignment(no_nomina, correo, id_perfil, id_acceso, actor_id_perfil=None):
    return _save(None, no_nomina, correo, id_perfil, id_acceso, actor_id_perfil)


def update_assignment(id_usuario, id_perfil, id_acceso, actor_id_perfil=None):
    return _save(int(id_usuario), None, None, id_perfil, id_acceso, actor_id_perfil)
