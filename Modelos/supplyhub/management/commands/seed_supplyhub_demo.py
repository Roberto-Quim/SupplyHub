"""Datos ficticios locales para recorrer la revisión sin tocar Gmail."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from supplyhub.models import GmailMailbox, GmailResponse, OrdenCompra, LineaOC


class Command(BaseCommand):
    help = 'Crea una OC y dos respuestas ficticias para un usuario existente, solo con DEBUG=True.'

    def add_arguments(self,parser):
        parser.add_argument('--username',required=True)

    @transaction.atomic
    def handle(self,*args,**options):
        if not settings.DEBUG:
            raise CommandError('La demostración solo está habilitada con DEBUG=True.')
        try:
            owner=get_user_model().objects.get(username=options['username'])
        except get_user_model().DoesNotExist as exc:
            raise CommandError('Primero crea o inicia sesión con el usuario local indicado.') from exc
        mailbox,_=GmailMailbox.objects.get_or_create(email=f'demo-{owner.pk}@supplyhub.invalid',defaults={'owner':owner,'encrypted_tokens':'','is_demo':True})
        if mailbox.owner_id != owner.pk or not mailbox.is_demo:
            raise CommandError('La identidad de demostración ya está ocupada; no se modificó.')
        oc,_=OrdenCompra.objects.get_or_create(numero_oc=f'DEMO-{owner.pk}',sistema_origen='SUPPLYHUB_DEMO',defaults={
            'proveedor':'DEMOSTRACIÓN — Proveedor ficticio','planta_original':'Maquinados Ramos','planta_normalizada':'MAQ_RA',
        })
        line,_=LineaOC.objects.get_or_create(orden=oc,release='DEMO',numero_linea='1',defaults={
            'codigo_articulo':'DEMO-PIEZA','descripcion':'DEMOSTRACIÓN — Pieza sin compra real',
            'cantidad_solicitada':10,'cantidad_pendiente':10,'correo_proveedor':'proveedor@example.invalid',
            'fecha_original':timezone.localdate(),
        })
        for number,body in [(1,'DEMOSTRACIÓN: confirmamos material listo para embarque. Elige una fecha de prueba al revisar.'),(2,'DEMOSTRACIÓN: respuesta duplicada de seguimiento. Puedes descartarla para probar el flujo.')]:
            response,created=GmailResponse.objects.get_or_create(mailbox=mailbox,message_id=f'demo-{number}',defaults={
                'sender':'proveedor@example.invalid','subject':f'DEMOSTRACIÓN — OC {oc.numero_oc} / respuesta {number}',
                'body':body,'received_at':timezone.now(),
            })
            if created:
                response.candidates.add(line)
        self.stdout.write(self.style.SUCCESS('Demostración lista. Entra a Seguimiento OC > Correos de proveedores con ese usuario. Repetir el comando no duplica ni reinicia las revisiones.'))
