from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="RFQCapex",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rfq", models.CharField(db_index=True, max_length=50, verbose_name="RFQ / Pedido")),
                ("descripcion", models.TextField(verbose_name="Descripción")),
                ("fecha_arranque", models.DateField(blank=True, null=True, verbose_name="Fecha de arranque")),
                ("solicitante", models.CharField(max_length=180)),
                ("correo_solicitante", models.EmailField(blank=True, max_length=254)),
                ("planta", models.CharField(choices=[("MACIMEX_TENANGO", "Macimex Tenango"), ("MAQ_RA", "MAQ RA")], db_index=True, max_length=32)),
                ("planta_origen", models.CharField(blank=True, max_length=180)),
                ("clave_capex", models.CharField(blank=True, max_length=180, verbose_name="Clave de proyecto / No. CAPEX")),
                ("tipo_capex", models.CharField(blank=True, max_length=180)),
                ("estado", models.CharField(choices=[("SOLICITADA", "Solicitada"), ("COTIZACION", "Cotización"), ("APROBACION", "Aprobación"), ("ORDENADA", "Ordenada"), ("CONCLUIDA", "Concluida")], db_index=True, default="SOLICITADA", max_length=20)),
                ("decision_seguimiento", models.CharField(choices=[("PENDIENTE", "Pendiente de revisión"), ("COTIZAR", "Cotizar"), ("NO_COTIZAR", "No cotizar")], db_index=True, default="PENDIENTE", max_length=20)),
                ("origen", models.CharField(choices=[("MANUAL", "Captura manual"), ("SHEET", "Google Sheet / Excel"), ("FORM_APPROVALS", "Form Approvals"), ("EMAIL", "Correo")], default="MANUAL", max_length=24)),
                ("identificador_origen", models.CharField(blank=True, max_length=255)),
                ("creado_por", models.CharField(blank=True, max_length=80)),
                ("actualizado_por", models.CharField(blank=True, max_length=80)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "supplyhub_rfq_capex",
                "ordering": ("-actualizado_en", "-id"),
            },
        ),
        migrations.CreateModel(
            name="HistorialEstadoRFQ",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("estado_anterior", models.CharField(blank=True, max_length=20)),
                ("estado_nuevo", models.CharField(choices=[("SOLICITADA", "Solicitada"), ("COTIZACION", "Cotización"), ("APROBACION", "Aprobación"), ("ORDENADA", "Ordenada"), ("CONCLUIDA", "Concluida")], max_length=20)),
                ("comentario", models.CharField(blank=True, max_length=500)),
                ("usuario", models.CharField(blank=True, max_length=80)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("rfq", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="historial_estados", to="supplyhub.rfqcapex")),
            ],
            options={
                "db_table": "supplyhub_rfq_estado_hist",
                "ordering": ("-creado_en", "-id"),
            },
        ),
        migrations.CreateModel(
            name="HistorialDecisionRFQ",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("decision_anterior", models.CharField(blank=True, max_length=20)),
                ("decision_nueva", models.CharField(choices=[("PENDIENTE", "Pendiente de revisión"), ("COTIZAR", "Cotizar"), ("NO_COTIZAR", "No cotizar")], max_length=20)),
                ("motivo", models.CharField(blank=True, max_length=500)),
                ("usuario", models.CharField(blank=True, max_length=80)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("rfq", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="historial_decisiones", to="supplyhub.rfqcapex")),
            ],
            options={
                "db_table": "supplyhub_rfq_decision_hist",
                "ordering": ("-creado_en", "-id"),
            },
        ),
        migrations.AddIndex(
            model_name="rfqcapex",
            index=models.Index(fields=["planta", "estado"], name="rfq_planta_estado_idx"),
        ),
        migrations.AddIndex(
            model_name="rfqcapex",
            index=models.Index(fields=["decision_seguimiento", "estado"], name="rfq_decision_estado_idx"),
        ),
    ]
