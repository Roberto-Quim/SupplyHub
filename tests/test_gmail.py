import base64
import json
import os
import time
from unittest.mock import patch
from datetime import date
from cryptography.fernet import Fernet
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from supplyhub.models import GmailMailbox, GmailResponse, OrdenCompra, LineaOC, HistorialSeguimiento
from supplyhub.services import gmail_service as gmail
from supplyhub.security.encryption_fernet import _get_fernet, decrypt_text

@override_settings(GMAIL_ENABLED=True,GMAIL_CLIENT_ID='client',GMAIL_CLIENT_SECRET='secret',GMAIL_REDIRECT_URI='http://127.0.0.1:8000/hub/correos/callback/',DATAANALYTICS_ENABLED=False)
class GmailTests(TestCase):
    def setUp(self):
        self.owner=get_user_model().objects.create_user(username='buyer')
        self.other=get_user_model().objects.create_user(username='other')
        self.client.force_login(self.owner)
        self.mailbox=GmailMailbox.objects.create(owner=self.owner,email='buyer@questum.com',encrypted_tokens='test')
        self.oc=OrdenCompra.objects.create(numero_oc='12345',proveedor='Proveedor',planta_original='Mac Ra',planta_normalizada='MAQ_RA')
        self.line=LineaOC.objects.create(orden=self.oc,numero_linea='1',release='2',codigo_articulo='A',descripcion='Pieza',cantidad_solicitada=2,correo_proveedor='supplier@example.com')

    def message(self,sender='supplier@example.com',body='OC 12345: entrega el viernes',mid='m1'):
        return {'id':mid,'internalDate':'1792000000000','labelIds':['INBOX'],'payload':{'mimeType':'text/plain','headers':[{'name':'From','value':sender},{'name':'Subject','value':'Seguimiento OC 12345'}],'body':{'data':base64.urlsafe_b64encode(body.encode()).decode()}}}

    def pending(self):
        self.assertTrue(gmail.ingest(self.mailbox,self.message()))
        return GmailResponse.objects.get()

    def test_internal_domains_and_multiple_senders_rejected(self):
        for sender in ['A <a@questum.com>','A <a@sub.questum.com>','a@questum.com, supplier@example.com']:
            self.assertIsNone(gmail.external_sender(sender))
            self.assertFalse(gmail.ingest(self.mailbox,self.message(sender)))
        self.assertEqual(gmail.external_sender('Questum <supplier@example.com>'),'supplier@example.com')

    def test_known_supplier_reference_and_deduplication(self):
        response=self.pending()
        self.assertIn(self.line,response.candidates.all())
        self.assertFalse(gmail.ingest(self.mailbox,self.message()))
        self.assertFalse(gmail.ingest(self.mailbox,self.message('unknown@example.com',mid='unknown')))
        message=self.message(mid='no-reference')
        message['payload']['headers'][1]['value']='Hola'
        message['payload']['body']['data']=base64.urlsafe_b64encode(b'Hola').decode()
        self.assertFalse(gmail.ingest(self.mailbox,message))

    def test_quoted_internal_content_is_not_used(self):
        self.assertEqual(gmail.new_content('Confirmado\nEl lunes escribió:\nOC 12345'),'Confirmado')
        message=self.message(body='Hola\n> OC 12345')
        message['payload']['headers'][1]['value']='Sin referencia'
        self.assertFalse(gmail.ingest(self.mailbox,message))

    def test_tenango_and_sent_ignored(self):
        message=self.message()
        message['labelIds']=['SENT']
        self.assertFalse(gmail.ingest(self.mailbox,message))
        self.oc.planta_normalizada='MACIMEX_TENANGO'
        self.oc.save()
        self.assertFalse(gmail.ingest(self.mailbox,self.message()))

    def test_apply_once_records_email_and_date(self):
        response=self.pending()
        history=gmail.apply_response(response.pk,self.owner,self.line.pk,'Confirmado',date(2026,11,1))
        self.assertEqual(history.fuente,'CORREO')
        self.line.refresh_from_db()
        self.assertEqual(self.line.fecha_revisada,date(2026,11,1))
        with self.assertRaises(gmail.GmailError):
            gmail.apply_response(response.pk,self.owner,self.line.pk,'Otra')
        self.assertEqual(HistorialSeguimiento.objects.count(),1)

    def test_review_other_owner_and_invalid_line(self):
        response=self.pending()
        with self.assertRaises(GmailResponse.DoesNotExist):
            gmail.apply_response(response.pk,self.other,self.line.pk,'No')
        with self.assertRaises(gmail.GmailError):
            gmail.apply_response(response.pk,self.owner,9999,'No')
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse('supplyhub:gmail_index')),'supplier@example.com')
        self.assertEqual(self.client.post(reverse('supplyhub:gmail_sync',args=[self.mailbox.pk])).status_code,404)
        self.assertEqual(self.client.post(reverse('supplyhub:gmail_review',args=[response.pk]),{'action':'dismiss'}).status_code,404)

    @patch('supplyhub.services.gmail_service.connect')
    def test_oauth_state_required_expiring_and_single_use(self,connect):
        url=reverse('supplyhub:gmail_callback')
        self.client.get(url,{'state':'wrong','code':'code'})
        connect.assert_not_called()
        session=self.client.session
        session['gmail_oauth']={'state':'valid','at':time.time(),'user':self.owner.pk}
        session.save()
        self.client.get(url,{'state':'valid','code':'code'})
        connect.assert_called_once_with(self.owner,'code')
        self.client.get(url,{'state':'valid','code':'code'})
        self.assertEqual(connect.call_count,1)

    @patch('supplyhub.services.gmail_service.access_token',return_value='access')
    @patch('supplyhub.services.gmail_service.http')
    def test_sync_pagination_no_duplicate(self,http,token):
        http.side_effect=[{'messages':[{'id':'m1'}],'nextPageToken':'next'},self.message(),{'messages':[]}]
        self.assertEqual(gmail.sync(self.mailbox),1)
        self.assertEqual(http.call_args.kwargs['params']['pageToken'],'next')
        http.side_effect=[{'messages':[{'id':'m1'}]}]
        self.assertEqual(gmail.sync(self.mailbox),0)

    @patch('supplyhub.services.gmail_service.http')
    def test_connection_tokens_encrypted_and_owner_protected(self,http):
        self.mailbox.delete()
        key=Fernet.generate_key().decode()
        with patch.dict(os.environ,{'APP_ENCRYPTION_ENABLED':'True','APP_ENCRYPTION_KEY':key}):
            _get_fernet.cache_clear()
            tokens={'scope':gmail.SCOPE,'access_token':'access','refresh_token':'sensitive-refresh'}
            http.side_effect=[tokens,{'emailAddress':'buyer@questum.com'}]
            mailbox=gmail.connect(self.owner,'code')
            self.assertNotIn('sensitive-refresh',mailbox.encrypted_tokens)
            self.assertEqual(json.loads(decrypt_text(mailbox.encrypted_tokens))['refresh_token'],'sensitive-refresh')
            http.side_effect=[tokens,{'emailAddress':'buyer@questum.com'}]
            with self.assertRaises(gmail.GmailError):
                gmail.connect(self.other,'code')
        _get_fernet.cache_clear()

    def test_review_invalid_date_and_disconnect(self):
        response=self.pending()
        self.client.post(reverse('supplyhub:gmail_review',args=[response.pk]),{'line_id':self.line.pk,'comment':'Hola','revised_date':'bad'})
        self.assertFalse(HistorialSeguimiento.objects.exists())
        self.client.post(reverse('supplyhub:gmail_disconnect',args=[self.mailbox.pk]))
        self.mailbox.refresh_from_db()
        self.assertEqual(self.mailbox.encrypted_tokens,'')
        self.assertTrue(GmailResponse.objects.exists())

    @override_settings(GMAIL_ENABLED=False)
    def test_unconfigured_connection_fails_without_redirect_to_google(self):
        response=self.client.post(reverse('supplyhub:gmail_start'))
        self.assertRedirects(response,reverse('supplyhub:gmail_index'))
        self.assertNotIn('gmail_oauth',self.client.session)

    def test_supplier_email_can_be_registered_and_internal_rejected(self):
        url=reverse('supplyhub:gmail_supplier_email',args=[self.line.pk])
        self.client.post(url,{'email':'new@example.com'})
        self.line.refresh_from_db()
        self.assertEqual(self.line.correo_proveedor,'new@example.com')
        self.client.post(url,{'email':'internal@questum.com'})
        self.line.refresh_from_db()
        self.assertEqual(self.line.correo_proveedor,'new@example.com')

    @patch('supplyhub.services.gmail_service.connect')
    def test_expired_oauth_state_rejected(self,connect):
        session=self.client.session
        session['gmail_oauth']={'state':'old','at':time.time()-700,'user':self.owner.pk}
        session.save()
        self.client.get(reverse('supplyhub:gmail_callback'),{'state':'old','code':'code'})
        connect.assert_not_called()
