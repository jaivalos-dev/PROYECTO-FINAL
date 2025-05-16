from django.db import models
from django.contrib.auth.models import User

class FirmaElectronica(models.Model):
    archivo = models.FileField(upload_to='firmas/')  
    api_id = models.CharField(max_length=255)  
    fecha_creacion = models.DateTimeField(auto_now_add=True)  
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='firmas', null=True) 

    def __str__(self):
        return f'Firma {self.api_id} - {self.archivo.name}'