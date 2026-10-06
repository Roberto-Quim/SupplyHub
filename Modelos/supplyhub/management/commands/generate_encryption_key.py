from django.core.management.base import BaseCommand

from supplyhub.security.encryption_fernet import generate_encryption_key


class Command(BaseCommand):
    help = "Genera una llave Fernet para APP_CONFIG_ENCRYPTION_KEY o APP_ENCRYPTION_KEY."

    def handle(self, *args, **options):
        self.stdout.write(generate_encryption_key())
