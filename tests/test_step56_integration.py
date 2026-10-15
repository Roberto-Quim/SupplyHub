from io import BytesIO
from datetime import date
import pandas as pd
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from supplyhub.models import OrdenCompra, LineaOC, HistorialSeguimiento, RFQCapex
from supplyhub.services.rfq_capex_service import create_rfq, update_rfq
from supplyhub.services.parser_rfq_service import parsear_texto_correo_rfq

@override_settings(SUPPLYHUB_LOCAL_AUTH_ENABLED=True, DATAANALYTICS_ENABLED=False)
class Step56IntegrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='123456', password='StrongPass123!')
        self.client.post(reverse('login'), {'username':'123456', 'password':'StrongPass123!'})
        self.oc = OrdenCompra.objects.create(numero_oc='100', proveedor='Proveedor', planta_original='Mac Ra', planta_normalizada='MAQ_RA')
        self.linea = LineaOC.objects.create(orden=self.oc, numero_linea='1', release='2', codigo_articulo='A', descripcion='Pieza', cantidad_solicitada=3, cantidad_pendiente=3)

    def excel(self, data, sheet='Data'):
        file = BytesIO()
        pd.DataFrame(data).to_excel(file, index=False, sheet_name=sheet)
        file.seek(0)
        file.name = 'reporte.xlsx'
        return file

    def test_guardar_seguimiento_desde_pantalla(self):
        response = self.client.post(reverse('supplyhub:seguimiento_oc_detalle', args=[self.oc.pk]), {'linea_id':self.linea.pk, 'respuesta_proveedor':'En camino', 'fecha_revisada_propuesta':'2026-11-01', 'fecha_embarque_proveedor':'2026-10-30'})
        self.assertEqual(response.status_code, 302)
        self.linea.refresh_from_db()
        self.assertEqual(self.linea.fecha_revisada, date(2026,11,1))
        self.assertEqual(self.linea.comentario_actual, 'En camino')
        self.assertEqual(self.linea.comentarios, 'En camino')
        self.assertIsNotNone(self.linea.ultima_interaccion)
        self.assertEqual(HistorialSeguimiento.objects.get().linea_id, self.linea.pk)

    def test_fecha_invalida_no_crea_historial(self):
        response = self.client.post(reverse('supplyhub:seguimiento_oc_detalle', args=[self.oc.pk]), {'linea_id':self.linea.pk, 'respuesta_proveedor':'En camino', 'fecha_revisada_propuesta':'invalida'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(HistorialSeguimiento.objects.exists())

    def test_tenango_excluido_de_listado_y_detalle(self):
        self.oc.planta_normalizada = 'MACIMEX_TENANGO'
        self.oc.save()
        response = self.client.get(reverse('supplyhub:seguimiento_oc'))
        self.assertNotIn(self.oc, response.context['ordenes'])
        self.assertEqual(self.client.get(reverse('supplyhub:seguimiento_oc_detalle', args=[self.oc.pk])).status_code, 404)

    def test_importacion_oc_http_idempotente_con_release(self):
        url = reverse('supplyhub:importar_oc')
        self.assertContains(self.client.get(url), 'type="file"')
        data = {'Po Number':[200,200], 'Line Number':[1,1], 'Release Number':[1,2], 'Ship To Org Name':['Mac Ra','Mac Ra'], 'Supplier Name':['P','P'], 'Quantity Ordered':[3,4]}
        for _ in range(2):
            self.assertEqual(self.client.post(url, {'archivo':self.excel(data)}).status_code,302)
        self.assertEqual(OrdenCompra.objects.filter(numero_oc='200').count(),1)
        self.assertEqual(LineaOC.objects.filter(orden__numero_oc='200').count(),2)

    def test_importacion_rfq_pantalla_y_archivo(self):
        url = reverse('supplyhub:importar_rfq_capex')
        self.assertContains(self.client.get(url), 'type="file"')
        self.client.post(url, {'archivo':self.excel({'RFQ':[228], 'DESCRIPCION':['Equipo'], 'SOLICITANTE':['Edith'], 'PLANTA':['Ramos']})})
        self.assertTrue(RFQCapex.objects.filter(rfq='228').exists())

    def test_campos_control_se_guardan_al_crear_y_editar(self):
        data = {'rfq':'229', 'descripcion':'Equipo', 'solicitante':'Edith', 'planta':'MAQ_RA', 'numero_oc':'1000', 'comparativa':'https://example.com', 'tiempo_total':12}
        rfq = create_rfq(cleaned_data=data, actor='123456')
        rfq.refresh_from_db()
        self.assertEqual(rfq.numero_oc,'1000')
        self.assertEqual(rfq.tiempo_total,12)
        data['numero_oc']='2000'
        update_rfq(instance=rfq,cleaned_data=data,actor='123456')
        rfq.refresh_from_db()
        self.assertEqual(rfq.numero_oc,'2000')

    def test_parser_form_approvals(self):
        data = parsear_texto_correo_rfq('PEDIDO #228\nNombre del Solicitante: Edith\nSelecciona Unidad de Negocio: Tenango')
        self.assertEqual(data['rfq'],'228')
        self.assertEqual(data['solicitante'],'Edith')
        self.assertEqual(data['planta'],'MACIMEX_TENANGO')
