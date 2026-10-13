from django import forms

class ImportarOCForm(forms.Form):
    archivo_excel = forms.FileField(
        label="Archivo Excel de Oracle",
        help_text="Selecciona el reporte Open Purchase Orders (.xlsx o .xls)"
    )