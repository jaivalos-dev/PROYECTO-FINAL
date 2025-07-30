from django.db import models
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django.conf import settings


class Evento(models.Model):
    ESTADO_CHOICES = (
        ('agendado', 'Agendado'),
        ('en_curso', 'En Curso'),
        ('finalizado', 'Finalizado'),
        ('cancelado', 'Cancelado'),
    )
    
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    ubicacion = models.CharField(max_length=200, blank=True, null=True)
    organizador = models.CharField(max_length=100, blank=True, null=True)
    color = models.CharField(max_length=20, default='#0D6EFD')
    creador = models.ForeignKey(User, on_delete=models.CASCADE, related_name='eventos_creados')
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='agendado')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-fecha_inicio']
    
    def __str__(self):
        return self.titulo
    
    def get_absolute_url(self):
        return reverse('evento_detalle', args=[str(self.id)])
    
    def actualizar_estado_automatico(self):
        now = timezone.now()

        if self.estado == 'cancelado':
            return

        nuevo_estado = None
        if now < self.fecha_inicio:
            nuevo_estado = 'agendado'
        elif self.fecha_inicio <= now <= self.fecha_fin:
            nuevo_estado = 'en_curso'
        elif now > self.fecha_fin:
            nuevo_estado = 'finalizado'

        if nuevo_estado and nuevo_estado != self.estado:
            self.estado = nuevo_estado
            self.save()

            from .models import HistorialEvento  # para evitar import circular

            HistorialEvento.objects.create(
                evento=self,
                usuario=None,  # SISTEMA
                accion='actualización de estado',
                descripcion=f"El sistema cambió el estado a '{self.get_estado_display()}'."
            )

    def usuario_puede_modificar(self, user):
        return (
            user == self.creador or
            getattr(user.perfil, 'es_admin_agenda', False) or
            user.is_superuser
        )
    
    def get_color_estado(self):
        if self.estado == 'en_curso':
            return '#FFC107'  # Amarillo
        elif self.estado == 'finalizado':
            return '#6C757D'  # Gris
        elif self.estado == 'cancelado':
            return '#DC3545'  # Rojo
        return self.color  # color original definido por el usuario
    
class HistorialEvento(models.Model):
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='historial')
    usuario = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    fecha = models.DateTimeField(auto_now_add=True)
    accion = models.CharField(max_length=50)  # creación, edición, cancelación, estado, etc.
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-fecha']  # lo más reciente primero

    def __str__(self):
        usuario_str = self.usuario.username if self.usuario else "SISTEMA"
        return f"{self.accion.upper()} por {usuario_str} el {self.fecha.strftime('%d/%m/%Y %H:%M')}"

def ruta_respaldo_evento(instance, filename):
    # Guarda el archivo en: media/eventos/respaldo/evento_<id>/<nombre original>
    return f"eventos/respaldo/evento_{instance.evento.id}/{filename}"

class ArchivoRespaldo(models.Model):
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='archivos_respaldo')
    archivo = models.FileField(
        upload_to=ruta_respaldo_evento,
        validators=[
            FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'png'])
        ]
    )
    nombre_original = models.CharField(max_length=255)
    fecha_subida = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Archivo de respaldo para {self.evento.titulo}"