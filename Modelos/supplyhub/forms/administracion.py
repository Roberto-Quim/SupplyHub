import re
from django import forms
from supplyhub.models import SupplierSite
from supplyhub.services import administracion_service as service


class AssignmentForm(forms.Form):
    nomina = forms.RegexField(r'^\d{1,10}$', label='Nómina', max_length=10, required=False)
    correo = forms.EmailField(max_length=200, required=False)
    metodo = forms.TypedChoiceField(label='Método de ingreso', choices=service.METHODS.items(), coerce=int)
    perfil = forms.TypedChoiceField(coerce=int)

    def __init__(self, *args, profiles=(), editing=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['perfil'].choices = [(p['id'], p['nombre']) for p in profiles if p['activo']]
        if editing:
            self.fields['nomina'].disabled = self.fields['correo'].disabled = True

    def clean_correo(self):
        return self.cleaned_data['correo'].lower()

    def clean(self):
        data = super().clean()
        method = data.get('metodo')
        if method == 1 and not data.get('correo'):
            self.add_error('correo', 'Google requiere un correo.')
        if method == 3 and not data.get('nomina'):
            self.add_error('nomina', 'Se requiere número de nómina.')
        if method == 2 and not (data.get('correo') or data.get('nomina')):
            raise forms.ValidationError('Directorio Activo requiere nómina o correo.')
        return data


class ProfileForm(forms.Form):
    nombre = forms.CharField(max_length=100)
    modulos = forms.TypedMultipleChoiceField(label='Submódulos permitidos', coerce=int, required=False, widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, modules=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['modulos'].choices = [(m['id'], f"{m['grupo']} / {m['nombre']} — {m['ruta']}") for m in modules if m['activo']]


class ModuleForm(forms.Form):
    nombre = forms.CharField(label='Nombre del submódulo', max_length=100)
    grupo = forms.CharField(label='Módulo padre', max_length=100, required=False)
    padre = forms.TypedChoiceField(label='Módulo padre', coerce=int, required=False)
    ruta = forms.CharField(max_length=200)
    orden = forms.IntegerField(min_value=0, max_value=9999, initial=0)

    def __init__(self, *args, parents=(), central=False, **kwargs):
        super().__init__(*args, **kwargs)
        if central:
            del self.fields['grupo']
            self.fields['padre'].required = True
            self.fields['padre'].choices = [(m['id_modulo'], m['modulo']) for m in parents if m['activo']]
        else:
            del self.fields['padre']
            self.fields['grupo'].required = True

    def clean_ruta(self):
        route = self.cleaned_data['ruta'].strip()
        if not re.fullmatch(r'/[a-zA-Z0-9_/-]*/', route) or '//' in route:
            raise forms.ValidationError('Usa una ruta interna, por ejemplo /hub/rfq-capex/.')
        return route


class ParentModuleForm(forms.Form):
    nombre = forms.CharField(max_length=100)
    orden = forms.IntegerField(min_value=0, max_value=9999, initial=0)


class SupplierSiteForm(forms.ModelForm):
    class Meta:
        model = SupplierSite
        fields = ['proveedor', 'codigo', 'planta', 'contacto', 'correo', 'telefono']
        labels = {'codigo': 'Supplier Site', 'telefono': 'Teléfono'}

    def clean(self):
        data = super().clean()
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = value.strip()
        if data.get('correo'):
            data['correo'] = data['correo'].lower()
        return data


class LogFilterForm(forms.Form):
    fecha_inicio = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    fecha_fin = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    q = forms.CharField(required=False, max_length=100, label='Buscar')

    def clean(self):
        data = super().clean()
        if data.get('fecha_inicio') and data.get('fecha_fin') and data['fecha_inicio'] > data['fecha_fin']:
            raise forms.ValidationError('La fecha inicial debe ser anterior a la final.')
        return data
