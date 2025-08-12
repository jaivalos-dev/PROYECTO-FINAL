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
    
    TIPO_PERMISO_CHOICES = (
        ('full', 'Acceso Completo'),
        ('agenda', 'Solo Agenda'),
        ('firma', 'Solo Firma Electrónica'),
        ('ninguno', 'Sin Acceso'),
    )
    
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    nombre_completo = models.CharField(max_length=200, blank=True)
    telefono = models.CharField(max_length=15, blank=True)
    departamento = models.CharField(max_length=50, choices=DEPARTAMENTO_CHOICES, default='otro')
    puesto = models.CharField(max_length=100, blank=True)
    ROL_CHOICES = (
        ('admin', 'Administrador'),
        ('operador', 'Operador'),
    )
    rol = models.CharField(max_length=10, choices=ROL_CHOICES, default='operador')
    # Simplificación del sistema de permisos
    tipo_permiso = models.CharField(max_length=10, choices=TIPO_PERMISO_CHOICES, default='ninguno')
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    # Propiedades para mantener compatibilidad con código existente
    @property
    def permiso_agenda(self):
        return self.tipo_permiso in ['full', 'agenda']
    
    @property
    def permiso_firma(self):
        return self.tipo_permiso in ['full', 'firma']
    
    @property
    def es_admin_agenda(self):
        return self.tipo_permiso == 'full'
    
    @property
    def es_admin_firma(self):
        return self.tipo_permiso == 'full'
    
    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfiles"
    
    def __str__(self):
        return f"Perfil de {self.usuario.username}"

# Señales para crear/actualizar perfil cuando se crea/actualiza usuario
@receiver(post_save, sender=User)
def crear_o_guardar_perfil(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(usuario=instance)  # se crea automático al crear usuario
    else:
        # Si por alguna razón no existe, la creamos (robusto ante datos viejos)
        if not hasattr(instance, 'perfil'):
            Perfil.objects.create(usuario=instance)
        else:
            instance.perfil.save()

@receiver(post_save, sender=User)
def guardar_perfil(sender, instance, **kwargs):
    if hasattr(instance, 'perfil'):
        instance.perfil.save()
    else:
        Perfil.objects.create(usuario=instance)