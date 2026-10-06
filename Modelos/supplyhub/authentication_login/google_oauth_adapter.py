"""Adaptador Google OAuth corporativo para SupplyHub."""
from __future__ import annotations

import logging
import re

from django.conf import settings
from django.shortcuts import redirect

from supplyhub.services.dataanalytics_access_service import (
    METODO_CORREO,
    TIPO_CORREO,
    authorize_and_log,
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

    def pre_social_login(self, request, sociallogin):
        try:
            from allauth.core.exceptions import ImmediateHttpResponse
        except ImportError:
            from allauth.exceptions import ImmediateHttpResponse

        email = ""
        if sociallogin.account.extra_data:
            email = (sociallogin.account.extra_data.get("email") or "").strip().lower()

        domain = settings.GOOGLE_ALLOWED_DOMAIN.strip().lower()
        if domain and (not email or email.split("@")[-1] != domain):
            logger.warning("Google OAuth rechazado por dominio corporativo.")
            raise ImmediateHttpResponse(redirect(settings.LOGIN_URL))

        if not sociallogin.is_existing and email:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                existing = User.objects.get(email__iexact=email)
                sociallogin.connect(request, existing)
            except (User.DoesNotExist, User.MultipleObjectsReturned):
                pass

        allowed, id_usuario, id_perfil = authorize_and_log(
            TIPO_CORREO,
            correo=email or None,
            metodo_acceso=METODO_CORREO,
        )
        if not allowed:
            logger.warning("Google OAuth autenticó identidad pero DataAnalytics negó acceso.")
            raise ImmediateHttpResponse(redirect(settings.LOGIN_URL))

        guser = getattr(sociallogin, "user", None)
        display = (guser.get_full_name() if guser else "") or email
        store_session_identity(
            request.session,
            id_usuario,
            id_perfil,
            metodo_acceso=METODO_CORREO,
            correo=email,
            display_name=display,
            source="google",
        )


DomainRestrictedSocialAccountAdapter = CorporateGoogleSocialAccountAdapter
