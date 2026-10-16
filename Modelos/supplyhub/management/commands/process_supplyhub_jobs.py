from django.core.management.base import BaseCommand
from supplyhub.services.operacion_service import generate_reminders, send_approved, sync_mailboxes


class Command(BaseCommand):
    help = 'Procesa consultas habilitadas, genera recordatorios y envía únicamente los aprobados.'

    def handle(self, *args, **options):
        self.stdout.write(f'Respuestas nuevas: {sync_mailboxes()}; recordatorios nuevos: {generate_reminders()}; enviados aprobados: {send_approved()}')
