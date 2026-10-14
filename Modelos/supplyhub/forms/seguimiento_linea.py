from django import forms
from supplyhub.models import HistorialSeguimiento, LineaOC

# Lista de respuestas frecuentes de Jacqueline
OPCIONES_RESPUESTA_PREDETERMINADA = [
    ("", "-- Seleccionar respuesta predeterminada --"),
    ("Material enviado por proveedor //", "Material enviado por proveedor //"),
    ("Se re-confirma fecha de entrega //", "Se re-confirma fecha de entrega //"),
    ("Se solicita estatus //", "Se solicita estatus //"),
    ("CUENTA BLOQUEADA //", "CUENTA BLOQUEADA //"),
    ("*URGENTE* //", "*URGENTE* //"),
    ("Confirma fecha de entrega por correo //", "Confirma fecha de entrega por correo //"),
    ("Se envía recordatorio de confirmación de recibido //", "Se envía recordatorio de confirmación de recibido //"),
    ("Llamada con proveedor pdte fecha de entrega //", "Llamada con proveedor pdte fecha de entrega //"),
    ("Se envía OC actualizada", "Se envía OC actualizada"),
    ("Recolección programada con Logística //", "Recolección programada con Logística //"),
    ("CAMBIO DE PRECIO //", "CAMBIO DE PRECIO //"),
    ("BPA EN AUTORIZACIÓN //", "BPA EN AUTORIZACIÓN //"),
    ("ANTICIPO EN APROBACIÓN //", "ANTICIPO EN APROBACIÓN //"),
    ("Notifican entrega en planta, pdte ingreso //", "Notifican entrega en planta, pdte ingreso //"),
]

class RegistrarSeguimientoForm(forms.Form):
    plantilla_respuesta = forms.ChoiceField(
        choices=OPCIONES_RESPUESTA_PREDETERMINADA,
        required=False,
        widget=forms.Select(attrs={'class': 'q-input', 'id': 'selectPlantilla'})
    )
    respuesta_proveedor = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'q-input', 'rows': 3, 'id': 'txtRespuesta', 'placeholder': 'Escribe la respuesta o selecciona una plantilla arriba...'}),
        required=True
    )
    nueva_fecha_comprometida = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'q-input', 'type': 'date'})
    )
    
    # Campos adicionales de Jacqui
    fecha_embarque_proveedor = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'q-input', 'type': 'date'})
    )
    fecha_entrega_planta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'q-input', 'type': 'date'})
    )
    dias_tarde = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'q-input'})
    )
    stock = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'q-input'})
    )
    min_max = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'q-input', 'placeholder': 'Ej. 1-1 / 3-3'})
    )