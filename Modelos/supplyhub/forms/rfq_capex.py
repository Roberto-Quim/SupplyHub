from django import forms
from supplyhub.models import RFQCapex

class RFQCapexForm(forms.ModelForm):
    class Meta:
        model = RFQCapex
        fields = [
            'rfq', 'solicitante', 'correo_solicitante', 'planta',
            'clave_capex', 'tipo_capex', 'fecha_arranque', 'descripcion',
            'comparativa', 'proveedor_seleccionado', 'numero_oc',
            'fecha_oc', 'fecha_tentativa_entrega', 'fecha_entrega',
            'en_tiempo', 'tiempo_total'
        ]
        widgets = {
            'rfq': forms.TextInput(attrs={'class': 'q-input', 'placeholder': 'Ej. 228'}),
            'solicitante': forms.TextInput(attrs={'class': 'q-input'}),
            'correo_solicitante': forms.EmailInput(attrs={'class': 'q-input'}),
            'planta': forms.Select(attrs={'class': 'q-input'}),
            'clave_capex': forms.TextInput(attrs={'class': 'q-input', 'placeholder': 'Ej. Blackbird / 9132'}),
            'tipo_capex': forms.TextInput(attrs={'class': 'q-input'}),
            'fecha_arranque': forms.DateInput(attrs={'class': 'q-input', 'type': 'date'}),
            'descripcion': forms.Textarea(attrs={'class': 'q-input', 'rows': 3}),
            'comparativa': forms.URLInput(attrs={'class': 'q-input', 'placeholder': 'https://docs.google.com/...'}),
            'proveedor_seleccionado': forms.TextInput(attrs={'class': 'q-input'}),
            'numero_oc': forms.TextInput(attrs={'class': 'q-input'}),
            'fecha_oc': forms.DateInput(attrs={'class': 'q-input', 'type': 'date'}),
            'fecha_tentativa_entrega': forms.DateInput(attrs={'class': 'q-input', 'type': 'date'}),
            'fecha_entrega': forms.DateInput(attrs={'class': 'q-input', 'type': 'date'}),
            'en_tiempo': forms.TextInput(attrs={'class': 'q-input', 'placeholder': 'SI / NO'}),
            'tiempo_total': forms.NumberInput(attrs={'class': 'q-input', 'placeholder': 'Ej. 41'}),
        }


class RFQEstadoForm(forms.ModelForm):
    comentario = forms.CharField(widget=forms.TextInput(attrs={'class': 'q-input'}), required=False)

    class Meta:
        model = RFQCapex
        fields = ['estado']
        widgets = {
            'estado': forms.Select(attrs={'class': 'q-input'}),
        }


class RFQDecisionForm(forms.ModelForm):
    decision = forms.ChoiceField(
        choices=RFQCapex.Decision.choices, 
        required=False
    )
    motivo = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'q-input'}), 
        required=False
    )

    class Meta:
        model = RFQCapex
        fields = ['decision_seguimiento', 'proveedor_seleccionado']
        widgets = {
            'decision_seguimiento': forms.Select(attrs={'class': 'q-input'}),
            'proveedor_seleccionado': forms.TextInput(attrs={'class': 'q-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hace que decision_seguimiento no sea obligatorio en la validación inicial del form
        self.fields['decision_seguimiento'].required = False

    def clean(self):
        cleaned_data = super().clean()
        dec_seg = cleaned_data.get('decision_seguimiento')
        dec_alt = cleaned_data.get('decision')

        # Si el test o la vista mandó 'decision', lo asignamos a 'decision_seguimiento'
        final_decision = dec_seg or dec_alt
        if not final_decision:
            raise forms.ValidationError("Debe proporcionar una decisión válida.")

        cleaned_data['decision_seguimiento'] = final_decision
        return cleaned_data