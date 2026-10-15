from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from supplyhub.models import GmailMailbox, GmailResponse, GmailSyncRun, HistorialSeguimiento
from supplyhub.services import gmail_service as gmail

@override_settings(DATAANALYTICS_ENABLED=False)
class OperationsTests(TestCase):
    def setUp(self):
        self.owner=get_user_model().objects.create_user(username='demo-buyer')
        self.other=get_user_model().objects.create_user(username='another')
        self.mailbox=GmailMailbox.objects.create(owner=self.owner,email='buyer@questum.com',encrypted_tokens='encrypted')
        self.client.force_login(self.owner)

    @patch('supplyhub.services.gmail_service._sync',return_value=2)
    def test_success_is_logged_and_lock_released(self,sync):
        self.assertEqual(gmail.sync(self.mailbox),2)
        run=GmailSyncRun.objects.get()
        self.assertEqual(run.status,'SUCCESS')
        self.assertEqual(run.added,2)
        self.assertIsNotNone(run.finished_at)
        self.mailbox.refresh_from_db()
        self.assertIsNone(self.mailbox.sync_started)
        self.assertIsNone(self.mailbox.retry_after)

    @patch('supplyhub.services.gmail_service._sync',side_effect=gmail.GmailError('Provider error'))
    def test_failure_logged_and_immediate_retry_blocked(self,sync):
        with self.assertRaises(gmail.GmailError):
            gmail.sync(self.mailbox)
        run=GmailSyncRun.objects.get()
        self.assertEqual(run.status,'FAILED')
        self.mailbox.refresh_from_db()
        self.assertGreater(self.mailbox.retry_after,timezone.now())
        with self.assertRaisesMessage(gmail.GmailError,'Espera un minuto'):
            gmail.sync(self.mailbox)
        self.assertEqual(sync.call_count,1)
        self.assertEqual(GmailSyncRun.objects.count(),1)
        self.mailbox.retry_after=timezone.now()-timedelta(seconds=1)
        self.mailbox.save()
        sync.side_effect=None
        sync.return_value=0
        gmail.sync(self.mailbox)
        self.assertEqual(GmailSyncRun.objects.count(),2)
        self.mailbox.refresh_from_db()
        self.assertIsNone(self.mailbox.retry_after)

    @patch('supplyhub.services.gmail_service._sync')
    def test_concurrent_run_is_blocked(self,sync):
        self.mailbox.sync_started=timezone.now()
        self.mailbox.save()
        with self.assertRaisesMessage(gmail.GmailError,'consulta en curso'):
            gmail.sync(self.mailbox)
        sync.assert_not_called()

    @patch('supplyhub.services.gmail_service._sync',return_value=0)
    def test_stale_run_recovered(self,sync):
        self.mailbox.sync_started=timezone.now()-timedelta(minutes=31)
        self.mailbox.save()
        stale=GmailSyncRun.objects.create(mailbox=self.mailbox)
        gmail.sync(self.mailbox)
        stale.refresh_from_db()
        self.assertEqual(stale.status,'FAILED')
        self.assertIsNotNone(stale.finished_at)
        self.assertEqual(GmailSyncRun.objects.filter(status='SUCCESS').count(),1)

    @patch('supplyhub.services.gmail_service._sync',side_effect=RuntimeError('secret-token=do-not-log'))
    def test_unexpected_exception_does_not_leak(self,sync):
        with self.assertRaises(gmail.GmailError):
            gmail.sync(self.mailbox)
        self.assertNotIn('do-not-log',GmailSyncRun.objects.get().error)

    @patch('supplyhub.services.gmail_service._sync')
    def test_disconnected_and_demo_mailboxes_cannot_sync(self,sync):
        self.mailbox.encrypted_tokens=''
        self.mailbox.save()
        with self.assertRaises(gmail.GmailError):
            gmail.sync(self.mailbox)
        self.mailbox.is_demo=True
        self.mailbox.encrypted_tokens='token'
        self.mailbox.save()
        with self.assertRaises(gmail.GmailError):
            gmail.sync(self.mailbox)
        sync.assert_not_called()

    def test_dashboard_history_is_owner_scoped(self):
        GmailSyncRun.objects.create(mailbox=self.mailbox,status='FAILED',error='Owner-only history')
        self.assertContains(self.client.get(reverse('supplyhub:gmail_index')),'Owner-only history')
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse('supplyhub:gmail_index')),'Owner-only history')

    @override_settings(DEBUG=True)
    def test_demo_idempotent_and_reviewable_without_google(self):
        for _ in range(2):
            call_command('seed_supplyhub_demo',username=self.owner.username,stdout=StringIO())
        mailbox=GmailMailbox.objects.get(is_demo=True)
        self.assertEqual(GmailResponse.objects.filter(mailbox=mailbox).count(),2)
        self.assertEqual(mailbox.encrypted_tokens,'')
        response=GmailResponse.objects.filter(mailbox=mailbox).first()
        history=gmail.apply_response(response.pk,self.owner,response.candidates.get().pk,'Respuesta de prueba')
        self.assertEqual(history.fuente,'CORREO')
        call_command('seed_supplyhub_demo',username=self.owner.username,stdout=StringIO())
        response.refresh_from_db()
        self.assertEqual(response.status,'APPLIED')
        self.assertEqual(HistorialSeguimiento.objects.count(),1)
        self.assertContains(self.client.get(reverse('supplyhub:gmail_index')),'DEMOSTRACIÓN')

    @override_settings(DEBUG=False)
    def test_demo_disabled_in_production(self):
        with self.assertRaises(CommandError):
            call_command('seed_supplyhub_demo',username=self.owner.username,stdout=StringIO())
        self.assertFalse(GmailMailbox.objects.filter(is_demo=True).exists())

    @override_settings(DEBUG=True)
    def test_demo_requires_existing_user(self):
        with self.assertRaises(CommandError):
            call_command('seed_supplyhub_demo',username='missing',stdout=StringIO())
