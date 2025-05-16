from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Perfil(models.Model):
    DEPARTAMENTO_CHOICES = (
        ('direccion', 'Dirección'),
        ('administrativo', 'Administrativo'),
        ('financiero', 'Financiero'),
        ('recursos_humanos', 'Recursos Humanos'),
        ('tecnologia', 'Tecnología'),
        ('comercial', 'Comercial'),
        ('operaciones', 'Operaciones'),
        ('legal', 'Legal'),
        ('marketing', 'Marketing'),
        ('otro', 'Otro'),
    )
    
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    nombre_completo = models.CharField(max_length=200, blank=True)
    telefono = models.CharField(max_length=15, blank=True)
    departamento = models.CharField(max_length=50, choices=DEPARTAMENTO_CHOICES, default='otro')
    puesto = models.CharField(max_length=100, blank=True)
    permiso_agenda = models.BooleanField(default=False, verbose_name="Acceso al módulo de Agenda")
    permiso_firma = models.BooleanField(default=False, verbose_name="Acceso al módulo de Firma Electrónica")
    es_admin_agenda = models.BooleanField(default=False, verbose_name="Administrador de Agenda")
    es_admin_firma = models.BooleanField(default=False, verbose_name="Administrador de Firma Electrónica")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfiles"
    
    def __str__(self):
        return f"Perfil de {self.usuario.username}"

# Señales para crear/actualizar perfil cuando se crea/actualiza usuario
@receiver(post_save, sender=User)
def crear_perfil(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(usuario=instance)

@receiver(post_save, sender=User)
def guardar_perfil(sender, instance, **kwargs):
    if hasattr(instance, 'perfil'):
        instance.perfil.save()
    else:
        Perfil.objects.create(usuario=instance)