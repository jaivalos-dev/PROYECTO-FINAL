from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.db.models import Q
from .models import Evento, HistorialEvento
from django.urls import reverse_lazy
from django.contrib import messages
from .forms import EventoForm
from usuarios.decorators import permiso_agenda_requerido, admin_agenda_requerido
import openpyxl
from django.http import HttpResponse
from django.utils.dateparse import parse_datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from django.core.mail import send_mail


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

            HistorialEvento.objects.create(
                evento=evento,
                usuario=request.user,
                accion='creación',
                descripcion='Evento creado por el usuario.'
            )

            asunto = f'Evento creado: {evento.titulo}'
            mensaje = (
                f"Hola {request.user.first_name or request.user.username},\n\n"
                f"Tu evento '{evento.titulo}' ha sido creado exitosamente.\n"
                f"Fecha y hora: {evento.fecha_inicio.strftime('%d/%m/%Y %H:%M')} a {evento.fecha_fin.strftime('%d/%m/%Y %H:%M')}\n"
                f"Ubicación: {evento.ubicacion or 'No especificada'}\n"
                f"Estado: {evento.get_estado_display()}\n\n"
                f"Gracias por usar el sistema de calendarización.\n"
            )

            send_mail(
                subject=asunto,
                message=mensaje,
                from_email=None,  # Usa DEFAULT_FROM_EMAIL
                recipient_list=[request.user.email],
                fail_silently=False,
            )

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
            evento_actualizado.actualizar_estado_automatico()
            evento_actualizado.save()
            messages.success(request, 'Evento actualizado exitosamente.')

            HistorialEvento.objects.create(
                evento=evento_actualizado,
                usuario=request.user,
                accion='edición',
                descripcion='Evento editado por el usuario.'
            )

            asunto = f'Evento editado: {evento_actualizado.titulo}'
            mensaje = (
                f"Hola {request.user.first_name or request.user.username},\n\n"
                f"Tu evento '{evento_actualizado.titulo}' ha sido actualizado.\n"
                f"Nuevo horario: {evento_actualizado.fecha_inicio.strftime('%d/%m/%Y %H:%M')} a {evento_actualizado.fecha_fin.strftime('%d/%m/%Y %H:%M')}\n"
                f"Ubicación: {evento_actualizado.ubicacion or 'No especificada'}\n"
                f"Estado: {evento_actualizado.get_estado_display()}\n\n"
                f"Gracias por mantener tu agenda actualizada.\n"
            )

            send_mail(
                subject=asunto,
                message=mensaje,
                from_email=None,
                recipient_list=[request.user.email],
                fail_silently=False,
            )

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
        asunto = f'Evento eliminado: {evento.titulo}'
        mensaje = (
            f"Hola {request.user.first_name or request.user.username},\n\n"
            f"Tu evento '{evento.titulo}' ha sido eliminado del sistema.\n"
            f"Estaba programado para el {evento.fecha_inicio.strftime('%d/%m/%Y %H:%M')} en {evento.ubicacion or 'No especificada'}.\n\n"
            f"Si no fuiste tú quien lo eliminó, por favor contacta al administrador.\n"
        )

        send_mail(
            subject=asunto,
            message=mensaje,
            from_email=None,
            recipient_list=[request.user.email],
            fail_silently=False,
        )

        HistorialEvento.objects.create(
            evento=evento,
            usuario=request.user,
            accion='eliminación',
            descripcion='Evento eliminado por el usuario.'
        )

        evento.delete()
        messages.success(request, 'Evento eliminado exitosamente.')

        return redirect('agenda_home')
    
    return render(request, 'agenda/evento_confirm_delete.html', {'evento': evento})

