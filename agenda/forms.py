from django import forms
from .models import Evento, ArchivoRespaldo
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
import datetime as dt

class EventoForm(forms.ModelForm):
    # Campos personalizados para fecha y hora
    fecha_inicio_fecha = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="Fecha de inicio"
    )
    fecha_inicio_hora = forms.ChoiceField(
        choices=[(f'{h:02d}:00', f'{h:02d}:00') for h in range(24)] +
                [(f'{h:02d}:30', f'{h:02d}:30') for h in range(24)],
        label="Hora de inicio"
    )
    
    fecha_fin_fecha = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="Fecha de fin"
    )
    fecha_fin_hora = forms.ChoiceField(
        choices=[(f'{h:02d}:00', f'{h:02d}:00') for h in range(24)] +
                [(f'{h:02d}:30', f'{h:02d}:30') for h in range(24)],
        label="Hora de fin"
    )

    repetir = forms.BooleanField(required=False, label="¿Repetir este evento?")
    frecuencia = forms.ChoiceField(
        choices=[
            ('diaria', 'Diariamente'),
            ('semanal', 'Semanalmente'),
            ('mensual', 'Mensualmente'),
        ],
        required=False,
        label="Frecuencia"
    )
    fecha_limite_repeticion = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="Repetir hasta"
    )
    
    class Meta:
        model = Evento
        fields = ['titulo', 'descripcion', 'ubicacion', 'organizador', 'color']
        exclude = ['fecha_inicio', 'fecha_fin']  # Excluimos estos campos ya que los manejaremos con campos personalizados
        widgets = {
            'color': forms.TextInput(attrs={'type': 'color'}),  # Mantener el widget de color
        }
    
    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance', None)
        super(EventoForm, self).__init__(*args, **kwargs)
        
        # Ordenar correctamente las opciones de hora
        hora_choices = []
        for h in range(24):
            hora_choices.append((f'{h:02d}:00', f'{h:02d}:00'))
            hora_choices.append((f'{h:02d}:30', f'{h:02d}:30'))
        
        self.fields['fecha_inicio_hora'].choices = hora_choices
        self.fields['fecha_fin_hora'].choices = hora_choices
        
        # Si estamos editando un evento existente, inicializar los campos personalizados
        if instance:
            self.initial['fecha_inicio_fecha'] = instance.fecha_inicio.date()
            # Redondear a la media hora más cercana
            hora = instance.fecha_inicio.hour
            minutos = instance.fecha_inicio.minute
            if minutos < 15:
                minutos = 0
            elif minutos < 45:
                minutos = 30
            else:
                minutos = 0
                hora = (hora + 1) % 24
            self.initial['fecha_inicio_hora'] = f'{hora:02d}:{minutos:02d}'
            
            self.initial['fecha_fin_fecha'] = instance.fecha_fin.date()
            # Redondear a la media hora más cercana
            hora = instance.fecha_fin.hour
            minutos = instance.fecha_fin.minute
            if minutos < 15:
                minutos = 0
            elif minutos < 45:
                minutos = 30
            else:
                minutos = 0
                hora = (hora + 1) % 24
            self.initial['fecha_fin_hora'] = f'{hora:02d}:{minutos:02d}'
        else:
            # Si es un nuevo evento, inicializar con valores por defecto (ahora redondeado a la media hora)
            now = dt.datetime.now()
            hora = now.hour
            minutos = now.minute
            if minutos < 15:
                minutos = 0
            elif minutos < 45:
                minutos = 30
            else:
                minutos = 0
                hora = (hora + 1) % 24
                
            self.initial['fecha_inicio_fecha'] = now.date()
            self.initial['fecha_inicio_hora'] = f'{hora:02d}:{minutos:02d}'
            
            # La fecha de fin es 30 minutos después por defecto
            end_time = now + dt.timedelta(minutes=30)
            self.initial['fecha_fin_fecha'] = end_time.date()
            hora = end_time.hour
            minutos = end_time.minute
            if minutos < 15:
                minutos = 0
            elif minutos < 45:
                minutos = 30
            else:
                minutos = 0
                hora = (hora + 1) % 24
            self.initial['fecha_fin_hora'] = f'{hora:02d}:{minutos:02d}'

        if instance and instance.pk:
            # Solo ocultar si es edición
            self.fields['repetir'].widget = forms.HiddenInput()
            self.fields['frecuencia'].widget = forms.HiddenInput()
            self.fields['fecha_limite_repeticion'].widget = forms.HiddenInput()
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Obtener los valores de los campos personalizados
        fecha_inicio_fecha = cleaned_data.get('fecha_inicio_fecha')
        fecha_inicio_hora = cleaned_data.get('fecha_inicio_hora')
        fecha_fin_fecha = cleaned_data.get('fecha_fin_fecha')
        fecha_fin_hora = cleaned_data.get('fecha_fin_hora')
        
        # Validar que todos los campos de fecha y hora están presentes
        if not (fecha_inicio_fecha and fecha_inicio_hora and fecha_fin_fecha and fecha_fin_hora):
            raise ValidationError('Todos los campos de fecha y hora son obligatorios.')
        
        # Convertir a objetos datetime
        hora_inicio, minuto_inicio = map(int, fecha_inicio_hora.split(':'))
        hora_fin, minuto_fin = map(int, fecha_fin_hora.split(':'))
        
        fecha_inicio = dt.datetime.combine(
            fecha_inicio_fecha,
            dt.time(hora_inicio, minuto_inicio)
        )
        
        fecha_fin = dt.datetime.combine(
            fecha_fin_fecha,
            dt.time(hora_fin, minuto_fin)
        )
        
        # Validar que la fecha de fin sea posterior a la de inicio
        if fecha_fin <= fecha_inicio:
            raise ValidationError('La fecha y hora de finalización debe ser posterior a la fecha y hora de inicio.')
        
        # Guardar los valores procesados para ser usados en save()
        cleaned_data['fecha_inicio'] = fecha_inicio
        cleaned_data['fecha_fin'] = fecha_fin

        if cleaned_data.get('repetir'):
            frecuencia = cleaned_data.get('frecuencia')
            fecha_limite = cleaned_data.get('fecha_limite_repeticion')
            fecha_inicio = cleaned_data.get('fecha_inicio')

            if not frecuencia or not fecha_limite:
                raise ValidationError("Debes indicar la frecuencia y hasta cuándo repetir el evento.")

            if fecha_inicio and fecha_limite:
                max_fecha = fecha_inicio.date() + dt.timedelta(days=365)
                if fecha_limite > max_fecha:
                    raise ValidationError("La fecha límite de repetición no puede ser mayor a 1 año desde la fecha de inicio.")

        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super(EventoForm, self).save(commit=False)
        
        # Asignar las fechas
        instance.fecha_inicio = self.cleaned_data['fecha_inicio']
        instance.fecha_fin = self.cleaned_data['fecha_fin']
        
        # Asignar configuración de recurrencia
        instance.repetir = self.cleaned_data.get('repetir', False)
        instance.frecuencia = self.cleaned_data.get('frecuencia') or None
        instance.fecha_limite_repeticion = self.cleaned_data.get('fecha_limite_repeticion') or None

        if commit:
            instance.save()

        return instance
    


class ArchivoRespaldoForm(forms.ModelForm):
    class Meta:
        model = ArchivoRespaldo
        fields = ['archivo']
        widgets = {
            'archivo': forms.FileInput(attrs={
                'accept': '.pdf,.jpg,.jpeg,.png'
            })
        }

    def clean_archivo(self):
        archivo = self.cleaned_data.get('archivo')

        if archivo:
            if archivo.size > 2 * 1024 * 1024:  # archivo individual > 2MB
                raise forms.ValidationError("El archivo no debe superar los 2MB.")
        return archivo