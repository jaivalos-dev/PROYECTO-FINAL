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
        file_in = request.FILES['file_in']
        print("1. Archivo recibido:", file_in.name)  # Log 1

        # Guardar una copia del contenido del archivo
        file_content = file_in.read()
        print("2. Contenido del archivo leído")  # Log 2
        
        # Leer credenciales del modal (sin loggear)
        sign_user = request.POST.get('sign_user', '').strip()
        sign_password = request.POST.get('sign_password', '').strip()
        sign_pin = request.POST.get('sign_pin', '').strip()        

        # Crear el multipart form data
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
                'file_in': (file_in.name, file_content, 'application/pdf')
            }
        )

        headers = {
            'Content-Type': multipart_data.content_type
        }

        try:
            endpoint = f"{settings.SIGNBOX_BASE_URL}{settings.SIGNBOX_SIGN_ENDPOINT}"
            response = requests.post(endpoint, headers=headers, data=multipart_data, timeout=10)

            print("Respuesta del api: ", response.text)

            if response.status_code == 200:
                api_id = response.text.split('=')[1].strip()
                print("3. API ID recibido:", api_id)  # Log 3

                from django.core.files.uploadedfile import InMemoryUploadedFile
                import io
                file_io = io.BytesIO(file_content)
                new_file = InMemoryUploadedFile(
                    file_io,
                    'file_in',
                    file_in.name,
                    'application/pdf',
                    len(file_content),
                    None
                )

                print("4. Nuevo archivo creado en memoria")  # Log 4

                try:
                    firma = FirmaElectronica(
                        archivo=new_file,
                        api_id=api_id,
                        usuario=request.user
                    )
                    print("5. Objeto FirmaElectronica creado")  # Log 5
                    firma.save()
                    print("6. Objeto guardado en la base de datos")  # Log 6
                    saved_firma = FirmaElectronica.objects.get(api_id=api_id)
                    print("7. Objeto verificado en la base de datos:", saved_firma)  # Log 7

                except Exception as db_error:
                    return JsonResponse({
                        'ok': False,
                        'error': f'Error al guardar en la base de datos: {str(db_error)}'
                    })

                return JsonResponse({'ok': True, 'api_id': api_id})

            else:
                return JsonResponse({
                    'ok': False,
                    'error': f'Error en la API ({response.status_code}): {response.text}'
                })

        except Timeout:
            return JsonResponse({'ok': False, 'error': 'Tiempo de espera excedido'})
        except requests.RequestException as e:
            return JsonResponse({'ok': False, 'error': f'Error en la solicitud: {str(e)}'})
        except Exception as e:
            return JsonResponse({'ok': False, 'error': f'Error inesperado: {str(e)}'})

    return render(request, 'firmaElectronica/firma_home.html')