from django.urls import path
from .views import (
    agenda_home, 
    crear_evento, 
    editar_evento, 
    eliminar_evento, 
    cancelar_evento,
    eventos_json,
    exportar_eventos_excel,
    exportar_eventos_pdf, 
    eliminar_archivo_respaldo
)

urlpatterns = [
    path('', agenda_home, name='agenda_home'),
    path('evento/crear/', crear_evento, name='crear_evento'),
    path('evento/editar/<int:pk>/', editar_evento, name='editar_evento'),
    path('evento/eliminar/<int:pk>/', eliminar_evento, name='eliminar_evento'),
    path('evento/cancelar/<int:pk>/', cancelar_evento, name='cancelar_evento'),
    path('eventos/json/', eventos_json, name='eventos_json'),
    path('exportar_excel/', exportar_eventos_excel, name='exportar_eventos_excel'),
    path('exportar_pdf/', exportar_eventos_pdf, name='exportar_eventos_pdf'),
    path('archivo/eliminar/<int:pk>/', eliminar_archivo_respaldo, name='eliminar_archivo_respaldo'),

]