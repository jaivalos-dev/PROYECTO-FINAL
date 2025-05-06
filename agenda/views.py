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
    # Actualizar estados de eventos automáticamente
    eventos = Evento.objects.all()
    for evento in eventos:
        evento.actualizar_estado_automatico()
        evento.save()
    
    return render(request, 'agenda/agenda_home.html', {'eventos': eventos})

@permiso_agenda_requerido
def crear_evento(request):
    if request.method == 'POST':
        form = EventoForm(request.POST)
        if form.is_valid():
            evento = form.save(commit=False)
            
            # Validar que la fecha de fin sea posterior a la fecha de inicio
            if evento.fecha_fin <= evento.fecha_inicio:
                messages.error(request, 'La fecha de finalización debe ser posterior a la fecha de inicio.')
                return render(request, 'agenda/evento_form.html', {'form': form})
            
            # Verificar si hay eventos traslapados
            eventos_traslapados = Evento.objects.filter(
                Q(fecha_inicio__lt=evento.fecha_fin) & Q(fecha_fin__gt=evento.fecha_inicio)
            ).exclude(estado='cancelado')
            
            if eventos_traslapados.exists():
                messages.error(request, 'Ya existe un evento agendado en ese horario.')
                return render(request, 'agenda/evento_form.html', {'form': form})
            
            evento.creador = request.user
            evento.save()
            messages.success(request, 'Evento creado exitosamente.')
            return redirect('agenda_home')
    else:
        form = EventoForm(initial={'fecha_inicio': timezone.now()})
    
    return render(request, 'agenda/evento_form.html', {'form': form})

@permiso_agenda_requerido
def editar_evento(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    
    # Verificar que el usuario sea el creador del evento o un administrador
    if not (request.user == evento.creador or request.user.perfil.es_admin_agenda or request.user.is_superuser):
        messages.error(request, 'No tienes permiso para editar este evento.')
        return HttpResponseForbidden("No tienes permiso para editar este evento.")
    
    if request.method == 'POST':
        form = EventoForm(request.POST, instance=evento)
        if form.is_valid():
            evento_actualizado = form.save(commit=False)
            
            # Validar que la fecha de fin sea posterior a la fecha de inicio
            if evento_actualizado.fecha_fin <= evento_actualizado.fecha_inicio:
                messages.error(request, 'La fecha de finalización debe ser posterior a la fecha de inicio.')
                return render(request, 'agenda/evento_form.html', {'form': form, 'evento': evento})
            
            # Verificar si hay eventos traslapados, excluyendo el evento actual
            eventos_traslapados = Evento.objects.filter(
                Q(fecha_inicio__lt=evento_actualizado.fecha_fin) & 
                Q(fecha_fin__gt=evento_actualizado.fecha_inicio)
            ).exclude(id=evento.id).exclude(estado='cancelado')
            
            if eventos_traslapados.exists():
                messages.error(request, 'Ya existe un evento agendado en ese horario.')
                return render(request, 'agenda/evento_form.html', {'form': form, 'evento': evento})
            
            evento_actualizado.save()
            messages.success(request, 'Evento actualizado exitosamente.')
            return redirect('agenda_home')
    else:
        form = EventoForm(instance=evento)
    
    return render(request, 'agenda/evento_form.html', {'form': form, 'evento': evento})

@permiso_agenda_requerido
def eliminar_evento(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    
    # Verificar que el usuario sea el creador del evento o un administrador
    if not (request.user == evento.creador or request.user.perfil.es_admin_agenda or request.user.is_superuser):
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
    if not (request.user == evento.creador or request.user.perfil.es_admin_agenda or request.user.is_superuser):
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
    eventos = Evento.objects.all()
    
    # Actualizar estados automáticamente
    for evento in eventos:
        evento.actualizar_estado_automatico()
        evento.save()
    
    evento_list = []
    for evento in eventos:
        # Definir colores según el estado
        color = evento.color
        if evento.estado == 'en_curso':
            color = '#FFC107'  # Amarillo para eventos en curso
        elif evento.estado == 'finalizado':
            color = '#6C757D'  # Gris para eventos finalizados
        elif evento.estado == 'cancelado':
            color = '#DC3545'  # Rojo para eventos cancelados
        
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