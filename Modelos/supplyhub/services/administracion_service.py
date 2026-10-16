"""Administración central DataAnalytics; almacenamiento Dev solo en desarrollo explícito."""
from contextlib import contextmanager
from functools import wraps
from uuid import uuid4
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from supplyhub.models import DevPerfil, DevModulo, DevAsignacion, AuditoriaAdministracion, ErrorLog
from .dataanalytics_permissions_service import can_access_route
from .da_admin import dataanalytics_user_admin_service as users
from .da_admin import dataanalytics_perfiles_service as profiles
from .da_admin import dataanalytics_modulos_service as modules
from .da_admin import dataanalytics_usuario_metodos_service as assignments

METHODS = {1: 'Google', 2: 'Directorio Activo', 3: 'Nómina'}
PROTECTED_ROUTES = frozenset(['/administracion/supplier-sites/', '/administracion/usuarios/', '/administracion/perfiles/', '/administracion/modulos/', '/administracion/error-logs/'])


def local_demo():
    return bool(settings.DEBUG and settings.SUPPLYHUB_LOCAL_AUTH_ENABLED and not settings.DATAANALYTICS_ENABLED)


def actor_profile(request):
    try:
        return int(request.session.get('sh_id_perfil', 0))
    except (ValueError, TypeError):
        return 0


def may_manage(request, route, ti_only=False):
    if not request.user.is_authenticated:
        return False
    if not settings.DATAANALYTICS_ENABLED:
        return local_demo() and request.user.is_superuser
    profile = actor_profile(request)
    allowed = users.is_ti_profile(profile) if ti_only else users.profile_can_manage(profile)
    return allowed and can_access_route(profile, route)


