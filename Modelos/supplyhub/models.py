"""Modelos de negocio expuestos por la app Django SupplyHub."""

from .domain.rfq_capex import HistorialDecisionRFQ, HistorialEstadoRFQ, RFQCapex

__all__ = ["RFQCapex", "HistorialEstadoRFQ", "HistorialDecisionRFQ"]

from django.db import models
from django.utils import timezone
from .domain.rfq_capex import RFQCapex

# --- MODELOS EXISTENTES DE FEAT 4 ---
# (Asegúrate de tener aquí tu clase RFQCapex original y sus historiales)
# class RFQCapex(models.Model):
#     ...

# --- NUEVOS MODELOS DE FEAT 5 ---
class OrdenCompra(models.Model):
    class EstadoOC(models.TextChoices):
        ABIERTA = "ABIERTA", "Abierta"
        CERRADA = "CERRADA", "Cerrada"

    class PlantaNormalizada(models.TextChoices):
        MACIMEX_TENANGO = "MACIMEX_TENANGO", "Macimex Tenango"
        MAQ_RA = "MAQ_RA", "MAQ RA"
        DESCONOCIDA = "DESCONOCIDA", "Desconocida"

    numero_oc = models.CharField(max_length=50, db_index=True)
    proveedor = models.CharField(max_length=200)
    supplier_site = models.CharField(max_length=200, blank=True, null=True)
    planta_original = models.CharField(max_length=200)
    fecha_creacion_po = models.DateField(null=True, blank=True)
    comprador = models.CharField(max_length=150, blank=True, default='')
    estatus_autorizacion = models.CharField(max_length=50, blank=True, default='')
    moneda = models.CharField(max_length=10, blank=True, default='')
    planta_normalizada = models.CharField(
        max_length=50, 
        choices=PlantaNormalizada.choices, 
        default=PlantaNormalizada.DESCONOCIDA
    )
    estado = models.CharField(
        max_length=20, 
        choices=EstadoOC.choices, 
        default=EstadoOC.ABIERTA
    )
    sistema_origen = models.CharField(max_length=50, default="ORACLE_QES")
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('numero_oc', 'sistema_origen')

    def __str__(self):
        return f"OC {self.numero_oc} - {self.proveedor}"


class LineaOC(models.Model):
    class EstadoEntrega(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        PARCIAL = "PARCIAL", "Parcialmente Entregada"
        ENTREGADA = "ENTREGADA", "Entregada"
        CANCELADA = "CANCELADA", "Cancelada"

    orden = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, related_name="lineas")
    numero_linea = models.CharField(max_length=50)
    codigo_articulo = models.CharField(max_length=100)
    descripcion = models.TextField()

    unidad_medida = models.CharField(max_length=20, blank=True, default='')
    ubicacion_entrega = models.CharField(max_length=150, blank=True, default='')
    cantidad_pendiente = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    estatus_necesidad = models.CharField(max_length=50, blank=True, default='')
    correo_proveedor = models.EmailField(blank=True, default='')
    
    cantidad_solicitada = models.DecimalField(max_digits=14, decimal_places=4)
    cantidad_recibida = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    release = models.CharField(max_length=50, blank=True, default='')  # Columna R
    dias_tarde = models.IntegerField(null=True, blank=True, default=0)
    stock = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, default=0)
    min_max = models.CharField(max_length=50, blank=True, default='')
    fecha_embarque_proveedor = models.DateField(null=True, blank=True)
    fecha_entrega_planta = models.DateField(null=True, blank=True)
    comentarios = models.TextField(blank=True, default='')
    
    fecha_original = models.DateField(null=True, blank=True)
    fecha_comprometida = models.DateField(null=True, blank=True)
    fecha_revisada = models.DateField(null=True, blank=True)

    
    
    estado_entrega = models.CharField(
        max_length=20, 
        choices=EstadoEntrega.choices, 
        default=EstadoEntrega.PENDIENTE
    )
    
    comentario_actual = models.TextField(blank=True, default="")
    ultima_interaccion = models.DateTimeField(null=True, blank=True)
    proximo_recordatorio = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('orden', 'release', 'numero_linea')

    def __str__(self):
        return f"Línea {self.numero_linea} - {self.codigo_articulo}"


class HistorialSeguimiento(models.Model):
    class Fuente(models.TextChoices):
        MANUAL = "MANUAL", "Captura Manual"
        IMPORTACION = "IMPORTACION", "Importación de Archivo"
        CORREO = "CORREO", "Correo Electrónico"

    linea = models.ForeignKey(LineaOC, on_delete=models.CASCADE, related_name="historial")
    respuesta_proveedor = models.TextField()
    fecha_interaccion = models.DateTimeField(default=timezone.now)
    usuario_responsable = models.CharField(max_length=100)
    fuente = models.CharField(max_length=20, choices=Fuente.choices, default=Fuente.MANUAL)
    
    fecha_revisada_propuesta = models.DateField(null=True, blank=True)
    estado_validacion = models.BooleanField(default=True)
    
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_registro']


class RecordatorioOC(models.Model):
    class EstadoRecordatorio(models.TextChoices):
        PROGRAMADO = "PROGRAMADO", "Programado"
        GENERADO = "GENERADO", "Generado"
        ENVIADO = "ENVIADO", "Enviado"
        OMITIDO = "OMITIDO", "Omitido/Cancelado"

    linea = models.ForeignKey(LineaOC, on_delete=models.CASCADE, related_name="recordatorios")
    fecha_programada = models.DateTimeField()
    fecha_ejecucion = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(
        max_length=20, 
        choices=EstadoRecordatorio.choices, 
        default=EstadoRecordatorio.PROGRAMADO
    )
    intentos = models.IntegerField(default=0)