"""Gmail de solo lectura. Los mensajes externos requieren revisión humana."""
import base64
import json
import re
from datetime import datetime, timedelta, timezone as utc_timezone
from email.utils import getaddresses
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from supplyhub.models import GmailMailbox, GmailResponse, GmailSyncRun, LineaOC, HistorialSeguimiento
from supplyhub.security.encryption_fernet import encrypt_text, decrypt_text, is_encryption_configured
from supplyhub.services.seguimiento_oc_service import registrar_interaccion_linea

SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'
API = 'https://gmail.googleapis.com/gmail/v1/users/me'

class GmailError(Exception):
    pass


def require_config():
    if not (settings.GMAIL_ENABLED and settings.GMAIL_CLIENT_ID and settings.GMAIL_CLIENT_SECRET and is_encryption_configured()):
        raise GmailError('Configura Gmail y el cifrado antes de conectar un buzón.')


def http(method, url, **kwargs):
    try:
        response = requests.request(
            method,
            url,
            timeout=30,
            **kwargs
        )
        response.raise_for_status()
        return response.json()

    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "desconocido"
        error_code = "desconocido"

        if exc.response is not None:
            try:
                payload = exc.response.json()
                error_code = str(payload.get("error", "desconocido"))
                if isinstance(payload.get("error"), dict):
                    error_code = str(payload["error"].get("status", "desconocido"))
            except ValueError:
                pass

        raise GmailError(
            f"Google rechazó la solicitud (HTTP {status}, error: {error_code})."
        ) from exc

    except (requests.RequestException, ValueError) as exc:
        raise GmailError(
            "No se pudo completar la comunicación con Google."
        ) from exc

def authorization_url(state):
    require_config()
    return 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode({
        'client_id':settings.GMAIL_CLIENT_ID, 'redirect_uri':settings.GMAIL_REDIRECT_URI,
        'response_type':'code', 'scope':SCOPE, 'access_type':'offline',
        'prompt':'consent select_account', 'state':state,
    })


def connect(owner, code):
    require_config()
    tokens = http('POST', 'https://oauth2.googleapis.com/token', data={
        'code':code, 'client_id':settings.GMAIL_CLIENT_ID,
        'client_secret':settings.GMAIL_CLIENT_SECRET,
        'redirect_uri':settings.GMAIL_REDIRECT_URI, 'grant_type':'authorization_code',
    })
    if SCOPE not in tokens.get('scope','').split() or not tokens.get('refresh_token'):
        raise GmailError('Google debe autorizar lectura de Gmail y acceso sin conexión.')
    profile = http('GET', API+'/profile', headers={'Authorization':'Bearer '+tokens['access_token']})
    email = profile['emailAddress'].lower()
    if email.rsplit('@',1)[-1] != 'questum.com':
        raise GmailError('Conecta tu buzón corporativo @questum.com.')
    with transaction.atomic():
        existing = GmailMailbox.objects.select_for_update().filter(email=email).first()
        if existing and existing.owner_id != owner.pk:
            raise GmailError('Este buzón ya está conectado por otra persona.')
        mailbox, _ = GmailMailbox.objects.update_or_create(email=email, defaults={
            'owner':owner, 'encrypted_tokens':encrypt_text(json.dumps({'refresh_token':tokens['refresh_token']})),
        })
    return mailbox


def access_token(mailbox):
    require_config()
    try:
        refresh = json.loads(decrypt_text(mailbox.encrypted_tokens))['refresh_token']
    except Exception as exc:
        raise GmailError('No se pudieron descifrar las credenciales. Revisa la clave o reconecta el buzón.') from exc
    return http('POST','https://oauth2.googleapis.com/token',data={
        'client_id':settings.GMAIL_CLIENT_ID,'client_secret':settings.GMAIL_CLIENT_SECRET,
        'grant_type':'refresh_token','refresh_token':refresh,
    })['access_token']


def external_sender(header):
    addresses = [address.lower() for _, address in getaddresses([header]) if address]
    if len(addresses) != 1 or '@' not in addresses[0]:
        return None
    domain = addresses[0].rsplit('@',1)[-1]
    if domain == 'questum.com' or domain.endswith('.questum.com'):
        return None
    return addresses[0]


def plain_body(payload):
    if payload.get('filename'):
        return ''
    if payload.get('mimeType') == 'text/plain':
        raw = payload.get('body',{}).get('data','')
        try:
            return base64.urlsafe_b64decode(raw + '=' * (-len(raw)%4)).decode('utf-8', errors='replace')
        except ValueError:
            return ''
    return '\n'.join(filter(None, (plain_body(p) for p in payload.get('parts',[]))))


def new_content(text):
    lines = []
    for line in text.splitlines():
        if re.match(r'^\s*(>|El .+escribi[oó]:|On .+wrote:|De:|From:|--\s*$)',line,re.I):
            break
        lines.append(line)
    return '\n'.join(lines).strip()[:20000]


