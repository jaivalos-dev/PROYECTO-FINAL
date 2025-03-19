
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('agenda/', include('agenda.urls')),
    path('firmaElectronica/', include('firmaElectronica.urls')),
]
