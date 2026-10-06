"""Backend de autenticación por número de nómina.

La contraseña se valida contra la fuente corporativa y nunca se persiste en Django.
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend

from supplyhub.connectors.payroll_connection import (
    get_payroll_worker_data,
    validate_payroll_login,
)

logger = logging.getLogger("supplyhub")
User = get_user_model()
PAYROLL_SESSION_KEY = "payroll_worker"


class PayrollDatabaseBackend(BaseBackend):
    def authenticate(self, request, employee_number=None, password=None, **kwargs):
        if not settings.PAYROLL_AUTH_ENABLED or not employee_number or not password:
            return None

        validated = validate_payroll_login(str(employee_number).strip(), str(password))
        if validated is None:
            logger.info("Login por nómina rechazado.")
            return None

        worker_data = get_payroll_worker_data(validated)
        user, _ = User.objects.get_or_create(username=validated)
        user.set_unusable_password()
        user.is_active = True

        # Solo campos genéricos cuando la fuente los expone con estos nombres.
        email = worker_data.get("Correo") or worker_data.get("Email") or ""
        first = worker_data.get("Nombre") or ""
        last = worker_data.get("Apellidos") or worker_data.get("Apellido") or ""
        if email:
            user.email = str(email).strip()
        if first:
            user.first_name = str(first).strip()
        if last:
            user.last_name = str(last).strip()
        user.save()

        if request is not None and worker_data:
            request.session[PAYROLL_SESSION_KEY] = worker_data
        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
