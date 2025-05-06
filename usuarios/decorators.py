from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from functools import wraps
from django.contrib import messages

def permiso_agenda_requerido(function):
    @wraps(function)
    def wrap(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if request.user.is_superuser or request.user.perfil.permiso_agenda:
            return function(request, *args, **kwargs)
        else:
            messages.error(request, "No tienes permiso para acceder al módulo de Agenda.")
            return HttpResponseForbidden("No tienes permiso para acceder a esta página.")
    return wrap

def permiso_firma_requerido(function):
    @wraps(function)
    def wrap(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if request.user.is_superuser or request.user.perfil.permiso_firma:
            return function(request, *args, **kwargs)
        else:
            messages.error(request, "No tienes permiso para acceder al módulo de Firma Electrónica.")
            return HttpResponseForbidden("No tienes permiso para acceder a esta página.")
    return wrap

def admin_agenda_requerido(function):
    @wraps(function)
    def wrap(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if request.user.is_superuser or request.user.perfil.es_admin_agenda:
            return function(request, *args, **kwargs)
        else:
            messages.error(request, "Necesitas ser administrador del módulo de Agenda para acceder a esta página.")
            return HttpResponseForbidden("No tienes permiso para acceder a esta página.")
    return wrap

def admin_firma_requerido(function):
    @wraps(function)
    def wrap(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if request.user.is_superuser or request.user.perfil.es_admin_firma:
            return function(request, *args, **kwargs)
        else:
            messages.error(request, "Necesitas ser administrador del módulo de Firma Electrónica para acceder a esta página.")
            return HttpResponseForbidden("No tienes permiso para acceder a esta página.")
    return wrap