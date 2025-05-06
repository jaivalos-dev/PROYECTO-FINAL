from django.db import models
from django.contrib.auth.models import User

class FirmaElectronica(models.Model):
    archivo = models.FileField(upload_to='firmas/')  # Guarda el archivo subido
    api_id = models.CharField(max_length=255)  # Almacena el ID devuelto por la API
    fecha_creacion = models.DateTimeField(auto_now_add=True)  # Marca la fecha de creación
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='firmas', null=True)  # Usuario que creó la firma

    def __str__(self):
        return f'Firma {self.api_id} - {self.archivo.name}'