"""Autenticación Active Directory mediante ldap3/LDAPS.

No usa cuenta de servicio: realiza bind con las credenciales del usuario. La
contraseña no se guarda en Django ni se registra en logs.
"""
from __future__ import annotations

import logging
import ssl

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend

logger = logging.getLogger("supplyhub")
User = get_user_model()

_EMPLOYEE_NUMBER_CANDIDATES = (
    "initials",
    "employeeID",
    "employeeNumber",
    "extensionAttribute1",
    "extensionAttribute2",
    "extensionAttribute3",
    "extensionAttribute4",
    "extensionAttribute5",
)


def _parse_server_uri(uri: str) -> tuple[str, int, bool]:
    if uri.startswith("ldaps://"):
        use_ssl, rest = True, uri[8:]
    elif uri.startswith("ldap://"):
        use_ssl, rest = False, uri[7:]
    else:
        return uri, 389, False
    if ":" in rest:
        host, raw_port = rest.rsplit(":", 1)
        try:
            return host, int(raw_port), use_ssl
        except ValueError:
            pass
    return rest, (636 if use_ssl else 389), use_ssl


def _normalize_username(raw: str, domain: str) -> tuple[str, str]:
    raw = raw.strip()
    if "\\" in raw:
        _, sam = raw.split("\\", 1)
        return sam.lower(), raw
    if "@" in raw:
        sam = raw.split("@", 1)[0]
        return sam.lower(), f"{domain}\\{sam}"
    return raw.lower(), f"{domain}\\{raw}"


def _value(entry, name: str) -> str:
    try:
        attr = getattr(entry, name, None)
        if attr is None:
            return ""
        val = getattr(attr, "value", attr)
        if val is None:
            return ""
        return str(val).strip()
    except Exception:
        return ""


class ActiveDirectoryLDAPBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not settings.AD_LDAP_ENABLED or not username or not password:
            return None

        server_uri = settings.AD_LDAP_SERVER_URI.strip()
        domain = settings.AD_LDAP_DOMAIN.strip()
        base_dn = settings.AD_LDAP_USER_SEARCH_BASE_DN.strip()
        filter_tpl = settings.AD_LDAP_USER_SEARCH_FILTER.strip()
        if not server_uri or not domain or not base_dn:
            logger.error("Configuración AD incompleta.")
            return None

        try:
            import ldap3

            sam, bind_user = _normalize_username(username, domain)
            host, port, uri_ssl = _parse_server_uri(server_uri)
            use_ssl = settings.AD_LDAP_USE_SSL or uri_ssl
            tls = None
            if use_ssl or settings.AD_LDAP_START_TLS:
                validate = ssl.CERT_REQUIRED if settings.AD_LDAP_TLS_VALIDATE == "required" else ssl.CERT_NONE
                tls = ldap3.Tls(validate=validate)

            server = ldap3.Server(host, port=port, use_ssl=use_ssl, tls=tls, get_info=ldap3.NONE)
            auto_bind = (
                ldap3.AUTO_BIND_TLS_BEFORE_BIND
                if settings.AD_LDAP_START_TLS and not use_ssl
                else True
            )
            conn = ldap3.Connection(
                server,
                user=bind_user,
                password=password,
                auto_bind=auto_bind,
                raise_exceptions=True,
            )

            attrs = [
                "givenName", "sn", "mail", "displayName", "sAMAccountName",
                "userPrincipalName", *_EMPLOYEE_NUMBER_CANDIDATES,
            ]
            search_filter = filter_tpl.replace("{username}", sam)
            conn.search(base_dn, search_filter, attributes=attrs)
            entry = conn.entries[0] if conn.entries else None
            values = {name: _value(entry, name) for name in attrs} if entry is not None else {}
            try:
                conn.unbind()
            except Exception:
                pass

            user, _ = User.objects.get_or_create(username=sam)
            user.set_unusable_password()
            user.is_active = True
            user.email = values.get("mail") or user.email
            user.first_name = values.get("givenName") or user.first_name
            user.last_name = values.get("sn") or user.last_name
            user.save()

            for key in _EMPLOYEE_NUMBER_CANDIDATES:
                if values.get(key):
                    user._supplyhub_employee_number = values[key]
                    break
            return user
        except Exception:
            # No imprimir usuario ni password; el detalle técnico sí queda en traceback.
            logger.exception("Error de autenticación Active Directory; identidad omitida.")
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
