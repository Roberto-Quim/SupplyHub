"""
Tests para FASE B.1: Validaciones Extendidas OC (Órdenes de Compra).
Verifica que las reglas de negocio detecten errores y advertencias correctamente.
"""
import pandas as pd
from datetime import date, timedelta
from io import BytesIO
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from supplyhub.models import OrdenCompra, LineaOC
from supplyhub.services.prevision_oc_service import previsualizar_oracle_open_po, validar_linea_oc


class ValidacionesOCTest(TestCase):
    """Tests para validaciones de negocio en importación OC"""
    
    def crear_archivo_excel(self, registros: list) -> SimpleUploadedFile:
        """Crea un archivo Excel de prueba con formato QES"""
        df = pd.DataFrame(registros)
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Data', index=False)
        buffer.seek(0)
        return SimpleUploadedFile("test_qes_open_po.xlsx", buffer.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    
    def test_validacion_proveedor_vacio(self):
        """Test: Error si falta nombre del proveedor"""
        datos = [{
            'Po Number': 100001,
            'Release Number': 1,
            'Line Number': 1,
            'Supplier Name': '',  # Proveedor vacío
            'Ship To Org Name': 'Macimex SLP',
            'Item': 'MAT-001',
            'Item Description': 'Material de prueba',
            'Unit Of Measure': 'PZA',
            'Quantity Ordered': 100,
            'Quantity due': 100,
            'Quantity Received': 0,
            'Unit Price': 10.00,
            'Status need': 'Approved',
            'Buyer Full Name': 'Test',
            'Authorization Status': 'APPROVED',
            'C Currency': 'MXN',
            'Rel Creation Date': '2026-11-01',
            'Need By Date': '2026-11-15',
            'Correo Proveedor': ''
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_oracle_open_po(archivo)
        
        reg = resultado['registros'][0]
        self.assertTrue(reg.get('tiene_errores'))
        self.assertTrue(any('proveedor' in v['mensaje'].lower() for v in reg.get('validaciones', [])))
    
    def test_validacion_cantidades_negativas(self):
        """Test: Error si hay cantidades negativas"""
        datos = [{
            'Po Number': 100001,
            'Release Number': 1,
            'Line Number': 1,
            'Supplier Name': 'ACME Corp',
            'Ship To Org Name': 'Macimex SLP',
            'Item': 'MAT-001',
            'Item Description': 'Material',
            'Unit Of Measure': 'PZA',
            'Quantity Ordered': -10,  # Negativa
            'Quantity due': 100,
            'Quantity Received': 0,
            'Unit Price': 10.00,
            'Status need': 'Approved',
            'Buyer Full Name': 'Test',
            'Authorization Status': 'APPROVED',
            'C Currency': 'MXN',
            'Rel Creation Date': '2026-11-01',
            'Need By Date': '2026-11-15',
            'Correo Proveedor': ''
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_oracle_open_po(archivo)
        
        reg = resultado['registros'][0]
        self.assertTrue(reg.get('tiene_errores'))
        self.assertTrue(any('negativa' in v['mensaje'].lower() for v in reg.get('validaciones', [])))
    
    def test_validacion_precio_negativo(self):
        """Test: Error si precio unitario es negativo"""
        datos = [{
            'Po Number': 100001,
            'Release Number': 1,
            'Line Number': 1,
            'Supplier Name': 'ACME Corp',
            'Ship To Org Name': 'Macimex SLP',
            'Item': 'MAT-001',
            'Item Description': 'Material',
            'Unit Of Measure': 'PZA',
            'Quantity Ordered': 100,
            'Quantity due': 100,
            'Quantity Received': 0,
            'Unit Price': -10.00,  # Negativo
            'Status need': 'Approved',
            'Buyer Full Name': 'Test',
            'Authorization Status': 'APPROVED',
            'C Currency': 'MXN',
            'Rel Creation Date': '2026-11-01',
            'Need By Date': '2026-11-15',
            'Correo Proveedor': ''
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_oracle_open_po(archivo)
        
        reg = resultado['registros'][0]
        self.assertTrue(reg.get('tiene_errores'))
        self.assertTrue(any('precio' in v['mensaje'].lower() and 'negativo' in v['mensaje'].lower() for v in reg.get('validaciones', [])))
    
    def test_alerta_precio_cero(self):
        """Test: Advertencia si precio es cero con cantidad solicitada"""
        datos = [{
            'Po Number': 100001,
            'Release Number': 1,
            'Line Number': 1,
            'Supplier Name': 'ACME Corp',
            'Ship To Org Name': 'Macimex SLP',
            'Item': 'MAT-001',
            'Item Description': 'Material',
            'Unit Of Measure': 'PZA',
            'Quantity Ordered': 100,
            'Quantity due': 100,
            'Quantity Received': 0,
            'Unit Price': 0.00,  # Cero
            'Status need': 'Approved',
            'Buyer Full Name': 'Test',
            'Authorization Status': 'APPROVED',
            'C Currency': 'MXN',
            'Rel Creation Date': '2026-11-01',
            'Need By Date': '2026-11-15',
            'Correo Proveedor': ''
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_oracle_open_po(archivo)
        
        reg = resultado['registros'][0]
        self.assertTrue(reg.get('tiene_warnings'))
        self.assertTrue(any('precio' in v['mensaje'].lower() and 'cero' in v['mensaje'].lower() for v in reg.get('validaciones', [])))
    
    def test_alerta_cantidad_pendiente_mayor_solicitada(self):
        """Test: Advertencia si cantidad pendiente > solicitada"""
        datos = [{
            'Po Number': 100001,
            'Release Number': 1,
            'Line Number': 1,
            'Supplier Name': 'ACME Corp',
            'Ship To Org Name': 'Macimex SLP',
            'Item': 'MAT-001',
            'Item Description': 'Material',
            'Unit Of Measure': 'PZA',
            'Quantity Ordered': 100,
            'Quantity due': 150,  # Mayor que solicitada
            'Quantity Received': 0,
            'Unit Price': 10.00,
            'Status need': 'Approved',
            'Buyer Full Name': 'Test',
            'Authorization Status': 'APPROVED',
            'C Currency': 'MXN',
            'Rel Creation Date': '2026-11-01',
            'Need By Date': '2026-11-15',
            'Correo Proveedor': ''
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_oracle_open_po(archivo)
        
        reg = resultado['registros'][0]
        self.assertTrue(reg.get('tiene_warnings'))
        self.assertTrue(any('mayor que solicitada' in v['mensaje'].lower() for v in reg.get('validaciones', [])))
    
    def test_alerta_suma_cantidades_inconsistente(self):
        """Test: Advertencia si recibida + pendiente ≠ solicitada"""
        datos = [{
            'Po Number': 100001,
            'Release Number': 1,
            'Line Number': 1,
            'Supplier Name': 'ACME Corp',
            'Ship To Org Name': 'Macimex SLP',
            'Item': 'MAT-001',
            'Item Description': 'Material',
            'Unit Of Measure': 'PZA',
            'Quantity Ordered': 100,
            'Quantity due': 40,
            'Quantity Received': 50,  # 50 + 40 = 90 ≠ 100
            'Unit Price': 10.00,
            'Status need': 'Approved',
            'Buyer Full Name': 'Test',
            'Authorization Status': 'APPROVED',
            'C Currency': 'MXN',
            'Rel Creation Date': '2026-11-01',
            'Need By Date': '2026-11-15',
            'Correo Proveedor': ''
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_oracle_open_po(archivo)
        
        reg = resultado['registros'][0]
        self.assertTrue(reg.get('tiene_warnings'))
        self.assertTrue(any('suma' in v['mensaje'].lower() for v in reg.get('validaciones', [])))
    
    def test_alerta_fecha_antigua(self):
        """Test: Advertencia si fecha Need By es muy antigua (>2 años)"""
        fecha_antigua = date.today() - timedelta(days=800)
        
        datos = [{
            'Po Number': 100001,
            'Release Number': 1,
            'Line Number': 1,
            'Supplier Name': 'ACME Corp',
            'Ship To Org Name': 'Macimex SLP',
            'Item': 'MAT-001',
            'Item Description': 'Material',
            'Unit Of Measure': 'PZA',
            'Quantity Ordered': 100,
            'Quantity due': 100,
            'Quantity Received': 0,
            'Unit Price': 10.00,
            'Status need': 'Approved',
            'Buyer Full Name': 'Test',
            'Authorization Status': 'APPROVED',
            'C Currency': 'MXN',
            'Rel Creation Date': '2026-11-01',
            'Need By Date': fecha_antigua.strftime('%Y-%m-%d'),
            'Correo Proveedor': ''
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_oracle_open_po(archivo)
        
        reg = resultado['registros'][0]
        self.assertTrue(reg.get('tiene_warnings'))
        self.assertTrue(any('muy antigua' in v['mensaje'].lower() for v in reg.get('validaciones', [])))
    
    def test_alerta_linea_vencida(self):
        """Test: Advertencia si línea está vencida (fecha pasada con cantidad pendiente)"""
        fecha_pasada = date.today() - timedelta(days=30)
        
        datos = [{
            'Po Number': 100001,
            'Release Number': 1,
            'Line Number': 1,
            'Supplier Name': 'ACME Corp',
            'Ship To Org Name': 'Macimex SLP',
            'Item': 'MAT-001',
            'Item Description': 'Material',
            'Unit Of Measure': 'PZA',
            'Quantity Ordered': 100,
            'Quantity due': 50,  # Tiene pendiente
            'Quantity Received': 50,
            'Unit Price': 10.00,
            'Status need': 'Approved',
            'Buyer Full Name': 'Test',
            'Authorization Status': 'APPROVED',
            'C Currency': 'MXN',
            'Rel Creation Date': '2026-11-01',
            'Need By Date': fecha_pasada.strftime('%Y-%m-%d'),
            'Correo Proveedor': ''
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_oracle_open_po(archivo)
        
        reg = resultado['registros'][0]
        self.assertTrue(reg.get('tiene_warnings'))
        self.assertTrue(any('vencida' in v['mensaje'].lower() or 'retraso' in v['mensaje'].lower() for v in reg.get('validaciones', [])))
    
    def test_alerta_cambio_precio_significativo(self):
        """Test: Alerta sobre cambio de precio >20%"""
        # Crear OC y línea existente
        orden = OrdenCompra.objects.create(
            numero_oc="100001",
            sistema_origen="ORACLE_QES",
            proveedor="ACME Corp"
        )
        LineaOC.objects.create(
            orden=orden,
            release="1",
            numero_linea="1",
            codigo_articulo="MAT-001",
            descripcion="Material",
            unidad_medida="PZA",
            cantidad_solicitada=100,
            cantidad_pendiente=100,
            cantidad_recibida=0,
            precio_unitario=10.00,  # Precio original: $10
            fecha_original=date.today() + timedelta(days=7),
            estatus_necesidad="Approved"
        )
        
        # Archivo con precio aumentado >20%
        datos = [{
            'Po Number': 100001,
            'Release Number': 1,
            'Line Number': 1,
            'Supplier Name': 'ACME Corp',
            'Ship To Org Name': 'Macimex SLP',
            'Item': 'MAT-001',
            'Item Description': 'Material',
            'Unit Of Measure': 'PZA',
            'Quantity Ordered': 100,
            'Quantity due': 100,
            'Quantity Received': 0,
            'Unit Price': 13.00,  # +30% (de $10 a $13)
            'Status need': 'Approved',
            'Buyer Full Name': 'Test',
            'Authorization Status': 'APPROVED',
            'C Currency': 'MXN',
            'Rel Creation Date': '2026-11-01',
            'Need By Date': (date.today() + timedelta(days=7)).strftime('%Y-%m-%d'),
            'Correo Proveedor': ''
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_oracle_open_po(archivo)
        
        reg = resultado['registros'][0]
        self.assertEqual(reg['estado'], 'actualizar')
        self.assertTrue(reg.get('tiene_warnings'))
        self.assertTrue(any('cambio significativo' in v['mensaje'].lower() and 'precio' in v['mensaje'].lower() for v in reg.get('validaciones', [])))
    
    def test_alerta_fecha_pospuesta(self):
        """Test: Alerta si fecha de entrega se pospone >7 días"""
        # Crear OC y línea existente
        orden = OrdenCompra.objects.create(
            numero_oc="100001",
            sistema_origen="ORACLE_QES",
            proveedor="ACME Corp"
        )
        fecha_original = date.today() + timedelta(days=10)
        LineaOC.objects.create(
            orden=orden,
            release="1",
            numero_linea="1",
            codigo_articulo="MAT-001",
            descripcion="Material",
            unidad_medida="PZA",
            cantidad_solicitada=100,
            cantidad_pendiente=100,
            cantidad_recibida=0,
            precio_unitario=10.00,
            fecha_original=fecha_original,
            estatus_necesidad="Approved"
        )
        
        # Archivo con fecha pospuesta 15 días
        fecha_nueva = fecha_original + timedelta(days=15)
        datos = [{
            'Po Number': 100001,
            'Release Number': 1,
            'Line Number': 1,
            'Supplier Name': 'ACME Corp',
            'Ship To Org Name': 'Macimex SLP',
            'Item': 'MAT-001',
            'Item Description': 'Material',
            'Unit Of Measure': 'PZA',
            'Quantity Ordered': 100,
            'Quantity due': 100,
            'Quantity Received': 0,
            'Unit Price': 10.00,
            'Status need': 'Approved',
            'Buyer Full Name': 'Test',
            'Authorization Status': 'APPROVED',
            'C Currency': 'MXN',
            'Rel Creation Date': '2026-11-01',
            'Need By Date': fecha_nueva.strftime('%Y-%m-%d'),
            'Correo Proveedor': ''
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_oracle_open_po(archivo)
        
        reg = resultado['registros'][0]
        self.assertEqual(reg['estado'], 'actualizar')
        self.assertTrue(reg.get('tiene_warnings'))
        self.assertTrue(any('pospuesta' in v['mensaje'].lower() for v in reg.get('validaciones', [])))
    
    def test_registro_valido_sin_errores(self):
        """Test: Registro válido no genera errores ni advertencias"""
        datos = [{
            'Po Number': 100001,
            'Release Number': 1,
            'Line Number': 1,
            'Supplier Name': 'ACME Corporation',
            'Ship To Org Name': 'Macimex San Luis Potosí',
            'Item': 'MAT-12345',
            'Item Description': 'Material de prueba estándar',
            'Unit Of Measure': 'PZA',
            'Quantity Ordered': 100,
            'Quantity due': 100,
            'Quantity Received': 0,
            'Unit Price': 25.50,
            'Status need': 'Approved',
            'Buyer Full Name': 'Jacqueline Test',
            'Authorization Status': 'APPROVED',
            'C Currency': 'MXN',
            'Rel Creation Date': '2026-11-01',
            'Need By Date': (date.today() + timedelta(days=15)).strftime('%Y-%m-%d'),
            'Correo Proveedor': 'ventas@acme.com'
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_oracle_open_po(archivo)
        
        reg = resultado['registros'][0]
        self.assertEqual(reg['estado'], 'nuevo')
        self.assertFalse(reg.get('tiene_errores'))
        self.assertFalse(reg.get('tiene_warnings'))
