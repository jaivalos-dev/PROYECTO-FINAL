from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Perfil

class PerfilInline(admin.StackedInline):
    model = Perfil
    can_delete = False
    verbose_name_plural = 'Perfiles'

class UserAdmin(BaseUserAdmin):
    inlines = (PerfilInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_permiso_agenda', 'get_permiso_firma')
    
    def get_permiso_agenda(self, obj):
        return obj.perfil.permiso_agenda
    get_permiso_agenda.short_description = 'Acceso Agenda'
    get_permiso_agenda.boolean = True
    
    def get_permiso_firma(self, obj):
        return obj.perfil.permiso_firma
    get_permiso_firma.short_description = 'Acceso Firma'
    get_permiso_firma.boolean = True

# Re-registrar UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)