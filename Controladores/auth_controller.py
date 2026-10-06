"""Controlador de autenticación de SupplyHub."""
from __future__ import annotations

import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.backends import ModelBackend
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from supplyhub.services.dataanalytics_access_service import (
    DENIED_MESSAGE,
    METODO_AD,
    METODO_NOMINA,
    TIPO_CORREO,
    TIPO_NOMINA,
    authorize_and_log,
    clear_session_identity,
    normalize_payroll,
    store_session_identity,
)

logger = logging.getLogger("supplyhub")


def _safe_next(request: HttpRequest) -> str:
    candidate = request.POST.get("next") or request.GET.get("next") or ""
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return reverse("supplyhub:hub_index")


def main_login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(_safe_next(request))

    if request.method == "POST":
        if not settings.SUPPLYHUB_LOCAL_AUTH_ENABLED:
            messages.error(request, "El acceso local está deshabilitado.")
            return redirect("login")

        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        user = ModelBackend().authenticate(request, username=username, password=password)
        if user is None:
            messages.error(request, "Usuario o contraseña incorrectos.")
        else:
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            store_session_identity(
                request.session,
                id_usuario=0,
                id_perfil=0,
                metodo_acceso=0,
                no_nomina="",
                correo=(user.email or "").strip().lower(),
                display_name=(user.get_full_name() or user.get_username()).strip(),
                source="local-dev",
                django_username=user.get_username(),
            )
            return redirect(_safe_next(request))

    return render(
        request,
        "auth/login.html",
        {
            "next": _safe_next(request),
            "local_auth_enabled": settings.SUPPLYHUB_LOCAL_AUTH_ENABLED,
            "google_enabled": settings.GOOGLE_OAUTH_ENABLED,
            "google_configured": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
            "ad_enabled": settings.AD_LDAP_ENABLED,
            "payroll_enabled": settings.PAYROLL_AUTH_ENABLED,
            "dataanalytics_enabled": settings.DATAANALYTICS_ENABLED,
        },
    )


def active_directory_login_view(request: HttpRequest) -> HttpResponse:
    if not settings.AD_LDAP_ENABLED:
        messages.error(request, "Active Directory no está habilitado en este ambiente.")
        return redirect("login")

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        user = authenticate(request, username=username, password=password)
        if user is None:
            messages.error(request, "No fue posible autenticar con Active Directory.")
            return render(request, "auth/ad_login.html")

        employee_number = normalize_payroll(
            getattr(user, "_supplyhub_employee_number", "")
        )
        correo = (user.email or "").strip().lower()
        tipo = TIPO_NOMINA if employee_number else TIPO_CORREO
        allowed, id_usuario, id_perfil = authorize_and_log(
            tipo,
            no_nomina=employee_number or None,
            correo=correo or None,
            metodo_acceso=METODO_AD,
        )
        if not allowed:
            messages.error(request, DENIED_MESSAGE)
            return redirect("login")

        # Si AD obtuvo nómina, también se usa como username corporativo.
        if employee_number and user.username != employee_number:
            user.username = employee_number
            user.save(update_fields=["username"])

        login(
            request,
            user,
            backend="supplyhub.authentication_login.active_directory_backend.ActiveDirectoryLDAPBackend",
        )
        store_session_identity(
            request.session,
            id_usuario,
            id_perfil,
            metodo_acceso=METODO_AD,
            no_nomina=employee_number,
            correo=correo,
            display_name=(user.get_full_name() or user.get_username()).strip(),
            source="active-directory",
            django_username=user.get_username(),
        )
        return redirect(reverse("supplyhub:hub_index"))

    return render(request, "auth/ad_login.html")


def payroll_login_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST" and not settings.PAYROLL_AUTH_ENABLED:
        messages.error(request, "El acceso por nómina todavía no está configurado en este ambiente.")
        return redirect("supplyhub:payroll_login")

    if request.method == "POST":
        employee_number = normalize_payroll(request.POST.get("employee_number"))
        password = request.POST.get("password") or ""
        user = authenticate(
            request,
            employee_number=employee_number,
            password=password,
        )
        if user is None:
            messages.error(request, "No fue posible autenticar con nómina.")
        else:
            payroll = normalize_payroll(getattr(user, "_supplyhub_payroll", "")) or employee_number
            allowed, id_usuario, id_perfil = authorize_and_log(
                TIPO_NOMINA,
                no_nomina=payroll,
                metodo_acceso=METODO_NOMINA,
            )
            if not allowed:
                messages.error(request, DENIED_MESSAGE)
                return redirect("login")

            login(
                request,
                user,
                backend="supplyhub.authentication_login.payroll_backend.PayrollDatabaseBackend",
            )
            store_session_identity(
                request.session,
                id_usuario,
                id_perfil,
                metodo_acceso=METODO_NOMINA,
                no_nomina=payroll,
                correo=(user.email or "").strip().lower(),
                display_name=(user.get_full_name() or payroll).strip(),
                source="payroll",
                django_username=user.get_username(),
            )
            return redirect(reverse("supplyhub:hub_index"))

    return render(
        request,
        "auth/payroll_login.html",
        {"payroll_enabled": settings.PAYROLL_AUTH_ENABLED},
    )


def logout_view(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    clear_session_identity(request.session)
    logout(request)
    return redirect("login")
