from django.db import models
from django.contrib.auth.models import User
from datetime import datetime
import uuid
import secrets

def path_firmas(instance, filename):
    user_id = instance.usuario_id or 'anon'
    fecha = instance.fecha_creacion or datetime.now()
    return f'firmas/{user_id}/{fecha.strftime("%Y/%m")}/{filename}'

def path_firmas_result(instance, filename):
    # dónde guardar el PDF FIRMADO que llega por webhook
    user_id = instance.usuario_id or 'anon'
    fecha = instance.fecha_creacion or datetime.now()
    return f'firmas/{user_id}/{fecha.strftime("%Y/%m")}/firmados/{filename}'

class FirmaElectronica(models.Model):
    class Estados(models.TextChoices):
        EN_PROCESO = 'proceso', 'En proceso'
        FIRMADO    = 'firmado', 'Firmado'
        ERROR      = 'error',   'Error'

    archivo = models.FileField(upload_to=path_firmas)
    nombre_original = models.CharField(max_length=255)

    # === NUEVO: identificación y seguridad del webhook ===
    ref = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    cb_token = models.CharField(max_length=64, blank=True, default='')  # token secreto callback

    # Respuesta del API / job
    api_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)

    # Estado / errores
    estado = models.CharField(max_length=20, choices=Estados.choices,
                              default=Estados.EN_PROCESO, db_index=True)
    error_msg = models.TextField(blank=True)

    # === NUEVO: archivo firmado que llega en url_out ===
    archivo_firmado = models.FileField(upload_to=path_firmas_result, null=True, blank=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True, db_index=True)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE,
                                related_name='firmas', null=True, blank=True)

    def issue_token(self):
        self.cb_token = secrets.token_urlsafe(24)
        return self.cb_token

    def __str__(self):
        base = self.nombre_original or (self.archivo.name if self.archivo else 'sin_archivo')
        return f'[{self.get_estado_display()}] {base} (api_id={self.api_id or "-"})'

    class Meta:
        ordering = ['-fecha_creacion']
        indexes = [ models.Index(fields=['estado', 'fecha_creacion']) ]