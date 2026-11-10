"""
Tests para FASE B.1: Validaciones Extendidas RFQ/CAPEX.
Verifica que las reglas de negocio detecten errores y advertencias correctamente.
"""
import pandas as pd
from datetime import date, timedelta
from io import BytesIO
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from supplyhub.models import RFQCapex
from supplyhub.services.prevision_rfq_service import previsualizar_rfq_excel, validar_registro_rfq


class ValidacionesRFQTest(TestCase):
    """Tests para validaciones de negocio en importación RFQ"""
    
    def crear_archivo_excel(self, registros: list) -> SimpleUploadedFile:
        """Crea un archivo Excel de prueba"""
        df = pd.DataFrame(registros)
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        buffer.seek(0)
        return SimpleUploadedFile("test_rfq.xlsx", buffer.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    
    def test_validacion_campos_obligatorios(self):
        """Test: Detecta falta de campos obligatorios (descripción, solicitante)"""
        datos = [
            {'RFQ': '12345', 'DESCRIPCION': '', 'SOLICITANTE': 'Juan', 'PLANTA': 'Maq RA'},  # Falta descripción
        ]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_rfq_excel(archivo)
        
        # Debe haber 1 registro
        self.assertEqual(len(resultado['registros']), 1)
        
        reg = resultado['registros'][0]
        # Debe tener validaciones
        self.assertIn('validaciones', reg)
        # Debe tener errores
        self.assertTrue(reg.get('tiene_errores'), f"Registro sin errores: {reg}")
        # Verificar mensaje específico
        self.assertTrue(any('descripción' in v['mensaje'].lower() for v in reg.get('validaciones', [])),
                       f"Validaciones: {reg.get('validaciones', [])}")
    
    def test_validacion_longitud_campos(self):
        """Test: Alerta sobre campos de texto muy largos"""
        descripcion_larga = 'A' * 600  # 600 caracteres (máximo recomendado: 500)
        solicitante_largo = 'B' * 250  # 250 caracteres (máximo: 200)
        
        datos = [{
            'RFQ': '12345',
            'DESCRIPCION': descripcion_larga,
            'SOLICITANTE': solicitante_largo,
            'PLANTA': 'Maq RA'
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_rfq_excel(archivo)
        
        reg = resultado['registros'][0]
        self.assertTrue(reg.get('tiene_warnings'))
        
        # Verificar advertencias específicas
        warnings = [v for v in reg['validaciones'] if v['tipo'] == 'warning']
        self.assertTrue(any('muy larga' in w['mensaje'].lower() for w in warnings))
        self.assertTrue(any('muy largo' in w['mensaje'].lower() for w in warnings))
    
    def test_validacion_formato_rfq(self):
        """Test: RFQ debe ser numérico"""
        datos = [
            {'RFQ': 'ABC123', 'DESCRIPCION': 'Test', 'SOLICITANTE': 'Juan', 'PLANTA': 'Maq RA'},
            {'RFQ': '12-345', 'DESCRIPCION': 'Test', 'SOLICITANTE': 'Juan', 'PLANTA': 'Maq RA'},
        ]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_rfq_excel(archivo)
        
        # Ambos deben tener errores por formato inválido
        for reg in resultado['registros']:
            self.assertTrue(reg.get('tiene_errores'))
            self.assertTrue(any('inválido' in v['mensaje'] for v in reg.get('validaciones', [])))
    
    def test_validacion_fecha_oc_antigua(self):
        """Test: Alerta sobre fecha de OC muy antigua (>2 años)"""
        fecha_antigua = date.today() - timedelta(days=800)
        
        datos = [{
            'RFQ': '12345',
            'DESCRIPCION': 'Test',
            'SOLICITANTE': 'Juan',
            'PLANTA': 'Maq RA',
            '#OC': '100001',
            'FECHA DE OC': fecha_antigua.strftime('%Y-%m-%d')
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_rfq_excel(archivo)
        
        reg = resultado['registros'][0]
        self.assertTrue(reg.get('tiene_warnings'))
        self.assertTrue(any('muy antigua' in v['mensaje'] for v in reg.get('validaciones', [])))
    
    def test_validacion_fecha_oc_futura(self):
        """Test: Alerta sobre fecha de OC futura (>1 mes)"""
        fecha_futura = date.today() + timedelta(days=45)
        
        datos = [{
            'RFQ': '12345',
            'DESCRIPCION': 'Test',
            'SOLICITANTE': 'Juan',
            'PLANTA': 'Maq RA',
            '#OC': '100001',
            'FECHA DE OC': fecha_futura.strftime('%Y-%m-%d')
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_rfq_excel(archivo)
        
        reg = resultado['registros'][0]
        self.assertTrue(reg.get('tiene_warnings'))
        self.assertTrue(any('futura' in v['mensaje'] for v in reg.get('validaciones', [])))
    
    def test_validacion_oc_sin_proveedor(self):
        """Test: Alerta si tiene OC pero falta proveedor"""
        datos = [{
            'RFQ': '12345',
            'DESCRIPCION': 'Test',
            'SOLICITANTE': 'Juan',
            'PLANTA': 'Maq RA',
            '#OC': '100001',
            'PROVEEDOR SELECCIONADO': ''  # Falta proveedor
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_rfq_excel(archivo)
        
        reg = resultado['registros'][0]
        self.assertTrue(reg.get('tiene_warnings'))
        self.assertTrue(any('falta proveedor' in v['mensaje'].lower() for v in reg.get('validaciones', [])))
    
    def test_validacion_oc_sin_fecha(self):
        """Test: Alerta si tiene OC pero falta fecha"""
        datos = [{
            'RFQ': '12345',
            'DESCRIPCION': 'Test',
            'SOLICITANTE': 'Juan',
            'PLANTA': 'Maq RA',
            '#OC': '100001',
            'PROVEEDOR SELECCIONADO': 'ACME Corp'
            # Falta FECHA DE OC
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_rfq_excel(archivo)
        
        reg = resultado['registros'][0]
        self.assertTrue(reg.get('tiene_warnings'))
        self.assertTrue(any('falta fecha' in v['mensaje'].lower() for v in reg.get('validaciones', [])))
    
    def test_alerta_cambio_planta(self):
        """Test: Alerta sobre cambio de planta en actualización"""
        # Crear RFQ existente
        RFQCapex.objects.create(
            rfq="12345",
            descripcion="Test",
            solicitante="Juan",
            planta=RFQCapex.Planta.MAQ_RA
        )
        
        # Archivo con cambio de planta
        datos = [{
            'RFQ': '12345',
            'DESCRIPCION': 'Test',
            'SOLICITANTE': 'Juan',
            'PLANTA': 'Macimex Tenango'  # Cambio de planta
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_rfq_excel(archivo)
        
        reg = resultado['registros'][0]
        self.assertEqual(reg['estado'], 'actualizar')
        self.assertTrue(reg.get('tiene_warnings'))
        self.assertTrue(any('cambio de planta' in v['mensaje'].lower() for v in reg.get('validaciones', [])))
    
    def test_alerta_cambio_solicitante(self):
        """Test: Alerta sobre cambio de solicitante en actualización"""
        # Crear RFQ existente
        RFQCapex.objects.create(
            rfq="12345",
            descripcion="Test",
            solicitante="Juan Pérez",
            planta=RFQCapex.Planta.MAQ_RA
        )
        
        # Archivo con cambio de solicitante
        datos = [{
            'RFQ': '12345',
            'DESCRIPCION': 'Test',
            'SOLICITANTE': 'María García',  # Cambio de solicitante
            'PLANTA': 'Maq RA'
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_rfq_excel(archivo)
        
        reg = resultado['registros'][0]
        self.assertEqual(reg['estado'], 'actualizar')
        self.assertTrue(reg.get('tiene_warnings'))
        self.assertTrue(any('cambio de solicitante' in v['mensaje'].lower() for v in reg.get('validaciones', [])))
    
    def test_registro_valido_sin_errores(self):
        """Test: Registro válido no genera errores ni advertencias"""
        datos = [{
            'RFQ': '12345',
            'DESCRIPCION': 'Compra de equipo de cómputo para área de IT',
            'SOLICITANTE': 'Juan Pérez',
            'PLANTA': 'Maq RA',
            'PROYECTO': 'CAPEX-2026-001',
            'PROVEEDOR SELECCIONADO': 'Dell México',
            '#OC': '100001',
            'FECHA DE OC': date.today().strftime('%Y-%m-%d')
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_rfq_excel(archivo)
        
        reg = resultado['registros'][0]
        self.assertEqual(reg['estado'], 'nuevo')
        self.assertFalse(reg.get('tiene_errores'))
        self.assertFalse(reg.get('tiene_warnings'))
        self.assertEqual(len(reg.get('validaciones', [])), 0)
