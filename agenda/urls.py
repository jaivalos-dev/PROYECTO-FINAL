from django.urls import path
from .views import agenda_home  # Importa la vista

urlpatterns = [
    path('', agenda_home, name='agenda_home'),
]
