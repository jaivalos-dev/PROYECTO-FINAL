from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .forms import UsuarioRegistroForm, PerfilForm, LoginForm

def registro_usuario(request):
    if request.method == 'POST':
        form_usuario = UsuarioRegistroForm(request.POST)
        form_perfil = PerfilForm(request.POST)
        
        if form_usuario.is_valid() and form_perfil.is_valid():
            usuario = form_usuario.save()
            
            # Completar datos del perfil
            perfil = usuario.perfil
            perfil.telefono = form_perfil.cleaned_data.get('telefono')
            perfil.departamento = form_perfil.cleaned_data.get('departamento')
            perfil.puesto = form_perfil.cleaned_data.get('puesto')
            perfil.nombre_completo = f"{usuario.first_name} {usuario.last_name}"
            perfil.save()
            
            # Por defecto, los usuarios nuevos no tienen permisos
            # Los administradores deben asignar permisos manualmente
            
            # Iniciar sesión automáticamente
            username = form_usuario.cleaned_data.get('username')
            password = form_usuario.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            login(request, user)
            
            messages.success(request, f"¡Registro exitoso! Bienvenido/a, {username}. Un administrador revisará tu cuenta para asignar los permisos correspondientes.")
            return redirect('home')
    else:
        form_usuario = UsuarioRegistroForm()
        form_perfil = PerfilForm()
    
    return render(request, 'usuarios/registro.html', {
        'form_usuario': form_usuario,
        'form_perfil': form_perfil
    })

def login_usuario(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, f"Bienvenido/a, {username}!")
                
                # Redirigir a la página que intentaba acceder o a home
                next_page = request.GET.get('next', 'home')
                return redirect(next_page)
            else:
                messages.error(request, "Usuario o contraseña incorrectos.")
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")
    else:
        form = LoginForm()
    
    return render(request, 'usuarios/login.html', {'form': form})

@login_required
def perfil_usuario(request):
    if request.method == 'POST':
        form = PerfilForm(request.POST, instance=request.user.perfil)
        if form.is_valid():
            form.save()
            messages.success(request, "Tu perfil ha sido actualizado.")
            return redirect('perfil_usuario')
    else:
        form = PerfilForm(instance=request.user.perfil)
    
    return render(request, 'usuarios/perfil.html', {'form': form})

@login_required
def administrar_usuarios(request):
    # Verificar si es superusuario
    if not request.user.is_superuser:
        messages.error(request, "No tienes permisos para acceder a esta página.")
        return redirect('home')
    
    usuarios = User.objects.all().select_related('perfil')
    
    return render(request, 'usuarios/administrar_usuarios.html', {
        'usuarios': usuarios
    })

@login_required
def editar_permisos(request, user_id):
    # Verificar si es superusuario
    if not request.user.is_superuser:
        messages.error(request, "No tienes permisos para acceder a esta página.")
        return redirect('home')
    
    usuario = User.objects.get(id=user_id)
    perfil = usuario.perfil
    
    if request.method == 'POST':
        # Actualizar permisos
        perfil.permiso_agenda = 'permiso_agenda' in request.POST
        perfil.permiso_firma = 'permiso_firma' in request.POST
        perfil.es_admin_agenda = 'es_admin_agenda' in request.POST
        perfil.es_admin_firma = 'es_admin_firma' in request.POST
        perfil.save()
        
        messages.success(request, f"Permisos actualizados para {usuario.username}")
        return redirect('administrar_usuarios')
    
    return render(request, 'usuarios/editar_permisos.html', {
        'usuario': usuario,
        'perfil': perfil
    })

def acceso_denegado(request, message=None):
    return render(request, 'usuarios/acceso_denegado.html', {'message': message})