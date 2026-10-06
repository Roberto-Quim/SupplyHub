from getpass import getpass

from cryptography.fernet import Fernet
from django.core.management.base import BaseCommand, CommandError

from supplyhub.security.env import _KEY_ENV_FALLBACK, _KEY_ENV_PRIMARY


class Command(BaseCommand):
    help = "Cifra un secreto de configuración y devuelve fernet:<token>."

    def add_arguments(self, parser):
        parser.add_argument("--value", default=None, help="Evitar en terminal compartida; preferir --prompt.")
        parser.add_argument("--prompt", action="store_true", help="Solicita el secreto sin eco.")

    def handle(self, *args, **options):
        import os

        key = os.environ.get(_KEY_ENV_PRIMARY, "").strip() or os.environ.get(_KEY_ENV_FALLBACK, "").strip()
        if not key:
            raise CommandError(
                f"Define {_KEY_ENV_PRIMARY} (preferido) o {_KEY_ENV_FALLBACK} fuera del repositorio."
            )

        value = getpass("Secreto: ") if options["prompt"] else options["value"]
        if value is None:
            raise CommandError("Usa --prompt o --value.")

        try:
            token = Fernet(key.encode("utf-8")).encrypt(value.encode("utf-8")).decode("utf-8")
        except Exception as exc:
            raise CommandError("La llave Fernet no es válida.") from exc

        self.stdout.write(f"fernet:{token}")
