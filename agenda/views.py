from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.db.models import Q
from .models import Evento
from django.urls import reverse_lazy
from django.contrib import messages
from .forms import EventoForm
from usuarios.decorators import permiso_agenda_requerido, admin_agenda_requerido

@permiso_agenda_requerido
def agenda_home(request):
    now = timezone.now()
    eventos = Evento.objects.all()

    for evento in eventos:
        estado_anterior = evento.estado
        evento.actualizar_estado_automatico()
        if evento.estado != estado_anterior:
            evento.save()

    return render(request, 'agenda/agenda_home.html', {'eventos': eventos})

@permiso_agenda_requerido
def crear_evento(request):
    if request.method == 'POST':
        form = EventoForm(request.POST)
        if form.is_valid():
            evento = form.save(commit=False)
            evento.creador = request.user
            
            # Verificar si hay eventos traslapados
            eventos_traslapados = Evento.objects.filter(
                Q(fecha_inicio__lt=evento.fecha_fin) & 
                Q(fecha_fin__gt=evento.fecha_inicio) & 
                Q(ubicacion=evento.ubicacion)
            ).exclude(id=evento.id if 'evento' in locals() else None).exclude(estado='cancelado')
            
            if eventos_traslapados.exists():
                eventos_conflicto = [f"{e.titulo} ({e.fecha_inicio.strftime('%d/%m/%Y %H:%M')} - {e.fecha_fin.strftime('%d/%m/%Y %H:%M')})" for e in eventos_traslapados]
                print(f"¡CONFLICTO DETECTADO! Eventos traslapados: {', '.join(eventos_conflicto)}")
                messages.error(request, f'Ya existe un evento agendado en ese horario: "{eventos_traslapados.first().titulo}"')
                return render(request, 'agenda/evento_form.html', {'form': form})
            
            evento.save()
            messages.success(request, 'Evento creado exitosamente.')
            return redirect('agenda_home')
        else:
            # Si el formulario no es válido, asegurarnos de que los errores se muestren
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Error en {field}: {error}")
            
            # Si hay errores no relacionados con campos específicos
            for error in form.non_field_errors():
                messages.error(request, error)
    else:
        form = EventoForm()
    
    return render(request, 'agenda/evento_form.html', {'form': form})

@permiso_agenda_requerido
def editar_evento(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    
    # Verificar que el usuario sea el creador del evento o un administrador
    if not evento.usuario_puede_modificar(request.user):
        messages.error(request, 'No tienes permiso para editar este evento.')
        return HttpResponseForbidden("No tienes permiso para editar este evento.")
    
    if request.method == 'POST':
        form = EventoForm(request.POST, instance=evento)
        if form.is_valid():
            evento_actualizado = form.save(commit=False)
            
            # Verificar si hay eventos traslapados, excluyendo el evento actual
            eventos_traslapados = Evento.objects.filter(
                Q(fecha_inicio__lt=evento.fecha_fin) & 
                Q(fecha_fin__gt=evento.fecha_inicio) & 
                Q(ubicacion=evento.ubicacion)
            ).exclude(id=evento.id if 'evento' in locals() else None).exclude(estado='cancelado')
            
            if eventos_traslapados.exists():
                messages.error(request, f'Ya existe un evento agendado en ese horario: "{eventos_traslapados.first().titulo}"')
                return render(request, 'agenda/evento_form.html', {'form': form, 'evento': evento})
            
            evento_actualizado.save()
            messages.success(request, 'Evento actualizado exitosamente.')
            return redirect('agenda_home')
        else:
            # Si el formulario no es válido, asegurarnos de que los errores se muestren
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Error en {field}: {error}")
            
            # Si hay errores no relacionados con campos específicos
            for error in form.non_field_errors():
                messages.error(request, error)
    else:
        form = EventoForm(instance=evento)
    
    return render(request, 'agenda/evento_form.html', {'form': form, 'evento': evento})

@permiso_agenda_requerido
def eliminar_evento(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    
    # Verificar que el usuario sea el creador del evento o un administrador
    if not evento.usuario_puede_modificar(request.user):
        messages.error(request, 'No tienes permiso para eliminar este evento.')
        return HttpResponseForbidden("No tienes permiso para eliminar este evento.")
    
    if request.method == 'POST':
        evento.delete()
        messages.success(request, 'Evento eliminado exitosamente.')
        return redirect('agenda_home')
    
    return render(request, 'agenda/evento_confirm_delete.html', {'evento': evento})

@permiso_agenda_requerido
def cancelar_evento(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    
    # Verificar que el usuario sea el creador del evento o un administrador
    if not evento.usuario_puede_modificar(request.user):
        messages.error(request, 'No tienes permiso para cancelar este evento.')
        return HttpResponseForbidden("No tienes permiso para cancelar este evento.")
    
    if request.method == 'POST':
        evento.estado = 'cancelado'
        evento.save()
        messages.success(request, 'Evento cancelado exitosamente.')
        return redirect('agenda_home')
    
    return render(request, 'agenda/evento_confirm_cancel.html', {'evento': evento})

@permiso_agenda_requerido
def eventos_json(request):
    
    estado = request.GET.get('estado')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    
    eventos = Evento.objects.all()

    if estado:
        eventos = eventos.filter(estado=estado)

    if fecha_inicio and fecha_fin:
        eventos = eventos.filter(
            fecha_inicio__gte=fecha_inicio,
            fecha_fin__lte=fecha_fin
        )
    # Actualizar estados automáticamente
    for evento in eventos:
        evento.actualizar_estado_automatico()
        evento.save()
    
    evento_list = []
    for evento in eventos:
        
        color = evento.get_color_estado()
        
        # Solo incluir eventos no cancelados o si el usuario es el creador/admin
        if evento.estado != 'cancelado' or request.user == evento.creador or request.user.perfil.es_admin_agenda or request.user.is_superuser:
            evento_list.append({
                'id': evento.id,
                'title': evento.titulo,
                'start': evento.fecha_inicio.isoformat(),
                'end': evento.fecha_fin.isoformat(),
                'color': color,
                'url': reverse_lazy('editar_evento', args=[evento.id]),
                'creator': evento.creador.username,
                'status': evento.get_estado_display()
            })
    
    return JsonResponse(evento_list, safe=False)