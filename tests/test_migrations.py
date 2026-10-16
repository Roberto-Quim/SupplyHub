from django.test import TransactionTestCase
from django.db import connection, models
from django.db.migrations.executor import MigrationExecutor


class AuditMigrationCompatibilityTests(TransactionTestCase):
    def test_audit_branch_schema_preserves_source_and_inactive_records(self):
        old = ('supplyhub','0008_gmailmailbox_is_demo_gmailmailbox_retry_after_and_more')
        target = ('supplyhub','0009_auditoriaadministracion_devasignacion_devmodulo_and_more')
        executor = MigrationExecutor(connection)
        executor.migrate([old])
        apps = executor.loader.project_state([old]).apps
        Order = apps.get_model('supplyhub','OrdenCompra')
        Line = apps.get_model('supplyhub','LineaOC')
        History = apps.get_model('supplyhub','HistorialSeguimiento')
        order = Order.objects.create(numero_oc='MIG',proveedor='Synthetic',planta_original='IRA')
        line = Line.objects.create(orden=order,numero_linea='1',codigo_articulo='A',descripcion='Synthetic',cantidad_solicitada=1)
        history = History.objects.create(linea=line,respuesta_proveedor='Conservar',usuario_responsable='buyer',fuente='CORREO')
        with connection.cursor() as cursor:
            cursor.execute('ALTER TABLE supplyhub_historialseguimiento DROP COLUMN fecha_interaccion')
            cursor.execute('ALTER TABLE supplyhub_historialseguimiento DROP COLUMN estado_validacion')
            cursor.execute('ALTER TABLE supplyhub_historialseguimiento ADD COLUMN activo bool NOT NULL DEFAULT 1')
            cursor.execute('UPDATE supplyhub_historialseguimiento SET activo = 0')
        executor = MigrationExecutor(connection)
        executor.migrate([target])
        current = executor.loader.project_state([target]).apps.get_model('supplyhub','HistorialSeguimiento').objects.get(pk=history.pk)
        self.assertEqual(current.fuente,'CORREO')
        self.assertEqual(current.respuesta_proveedor,'Conservar')
        self.assertFalse(current.activo)
        self.assertIsNotNone(current.fecha_interaccion)
