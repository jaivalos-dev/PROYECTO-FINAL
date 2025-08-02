from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import error_404_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('agenda/', include('agenda.urls')),
    path('firmaElectronica/', include('firmaElectronica.urls')),
    path('usuarios/', include('usuarios.urls')),  # Nueva URL
]

# Añadir esta línea para servir archivos de medios en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = error_404_view