@permiso_agenda_requerido
def cancelar_evento(request, pk):
    evento = get_object_or_404(Evento, pk=pk)

    if not evento.usuario_puede_modificar(request.user):
        messages.error(request, 'No tienes permiso para cancelar este evento.')
        return HttpResponseForbidden("No tienes permiso para cancelar este evento.")

    if request.method == 'POST':
        evento.estado = 'cancelado'
        evento.save()

        HistorialEvento.objects.create(
            evento=evento,
            usuario=request.user,
            accion='cancelación',
            descripcion='Evento cancelado por el usuario.'
        )

        # Enviar correo al creador
        asunto = f"Evento cancelado: {evento.titulo}"
        mensaje = (
            f"Hola {evento.creador.first_name or evento.creador.username},\n\n"
            f"Tu evento '{evento.titulo}' ha sido cancelado correctamente.\n"
            f"Fecha y hora: {evento.fecha_inicio.strftime('%d/%m/%Y %H:%M')} a {evento.fecha_fin.strftime('%d/%m/%Y %H:%M')}\n"
            f"Ubicación: {evento.ubicacion or 'No especificada'}\n"
            f"Estado actual: {evento.get_estado_display()}\n\n"
            f"Gracias por mantener tu agenda actualizada.\n"
        )

        send_mail(
            subject=asunto,
            message=mensaje,
            from_email=None,
            recipient_list=[evento.creador.email],
            fail_silently=False,
        )

        messages.success(request, 'Evento cancelado y notificado por correo exitosamente.')
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

@permiso_agenda_requerido
def exportar_eventos_excel(request):

    estado = request.GET.get('estado')
    start = request.GET.get('start')
    end = request.GET.get('end')

    if request.user.is_superuser or getattr(request.user.perfil, 'es_admin_agenda', False):
        eventos = Evento.objects.all()
    else:
        eventos = Evento.objects.filter(creador=request.user)

    if estado:
        eventos = eventos.filter(estado=estado)

    if start and end:
        eventos = eventos.filter(
            fecha_inicio__gte=parse_datetime(start),
            fecha_fin__lte=parse_datetime(end)
        )

    eventos = eventos.order_by('fecha_inicio')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Eventos"

    # Encabezados
    ws.append(["Título", "Inicio", "Fin", "Ubicación", "Organizador", "Estado", "Creador"])

    for evento in eventos:
        ws.append([
            evento.titulo,
            evento.fecha_inicio.strftime("%Y-%m-%d %H:%M"),
            evento.fecha_fin.strftime("%Y-%m-%d %H:%M"),
            evento.ubicacion,
            evento.organizador,
            evento.get_estado_display(),
            evento.creador.username
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=eventos.xlsx'
    wb.save(response)
    return response

@permiso_agenda_requerido
def exportar_eventos_pdf(request):
    from django.utils.dateparse import parse_datetime

    estado = request.GET.get('estado')
    start = request.GET.get('start')
    end = request.GET.get('end')

    if request.user.is_superuser or getattr(request.user.perfil, 'es_admin_agenda', False):
        eventos = Evento.objects.all()
    else:
        eventos = Evento.objects.filter(creador=request.user)

    if estado:
        eventos = eventos.filter(estado=estado)

    if start and end:
        eventos = eventos.filter(
            fecha_inicio__gte=parse_datetime(start),
            fecha_fin__lte=parse_datetime(end)
        )

    eventos = eventos.order_by('fecha_inicio')

    # Configuración del PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="eventos.pdf"'
    
    doc = SimpleDocTemplate(response, pagesize=letter,
        title="Agenda de Eventos Exportada",
        author=request.user.get_full_name() or request.user.username,
        subject="Exportación de eventos filtrados",
        creator="Sistema de Calendarización CCG"
    )
    elements = []
    styles = getSampleStyleSheet()

    # Título
    elements.append(Paragraph("Agenda de Eventos Exportada", styles['Title']))
    elements.append(Spacer(1, 20))

    # Tabla
    data = [["Título", "Inicio", "Fin", "Ubicación", "Estado", "Creador"]]
    for evento in eventos:
        data.append([
            evento.titulo,
            evento.fecha_inicio.strftime("%Y-%m-%d %H:%M"),
            evento.fecha_fin.strftime("%Y-%m-%d %H:%M"),
            evento.ubicacion or "—",
            evento.get_estado_display(),
            evento.creador.username
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0D6EFD")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 10),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,1), (-1,-1), colors.whitesmoke),
    ]))

    elements.append(table)
    doc.build(elements)
    return response