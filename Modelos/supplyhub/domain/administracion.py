"""Catálogos operativos; las tablas Dev* se usan exclusivamente sin DataAnalytics en DEBUG."""
from django.db import models
from django.db.models.functions import Lower


class DevPerfil(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    activo = models.BooleanField(default=True)
    modulos = models.ManyToManyField('DevModulo', blank=True)

    def __str__(self):
        return self.nombre


class DevModulo(models.Model):
    nombre = models.CharField(max_length=100)
    grupo = models.CharField(max_length=100)
    ruta = models.CharField(max_length=200, unique=True)
    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['grupo', 'orden', 'nombre']

    def __str__(self):
        return f'{self.grupo} / {self.nombre}'


class DevAsignacion(models.Model):
    nomina = models.CharField(max_length=10, blank=True)
    correo = models.EmailField(max_length=200, blank=True)
    metodo = models.PositiveSmallIntegerField(choices=[(1, 'Google'), (2, 'Directorio Activo'), (3, 'Nómina')])
    perfil = models.ForeignKey(DevPerfil, on_delete=models.PROTECT)
    activo = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['nomina', 'metodo'], condition=~models.Q(nomina=''), name='dev_persona_nomina_metodo'),
            models.UniqueConstraint(Lower('correo'), 'metodo', condition=~models.Q(correo=''), name='dev_persona_correo_metodo'),
        ]


class SupplierSite(models.Model):
    proveedor = models.CharField(max_length=200)
    codigo = models.CharField(max_length=100)
    planta = models.CharField(max_length=100)
    contacto = models.CharField(max_length=150, blank=True)
    correo = models.EmailField(blank=True)
    telefono = models.CharField(max_length=40, blank=True)
    activo = models.BooleanField(default=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['proveedor', 'codigo', 'planta']
        constraints = [models.UniqueConstraint(Lower('proveedor'), Lower('codigo'), Lower('planta'), name='supplier_site_identidad')]

    def __str__(self):
        return f'{self.proveedor} / {self.codigo} / {self.planta}'


class ErrorLog(models.Model):
    referencia = models.UUIDField(unique=True, editable=False)
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)
    nivel = models.CharField(max_length=20, default='ERROR')
    origen = models.CharField(max_length=120)
    mensaje = models.CharField(max_length=500)
    ruta = models.CharField(max_length=200, blank=True)
    usuario = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-fecha', '-pk']


class AuditoriaAdministracion(models.Model):
    fecha = models.DateTimeField(auto_now_add=True)
    actor = models.CharField(max_length=100)
    entidad = models.CharField(max_length=50)
    identificador = models.CharField(max_length=100)
    accion = models.CharField(max_length=30)
    detalle = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['-fecha', '-pk']
