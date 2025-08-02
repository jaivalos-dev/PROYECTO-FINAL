from django.urls import path
from .views import home, error_404_view

urlpatterns = [
    path('', home, name='home'),
    # path('hola/', error_404_view, name='error_404'),
]

handler404 = error_404_view