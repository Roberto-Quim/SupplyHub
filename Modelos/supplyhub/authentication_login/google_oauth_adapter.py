"""Adaptador Google OAuth corporativo para SupplyHub.

Google prueba la identidad por correo. DataAnalytics resuelve ese correo hacia
IdUsuario/IdPerfil; en SupplyHub, IdUsuario se usa como nómina/username
corporativo cuando la integración está activa.
"""
from __future__ import annotations

import logging
import re

from django.conf import settings
from django.shortcuts import redirect

from supplyhub.services.dataanalytics_access_service import (
    METODO_CORREO,
    TIPO_CORREO,
    authorize_and_log,
    normalize_payroll,
    store_session_identity,
)

logger = logging.getLogger("supplyhub")

try:
    from allauth.socialaccount.adapter import DefaultSocialAccountAdapter as _AdapterBase
except (ImportError, RuntimeError):
    _AdapterBase = object


class CorporateGoogleSocialAccountAdapter(_AdapterBase):
    def is_open_for_signup(self, request, sociallogin):
        return True

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        email = (data.get("email") or "").strip().lower()
        # Fallback solo mientras DataAnalytics aún no ha resuelto la nómina.
        if email and "@" in email:
            base = re.sub(r"[^\w.@+-]", "", email.split("@", 1)[0]).lower()
            if base:
                user.username = self._unique_username(base)
        user.email = user.email or email
        user.first_name = user.first_name or (data.get("first_name") or "")
        user.last_name = user.last_name or (data.get("last_name") or "")
        return user

    @staticmethod
    def _unique_username(base: str) -> str:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if not User.objects.filter(username=base).exists():
            return base
        i = 2
        while User.objects.filter(username=f"{base}{i}").exists():
            i += 1
        return f"{base}{i}"

    @staticmethod
    def _immediate_redirect():
        try:
            from allauth.core.exceptions import ImmediateHttpResponse
        except ImportError:
            from allauth.exceptions import ImmediateHttpResponse
        return ImmediateHttpResponse

    def _bind_to_payroll_user(self, request, sociallogin, payroll: str, email: str):
        """Une Google con la misma cuenta Django cuyo username es la nómina."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        payroll = normalize_payroll(payroll)
        if not payroll:
            return getattr(sociallogin, "user", None)

        payroll_user = User.objects.filter(username=payroll).first()
        email_user = User.objects.filter(email__iexact=email).first() if email else None

        if payroll_user is not None:
            if not sociallogin.is_existing:
                sociallogin.connect(request, payroll_user)
            return payroll_user

        if email_user is not None:
            email_user.username = payroll
            email_user.save(update_fields=["username"])
            if not sociallogin.is_existing:
                sociallogin.connect(request, email_user)
            return email_user

        google_user = getattr(sociallogin, "user", None)
        if google_user is not None:
            google_user.username = payroll
        return google_user

    def pre_social_login(self, request, sociallogin):
        ImmediateHttpResponse = self._immediate_redirect()

        extra = sociallogin.account.extra_data or {}
        email = (extra.get("email") or "").strip().lower()
        verified = extra.get("verified_email", True)
        if not verified:
            logger.warning("Google OAuth rechazado: correo no verificado.")
            raise ImmediateHttpResponse(redirect(settings.LOGIN_URL))

        domain = settings.GOOGLE_ALLOWED_DOMAIN.strip().lower()
        if domain and (not email or email.split("@")[-1] != domain):
            logger.warning("Google OAuth rechazado por dominio corporativo.")
            raise ImmediateHttpResponse(redirect(settings.LOGIN_URL))

        allowed, id_usuario, id_perfil = authorize_and_log(
            TIPO_CORREO,
            correo=email or None,
            metodo_acceso=METODO_CORREO,
        )
        if not allowed:
            logger.warning("Google OAuth autenticó identidad pero DataAnalytics negó acceso.")
            raise ImmediateHttpResponse(redirect(settings.LOGIN_URL))

        # Regla corporativa: DataAnalytics.IdUsuario corresponde a la nómina.
        payroll = normalize_payroll(id_usuario) if settings.DATAANALYTICS_ENABLED else ""
        user = self._bind_to_payroll_user(request, sociallogin, payroll, email)

        # Sin DataAnalytics (solo pruebas OAuth locales), evita duplicar por correo.
        if not payroll and not sociallogin.is_existing and email:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                existing = User.objects.get(email__iexact=email)
                sociallogin.connect(request, existing)
                user = existing
            except (User.DoesNotExist, User.MultipleObjectsReturned):
                pass

        display = ""
        if user is not None:
            display = (user.get_full_name() or "").strip()
        display = display or email or payroll

        store_session_identity(
            request.session,
            id_usuario,
            id_perfil,
            metodo_acceso=METODO_CORREO,
            no_nomina=payroll,
            correo=email,
            display_name=display,
            source="google",
            django_username=getattr(user, "username", "") if user else "",
        )


DomainRestrictedSocialAccountAdapter = CorporateGoogleSocialAccountAdapter
