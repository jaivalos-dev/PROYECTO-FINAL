from django.db import models
from django.contrib.auth.models import User
from datetime import datetime

def path_firmas(instance, filename):
    # Carpeta por usuario y año/mes: firmas/<user_id>/2025/08/archivo.pdf
    user_id = instance.usuario_id or 'anon'
    fecha = instance.fecha_creacion or datetime.now()
    return f'firmas/{user_id}/{fecha.strftime("%Y/%m")}/{filename}'

class FirmaElectronica(models.Model):
    class Estados(models.TextChoices):
        EN_PROCESO = 'proceso', 'En proceso'
        FIRMADO    = 'firmado', 'Firmado'
        ERROR      = 'error',   'Error'

    # Datos de archivo y trazabilidad
    archivo = models.FileField(upload_to=path_firmas)
    nombre_original = models.CharField(max_length=255)  # ej. "contrato.pdf"

    # Respuesta del API (puede venir después, así que permite null)
    api_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)

    # Estado y error (inician "En proceso" al crear el registro)
    estado = models.CharField(max_length=20, choices=Estados.choices,
                              default=Estados.EN_PROCESO, db_index=True)
    error_msg = models.TextField(blank=True)  # guardar detalle si falla

    # Auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True, db_index=True)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE,
                                related_name='firmas', null=True, blank=True)

    def __str__(self):
        base = self.nombre_original or (self.archivo.name if self.archivo else 'sin_archivo')
        return f'[{self.get_estado_display()}] {base} (api_id={self.api_id or "-"})'

    class Meta:
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['estado', 'fecha_creacion']),
        ]
