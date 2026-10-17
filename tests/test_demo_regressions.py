from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from supplyhub.models import OrdenCompra, LineaOC, HistorialSeguimiento

@override_settings(DEBUG=True, SUPPLYHUB_LOCAL_AUTH_ENABLED=True, DATAANALYTICS_ENABLED=False, SUPPLYHUB_REVALIDATE_SESSION=False)
class DemoRegressionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username='audit', password='synthetic-test-only')
        self.client.force_login(self.user)
        self.order = OrdenCompra.objects.create(numero_oc='AUDIT', proveedor='Synthetic', planta_original='IRA', planta_normalizada='MAQ_RA')
        self.line = LineaOC.objects.create(orden=self.order, numero_linea='1', codigo_articulo='A', descripcion='Synthetic', cantidad_solicitada=1, stock=None)
        self.detail = reverse('supplyhub:seguimiento_oc_detalle', args=[self.order.pk])

    def test_detail_with_history_and_nullable_stock(self):
        HistorialSeguimiento.objects.create(linea=self.line, respuesta_proveedor='Synthetic', usuario_responsable='audit')
        self.assertContains(self.client.get(self.detail), 'Synthetic')

    def test_supplier_email_follow_redirect(self):
        response = self.client.post(reverse('supplyhub:gmail_supplier_email', args=[self.line.pk]), {'email':'supplier@example.com'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.line.refresh_from_db()
        self.assertEqual(self.line.correo_proveedor, 'supplier@example.com')

    def test_admin_source_failure_remains_available(self):
        with patch('supplyhub.services.administracion_service.catalog', side_effect=RuntimeError('synthetic source failure')):
            for kind in ['usuarios', 'perfiles', 'modulos']:
                with self.subTest(kind=kind):
                    response = self.client.get(reverse('supplyhub:admin_'+kind))
                    self.assertContains(response, 'La fuente de datos no está disponible.')

    def test_tracking_rejects_unsupported_method(self):
        self.assertEqual(self.client.delete(self.detail).status_code, 405)

    def test_supplier_email_non_ascii_invalid_is_validation_error(self):
        response = self.client.post(reverse('supplyhub:gmail_supplier_email', args=[self.line.pk]), {'email':'not-an-email'}, follow=True)
        self.assertContains(response, 'Ingresa un correo externo válido')

    def test_oauth_malformed_state_is_rejected(self):
        import time
        session = self.client.session
        session['gmail_oauth'] = {'state':'synthetic', 'at':time.time(), 'user':self.user.pk}
        session.save()
        with patch('supplyhub.services.gmail_service.connect') as connect:
            response = self.client.get(reverse('supplyhub:gmail_callback'), {'state':'ñ', 'code':'synthetic'})
        self.assertRedirects(response, reverse('supplyhub:gmail_index'))
        connect.assert_not_called()
