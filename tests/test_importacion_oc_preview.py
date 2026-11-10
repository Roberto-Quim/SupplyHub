"""
Tests para FASE A.2: Vista Previa de Importación OC (Seguimiento de Órdenes de Compra).
Verifica que la previsualización detecte correctamente registros nuevos, actualizaciones,
duplicados y errores. También valida la idempotencia de importaciones repetidas.
"""
import os
import pandas as pd
from datetime import date
from io import BytesIO
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from supplyhub.models import OrdenCompra, LineaOC
from supplyhub.services.prevision_oc_service import previsualizar_oracle_open_po
from supplyhub.services.importacion_oc_service import importar_oracle_open_po


class ImportacionOCPreviewTest(TestCase):
    """Tests para vista previa de importación OC"""
    
    def crear_archivo_excel(self, registros: list) -> SimpleUploadedFile:
        """
        Crea un archivo Excel de prueba con las columnas esperadas de Oracle QES.
        
        Args:
            registros: lista de dicts con datos de líneas OC
        """
        df = pd.DataFrame(registros)
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Data', index=False)
        buffer.seek(0)
        return SimpleUploadedFile(
            "test_qes_open_po.xlsx",
            buffer.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    def test_previa_registros_nuevos(self):
        """Test: Detecta correctamente registros completamente nuevos"""
        datos = [
            {
                'Po Number': 100001,
                'Release Number': 1,
                'Line Number': 1,
                'Supplier Name': 'ACME Corporation',
                'Ship To Org Name': 'Macimex San Luis Potosí',
                'Item': 'MAT-12345',
                'Item Description': 'Material de prueba A',
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
                'Need By Date': '2026-11-15',
                'Correo Proveedor': 'ventas@acme.com'
            },
            {
                'Po Number': 100002,
                'Release Number': 1,
                'Line Number': 1,
                'Supplier Name': 'Beta Supplies',
                'Ship To Org Name': 'Macimex Guanajuato',
                'Item': 'MAT-67890',
                'Item Description': 'Material de prueba B',
                'Unit Of Measure': 'KG',
                'Quantity Ordered': 500,
                'Quantity due': 500,
                'Quantity Received': 0,
                'Unit Price': 12.75,
                'Status need': 'Approved',
                'Buyer Full Name': 'Jacqueline Test',
                'Authorization Status': 'APPROVED',
                'C Currency': 'MXN',
                'Rel Creation Date': '2026-11-02',
                'Need By Date': '2026-11-20',
                'Correo Proveedor': 'pedidos@betasupplies.com'
            }
        ]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_oracle_open_po(archivo)
        
        self.assertEqual(resultado['resumen']['nuevos'], 2)
        self.assertEqual(resultado['resumen']['actualizar'], 0)
        self.assertEqual(resultado['resumen']['duplicados'], 0)
        self.assertEqual(resultado['resumen']['errores'], 0)
        self.assertEqual(len(resultado['registros']), 2)
        
        # Verificar primer registro
        reg1 = resultado['registros'][0]
        self.assertEqual(reg1['estado'], 'nuevo')
        self.assertEqual(reg1['numero_oc'], '100001')
        self.assertIn('OC nueva', reg1['razon'])
    
    def test_previa_registros_duplicados(self):
        """Test: Detecta correctamente registros ya existentes sin cambios"""
        # Crear OC y línea existente en BD
        orden = OrdenCompra.objects.create(
            numero_oc="200001",
            sistema_origen="ORACLE_QES",
            proveedor="Gamma Industries",
            planta_original="Macimex San Luis Potosí",
            planta_normalizada="MACIMEX_SLP",
            comprador="Jacqueline Test"
        )
        LineaOC.objects.create(
            orden=orden,
            release="1",
            numero_linea="1",
            codigo_articulo="MAT-11111",
            descripcion="Material Gamma",
            unidad_medida="PZA",
            cantidad_solicitada=200,
            cantidad_pendiente=200,
            cantidad_recibida=0,
            precio_unitario=30.00,
            fecha_original=pd.to_datetime('2026-11-15').date(),
            estatus_necesidad="Approved"
        )
        
        # Archivo con los mismos datos
        datos = [{
            'Po Number': 200001,
            'Release Number': 1,
            'Line Number': 1,
            'Supplier Name': 'Gamma Industries',
            'Ship To Org Name': 'Macimex San Luis Potosí',
            'Item': 'MAT-11111',
            'Item Description': 'Material Gamma',
            'Unit Of Measure': 'PZA',
            'Quantity Ordered': 200,
            'Quantity due': 200,
            'Quantity Received': 0,
            'Unit Price': 30.00,
            'Status need': 'Approved',
            'Buyer Full Name': 'Jacqueline Test',
            'Authorization Status': 'APPROVED',
            'C Currency': 'MXN',
            'Rel Creation Date': '2026-11-01',
            'Need By Date': '2026-11-15',
            'Correo Proveedor': ''
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_oracle_open_po(archivo)
        
        self.assertEqual(resultado['resumen']['nuevos'], 0)
        self.assertEqual(resultado['resumen']['actualizar'], 0)
        self.assertEqual(resultado['resumen']['duplicados'], 1)
        self.assertEqual(resultado['resumen']['errores'], 0)
        
        reg = resultado['registros'][0]
        self.assertEqual(reg['estado'], 'duplicado')
        self.assertIn('idéntico', reg['razon'].lower())
    
    def test_previa_registros_actualizar(self):
        """Test: Detecta correctamente registros con cambios que deben actualizarse"""
        # Crear OC y línea existente
        orden = OrdenCompra.objects.create(
            numero_oc="300001",
            sistema_origen="ORACLE_QES",
            proveedor="Delta Corp",
            planta_original="Macimex Guanajuato",
            planta_normalizada="MACIMEX_GUANAJUATO"
        )
        LineaOC.objects.create(
            orden=orden,
            release="",
            numero_linea="1",
            codigo_articulo="MAT-22222",
            descripcion="Material Delta",
            cantidad_solicitada=150,
            cantidad_pendiente=150,
            cantidad_recibida=0,
            precio_unitario=45.00
        )
        
        # Archivo con cantidades actualizadas (recibido parcial)
        datos = [{
            'Po Number': 300001,
            'Release Number': '',
            'Line Number': 1,
            'Supplier Name': 'Delta Corp',
            'Ship To Org Name': 'Macimex Guanajuato',
            'Item': 'MAT-22222',
            'Item Description': 'Material Delta',
            'Unit Of Measure': 'PZA',
            'Quantity Ordered': 150,
            'Quantity due': 50,  # Cambió de 150 a 50
            'Quantity Received': 100,  # Cambió de 0 a 100
            'Unit Price': 45.00,
            'Status need': 'Approved',
            'Buyer Full Name': 'Jacqueline Test',
            'Authorization Status': 'APPROVED',
            'C Currency': 'MXN',
            'Rel Creation Date': '2026-11-01',
            'Need By Date': '2026-11-15',
            'Correo Proveedor': ''
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_oracle_open_po(archivo)
        
        self.assertEqual(resultado['resumen']['nuevos'], 0)
        self.assertEqual(resultado['resumen']['actualizar'], 1)
        self.assertEqual(resultado['resumen']['duplicados'], 0)
        self.assertEqual(resultado['resumen']['errores'], 0)
        
        reg = resultado['registros'][0]
        self.assertEqual(reg['estado'], 'actualizar')
        self.assertIn('cantidad_pendiente', reg['razon'])
        self.assertIn('cantidad_recibida', reg['razon'])
    
    def test_previa_errores_validacion(self):
        """Test: Detecta errores de validación (OC sin número, campos obligatorios faltantes)"""
        datos = [
            {'Po Number': '', 'Line Number': 1},  # OC vacía
            {'Po Number': None, 'Line Number': 2},  # OC nula
        ]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_oracle_open_po(archivo)
        
        self.assertEqual(resultado['resumen']['errores'], 2)
        self.assertEqual(resultado['resumen']['nuevos'], 0)
        
        for reg in resultado['registros']:
            self.assertEqual(reg['estado'], 'error')
            self.assertIn('OC', reg['razon'])
    
    def test_idempotencia_importacion(self):
        """Test: Importar el mismo archivo 2 veces no duplica registros"""
        datos = [{
            'Po Number': 400001,
            'Release Number': 1,
            'Line Number': 1,
            'Supplier Name': 'Epsilon Ltd',
            'Ship To Org Name': 'Macimex San Luis Potosí',
            'Item': 'MAT-33333',
            'Item Description': 'Material Epsilon',
            'Unit Of Measure': 'L',
            'Quantity Ordered': 300,
            'Quantity due': 300,
            'Quantity Received': 0,
            'Unit Price': 18.50,
            'Status need': 'Approved',
            'Buyer Full Name': 'Jacqueline Test',
            'Authorization Status': 'APPROVED',
            'C Currency': 'MXN',
            'Rel Creation Date': '2026-11-03',
            'Need By Date': '2026-11-18',
            'Correo Proveedor': 'contacto@epsilon.com'
        }]
        
        archivo1 = self.crear_archivo_excel(datos)
        archivo2 = self.crear_archivo_excel(datos)
        
        # Primera importación
        resumen1 = importar_oracle_open_po(archivo1, "test_user")
        self.assertEqual(resumen1['insertados_oc'], 1)
        self.assertEqual(resumen1['insertados_linea'], 1)
        
        # Segunda importación (mismo archivo)
        resumen2 = importar_oracle_open_po(archivo2, "test_user")
        self.assertEqual(resumen2['insertados_oc'], 0)  # OC ya existe
        self.assertEqual(resumen2['insertados_linea'], 0)  # Línea ya existe
        self.assertEqual(resumen2['actualizados'], 1)  # Se actualiza la línea existente
        
        # Verificar que solo existe 1 OC y 1 línea en BD
        self.assertEqual(OrdenCompra.objects.filter(numero_oc="400001").count(), 1)
        self.assertEqual(LineaOC.objects.filter(orden__numero_oc="400001").count(), 1)
    
    def test_linea_nueva_para_oc_existente(self):
        """Test: Agregar líneas nuevas a una OC que ya existe"""
        # Crear OC existente con una línea
        orden = OrdenCompra.objects.create(
            numero_oc="500001",
            sistema_origen="ORACLE_QES",
            proveedor="Zeta Supply",
            planta_normalizada="MACIMEX_SLP"
        )
        LineaOC.objects.create(
            orden=orden,
            release="1",
            numero_linea="1",
            codigo_articulo="MAT-44444",
            descripcion="Línea original",
            unidad_medida="PZA",
            cantidad_solicitada=100,
            cantidad_pendiente=100,
            cantidad_recibida=0,
            precio_unitario=10.00,
            fecha_original=pd.to_datetime('2026-11-15').date(),
            estatus_necesidad="Approved"
        )
        
        # Archivo con línea 1 (duplicada) y línea 2 (nueva)
        datos = [
            {
                'Po Number': 500001,
                'Release Number': 1,
                'Line Number': 1,
                'Supplier Name': 'Zeta Supply',
                'Ship To Org Name': 'Macimex San Luis Potosí',
                'Item': 'MAT-44444',
                'Item Description': 'Línea original',
                'Unit Of Measure': 'PZA',
                'Quantity Ordered': 100,
                'Quantity due': 100,
                'Quantity Received': 0,
                'Unit Price': 10.00,
                'Status need': 'Approved',
                'Buyer Full Name': 'Jacqueline Test',
                'Authorization Status': 'APPROVED',
                'C Currency': 'MXN',
                'Rel Creation Date': '2026-11-01',
                'Need By Date': '2026-11-15',
                'Correo Proveedor': ''
            },
            {
                'Po Number': 500001,
                'Release Number': 1,
                'Line Number': 2,  # Nueva línea
                'Supplier Name': 'Zeta Supply',
                'Ship To Org Name': 'Macimex San Luis Potosí',
                'Item': 'MAT-55555',
                'Item Description': 'Línea nueva agregada',
                'Unit Of Measure': 'PZA',
                'Quantity Ordered': 50,
                'Quantity due': 50,
                'Quantity Received': 0,
                'Unit Price': 15.00,
                'Status need': 'Approved',
                'Buyer Full Name': 'Jacqueline Test',
                'Authorization Status': 'APPROVED',
                'C Currency': 'MXN',
                'Rel Creation Date': '2026-11-01',
                'Need By Date': '2026-11-15',
                'Correo Proveedor': ''
            }
        ]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_oracle_open_po(archivo)
        
        self.assertEqual(resultado['resumen']['nuevos'], 1)
        self.assertEqual(resultado['resumen']['duplicados'], 1)
        
        # Verificar que la línea 2 se detecta como nueva
        reg_nueva = [r for r in resultado['registros'] if r['numero_linea'] == '2'][0]
        self.assertEqual(reg_nueva['estado'], 'nuevo')
        self.assertIn('Línea nueva', reg_nueva['razon'])
    
    def test_normalizacion_valores_vacios(self):
        """Test: Valores vacíos ("", None, "nan") se normalizan como iguales"""
        # Crear línea con correo vacío
        orden = OrdenCompra.objects.create(
            numero_oc="600001",
            sistema_origen="ORACLE_QES",
            proveedor="Theta Inc"
        )
        LineaOC.objects.create(
            orden=orden,
            release="",
            numero_linea="1",
            codigo_articulo="MAT-66666",
            descripcion="Test normalización",
            unidad_medida="PZA",
            cantidad_solicitada=10,
            cantidad_pendiente=10,
            cantidad_recibida=0,
            precio_unitario=5.00,
            fecha_original=pd.to_datetime('2026-11-15').date(),
            estatus_necesidad="",
            correo_proveedor=""  # Vacío en BD
        )
        
        # Archivo con correo como NaN
        datos = [{
            'Po Number': 600001,
            'Release Number': None,  # None en archivo
            'Line Number': 1,
            'Supplier Name': 'Theta Inc',
            'Ship To Org Name': 'Macimex SLP',
            'Item': 'MAT-66666',
            'Item Description': 'Test normalización',
            'Unit Of Measure': 'PZA',
            'Quantity Ordered': 10,
            'Quantity due': 10,
            'Quantity Received': 0,
            'Unit Price': 5.00,
            'Status need': '',
            'Buyer Full Name': 'Test',
            'Authorization Status': 'APPROVED',
            'C Currency': 'MXN',
            'Rel Creation Date': '2026-11-01',
            'Need By Date': '2026-11-15',
            'Correo Proveedor': float('nan')  # NaN en archivo
        }]
        
        archivo = self.crear_archivo_excel(datos)
        resultado = previsualizar_oracle_open_po(archivo)
        
        # Debe detectarse como duplicado porque los valores vacíos se normalizan
        self.assertEqual(resultado['resumen']['duplicados'], 1)
        self.assertEqual(resultado['resumen']['actualizar'], 0)
