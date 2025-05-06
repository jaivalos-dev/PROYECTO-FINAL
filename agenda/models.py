from django.db import models
from django.urls import reverse
from django.contrib.auth.models import User

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
        """Actualiza el estado del evento basado en la fecha actual"""
        from django.utils import timezone
        now = timezone.now()
        
        if self.estado == 'cancelado':
            return  # No cambiar estado si fue cancelado manualmente
            
        if now < self.fecha_inicio:
            self.estado = 'agendado'
        elif self.fecha_inicio <= now <= self.fecha_fin:
            self.estado = 'en_curso'
        elif now > self.fecha_fin:
            self.estado = 'finalizado'