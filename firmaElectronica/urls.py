from django.urls import path
from .views import firma_home  # Importa la vista

urlpatterns = [
    path('', firma_home, name='firma_home'),
]
