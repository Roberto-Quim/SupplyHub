# Pruebas unitarias para SupplyHub - Módulo de Seguimiento de OC y RFQ CapEx
import tempfile
import pandas as pd
from datetime import date, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from supplyhub.models import OrdenCompra, LineaOC, HistorialSeguimiento, RFQCapex
from supplyhub.services.seguimiento_oc_service import (
    normalizar_planta,
    evaluar_estado_linea,
    registrar_interaccion_linea
)
from supplyhub.services.importacion_oc_service import importar_oracle_open_po
from supplyhub.services.importacion_rfq_service import importar_rfq_capex_excel

User = get_user_model()


class SupplyHubTestCase(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testbuyer",
            email="testbuyer@quimmco.com",
            password="Password123!"
        )
        self.client.login(username="testbuyer", password="Password123!")

        # Registro de Orden de Compra de prueba
        self.orden = OrdenCompra.objects.create(
            numero_oc="99001",
            proveedor="PROVEEDOR TEST RAMOS",
            planta_original="MACIMEX RAMOS ARIZPE",
            planta_normalizada=OrdenCompra.PlantaNormalizada.MAQ_RA,
            sistema_origen="ORACLE_QES"
        )

        # Partida al día
        self.linea_al_dia = LineaOC.objects.create(
            orden=self.orden,
            numero_linea="1",
            codigo_articulo="ART001",
            descripcion="Articulo al día de prueba",
            cantidad_solicitada=10.0,
            fecha_original=date.today() + timedelta(days=15),
            fecha_comprometida=date.today() + timedelta(days=15)
        )

        # Partida vencida
        self.linea_vencida = LineaOC.objects.create(
            orden=self.orden,
            numero_linea="2",
            codigo_articulo="ART002",
            descripcion="Articulo vencido de prueba",
            cantidad_solicitada=5.0,
            fecha_original=date.today() - timedelta(days=5),
            fecha_comprometida=date.today() - timedelta(days=5)
        )

    def test_normalizacion_plantas(self):
        """Verifica que las variaciones de nombres de planta se mapeen correctamente"""
        self.assertEqual(normalizar_planta("IRA"), OrdenCompra.PlantaNormalizada.MAQ_RA)
        self.assertEqual(normalizar_planta("MACIMEX RAMOS ARIZPE"), OrdenCompra.PlantaNormalizada.MAQ_RA)
        self.assertEqual(normalizar_planta("MACIMEX TENANGO DEL VALLE"), OrdenCompra.PlantaNormalizada.MACIMEX_TENANGO)
        self.assertEqual(normalizar_planta("OTRA PLANTA"), OrdenCompra.PlantaNormalizada.DESCONOCIDA)

    def test_evaluacion_vencimientos(self):
        """Valida la semaforización visual de partidas al día vs vencidas"""
        self.assertFalse(evaluar_estado_linea(self.linea_al_dia)["vencida"])
        self.assertTrue(evaluar_estado_linea(self.linea_vencida)["vencida"])

    def test_historial_seguimiento_oc(self):
        """Prueba la captura de comentarios y actualización de fecha prometida"""
        hist = registrar_interaccion_linea(
            linea=self.linea_vencida,
            respuesta="Material en tránsito",
            usuario="testbuyer",
            nueva_fecha=date.today() + timedelta(days=10)
        )
        self.linea_vencida.refresh_from_db()
        self.assertEqual(self.linea_vencida.comentario_actual, "Material en tránsito")
        self.assertEqual(HistorialSeguimiento.objects.count(), 1)
        self.assertEqual(hist.usuario_responsable, "testbuyer")

    def test_importacion_rfq_capex(self):
        """Prueba la ingesta desde Excel para el módulo de RFQ CAPEX"""
        data = {
            'RFQ': [228],
            'DESCRIPCION': ['Dispositivos hidráulicos'],
            'SOLICITANTE': ['Jose Manuel Martinez'],
            'PLANTA': ['Questum Maquinados Ramos'],
            'ESTATUS': ['Solicitada'],
            'COMPARATIVA': ['https://docs.google.com/test'],
            'PROVEEDOR SELECCIONADO': ['DISTOL'],
            '#OC': ['100999']
        }
        df = pd.DataFrame(data)
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            with pd.ExcelWriter(tmp.name, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Sheet1', index=False)
            tmp_path = tmp.name

        with open(tmp_path, 'rb') as f:
            resumen = importar_rfq_capex_excel(f, "testbuyer")

        self.assertEqual(resumen["insertados"], 1)
        self.assertTrue(RFQCapex.objects.filter(rfq="228").exists())