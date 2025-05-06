from django import forms
from .models import Evento
from django.utils import timezone

class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = ['titulo', 'descripcion', 'fecha_inicio', 'fecha_fin', 'ubicacion', 'organizador', 'color', 'estado']
        widgets = {
            'fecha_inicio': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'min': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            }),
            'fecha_fin': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'min': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            }),
            'color': forms.TextInput(attrs={'type': 'color'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get('fecha_inicio')
        fecha_fin = cleaned_data.get('fecha_fin')
        
        if fecha_inicio and fecha_fin:
            if fecha_fin <= fecha_inicio:
                raise forms.ValidationError('La fecha de finalización debe ser posterior a la fecha de inicio.')
        
        return cleaned_data