from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('registro/', views.registro_usuario, name='registro'),
    path('login/', views.login_usuario, name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('perfil/', views.perfil_usuario, name='perfil_usuario'),
    path('administrar/', views.administrar_usuarios, name='administrar_usuarios'),
    path('permisos/<int:user_id>/', views.editar_permisos, name='editar_permisos'),
    path('acceso-denegado/', views.acceso_denegado, name='acceso_denegado'),
]