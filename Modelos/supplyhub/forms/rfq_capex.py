from django import forms

from supplyhub.models import RFQCapex


class RFQCapexForm(forms.ModelForm):
    class Meta:
        model = RFQCapex
        fields = (
            "rfq",
            "descripcion",
            "fecha_arranque",
            "solicitante",
            "correo_solicitante",
            "planta",
            "clave_capex",
            "tipo_capex",
        )
        widgets = {
            "fecha_arranque": forms.DateInput(attrs={"type": "date"}),
            "descripcion": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_rfq(self):
        value = (self.cleaned_data.get("rfq") or "").strip()
        if value.startswith("#"):
            value = value[1:].strip()
        return value

    def clean_solicitante(self):
        return (self.cleaned_data.get("solicitante") or "").strip()


class RFQEstadoForm(forms.Form):
    estado = forms.ChoiceField(choices=RFQCapex.Estado.choices, label="Nuevo estado")
    comentario = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 2}),
    )


class RFQDecisionForm(forms.Form):
    decision = forms.ChoiceField(
        choices=RFQCapex.Decision.choices,
        label="Decisión de seguimiento",
    )
    motivo = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
