from functools import wraps
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from agenda.models import Evento

def permiso_agenda_requerido(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.perfil.permiso_agenda:
            return redirect('acceso_denegado')  # tu vista de acceso denegado
        return view_func(request, *args, **kwargs)
    return wrapper

def permiso_firma_requerido(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.perfil.permiso_firma:
            return redirect('acceso_denegado')
        return view_func(request, *args, **kwargs)
    return wrapper

def solo_creador_o_admin(view_func):
    @wraps(view_func)
    def _wrapped_view(request, pk, *args, **kwargs):
        evento = get_object_or_404(Evento, pk=pk)
        if not evento.usuario_puede_modificar(request.user):
            messages.error(request, 'No tienes permiso para realizar esta acción.')
            return redirect('acceso_denegado')
        return view_func(request, pk, *args, **kwargs)
    return _wrapped_view