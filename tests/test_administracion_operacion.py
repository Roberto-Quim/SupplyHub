from datetime import timedelta, date
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4
import pandas as pd
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, Client, override_settings, RequestFactory
from django.urls import reverse
from django.utils import timezone
from supplyhub.models import (DevPerfil, DevModulo, DevAsignacion, SupplierSite, ErrorLog,
    OrdenCompra, LineaOC, HistorialSeguimiento, RecordatorioOC, AuditoriaAdministracion)
from supplyhub.services import administracion_service as admin
from supplyhub.services.seguimiento_oc_service import registrar_interaccion_linea, anular_historial
from supplyhub.services.operacion_service import generate_reminders, approve_reminder, send_approved
from supplyhub.services.inventario_service import importar_min_max


@override_settings(DEBUG=True, SUPPLYHUB_LOCAL_AUTH_ENABLED=True, DATAANALYTICS_ENABLED=False, SUPPLYHUB_REVALIDATE_SESSION=False)
class AdministrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root = get_user_model().objects.create_superuser(username='admin-local',password='Pass12345!')
        cls.user = get_user_model().objects.create_user(username='compras',password='Pass12345!')
        cls.module = DevModulo.objects.create(nombre='RFQ',grupo='HUB',ruta='/hub/rfq-capex/')
        cls.profile = DevPerfil.objects.create(nombre='Compras')
        cls.profile.modulos.add(cls.module)

    def setUp(self):
        self.client.force_login(self.root)

    def url(self, name):
        return reverse('supplyhub:admin_'+name)

    def test_five_pages_render_without_placeholders(self):
        for name in ['usuarios','perfiles','modulos','supplier_sites','error_logs']:
            response=self.client.get(self.url(name))
            self.assertEqual(response.status_code,200,name)
            self.assertNotContains(response,'CRUD se implementará')

    def test_normal_user_cannot_enter_any_admin_page(self):
        self.client.force_login(self.user)
        for name in ['usuarios','perfiles','modulos','supplier_sites','error_logs']:
            self.assertEqual(self.client.get(self.url(name)).status_code,403)
        response=self.client.get('/')
        self.assertNotContains(response,'Log de Errores')

    @override_settings(DEBUG=False)
    def test_local_store_never_used_in_production(self):
        self.assertEqual(self.client.get(self.url('usuarios')).status_code,403)

    def test_create_independent_assignments_and_reject_duplicate(self):
        data=dict(nomina='12345',correo='persona@example.invalid',perfil=self.profile.pk,metodo=1)
        self.assertEqual(self.client.post(self.url('usuarios'),data).status_code,302)
        self.assertEqual(self.client.post(self.url('usuarios'),data).status_code,200)
        data['metodo']=3
        self.assertEqual(self.client.post(self.url('usuarios'),data).status_code,302)
        self.assertEqual(DevAsignacion.objects.count(),2)
        self.assertEqual(AuditoriaAdministracion.objects.filter(entidad='Usuario').count(),2)

    def test_edit_assignment_preserves_identity_and_state(self):
        item=DevAsignacion.objects.create(nomina='12345',correo='a@example.invalid',perfil=self.profile,metodo=1)
        response=self.client.post(reverse('supplyhub:admin_usuarios_editar',args=[item.pk]),dict(nomina='66666',correo='changed@example.invalid',perfil=self.profile.pk,metodo=3))
        self.assertEqual(response.status_code,302)
        item.refresh_from_db()
        self.assertEqual(item.nomina,'12345')
        self.assertEqual(item.correo,'a@example.invalid')
        self.assertEqual(item.metodo,3)
        self.client.post(self.url('usuarios'),dict(action='state',record_id=item.pk,active='0'))
        item.refresh_from_db();self.assertFalse(item.activo)

    def test_profile_assignments_replace_atomically(self):
        result=self.client.post(reverse('supplyhub:admin_perfiles_editar',args=[self.profile.pk]),dict(nombre='Compras actualizadas',modulos=[self.module.pk]))
        self.assertEqual(result.status_code,302)
        self.profile.refresh_from_db();self.assertEqual(self.profile.nombre,'Compras actualizadas')
        self.assertEqual(list(self.profile.modulos.all()),[self.module])
        result=self.client.post(reverse('supplyhub:admin_perfiles_editar',args=[self.profile.pk]),dict(nombre='No guardar',modulos=[99999]))
        self.assertEqual(result.status_code,200)
        self.profile.refresh_from_db();self.assertEqual(self.profile.nombre,'Compras actualizadas')

    def test_modules_create_edit_state_and_protected_routes(self):
        self.assertEqual(self.client.post(self.url('modulos'),dict(nombre='OC',grupo='HUB',ruta='/hub/seguimiento-oc/',orden=2)).status_code,302)
        item=DevModulo.objects.get(nombre='OC')
        self.assertEqual(self.client.post(reverse('supplyhub:admin_modulos_editar',args=[item.pk]),dict(nombre='Seguimiento OC',grupo='HUB',ruta=item.ruta,orden=3)).status_code,302)
        self.client.post(self.url('modulos'),dict(action='state',record_id=item.pk,active='0'))
        item.refresh_from_db();self.assertFalse(item.activo)
        protected=DevModulo.objects.create(nombre='Usuarios',grupo='Administración',ruta='/administracion/usuarios/')
        response=self.client.post(self.url('modulos'),dict(action='state',record_id=protected.pk,active='0'))
        self.assertContains(response,'administrativo base')
        protected.refresh_from_db();self.assertTrue(protected.activo)

    def test_external_route_rejected(self):
        response=self.client.post(self.url('modulos'),dict(nombre='Enlace',grupo='HUB',ruta='https://evil.invalid/',orden=1))
        self.assertEqual(response.status_code,200)
        self.assertFalse(DevModulo.objects.filter(nombre='Enlace').exists())

    def test_supplier_site_crud_filter_and_case_insensitive_duplicate(self):
        data=dict(proveedor='Proveedor',codigo='SITE1',planta='MAQ_RA',correo='sales@example.invalid')
        self.assertEqual(self.client.post(self.url('supplier_sites'),data).status_code,302)
        site=SupplierSite.objects.get()
        data['proveedor']='PROVEEDOR'
        self.assertEqual(self.client.post(self.url('supplier_sites'),data).status_code,200)
        self.assertEqual(SupplierSite.objects.count(),1)
        data['contacto']='Contacto compras'
        self.assertEqual(self.client.post(reverse('supplyhub:admin_supplier_sites_editar',args=[site.pk]),data).status_code,302)
        self.assertContains(self.client.get(self.url('supplier_sites'),{'q':'SITE1'}),'Contacto compras')
        self.client.post(self.url('supplier_sites'),dict(action='state',record_id=site.pk,active='0'))
        site.refresh_from_db();self.assertFalse(site.activo)

    def test_error_log_readonly_dates_and_escaped_content(self):
        item=ErrorLog.objects.create(referencia=uuid4(),origen='HTTP',mensaje='<script>alert(1)</script>')
        response=self.client.get(self.url('error_logs'))
        self.assertContains(response,'&lt;script&gt;')
        self.assertNotContains(response,'<script>alert(1)</script>')
        self.assertEqual(self.client.post(self.url('error_logs'),dict(action='delete',record_id=item.pk)).status_code,405)
        self.assertEqual(ErrorLog.objects.count(),1)
        response=self.client.get(self.url('error_logs'),{'fecha_inicio':'2026-12-31','fecha_fin':'2026-01-01'})
        self.assertContains(response,'fecha inicial')

    def test_csrf_required_for_writes(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.root)
        self.assertEqual(client.post(self.url('perfiles'),{'nombre':'Sin CSRF'}).status_code,403)
        self.assertFalse(DevPerfil.objects.filter(nombre='Sin CSRF').exists())

    @override_settings(DATAANALYTICS_ENABLED=True)
    @patch('supplyhub.services.administracion_service.can_access_route',return_value=True)
    @patch('supplyhub.services.administracion_service.users.profile_can_manage',return_value=True)
    @patch('supplyhub.services.administracion_service.users.is_ti_profile',return_value=False)
    def test_error_log_denies_admin_even_with_route(self,*mocks):
        session=self.client.session;session['sh_id_perfil']=2;session.save()
        self.assertEqual(self.client.get(self.url('error_logs')).status_code,403)

    @override_settings(DATAANALYTICS_ENABLED=True)
    @patch('supplyhub.services.administracion_service.can_access_route',return_value=True)
    @patch('supplyhub.services.administracion_service.users.profile_can_manage',return_value=True)
    @patch('supplyhub.services.administracion_service.check_connection',side_effect=RuntimeError('secret-token'))
    def test_central_failure_has_no_local_fallback_or_secret(self,*mocks):
        response=self.client.get(self.url('usuarios'))
        self.assertContains(response,'No se utilizará una copia local')
        self.assertNotContains(response,'secret-token')
        self.assertTrue(ErrorLog.objects.filter(origen='Administración.usuarios').exists())

    @override_settings(DATAANALYTICS_ENABLED=True)
    @patch('supplyhub.services.administracion_service.assignments.create_assignment',return_value=(51,''))
    def test_central_assignment_uses_real_dataanalytics_service(self,save):
        request=RequestFactory().post('/');request.user=self.root;request.session={'sh_id_perfil':7}
        admin.save_assignment(request,dict(nomina='123',correo='a@example.invalid',perfil=4,metodo=1))
        save.assert_called_once_with('123','a@example.invalid',4,1,actor_id_perfil=7)
        self.assertFalse(DevAsignacion.objects.exists())