def admin_required(route, ti_only=False):
    def decorate(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not may_manage(request, route, ti_only):
                raise PermissionDenied('Se requiere perfil TI.' if ti_only else 'Se requiere perfil TI o Administrador y permiso del submódulo.')
            return view(request, *args, **kwargs)
        return wrapped
    return decorate


@contextmanager
def central_connection():
    from supplyhub.connectors.dataanalytics_connection import get_dataanalytics_conn
    conn = get_dataanalytics_conn()
    try:
        yield conn
    finally:
        conn.close()


def check_connection():
    if settings.DATAANALYTICS_ENABLED:
        with central_connection() as conn:
            conn.cursor().execute('SELECT 1').fetchone()


def audit(request, entity, identifier, action):
    try:
        AuditoriaAdministracion.objects.create(actor=request.user.get_username(), entidad=entity, identificador=str(identifier), accion=action)
    except Exception:
        # La escritura central puede estar confirmada; no inducir al usuario a repetirla.
        logging.getLogger('supplyhub').error('Auditoría administrativa pendiente: actor=%s entidad=%s id=%s acción=%s', request.user.get_username(), entity, identifier, action)


def record_error(origin, request=None):
    """Solo metadatos controlados: nunca cuerpo, query string, tokens ni excepción SQL."""
    try:
        return ErrorLog.objects.create(referencia=uuid4(), origen=origin[:120], mensaje='La operación no se pudo completar.',
            ruta=(getattr(getattr(request, 'resolver_match', None), 'route', '') or '')[:200], usuario=(request.user.get_username() if request and request.user.is_authenticated else '')[:100])
    except Exception:
        return None


def catalog(kind):
    if settings.DATAANALYTICS_ENABLED:
        check_connection()
        if kind == 'usuarios':
            return [dict(id=x['id_usuario'], nomina=x['no_nomina'], correo=x['correo'], perfil=x['perfil'], perfil_id=x['id_perfil'], metodo=x['id_acceso'], metodo_nombre=METHODS.get(x['id_acceso'], 'Desconocido'), activo=x['activo']) for x in users.list_users()]
        if kind == 'perfiles':
            return [dict(id=x['id_perfil'], nombre=x['perfil'], activo=x['activo'], total=x['num_submodulos']) for x in profiles.list_profiles_full()]
        if kind == 'modulos':
            return [dict(id=x['id_submodulo'], nombre=x['submodulo'], grupo=x['modulo'], padre_id=x['id_modulo'], ruta=x['ruta'], orden=x['orden'], activo=x['activo']) for x in modules.list_submodulos()]
    if not local_demo():
        raise PermissionDenied('DataAnalytics debe estar habilitado.')
    if kind == 'usuarios':
        return [dict(id=x.pk, nomina=x.nomina, correo=x.correo, perfil=x.perfil.nombre, perfil_id=x.perfil_id, metodo=x.metodo, metodo_nombre=METHODS[x.metodo], activo=x.activo) for x in DevAsignacion.objects.select_related('perfil').order_by('-pk')]
    if kind == 'perfiles':
        return [dict(id=x.pk, nombre=x.nombre, activo=x.activo, total=x.modulos.filter(activo=True).count()) for x in DevPerfil.objects.prefetch_related('modulos').order_by('nombre')]
    return [dict(id=x.pk, nombre=x.nombre, grupo=x.grupo, ruta=x.ruta, orden=x.orden, activo=x.activo) for x in DevModulo.objects.all()]


def profile_detail(pk):
    if settings.DATAANALYTICS_ENABLED:
        result = profiles.get_profile_with_submodulos(pk)
        if not result:
            raise ValidationError('No se encontró el perfil.')
        return dict(nombre=result['perfil'], modulos=[x['id_submodulo'] for x in result['asignaciones'] if x['activo']])
    obj = DevPerfil.objects.get(pk=pk)
    return dict(nombre=obj.nombre, modulos=list(obj.modulos.values_list('pk', flat=True)))


def _result(result):
    ok, error = result
    if not ok:
        raise ValidationError(error or 'No se pudo completar la operación.')
    return ok


def save_assignment(request, data, pk=None):
    if settings.DATAANALYTICS_ENABLED:
        fn = assignments.update_assignment if pk else assignments.create_assignment
        args = (pk, data['perfil'], data['metodo']) if pk else (data['nomina'], data['correo'], data['perfil'], data['metodo'])
        result = _result(fn(*args, actor_id_perfil=actor_profile(request)))
    else:
        with transaction.atomic():
            obj = DevAsignacion.objects.select_for_update().get(pk=pk) if pk else DevAsignacion()
            if not pk:
                obj.nomina, obj.correo = data['nomina'], data['correo']
            obj.perfil = DevPerfil.objects.get(pk=data['perfil'], activo=True)
            obj.metodo = data['metodo']
            obj.full_clean()
            obj.save()
            result = obj.pk
    audit(request, 'Usuario', pk or result, 'EDITAR' if pk else 'CREAR')
    return result


def save_profile(request, data, pk=None):
    if settings.DATAANALYTICS_ENABLED:
        name = data['nombre'].strip().casefold()
        if name in ['ti', 'admin', 'administrador'] and not users.is_ti_profile(actor_profile(request)):
            raise ValidationError('Solo TI puede administrar perfiles privilegiados.')
        if pk:
            current = profile_detail(pk)
            if current['nombre'].strip().casefold() in ['ti', 'admin', 'administrador'] and name != current['nombre'].strip().casefold():
                raise ValidationError('Los nombres de los perfiles base están protegidos.')
            if pk == actor_profile(request):
                required = {x['id'] for x in catalog('modulos') if x['ruta'] in PROTECTED_ROUTES}
                previous = set(current['modulos']) & required
                if not previous.issubset(set(data['modulos'])):
                    raise ValidationError('No puedes retirar tus propios permisos administrativos.')
        if pk:
            _result(profiles.update_profile(pk, data['nombre'], data['modulos'], actor_id_perfil=actor_profile(request)))
            result = pk
        else:
            result = _result(profiles.create_profile(data['nombre'], data['modulos'], actor_id_perfil=actor_profile(request)))
    else:
        with transaction.atomic():
            obj = DevPerfil.objects.select_for_update().get(pk=pk) if pk else DevPerfil()
            obj.nombre = data['nombre']
            obj.full_clean()
            chosen = DevModulo.objects.filter(pk__in=data['modulos'], activo=True)
            if chosen.count() != len(set(data['modulos'])):
                raise ValidationError('Selecciona submódulos activos.')
            obj.save()
            obj.modulos.set(chosen)
            result = obj.pk
    audit(request, 'Perfil', result, 'EDITAR' if pk else 'CREAR')
    return result


def save_module(request, data, pk=None):
    if pk:
        current = next((x for x in catalog('modulos') if x['id'] == pk), None)
        if not current:
            raise ValidationError('No se encontró el submódulo.')
        if current['ruta'] in PROTECTED_ROUTES and current['ruta'] != data['ruta']:
            raise ValidationError('La ruta administrativa base está protegida.')
    if settings.DATAANALYTICS_ENABLED:
        if pk:
            if current['padre_id'] != data['padre']:
                raise ValidationError('En edición se conserva el módulo padre, como en DataAnalytics.')
            _result(modules.update_submodulo(pk, data['nombre'], data['ruta'], data['orden']))
            result = pk
        else:
            result = _result(modules.create_submodulo(data['padre'], data['nombre'], data['ruta'], data['orden'], actor_id_perfil=actor_profile(request)))
    else:
        obj = DevModulo.objects.get(pk=pk) if pk else DevModulo()
        for field in ['nombre', 'grupo', 'ruta', 'orden']:
            setattr(obj, field, data[field])
        obj.full_clean()
        obj.save()
        result = obj.pk
    audit(request, 'Modulo', result, 'EDITAR' if pk else 'CREAR')
    return result


def set_active(request, kind, pk, active):
    if kind == 'modulos':
        current = next((x for x in catalog(kind) if x['id'] == pk), None)
        if current and current['ruta'] in PROTECTED_ROUTES and not active:
            raise ValidationError('No se puede desactivar un submódulo administrativo base.')
    if settings.DATAANALYTICS_ENABLED:
        if kind == 'usuarios':
            if pk == int(request.session.get('sh_id_usuario', 0) or 0) and not active:
                raise ValidationError('No puedes desactivar tu asignación actual.')
            result = users.set_user_active(pk, active, actor_id_perfil=actor_profile(request))
        elif kind == 'perfiles':
            if pk == actor_profile(request) and not active:
                raise ValidationError('No puedes desactivar tu perfil actual.')
            result = profiles.set_profile_active(pk, active, actor_id_perfil=actor_profile(request))
        else:
            result = modules.set_submodulo_active(pk, active)
        if isinstance(result, tuple):
            _result(result)
        elif not result:
            raise ValidationError('No se pudo cambiar el estado.')
    else:
        model = {'usuarios': DevAsignacion, 'perfiles': DevPerfil, 'modulos': DevModulo}[kind]
        if not model.objects.filter(pk=pk).update(activo=active):
            raise ValidationError('Registro inexistente.')
    audit(request, kind, pk, 'ACTIVAR' if active else 'DESACTIVAR')
