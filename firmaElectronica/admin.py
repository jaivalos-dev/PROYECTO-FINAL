
from django.contrib import admin
from .models import DescargaDocumento

@admin.register(DescargaDocumento)
class DescargaDocumentoAdmin(admin.ModelAdmin):
    list_display = ('documento', 'usuario', 'fecha_descarga', 'ip')
    list_filter = ('usuario', 'fecha_descarga')
    search_fields = ('documento__id', 'usuario__username', 'ip', 'user_agent')
