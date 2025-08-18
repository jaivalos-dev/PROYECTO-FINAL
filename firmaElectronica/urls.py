# firmaElectronica/urls.py
from django.urls import path
from .views import firma_home, signbox_urlback, signbox_url_out, sign_status

urlpatterns = [
    path('', firma_home, name='firma_home'),
    # path('webhooks/signbox/callback/', signbox_urlback, name='signbox_urlback'),
    # path('webhooks/signbox/result/',   signbox_url_out, name='signbox_url_out'),
    path('sign/status/', sign_status, name='sign_status'),

]
