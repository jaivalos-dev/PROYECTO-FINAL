from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Perfil

# 🔹 Desregistrar el admin original de User
admin.site.unregister(User)

class PerfilInline(admin.StackedInline):
    model = Perfil
    can_delete = False
    verbose_name_plural = 'Perfiles'
    fields = (
        'nombre_completo', 'telefono', 'departamento', 'puesto',
        'rol', 'tipo_permiso'
    )
    extra = 0
    max_num = 1

class UserAdmin(BaseUserAdmin):
    inlines = (PerfilInline,)
    list_display = (
        'username', 'email', 'first_name', 'last_name', 'is_staff',
        'get_rol', 'get_permiso_agenda', 'get_permiso_firma'
    )

    def get_inline_instances(self, request, obj=None):
        # Ocultar inline al crear para evitar choque con la señal post_save
        if not obj:
            return []
        return super().get_inline_instances(request, obj)

    # ---- Métodos para mostrar datos en la lista ----
    def get_rol(self, obj):
        perfil = getattr(obj, 'perfil', None)
        return getattr(perfil, 'rol', '')
    get_rol.short_description = 'Rol'

    def get_permiso_agenda(self, obj):
        perfil = getattr(obj, 'perfil', None)
        return getattr(perfil, 'permiso_agenda', False)
    get_permiso_agenda.short_description = 'Acceso Agenda'
    get_permiso_agenda.boolean = True

    def get_permiso_firma(self, obj):
        perfil = getattr(obj, 'perfil', None)
        return getattr(perfil, 'permiso_firma', False)
    get_permiso_firma.short_description = 'Acceso Firma'
    get_permiso_firma.boolean = True

# 🔹 Registrar la nueva configuración
admin.site.register(User, UserAdmin)
