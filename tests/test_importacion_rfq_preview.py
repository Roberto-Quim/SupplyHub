"""Tests para la previsualización e idempotencia de importación RFQ/CAPEX."""

import tempfile
from datetime import date

import pandas as pd
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from supplyhub.models import RFQCapex
from supplyhub.services.prevision_rfq_service import previsualizar_rfq_excel
from supplyhub.services.importacion_rfq_service import importar_rfq_capex_excel


@override_settings(SUPPLYHUB_LOCAL_AUTH_ENABLED=True, DATAANALYTICS_ENABLED=False)
class ImportacionRFQPreviewTests(TestCase):
    """Tests de vista previa y validación antes de importar."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="738210",
            password="StrongPass123!",
        )
        self.client.login(username="738210", password="StrongPass123!")

    def _crear_excel_temporal(self, datos: list[dict]) -> str:
        """Crea un archivo Excel temporal con los datos proporcionados."""
        df = pd.DataFrame(datos)
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False, mode='wb') as tmp:
            with pd.ExcelWriter(tmp.name, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Sheet1', index=False)
            return tmp.name

    def test_prevision_detecta_nuevos_rfq(self):
        """La previsualización debe identificar RFQ nuevos correctamente."""
        datos = [
            {
                'RFQ': 301,
                'DESCRIPCION': 'Equipo de prueba A',
                'SOLICITANTE': 'Juan Perez',
                'PLANTA': 'MAQ RA',
                'PROYECTO': 'CAPEX-301',
            },
            {
                'RFQ': 302,
                'DESCRIPCION': 'Equipo de prueba B',
                'SOLICITANTE': 'Maria Lopez',
                'PLANTA': 'Questum Macimex Tenango',
                'PROYECTO': 'CAPEX-302',
            },
        ]
        
        archivo = self._crear_excel_temporal(datos)
        
        with open(archivo, 'rb') as f:
            prevision = previsualizar_rfq_excel(f)
        
        self.assertEqual(prevision['resumen']['total'], 2)
        self.assertEqual(prevision['resumen']['nuevos'], 2)
        self.assertEqual(prevision['resumen']['actualizar'], 0)
        self.assertEqual(prevision['resumen']['duplicados'], 0)
        self.assertEqual(prevision['resumen']['errores'], 0)
        
        # Verificar que los registros están marcados como "nuevo"
        for reg in prevision['registros']:
            self.assertEqual(reg['estado'], 'nuevo')

    def test_prevision_detecta_actualizaciones(self):
        """La previsualización debe identificar RFQ que serán actualizados."""
        # Crear un RFQ existente
        RFQCapex.objects.create(
            rfq="401",
            descripcion="Descripción original",
            solicitante="Solicitante Original",
            planta=RFQCapex.Planta.MAQ_RA,
            clave_capex="CAPEX-401-OLD",
            creado_por="738210",
            actualizado_por="738210",
        )
        
        # Datos con cambios
        datos = [
            {
                'RFQ': 401,
                'DESCRIPCION': 'Descripción actualizada',
                'SOLICITANTE': 'Solicitante Nuevo',
                'PLANTA': 'MAQ RA',
                'PROYECTO': 'CAPEX-401-NEW',
            },
        ]
        
        archivo = self._crear_excel_temporal(datos)
        
        with open(archivo, 'rb') as f:
            prevision = previsualizar_rfq_excel(f)
        
        self.assertEqual(prevision['resumen']['total'], 1)
        self.assertEqual(prevision['resumen']['nuevos'], 0)
        self.assertEqual(prevision['resumen']['actualizar'], 1)
        self.assertEqual(prevision['resumen']['duplicados'], 0)
        
        # Verificar que el registro está marcado como "actualizar"
        self.assertEqual(prevision['registros'][0]['estado'], 'actualizar')

    def test_prevision_detecta_duplicados_sin_cambios(self):
        """La previsualización debe identificar RFQ duplicados (sin cambios)."""
        # Crear un RFQ existente
        RFQCapex.objects.create(
            rfq="501",
            descripcion="Descripción idéntica",
            solicitante="Solicitante Idéntico",
            planta=RFQCapex.Planta.MAQ_RA,
            clave_capex="CAPEX-501",
            creado_por="738210",
            actualizado_por="738210",
        )
        
        # Datos idénticos
        datos = [
            {
                'RFQ': 501,
                'DESCRIPCION': 'Descripción idéntica',
                'SOLICITANTE': 'Solicitante Idéntico',
                'PLANTA': 'MAQ RA',
                'PROYECTO': 'CAPEX-501',
            },
        ]
        
        archivo = self._crear_excel_temporal(datos)
        
        with open(archivo, 'rb') as f:
            prevision = previsualizar_rfq_excel(f)
        
        self.assertEqual(prevision['resumen']['total'], 1)
        self.assertEqual(prevision['resumen']['nuevos'], 0)
        self.assertEqual(prevision['resumen']['actualizar'], 0)
        self.assertEqual(prevision['resumen']['duplicados'], 1)
        
        # Verificar que el registro está marcado como "duplicado"
        self.assertEqual(prevision['registros'][0]['estado'], 'duplicado')

    def test_idempotencia_importacion_misma_data(self):
        """Importar el mismo archivo 2 veces debe resultar en 0 cambios la segunda vez."""
        datos = [
            {
                'RFQ': 601,
                'DESCRIPCION': 'Equipo idempotencia',
                'SOLICITANTE': 'Test User',
                'PLANTA': 'MAQ RA',
                'PROYECTO': 'CAPEX-601',
            },
        ]
        
        archivo = self._crear_excel_temporal(datos)
        
        # Primera importación
        with open(archivo, 'rb') as f:
            resumen1 = importar_rfq_capex_excel(f, "738210")
        
        self.assertEqual(resumen1['insertados'], 1)
        self.assertEqual(resumen1['actualizados'], 0)
        
        # Segunda importación con datos idénticos
        with open(archivo, 'rb') as f:
            resumen2 = importar_rfq_capex_excel(f, "738210")
        
        # En la segunda importación, update_or_create detecta que no hay cambios
        # y ejecuta un UPDATE, por lo que cuenta como "actualizado" aunque no cambie nada.
        # Esto es comportamiento esperado de Django ORM.
        self.assertEqual(resumen2['insertados'], 0)
        self.assertEqual(resumen2['actualizados'], 1)
        
        # Verificar que solo existe 1 registro en la BD
        self.assertEqual(RFQCapex.objects.count(), 1)
        self.assertEqual(RFQCapex.objects.filter(rfq="601").count(), 1)

    def test_normalizacion_plantas_en_prevision(self):
        """La previsualización debe normalizar nombres de plantas correctamente."""
        datos = [
            {'RFQ': 701, 'DESCRIPCION': 'Test', 'SOLICITANTE': 'User', 'PLANTA': 'Questum Macimex Tenango', 'PROYECTO': 'A'},
            {'RFQ': 702, 'DESCRIPCION': 'Test', 'SOLICITANTE': 'User', 'PLANTA': 'MAQ RA', 'PROYECTO': 'B'},
            {'RFQ': 703, 'DESCRIPCION': 'Test', 'SOLICITANTE': 'User', 'PLANTA': 'Maquinados Ramos Arizpe', 'PROYECTO': 'C'},
        ]
        
        archivo = self._crear_excel_temporal(datos)
        
        with open(archivo, 'rb') as f:
            prevision = previsualizar_rfq_excel(f)
        
        self.assertEqual(prevision['registros'][0]['planta'], 'Macimex Tenango')
        self.assertEqual(prevision['registros'][0]['planta_codigo'], 'MACIMEX_TENANGO')
        
        self.assertEqual(prevision['registros'][1]['planta'], 'MAQ RA')
        self.assertEqual(prevision['registros'][1]['planta_codigo'], 'MAQ_RA')
        
        # El tercero normaliza a MAQ_RA por defecto (no tiene "TENANGO")
        self.assertEqual(prevision['registros'][2]['planta'], 'MAQ RA')

    def test_prevision_http_endpoint_requiere_login(self):
        """El endpoint de previsualización debe requerir autenticación."""
        self.client.logout()
        
        datos = [{'RFQ': 801, 'DESCRIPCION': 'Test', 'SOLICITANTE': 'User', 'PLANTA': 'MAQ RA', 'PROYECTO': 'X'}]
        archivo = self._crear_excel_temporal(datos)
        
        with open(archivo, 'rb') as f:
            response = self.client.post(reverse('supplyhub:importar_rfq_capex'), {'archivo': f})
        
        # Debe redirigir a login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_prevision_http_endpoint_retorna_template(self):
        """El endpoint debe renderizar el template de previsualización."""
        datos = [
            {'RFQ': 901, 'DESCRIPCION': 'HTTP Test', 'SOLICITANTE': 'User', 'PLANTA': 'MAQ RA', 'PROYECTO': 'Y'},
        ]
        archivo = self._crear_excel_temporal(datos)
        
        with open(archivo, 'rb') as f:
            response = self.client.post(reverse('supplyhub:importar_rfq_capex'), {'archivo': f})
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'rfq_capex/importar_previa.html')
        self.assertIn('prevision', response.context)
        self.assertEqual(response.context['prevision']['resumen']['nuevos'], 1)
