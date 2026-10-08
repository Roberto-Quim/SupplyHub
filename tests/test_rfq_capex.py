from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from supplyhub.models import HistorialDecisionRFQ, HistorialEstadoRFQ, RFQCapex
from supplyhub.services.rfq_capex_service import normalize_plant


@override_settings(SUPPLYHUB_LOCAL_AUTH_ENABLED=True, DATAANALYTICS_ENABLED=False)
class RFQCapexTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="738210",
            password="StrongPass123!",
        )
        self.client.post(
            reverse("login"),
            {"username": "738210", "password": "StrongPass123!"},
        )

    def _create(self):
        return self.client.post(
            reverse("supplyhub:rfq_capex_create"),
            {
                "rfq": "#228",
                "descripcion": "Equipo de prueba",
                "fecha_arranque": "2026-10-06",
                "solicitante": "Usuario Prueba",
                "correo_solicitante": "usuario@empresa.com",
                "planta": "MAQ_RA",
                "clave_capex": "CAPEX-001",
                "tipo_capex": "Equipo",
            },
            follow=True,
        )

    def test_normalizacion_plantas_conocidas(self):
        self.assertEqual(normalize_plant("Tenango"), "MACIMEX_TENANGO")
        self.assertEqual(normalize_plant("Questum Macimex Tenango"), "MACIMEX_TENANGO")
        self.assertEqual(normalize_plant("MAQ RA"), "MAQ_RA")
        self.assertEqual(normalize_plant("Maquinados Ramos"), "MAQ_RA")

    def test_crear_rfq_usa_pedido_y_genera_historial(self):
        response = self._create()
        self.assertEqual(response.status_code, 200)

        rfq = RFQCapex.objects.get()
        self.assertEqual(rfq.rfq, "228")
        self.assertEqual(rfq.creado_por, "738210")
        self.assertEqual(rfq.estado, RFQCapex.Estado.SOLICITADA)
        self.assertEqual(
            rfq.decision_seguimiento,
            RFQCapex.Decision.PENDIENTE,
        )
        self.assertEqual(HistorialEstadoRFQ.objects.count(), 1)
        self.assertEqual(HistorialDecisionRFQ.objects.count(), 1)

    def test_cambio_estado_es_append_only(self):
        self._create()
        rfq = RFQCapex.objects.get()

        response = self.client.post(
            reverse("supplyhub:rfq_capex_status", args=[rfq.pk]),
            {"estado": "COTIZACION", "comentario": "Luis indicó cotizar."},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        rfq.refresh_from_db()
        self.assertEqual(rfq.estado, "COTIZACION")
        self.assertEqual(HistorialEstadoRFQ.objects.count(), 2)

    def test_decision_seguimiento_se_audita(self):
        self._create()
        rfq = RFQCapex.objects.get()

        self.client.post(
            reverse("supplyhub:rfq_capex_decision", args=[rfq.pk]),
            {"decision": "COTIZAR", "motivo": "Confirmado por Luis."},
        )
        rfq.refresh_from_db()
        self.assertEqual(rfq.decision_seguimiento, "COTIZAR")
        self.assertEqual(HistorialDecisionRFQ.objects.count(), 2)

    def test_listado_rfqs_abre(self):
        self._create()
        response = self.client.get(reverse("supplyhub:rfq_capex"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "RFQ / CAPEX")
        self.assertContains(response, "#228")
