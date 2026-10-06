from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .dataanalytics_permissions_service import can_access_route


def supplyhub_route_required(route: str):
    """Guard backend. Con DataAnalytics activo falla cerrado."""
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            id_perfil = int(request.session.get("sh_id_perfil", 0) or 0)
            if not can_access_route(id_perfil, route):
                raise PermissionDenied("No tienes permiso para este módulo de SupplyHub.")
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
