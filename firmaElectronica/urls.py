# firmaElectronica/urls.py
from django.urls import path
from .views import firma_home, signbox_urlback, signbox_url_out, sign_status, historial_firmados, descargar_documento_firmado, reportes_firma, historial_detalle
# from proyectoFinal.firmaElectronica import views

urlpatterns = [
    path('', firma_home, name='firma_home'),
    path('sign/status/', sign_status, name='sign_status'),
    path('historial/', historial_firmados, name='historial_firmados'),
    path('descargar/<int:pk>/', descargar_documento_firmado, name='descargar_documento_firmado'),  
    path('reportes/', reportes_firma, name='reportes'),
    path('historial/detalle/<int:pk>/', historial_detalle, name='historial_detalle'),
]
