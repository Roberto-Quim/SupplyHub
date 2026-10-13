from django import forms
from supplyhub.models import HistorialSeguimiento

class RegistrarSeguimientoForm(forms.ModelForm):
    fecha_revisada_propuesta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'q-input'}),
        label="Nueva Fecha Compromiso / Revisada"
    )

    class Meta:
        model = HistorialSeguimiento
        fields = ['respuesta_proveedor', 'fecha_revisada_propuesta']
        widgets = {
            'respuesta_proveedor': forms.Textarea(attrs={
                'rows': 3, 
                'placeholder': 'Escribe la respuesta o estatus dado por el proveedor...',
                'class': 'q-input'
            }),
        }
        labels = {
            'respuesta_proveedor': 'Comentario / Respuesta del Proveedor',
        }
    