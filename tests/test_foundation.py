from django.test import SimpleTestCase
from django.urls import reverse


class FoundationTests(SimpleTestCase):
    def test_hub_index_responde(self):
        response = self.client.get(reverse("supplyhub:hub_index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SupplyHub")
