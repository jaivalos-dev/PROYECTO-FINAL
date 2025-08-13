from django.urls import path
from .views import firma_home 


urlpatterns = [
    path('', firma_home, name='firma_home'),
]