@override_settings(DEBUG=True,DATAANALYTICS_ENABLED=False,SUPPLYHUB_LOCAL_AUTH_ENABLED=True)
class TrackingOperationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=get_user_model().objects.create_user(username='buyer',password='Pass12345!')

    def setUp(self):
        self.client.force_login(self.user)
        self.order=OrdenCompra.objects.create(numero_oc='100',proveedor='Proveedor',planta_original='IRA',planta_normalizada='MAQ_RA',comprador='Tannia')
        self.line=LineaOC.objects.create(orden=self.order,release='1',numero_linea='1',codigo_articulo='ART1',descripcion='Pieza',cantidad_solicitada=10,cantidad_pendiente=10,correo_proveedor='sales@example.invalid')

    def test_history_cancel_preserves_source_and_recalculates_comment(self):
        first=registrar_interaccion_linea(self.line,'Primera','buyer',date(2026,11,1))
        second=registrar_interaccion_linea(self.line,'Segunda','buyer',fecha_revisada=date(2026,11,2),fuente='CORREO')
        anular_historial(self.line.pk,second.pk,'buyer','Fecha equivocada')
        second.refresh_from_db();self.line.refresh_from_db()
        self.assertFalse(second.activo);self.assertEqual(second.fuente,'CORREO')
        self.assertEqual(self.line.comentario_actual,'Primera');self.assertEqual(self.line.fecha_revisada,date(2026,11,1))
        self.assertEqual(HistorialSeguimiento.objects.count(),2)
        anular_historial(self.line.pk,first.pk,'buyer','Duplicada')
        self.line.refresh_from_db();self.assertIsNone(self.line.fecha_revisada)

    def test_cancel_older_then_newer_never_restores_annulled_date(self):
        first=registrar_interaccion_linea(self.line,'Primera','buyer',date(2026,11,1))
        second=registrar_interaccion_linea(self.line,'Segunda','buyer',date(2026,11,2))
        anular_historial(self.line.pk,first.pk,'buyer','Incorrecta')
        anular_historial(self.line.pk,second.pk,'buyer','Incorrecta')
        self.line.refresh_from_db()
        self.assertIsNone(self.line.fecha_revisada)
        self.assertEqual(self.line.comentario_actual,'')

    def test_cannot_cancel_history_through_another_order(self):
        other=OrdenCompra.objects.create(numero_oc='200',proveedor='Otro',planta_original='IRA')
        hist=registrar_interaccion_linea(self.line,'Texto','buyer')
        response=self.client.post(reverse('supplyhub:anular_historial',args=[other.pk,hist.pk]),{'motivo':'No'})
        self.assertEqual(response.status_code,404)
        self.assertEqual(self.client.get(reverse('supplyhub:anular_historial',args=[self.order.pk,hist.pk])).status_code,405)
        hist.refresh_from_db();self.assertTrue(hist.activo)

    def test_reminder_daily_idempotency_and_tenango_exclusion(self):
        now=timezone.now()
        self.assertEqual(generate_reminders(now),1)
        self.assertEqual(generate_reminders(now+timedelta(minutes=1)),0)
        self.assertEqual(generate_reminders(now+timedelta(hours=24)),1)
        self.order.planta_normalizada='MACIMEX_TENANGO';self.order.save()
        self.assertEqual(generate_reminders(now+timedelta(hours=48)),0)

    @override_settings(REMINDERS_SEND_ENABLED=True,DEFAULT_FROM_EMAIL='supply@example.invalid',EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_only_approved_sent_once(self):
        generate_reminders()
        self.assertEqual(send_approved(),0)
        item=RecordatorioOC.objects.get();self.assertTrue(approve_reminder(item.pk,'buyer'))
        self.assertEqual(send_approved(),1);self.assertEqual(send_approved(),0)
        from django.core import mail
        self.assertEqual(len(mail.outbox),1)
        self.assertEqual(mail.outbox[0].to,['sales@example.invalid'])

    @override_settings(REMINDERS_SEND_ENABLED=True,DEFAULT_FROM_EMAIL='supply@example.invalid')
    @patch('supplyhub.services.operacion_service.send_mail',side_effect=RuntimeError('secret-token'))
    def test_failed_smtp_not_retried_without_review(self,send):
        generate_reminders();item=RecordatorioOC.objects.get();approve_reminder(item.pk,'buyer')
        self.assertEqual(send_approved(),0);self.assertEqual(send_approved(),0)
        send.assert_called_once();item.refresh_from_db();self.assertEqual(item.estado,'FALLIDO')
        self.assertNotIn('secret-token',item.ultimo_error)

    @override_settings(REMINDERS_SEND_ENABLED=True,DEFAULT_FROM_EMAIL='supply@example.invalid')
    @patch('supplyhub.services.operacion_service.send_mail')
    def test_changing_recipient_invalidates_previous_approval(self,send):
        generate_reminders();item=RecordatorioOC.objects.get();approve_reminder(item.pk,'buyer')
        self.line.correo_proveedor='changed@example.invalid';self.line.save()
        self.assertEqual(send_approved(),0)
        send.assert_not_called();item.refresh_from_db();self.assertEqual(item.estado,'OMITIDO')

    def test_supplier_site_matching_and_no_cross_plant_assignment(self):
        site=SupplierSite.objects.create(proveedor='Proveedor',codigo='MX',planta='TENANGO')
        url=reverse('supplyhub:asignar_supplier_site',args=[self.order.pk])
        self.client.post(url,{'site_id':site.pk});self.order.refresh_from_db();self.assertIsNone(self.order.supplier_site)
        site.planta='MAQ_RA';site.save();self.client.post(url,{'site_id':site.pk});self.order.refresh_from_db();self.assertEqual(self.order.supplier_site,'MX')

    def test_minmax_aggregates_stock_by_item_and_plant(self):
        data=pd.DataFrame([dict(Planta='IRA',Item='ART1',**{'On Hand':2,'Minimo':1,'Maximo':10}),dict(Planta='IRA',Item='ART1',**{'On Hand':3,'Minimo':1,'Maximo':10}),dict(Planta='TENANGO',Item='ART1',**{'On Hand':99,'Minimo':1,'Maximo':10})])
        file=BytesIO();data.to_excel(file,sheet_name='Data',index=False);file.seek(0)
        self.assertEqual(importar_min_max(file)['actualizados'],1)
        self.line.refresh_from_db();self.assertEqual(self.line.stock,5);self.assertEqual(self.line.min_max,'1 / 10')

    def test_edit_history_keeps_original_and_records_correction(self):
        original=registrar_interaccion_linea(self.line,'Texto equivocado','original',date(2026,11,1),fuente='CORREO')
        url=reverse('supplyhub:editar_historial',args=[self.order.pk,original.pk])
        self.assertContains(self.client.get(url),'Texto equivocado')
        response=self.client.post(url,{'respuesta_proveedor':'Texto corregido','fecha_revisada_propuesta':'2026-11-02','motivo':'Error de captura'})
        self.assertEqual(response.status_code,302)
        original.refresh_from_db();self.line.refresh_from_db()
        self.assertFalse(original.activo);self.assertEqual(original.respuesta_proveedor,'Texto equivocado')
        self.assertEqual(original.fuente,'CORREO');self.assertEqual(original.usuario_responsable,'original')
        new=HistorialSeguimiento.objects.get(activo=True)
        self.assertEqual(new.usuario_responsable,'buyer');self.assertEqual(new.respuesta_proveedor,'Texto corregido')
        self.assertIn(str(new.pk),original.motivo_anulacion)
        self.assertEqual(self.line.fecha_revisada,date(2026,11,2))

    def test_history_edit_rejects_invalid_dates_and_other_order(self):
        original=registrar_interaccion_linea(self.line,'Original','buyer')
        url=reverse('supplyhub:editar_historial',args=[self.order.pk,original.pk])
        self.assertEqual(self.client.post(url,{'respuesta_proveedor':'No guardar','fecha_revisada_propuesta':'incorrecta','motivo':'Error'}).status_code,200)
        original.refresh_from_db();self.assertTrue(original.activo)
        other=OrdenCompra.objects.create(numero_oc='OTHER',proveedor='Otro',planta_original='IRA')
        self.assertEqual(self.client.get(reverse('supplyhub:editar_historial',args=[other.pk,original.pk])).status_code,404)
        self.assertEqual(HistorialSeguimiento.objects.count(),1)

    def test_failed_correction_rolls_back_annulment(self):
        from supplyhub.services.seguimiento_oc_service import corregir_historial
        original=registrar_interaccion_linea(self.line,'Original','buyer')
        with self.assertRaises(ValidationError):
            corregir_historial(self.line.pk,original.pk,'buyer','',None,'Error')
        original.refresh_from_db();self.assertTrue(original.activo)
        self.assertEqual(HistorialSeguimiento.objects.count(),1)

    def test_invalid_record_ids_are_not_server_errors(self):
        response=self.client.post(reverse('supplyhub:asignar_supplier_site',args=[self.order.pk]),{'site_id':'bad'})
        self.assertEqual(response.status_code,404)
        response=self.client.post(reverse('supplyhub:recordatorios'),{'record_id':'bad','action':'approve'})
        self.assertEqual(response.status_code,404)
        response=self.client.post(reverse('supplyhub:seguimiento_oc_detalle',args=[self.order.pk]),{'linea_id':'bad','respuesta_proveedor':'Texto'})
        self.assertEqual(response.status_code,404)

    def test_buyer_filter_and_reminder_screen(self):
        response=self.client.get(reverse('supplyhub:seguimiento_oc'),{'comprador':'Tannia'})
        self.assertContains(response,'100')
        response=self.client.get(reverse('supplyhub:seguimiento_oc'),{'comprador':'Otro'})
        self.assertNotContains(response,'Ver Detalle')
        self.assertEqual(self.client.get(reverse('supplyhub:recordatorios')).status_code,200)

class CentralSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=get_user_model().objects.create_user(username='corporate')

    @override_settings(DATAANALYTICS_ENABLED=True,SUPPLYHUB_REVALIDATE_SESSION=True)
    @patch('supplyhub.services.dataanalytics_access_service.validate_user',return_value=(0,0))
    def test_revoked_assignment_logs_out_existing_session(self,validate):
        self.client.force_login(self.user)
        session=self.client.session
        session.update({'sh_id_usuario':18,'sh_id_perfil':2,'sh_no_nomina':'12345','sh_metodo_acceso':3})
        session.save()
        response=self.client.get(reverse('supplyhub:seguimiento_oc'))
        self.assertEqual(response.status_code,302)
        self.assertNotIn('_auth_user_id',self.client.session)
        validate.assert_called_once_with(1,no_nomina='12345',correo=None,metodo_acceso=3)

    @patch('supplyhub.services.da_admin.dataanalytics_user_admin_service.get_user_by_id',return_value={'activo':True,'id_perfil':2,'correo':'a@example.invalid','no_nomina':'738210'})
    def test_assignment_id_never_used_as_payroll(self,lookup):
        from supplyhub.services.dataanalytics_access_service import resolve_assignment_payroll,corporate_username
        self.assertEqual(resolve_assignment_payroll(18,2,correo='a@example.invalid'),'738210')
        self.assertEqual(resolve_assignment_payroll(18,2,correo='other@example.invalid'),'')
        self.assertEqual(corporate_username(id_usuario=18,no_nomina=''),'')

    @override_settings(DATAANALYTICS_ENABLED=True)
    @patch('supplyhub.services.administracion_service.users.is_ti_profile',return_value=False)
    @patch('supplyhub.services.administracion_service.profiles.update_profile')
    def test_admin_cannot_rename_regular_profile_to_ti(self,save,is_ti):
        request=RequestFactory().post('/');request.user=self.user;request.session={'sh_id_perfil':2}
        with self.assertRaises(ValidationError):
            admin.save_profile(request,{'nombre':'TI','modulos':[]},pk=3)
        save.assert_not_called()

    @override_settings(DATAANALYTICS_ENABLED=True)
    @patch('supplyhub.services.menu_service.get_allowed_routes',return_value={'/hub/rfq-capex/','/administracion/usuarios/'})
    @patch('supplyhub.services.da_admin.dataanalytics_modulos_service.list_modulos',return_value=[{'id_modulo':1,'modulo':'Compras','orden':2,'activo':True}])
    @patch('supplyhub.services.da_admin.dataanalytics_modulos_service.list_submodulos',return_value=[{'id_modulo':1,'submodulo':'Solicitudes CAPEX','ruta':'/hub/rfq-capex/','orden':3,'activo':True}])
    def test_menu_uses_names_order_and_routes_from_central_catalog(self,*mocks):
        from supplyhub.services.menu_service import build_menu
        menu=build_menu(2)
        self.assertEqual(menu[0]['label'],'Compras')
        self.assertEqual(menu[0]['children'][0]['label'],'Solicitudes CAPEX')
        self.assertEqual(menu[0]['children'][0]['route'],'/hub/rfq-capex/')

    @override_settings(DATAANALYTICS_ENABLED=True)
    def test_real_service_rolls_back_profile_on_permission_failure(self):
        from unittest.mock import MagicMock
        from supplyhub.services.da_admin import dataanalytics_perfiles_service as profiles
        connection=MagicMock();cursor=connection.cursor.return_value
        cursor.fetchone.side_effect=[(1,), (0,)]
        with patch.object(profiles,'_get_conn',return_value=connection),patch.object(admin.users,'can_actor_modify_profile',return_value=True),patch.object(profiles,'_set_perfil_submodulos',side_effect=RuntimeError('synthetic')):
            ok,error=profiles.update_profile(3,'Compras',[1],actor_id_perfil=2)
        self.assertFalse(ok)
        connection.rollback.assert_called_once()
        connection.commit.assert_not_called()
        connection.close.assert_called_once()
        self.assertNotIn('synthetic',error)

    @override_settings(DATAANALYTICS_ENABLED=True)
    def test_real_module_service_uses_parameters_and_closes_connection(self):
        from unittest.mock import MagicMock
        from supplyhub.services.da_admin import dataanalytics_modulos_service as modules
        connection=MagicMock();cursor=connection.cursor.return_value
        cursor.fetchone.side_effect=[(0,), (42,)]
        name="Compras ' ; DROP TABLE X; --"
        with patch.object(modules,'_get_conn',return_value=connection):
            result,error=modules.create_modulo(name,'#',2)
        self.assertEqual(result,42)
        for call in cursor.execute.call_args_list:
            self.assertNotIn(name,call.args[0])
        self.assertEqual(cursor.execute.call_args_list[-1].args[1],(None,name,'#',2))
        connection.commit.assert_called_once();connection.close.assert_called_once()


class RFQRegressionTests(TestCase):
    def test_selected_supplier_saved_even_without_decision_change(self):
        from supplyhub.models import RFQCapex, HistorialDecisionRFQ
        from supplyhub.services.rfq_capex_service import change_decision
        obj=RFQCapex.objects.create(rfq='200',descripcion='Synthetic',solicitante='Synthetic',planta='MAQ_RA')
        change_decision(instance=obj,new_decision='PENDIENTE',actor='buyer',selected_supplier='Proveedor')
        obj.refresh_from_db()
        self.assertEqual(obj.proveedor_seleccionado,'Proveedor')
        self.assertEqual(HistorialDecisionRFQ.objects.filter(rfq=obj).count(),1)

    def test_import_preserves_creator_and_audits_status(self):
        from supplyhub.models import RFQCapex, HistorialEstadoRFQ
        from supplyhub.services.importacion_rfq_service import importar_rfq_capex_excel
        def file(status):
            output=BytesIO()
            pd.DataFrame({'RFQ':[200], 'DESCRIPCION':['Equipo'], 'SOLICITANTE':['Edith'], 'PLANTA':['Ramos'], 'ESTATUS':[status]}).to_excel(output,index=False)
            output.seek(0);return output
        self.assertEqual(importar_rfq_capex_excel(file('Solicitada'),'first')['insertados'],1)
        self.assertEqual(importar_rfq_capex_excel(file('Concluida'),'second')['actualizados'],1)
        obj=RFQCapex.objects.get(rfq='200')
        self.assertEqual(obj.creado_por,'first');self.assertEqual(obj.estado,'CONCLUIDA')
        self.assertTrue(HistorialEstadoRFQ.objects.filter(rfq=obj,estado_nuevo='CONCLUIDA').exists())