def ingest(mailbox, message):
    payload = message.get('payload',{})
    headers = {h['name'].lower():h['value'] for h in payload.get('headers',[])}
    sender = external_sender(headers.get('from',''))
    if not sender or set(message.get('labelIds',[])) & {'SENT','DRAFT','SPAM','TRASH'}:
        return False
    body = new_content(plain_body(payload))
    if not body:
        return False
    subject = headers.get('subject','')[:500]
    # Solo números explícitos OC/PO; nunca se infiere por una fecha o importe.
    numbers = re.findall(r'(?i)\b(?:OC|PO|orden\s+de\s+compra)\s*[:#-]?\s*(\d+)\b', subject+'\n'+body)
    matches = LineaOC.objects.filter(orden__numero_oc__in=numbers).exclude(orden__planta_normalizada='MACIMEX_TENANGO')
    matches = matches.filter(correo_proveedor__iexact=sender)
    if not matches.exists():
        return False
    with transaction.atomic():
        response, created = GmailResponse.objects.get_or_create(mailbox=mailbox, message_id=message['id'], defaults={
            'sender':sender,'subject':subject,'body':body,
            'received_at':datetime.fromtimestamp(int(message['internalDate'])/1000,tz=utc_timezone.utc),
        })
        if created:
            response.candidates.set(matches)
    return created


def _sync(mailbox):
    token = access_token(mailbox)
    headers = {'Authorization':'Bearer '+token}
    query = 'in:inbox newer_than:30d -from:(@questum.com)'
    page = None
    added = 0
    # Sincronización manual acotada; los IDs evitan duplicar al repetir.
    for _ in range(5):
        params = {'q':query,'maxResults':50}
        if page:
            params['pageToken']=page
        data = http('GET',API+'/messages',headers=headers,params=params)
        for item in data.get('messages',[]):
            if GmailResponse.objects.filter(mailbox=mailbox,message_id=item['id']).exists():
                continue
            message = http('GET',API+'/messages/'+item['id'],headers=headers,params={'format':'full'})
            added += bool(ingest(mailbox,message))
        page = data.get('nextPageToken')
        if not page:
            break
    return added


@transaction.atomic
def apply_response(response_id, owner, line_id, comment, revised_date=None):
    response = GmailResponse.objects.select_for_update().get(pk=response_id,mailbox__owner=owner)
    if response.status != 'PENDING':
        raise GmailError('La respuesta ya fue revisada.')
    try:
        line = response.candidates.select_for_update().exclude(orden__planta_normalizada='MACIMEX_TENANGO').get(pk=line_id)
    except LineaOC.DoesNotExist as exc:
        raise GmailError('Selecciona una partida candidata válida.') from exc
    if not comment.strip():
        raise GmailError('Escribe la respuesta que deseas registrar.')
    history = registrar_interaccion_linea(line,comment.strip(),owner.get_username(),revised_date,fuente=HistorialSeguimiento.Fuente.CORREO,fecha_interaccion=response.received_at)
    response.status='APPLIED'
    response.applied_history=history
    response.save(update_fields=['status','applied_history'])
    return history


def sync(mailbox):
    """Consulta manual con exclusión concurrente, bitácora y espera entre fallos."""
    now = timezone.now()
    with transaction.atomic():
        current = GmailMailbox.objects.select_for_update().get(pk=mailbox.pk)
        if current.is_demo or not current.encrypted_tokens:
            raise GmailError('Este buzón no tiene una conexión Gmail activa.')
        if current.sync_started and current.sync_started > now - timedelta(minutes=30):
            raise GmailError('Hay una consulta en curso. Espera a que termine.')
        if current.retry_after and current.retry_after > now:
            raise GmailError('Espera un minuto antes de volver a intentar la consulta.')
        GmailSyncRun.objects.filter(mailbox=current,status='RUNNING').update(
            status='FAILED',finished_at=now,error='Consulta interrumpida; se liberó después de 30 minutos.')
        current.sync_started=now
        current.save(update_fields=['sync_started'])
        run=GmailSyncRun.objects.create(mailbox=current)
    try:
        added=_sync(current)
    except Exception as exc:
        from .administracion_service import record_error
        record_error('Consulta Gmail')
        # No persistir excepciones de red: podrían contener tokens o URLs sensibles.
        GmailSyncRun.objects.filter(pk=run.pk).update(status='FAILED',finished_at=timezone.now(),error='No se completó la consulta. Revisa configuración, conexión o autorización. Puede haber respuestas guardadas antes del fallo; el reintento no las duplica.')
        GmailMailbox.objects.filter(pk=current.pk,sync_started=now).update(sync_started=None,retry_after=timezone.now()+timedelta(seconds=60))
        if isinstance(exc,GmailError):
            raise
        raise GmailError('No se pudo completar la consulta. Revisa el historial y vuelve a intentar.') from exc
    GmailSyncRun.objects.filter(pk=run.pk,status='RUNNING').update(status='SUCCESS',finished_at=timezone.now(),added=added)
    GmailMailbox.objects.filter(pk=current.pk,sync_started=now).update(sync_started=None,retry_after=None,last_sync=timezone.now())
    return added
