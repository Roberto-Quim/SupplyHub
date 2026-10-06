from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from supplyhub.authentication_login.payroll_backend import PayrollDatabaseBackend
from supplyhub.services.dataanalytics_access_service import store_session_identity
from supplyhub.services.menu_service import build_menu


class IdentityRuleTests(TestCase):
    @override_settings(PAYROLL_AUTH_ENABLED=True)
    @patch(
        "supplyhub.authentication_login.payroll_backend.get_payroll_worker_data",
        return_value={"Correo": "persona@empresa.com", "Nombre": "Persona"},
    )
    @patch(
        "supplyhub.authentication_login.payroll_backend.validate_payroll_login",
        return_value="12345",
    )
    def test_payroll_es_username_django(self, _validate, _worker):
        user = PayrollDatabaseBackend().authenticate(
            None, employee_number="12345", password="secreto"
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "12345")

    def test_session_usuario_prioriza_nomina(self):
        session = {}
        store_session_identity(
            session,
            id_usuario=12345,
            id_perfil=2,
            metodo_acceso=3,
            no_nomina="12345",
            correo="persona@empresa.com",
            source="payroll",
        )
        self.assertEqual(session["sh_usuario"], "12345")
        self.assertEqual(session["sh_no_nomina"], "12345")


class Step3MenuTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="devuser", password="StrongPass123!"
        )

    @override_settings(DATAANALYTICS_ENABLED=False)
    def test_menu_local_incluye_hub_y_administracion(self):
        menu = build_menu(0)
        self.assertEqual([item["label"] for item in menu], ["HUB", "Administración"])

    @override_settings(SUPPLYHUB_LOCAL_AUTH_ENABLED=True, DATAANALYTICS_ENABLED=False)
    def test_rutas_step3_abren_en_modo_local(self):
        self.client.post(
            reverse("login"),
            {"username": "devuser", "password": "StrongPass123!"},
        )
        self.assertEqual(self.client.get(reverse("supplyhub:rfq_capex")).status_code, 200)
        self.assertEqual(self.client.get(reverse("supplyhub:admin_usuarios")).status_code, 200)

    def test_login_muestra_metodos_corporativos(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "Continuar con Google")
        self.assertContains(response, "Ingresar con nómina")
