from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.db.models import Q
from .models import Evento, HistorialEvento, ArchivoRespaldo
from django.urls import reverse_lazy
from django.contrib import messages
from .forms import EventoForm, ArchivoRespaldoForm
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
import datetime as dt


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
        archivos = request.FILES.getlist('archivo')  # múltiples archivos
        form_archivos = ArchivoRespaldoForm()

        if form.is_valid():

            if len(archivos) > 2:
                messages.error(request, 'Solo puedes subir un máximo de 2 archivos.')
                return render(request, 'agenda/evento_form.html', {'form': form})

            peso_total = sum(a.size for a in archivos)
            if peso_total > 2 * 1024 * 1024:
                messages.error(request, 'El tamaño total de los archivos no puede superar los 2MB.')
                return render(request, 'agenda/evento_form.html', {'form': form})

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

            # Si es recurrente, generar repeticiones
            if form.cleaned_data.get('repetir'):
                frecuencia = form.cleaned_data['frecuencia']
                fecha_inicio = form.cleaned_data['fecha_inicio']
                fecha_fin = form.cleaned_data['fecha_fin']
                fecha_limite = dt.datetime.combine(form.cleaned_data['fecha_limite_repeticion'], dt.time.min)

                fecha_base_inicio = fecha_inicio
                fecha_base_fin = fecha_fin
                contador = 0

                while True:
                    # Avanzar a la siguiente repetición
                    if frecuencia == 'diaria':
                        fecha_base_inicio += dt.timedelta(days=1)
                        fecha_base_fin += dt.timedelta(days=1)
                    elif frecuencia == 'semanal':
                        fecha_base_inicio += dt.timedelta(weeks=1)
                        fecha_base_fin += dt.timedelta(weeks=1)
                    elif frecuencia == 'mensual':
                        mes = fecha_base_inicio.month + 1
                        anio = fecha_base_inicio.year + (mes - 1) // 12
                        mes = (mes - 1) % 12 + 1
                        dia = min(fecha_base_inicio.day, 28)
                        fecha_base_inicio = dt.datetime(anio, mes, dia, fecha_base_inicio.hour, fecha_base_inicio.minute)
                        fecha_base_fin = fecha_base_inicio + (fecha_fin - fecha_inicio)

                    if fecha_base_inicio > fecha_limite:
                        break

                    evento_hijo = Evento.objects.create(
                        titulo=evento.titulo,
                        descripcion=evento.descripcion,
                        fecha_inicio=fecha_base_inicio,
                        fecha_fin=fecha_base_fin,
                        ubicacion=evento.ubicacion,
                        organizador=evento.organizador,
                        color=evento.color,
                        creador=evento.creador,
                        estado='agendado',
                        repetir=False,
                        frecuencia=frecuencia,
                        fecha_limite_repeticion=form.cleaned_data['fecha_limite_repeticion'],
                        evento_padre=evento
                    )

                    HistorialEvento.objects.create(
                        evento=evento_hijo,
                        usuario=None,
                        accion='creación',
                        descripcion=f'Evento creado automáticamente como repetición del evento \"{evento.titulo}\".'
                    )

                    contador += 1
                    if contador > 100:
                        messages.warning(request, "Se alcanzó el límite de 100 repeticiones. Solo se generaron las primeras 100.")
                        break
                
                if contador > 0:
                    HistorialEvento.objects.create(
                        evento=evento,
                        usuario=None,
                        accion='creación',
                        descripcion=f'Se generaron automáticamente {contador} evento(s) recurrentes como parte de esta serie.'
                    )

            # Guardar archivos
            for archivo in archivos:
                form_archivo = ArchivoRespaldoForm(files={'archivo': archivo})
                if form_archivo.is_valid():
                    archivo_obj = form_archivo.save(commit=False)
                    archivo_obj.evento = evento
                    archivo_obj.nombre_original = archivo.name
                    archivo_obj.save()
                else:
                    messages.error(request, f"Archivo no válido: {archivo.name}")
                    return render(request, 'agenda/evento_form.html', {'form': form})
                
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
        archivos = request.FILES.getlist('archivo')
        if evento.evento_padre:
            archivos = []   
        form_archivos = ArchivoRespaldoForm()   
        if form.is_valid():
            evento_actualizado = form.save(commit=False)

        # Determinar el evento padre
        evento_raiz = evento.evento_padre if evento.evento_padre else evento

        # Calcular duración nueva
        nueva_duracion = evento_actualizado.fecha_fin - evento_actualizado.fecha_inicio

        # Aplicar cambios a los eventos de la serie
        for ev in evento_raiz.repeticiones.exclude(id=evento.pk):
            offset = ev.fecha_inicio - evento.fecha_inicio  # distancia original respecto al evento editado

            ev.fecha_inicio = evento_actualizado.fecha_inicio + offset
            ev.fecha_fin = ev.fecha_inicio + nueva_duracion

            ev.titulo = evento_actualizado.titulo
            ev.descripcion = evento_actualizado.descripcion
            ev.ubicacion = evento_actualizado.ubicacion
            ev.organizador = evento_actualizado.organizador
            ev.color = evento_actualizado.color
            ev.save()

            HistorialEvento.objects.create(
                evento=ev,
                usuario=request.user,
                accion='edición',
                descripcion='Evento actualizado como parte de una edición masiva de la serie.'
            )
            
            # Verificar si hay eventos traslapados, excluyendo el evento actual
            eventos_traslapados = Evento.objects.filter(
                Q(fecha_inicio__lt=evento.fecha_fin) & 
                Q(fecha_fin__gt=evento.fecha_inicio) & 
                Q(ubicacion=evento.ubicacion)
            ).exclude(id=evento.id if 'evento' in locals() else None).exclude(estado='cancelado')
            
            if eventos_traslapados.exists():
                messages.error(request, f'Ya existe un evento agendado en ese horario: "{eventos_traslapados.first().titulo}"')
                return render(request, 'agenda/evento_form.html', {'form': form, 'evento': evento})
            
            form.cleaned_data['repetir'] = evento.repetir
            form.cleaned_data['frecuencia'] = evento.frecuencia
            form.cleaned_data['fecha_limite_repeticion'] = evento.fecha_limite_repeticion   

            evento_actualizado.save()
            evento_actualizado.actualizar_estado_automatico()
            evento_actualizado.save()
            
            # VALIDAR CANTIDAD
            if len(archivos) + evento.archivos_respaldo.count() > 2:
                messages.error(request, "Solo se permiten hasta 2 archivos de respaldo por evento.")
                return render(request, 'agenda/evento_form.html', {
                    'form': form,
                    'evento': evento,
                    'form_archivos': form_archivos
                })

            # VALIDAR PESO TOTAL
            peso_total = sum(archivo.size for archivo in archivos)
            if peso_total > 2 * 1024 * 1024:
                messages.error(request, "El tamaño total de archivos no debe superar los 2MB.")
                return render(request, 'agenda/evento_form.html', {
                    'form': form,
                    'evento': evento,
                    'form_archivos': form_archivos
                })

            # GUARDAR ARCHIVOS
            for archivo in archivos:
                form_archivo = ArchivoRespaldoForm(files={'archivo': archivo})
                if form_archivo.is_valid():
                    archivo_obj = form_archivo.save(commit=False)
                    archivo_obj.evento = evento_actualizado
                    archivo_obj.nombre_original = archivo.name
                    archivo_obj.save()
                else:
                    messages.error(request, f"Archivo no válido: {archivo.name}")
                    return render(request, 'agenda/evento_form.html', {
                        'form': form,
                        'evento': evento,
                        'form_archivos': ArchivoRespaldoForm()
                    })

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
    
    return render(request, 'agenda/evento_form.html', {
        'form': form,
        'evento': evento,
        'form_archivos': ArchivoRespaldoForm()
    })

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
        cancelar_serie = request.POST.get('cancelar_serie') == '1'

        if cancelar_serie:
            # Si es hijo, cancelamos desde el padre
            padre = evento.evento_padre if evento.evento_padre else evento

            eventos_a_cancelar = [padre] + list(padre.repeticiones.all())
        else:
            eventos_a_cancelar = [evento]

        for ev in eventos_a_cancelar:
            ev.estado = 'cancelado'
            ev.save()

            HistorialEvento.objects.create(
                evento=ev,
                usuario=request.user,
                accion='cancelación',
                descripcion='Evento cancelado por el usuario como parte de una cancelación individual o masiva.'
            )

            # Enviar correo solo si no es SISTEMA (opcional)
            if ev.creador.email:
                send_mail(
                    subject=f"Evento cancelado: {ev.titulo}",
                    message=(
                        f"Hola {ev.creador.first_name or ev.creador.username},\n\n"
                        f"Tu evento '{ev.titulo}' ha sido cancelado correctamente.\n"
                        f"Fecha y hora: {ev.fecha_inicio.strftime('%d/%m/%Y %H:%M')} a {ev.fecha_fin.strftime('%d/%m/%Y %H:%M')}\n"
                        f"Ubicación: {ev.ubicacion or 'No especificada'}\n"
                        f"Estado actual: {ev.get_estado_display()}\n\n"
                        f"Gracias por mantener tu agenda actualizada.\n"
                    ),
                    from_email=None,
                    recipient_list=[ev.creador.email],
                    fail_silently=False,
                )

        messages.success(request, f"Se canceló correctamente el evento{' y su serie completa' if cancelar_serie else ''}.")
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

@permiso_agenda_requerido
def eliminar_archivo_respaldo(request, pk):
    archivo = get_object_or_404(ArchivoRespaldo, pk=pk)
    evento = archivo.evento

    if request.user != evento.creador and not request.user.is_superuser:
        return HttpResponseForbidden("No tienes permiso para eliminar este archivo.")

    archivo.archivo.delete(save=False)
    archivo.delete()
    messages.success(request, "Archivo eliminado exitosamente.")
    return redirect('editar_evento', pk=evento.pk)