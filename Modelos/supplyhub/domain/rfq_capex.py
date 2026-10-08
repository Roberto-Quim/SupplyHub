from django.db import models


class RFQCapex(models.Model):
    class Planta(models.TextChoices):
        MACIMEX_TENANGO = "MACIMEX_TENANGO", "Macimex Tenango"
        MAQ_RA = "MAQ_RA", "MAQ RA"

    class Estado(models.TextChoices):
        SOLICITADA = "SOLICITADA", "Solicitada"
        COTIZACION = "COTIZACION", "Cotización"
        APROBACION = "APROBACION", "Aprobación"
        ORDENADA = "ORDENADA", "Ordenada"
        CONCLUIDA = "CONCLUIDA", "Concluida"

    class Decision(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente de revisión"
        COTIZAR = "COTIZAR", "Cotizar"
        NO_COTIZAR = "NO_COTIZAR", "No cotizar"

    class Origen(models.TextChoices):
        MANUAL = "MANUAL", "Captura manual"
        SHEET = "SHEET", "Google Sheet / Excel"
        FORM_APPROVALS = "FORM_APPROVALS", "Form Approvals"
        EMAIL = "EMAIL", "Correo"

    rfq = models.CharField("RFQ / Pedido", max_length=50, db_index=True)
    descripcion = models.TextField("Descripción")
    fecha_arranque = models.DateField("Fecha de arranque", null=True, blank=True)
    solicitante = models.CharField(max_length=180)
    correo_solicitante = models.EmailField(blank=True)

    planta = models.CharField(max_length=32, choices=Planta.choices, db_index=True)
    planta_origen = models.CharField(max_length=180, blank=True)

    clave_capex = models.CharField("Clave de proyecto / No. CAPEX", max_length=180, blank=True)
    tipo_capex = models.CharField(max_length=180, blank=True)

    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.SOLICITADA,
        db_index=True,
    )
    decision_seguimiento = models.CharField(
        max_length=20,
        choices=Decision.choices,
        default=Decision.PENDIENTE,
        db_index=True,
    )

    origen = models.CharField(
        max_length=24,
        choices=Origen.choices,
        default=Origen.MANUAL,
    )
    identificador_origen = models.CharField(max_length=255, blank=True)

    creado_por = models.CharField(max_length=80, blank=True)
    actualizado_por = models.CharField(max_length=80, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplyhub_rfq_capex"
        ordering = ("-actualizado_en", "-id")
        indexes = [
            models.Index(fields=("planta", "estado"), name="rfq_planta_estado_idx"),
            models.Index(
                fields=("decision_seguimiento", "estado"),
                name="rfq_decision_estado_idx",
            ),
        ]

    def __str__(self):
        return f"RFQ {self.rfq} · {self.get_planta_display()}"


class HistorialEstadoRFQ(models.Model):
    rfq = models.ForeignKey(
        RFQCapex,
        on_delete=models.CASCADE,
        related_name="historial_estados",
    )
    estado_anterior = models.CharField(max_length=20, blank=True)
    estado_nuevo = models.CharField(max_length=20, choices=RFQCapex.Estado.choices)
    comentario = models.CharField(max_length=500, blank=True)
    usuario = models.CharField(max_length=80, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "supplyhub_rfq_estado_hist"
        ordering = ("-creado_en", "-id")

    def __str__(self):
        return f"{self.rfq.rfq}: {self.estado_anterior or '—'} → {self.estado_nuevo}"


class HistorialDecisionRFQ(models.Model):
    rfq = models.ForeignKey(
        RFQCapex,
        on_delete=models.CASCADE,
        related_name="historial_decisiones",
    )
    decision_anterior = models.CharField(max_length=20, blank=True)
    decision_nueva = models.CharField(max_length=20, choices=RFQCapex.Decision.choices)
    motivo = models.CharField(max_length=500, blank=True)
    usuario = models.CharField(max_length=80, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "supplyhub_rfq_decision_hist"
        ordering = ("-creado_en", "-id")

    def __str__(self):
        return f"{self.rfq.rfq}: {self.decision_anterior or '—'} → {self.decision_nueva}"
