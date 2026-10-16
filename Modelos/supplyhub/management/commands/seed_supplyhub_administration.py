from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from supplyhub.models import DevModulo, DevPerfil
from supplyhub.services.menu_service import MENU_CATALOG
from supplyhub.services import administracion_service as service


class Command(BaseCommand):
    help = 'Siembra idempotente de rutas SupplyHub. Desarrollo: --demo --username SUPERUSUARIO. Central: --actor-profile ID --apply.'

    def add_arguments(self, parser):
        parser.add_argument('--demo',action='store_true')
        parser.add_argument('--username')
        parser.add_argument('--actor-profile',type=int)
        parser.add_argument('--apply',action='store_true')

    def handle(self, *args, **options):
        if options['demo']:
            if not service.local_demo():
                raise CommandError('La demostración requiere DEBUG, login local y DataAnalytics deshabilitado.')
            if not get_user_model().objects.filter(username=options['username'],is_superuser=True,is_active=True).exists():
                raise CommandError('Indica un superusuario local existente y activo.')
            with transaction.atomic():
                for parent in MENU_CATALOG:
                    for order, child in enumerate(parent['children']):
                        DevModulo.objects.get_or_create(ruta=child['route'], defaults={'grupo':parent['label'],'nombre':child['label'],'orden':order})
                profile, _ = DevPerfil.objects.get_or_create(nombre='Compras demo')
                profile.modulos.add(*DevModulo.objects.filter(grupo='HUB'))
            self.stdout.write('Catálogos de demostración disponibles; no se crearon cuentas ni permisos corporativos.')
            return
        if not settings.DATAANALYTICS_ENABLED:
            raise CommandError('Habilita DataAnalytics para sembrar permisos corporativos.')
        actor = options['actor_profile']
        if not service.users.is_ti_profile(actor):
            raise CommandError('La siembra central requiere un perfil TI real.')
        if not options['apply']:
            for parent in MENU_CATALOG:
                for child in parent['children']:
                    self.stdout.write(f"{parent['label']} / {child['label']}: {child['route']}")
            self.stdout.write('Inspección solamente. Usa --apply para crear los registros faltantes.')
            return
        parents = service.modules.list_modulos()
        subs = service.modules.list_submodulos()
        for index, parent in enumerate(MENU_CATALOG):
            found = next((m for m in parents if m['modulo'].casefold()==parent['label'].casefold()),None)
            if found and not found['activo']:
                raise CommandError('El padre existe inactivo. Revísalo en Módulos antes de sembrar.')
            parent_id = found['id_modulo'] if found else service._result(service.modules.create_modulo(parent['label'],'#',index))
            for order, child in enumerate(parent['children']):
                if any(s['ruta']==child['route'] for s in subs):
                    continue
                service._result(service.modules.create_submodulo(parent_id,child['label'],child['route'],order,actor_id_perfil=actor))
        self.stdout.write('Rutas faltantes creadas con el mecanismo de permisos TI de DataAnalytics. Asigna Compras desde Perfiles.')
