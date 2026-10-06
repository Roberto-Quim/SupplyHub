from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


class FoundationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="devuser",
            password="StrongPass123!",
        )

    def test_hub_requiere_login(self):
        response = self.client.get(reverse("supplyhub:hub_index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    @override_settings(SUPPLYHUB_LOCAL_AUTH_ENABLED=True)
    def test_login_local_y_hub(self):
        response = self.client.post(
            reverse("login"),
            {"username": "devuser", "password": "StrongPass123!"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fundación MVC y autenticación base listas")
        self.assertEqual(self.client.session.get("sh_identity_source"), "local-dev")

    def test_login_renderiza(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SupplyHub")
