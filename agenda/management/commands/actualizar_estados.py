from django.core.management.base import BaseCommand
from agenda.models import Evento

class Command(BaseCommand):
    help = 'Actualiza los estados de los eventos automáticamente'

    def handle(self, *args, **options):
        eventos = Evento.objects.all()
        contador = 0
        
        for evento in eventos:
            estado_anterior = evento.estado
            evento.actualizar_estado_automatico()
            
            if estado_anterior != evento.estado:
                evento.save()
                contador += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Se actualizaron {contador} eventos exitosamente')
        )