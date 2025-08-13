from django.shortcuts import render
from django.http import JsonResponse
from .models import FirmaElectronica
import requests
from requests.exceptions import Timeout
from requests_toolbelt.multipart.encoder import MultipartEncoder
from usuarios.decorators import permiso_firma_requerido
from django.conf import settings

@permiso_firma_requerido
def firma_home(request):
    if request.method == 'POST':
        # Credenciales del modal (no loggear)
        sign_user = request.POST.get('sign_user', '').strip()
        sign_password = request.POST.get('sign_password', '').strip()
        sign_pin = request.POST.get('sign_pin', '').strip()

        files = request.FILES.getlist('file_in')
        if not files:
            return JsonResponse({'ok': False, 'error': 'No se recibieron archivos.'}, status=400)

        results = []
        for f in files:
            try:
                file_content = f.read()  # leer en memoria una vez

                multipart_data = MultipartEncoder(
                    fields={
                        'env': settings.SIGNBOX_ENV,
                        'format': settings.SIGNBOX_FORMAT,
                        'username': sign_user,
                        'password': sign_password,
                        'pin': sign_pin,
                        'level': settings.SIGNBOX_LEVEL,
                        'billing_username': settings.SIGNBOX_BILLING_USERNAME,
                        'billing_password': settings.SIGNBOX_BILLING_PASSWORD,
                        'identifier': 'DS0',
                        'img_bookmark': settings.SIGNBOX_IMG_BOOKMARK,
                        'img_name': settings.SIGNBOX_IMG_NAME,
                        'paragraph_format': '[{"font":["Universal",10],"align":"right","format":[" Firmado digitalmente por: $(CN)s","O=$(O)s","C=$(C)s","S=$(S)s"]}]',
                        'position': settings.SIGNBOX_POSITION,
                        'npage': str(settings.SIGNBOX_NPAGE),
                        'reason': settings.SIGNBOX_REASON,
                        'location': settings.SIGNBOX_LOCATION,
                        'file_in': (f.name, file_content, 'application/pdf')
                    }
                )
                headers = {'Content-Type': multipart_data.content_type}
                endpoint = f"{settings.SIGNBOX_BASE_URL}{settings.SIGNBOX_SIGN_ENDPOINT}"

                resp = requests.post(endpoint, headers=headers, data=multipart_data, timeout=10)
                print(f"[API] {f.name}: {resp.status_code} -> {resp.text}")

                if resp.status_code == 200 and 'id=' in resp.text:
                    api_id = resp.text.split('=')[1].strip()

                    # Guardar archivo original y registro
                    from django.core.files.uploadedfile import InMemoryUploadedFile
                    import io
                    file_io = io.BytesIO(file_content)
                    new_file = InMemoryUploadedFile(
                        file_io, 'file_in', f.name, 'application/pdf', len(file_content), None
                    )
                    firma = FirmaElectronica(
                        archivo=new_file,
                        nombre_original=f.name,  # nuevo
                        api_id=api_id,
                        usuario=request.user,
                        estado=FirmaElectronica.Estados.EN_PROCESO,  # nuevo
                        error_msg=''  # nuevo
                    )
                    firma.save()

                    results.append({'filename': f.name, 'api_id': api_id, 'status': 'ok'})
                else:

                    FirmaElectronica.objects.create(
                        archivo=new_file,  # o f directamente
                        nombre_original=f.name,
                        usuario=request.user,
                        estado=FirmaElectronica.Estados.ERROR,
                        error_msg=f'API {resp.status_code}: {resp.text[:200]}'
                    )

                    results.append({
                        'filename': f.name,
                        'api_id': None,
                        'status': 'error',
                        'error': f'API {resp.status_code}: {resp.text[:200]}'
                    })

            except Timeout:
                results.append({'filename': f.name, 'api_id': None, 'status': 'error', 'error': 'Tiempo de espera excedido'})
            except requests.RequestException as e:
                results.append({'filename': f.name, 'api_id': None, 'status': 'error', 'error': f'Error de red: {str(e)}'})
            except Exception as e:
                results.append({'filename': f.name, 'api_id': None, 'status': 'error', 'error': f'Error inesperado: {str(e)}'})

        # ok=True si al menos uno salió bien
        any_ok = any(r.get('status') == 'ok' for r in results)
        return JsonResponse({'ok': any_ok, 'results': results})

    return render(request, 'firmaElectronica/firma_home.html')
