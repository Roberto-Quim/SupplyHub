import secrets
import time
from django import forms
from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from supplyhub.models import GmailMailbox, GmailResponse, GmailSyncRun
from supplyhub.services import gmail_service as gmail
from supplyhub.services.permission_guard import supplyhub_route_required

ROUTE='/hub/seguimiento-oc/'

class ReviewForm(forms.Form):
    line_id=forms.IntegerField(min_value=1)
    comment=forms.CharField(max_length=20000)
    revised_date=forms.DateField(required=False)

@supplyhub_route_required(ROUTE)
def index(request):
    return render(request,'gmail/index.html',{
        'mailboxes':GmailMailbox.objects.filter(owner=request.user),
        'runs':GmailSyncRun.objects.filter(mailbox__owner=request.user).select_related('mailbox')[:30],
        'pending_count':GmailResponse.objects.filter(mailbox__owner=request.user,status='PENDING').count(),
        'configuration_ready': bool(settings.GMAIL_ENABLED and settings.GMAIL_CLIENT_ID and settings.GMAIL_CLIENT_SECRET and gmail.is_encryption_configured()),
        'responses':GmailResponse.objects.filter(mailbox__owner=request.user).select_related('mailbox').prefetch_related('candidates__orden').order_by('-received_at')[:100],
    })

@supplyhub_route_required(ROUTE)
@require_POST
def start(request):
    state=secrets.token_urlsafe(32)
    try:
        url=gmail.authorization_url(state)
    except gmail.GmailError as exc:
        messages.error(request,str(exc))
        return redirect('supplyhub:gmail_index')
    request.session['gmail_oauth']={'state':state,'at':time.time(),'user':request.user.pk}
    return redirect(url)

@supplyhub_route_required(ROUTE)
def callback(request):
    pending=request.session.pop('gmail_oauth',{})
    state = request.GET.get('state', '')
    valid=(pending.get('user')==request.user.pk and 0 <= time.time()-pending.get('at',0) <= 600 and state.isascii() and secrets.compare_digest(pending.get('state',''),state))
    if not valid or not request.GET.get('code') or request.GET.get('error'):
        messages.error(request,'AutorizaciÃ³n cancelada o vencida. Conecta el buzÃ³n otra vez.')
        return redirect('supplyhub:gmail_index')
    try:
        gmail.connect(request.user,request.GET['code'])
    except gmail.GmailError as exc:
        messages.error(request,str(exc))
    else:
        messages.success(request,'BuzÃ³n conectado con acceso de solo lectura.')
    return redirect('supplyhub:gmail_index')

@supplyhub_route_required(ROUTE)
@require_POST
def sync(request,pk):
    mailbox=get_object_or_404(GmailMailbox,pk=pk,owner=request.user)
    try:
        added=gmail.sync(mailbox)
    except gmail.GmailError as exc:
        messages.error(request,str(exc))
    else:
        messages.success(request,f'{added} respuestas nuevas para revisar. Ventana: Ãºltimos 30 dÃ­as, hasta 250 mensajes por consulta.')
    return redirect('supplyhub:gmail_index')

@supplyhub_route_required(ROUTE)
@require_POST
def disconnect(request,pk):
    mailbox=get_object_or_404(GmailMailbox,pk=pk,owner=request.user)
    # Conserva evidencias y revisiones; elimina la credencial local.
    mailbox.encrypted_tokens=''
    mailbox.save(update_fields=['encrypted_tokens'])
    messages.success(request,'Credencial eliminada de SupplyHub. Puedes revocar el acceso tambiÃ©n en tu cuenta Google.')
    return redirect('supplyhub:gmail_index')

@supplyhub_route_required(ROUTE)
@require_POST
def review(request,pk):
    response=get_object_or_404(GmailResponse,pk=pk,mailbox__owner=request.user)
    if request.POST.get('action')=='dismiss':
        GmailResponse.objects.filter(pk=response.pk,status='PENDING').update(status='DISMISSED')
    else:
        form=ReviewForm(request.POST)
        if form.is_valid():
            try:
                gmail.apply_response(response.pk,request.user,form.cleaned_data['line_id'],form.cleaned_data['comment'],form.cleaned_data['revised_date'])
            except gmail.GmailError as exc:
                messages.error(request,str(exc))
            else:
                messages.success(request,'Respuesta incorporada al historial de la partida.')
        else:
            messages.error(request,'Revisa la partida, el comentario y la fecha antes de aplicar.')
    return redirect('supplyhub:gmail_index')


@supplyhub_route_required(ROUTE)
@require_POST
def supplier_email(request,pk):
    from supplyhub.models import LineaOC
    line=get_object_or_404(LineaOC.objects.exclude(orden__planta_normalizada='MACIMEX_TENANGO'),pk=pk)
    field=forms.EmailField(required=False)
    try:
        email=field.clean(request.POST.get('email','')).lower()
        if email and not gmail.external_sender(email):
            raise forms.ValidationError('Usa el correo externo del proveedor.')
    except forms.ValidationError:
        messages.error(request,'Ingresa un correo externo válido del proveedor.')
    else:
        line.correo_proveedor=email
        line.save(update_fields=['correo_proveedor'])
        messages.success(request,'Correo del proveedor actualizado.')
    return redirect('supplyhub:seguimiento_oc_detalle',pk=line.orden_id)
