from django.shortcuts import render
from django.http import JsonResponse
from .models import FirmaElectronica
import requests
from requests.exceptions import Timeout
from requests_toolbelt.multipart.encoder import MultipartEncoder
from usuarios.decorators import permiso_firma_requerido

@permiso_firma_requerido
def firma_home(request):
    if request.method == 'POST':
        file_in = request.FILES['file_in']
        print("1. Archivo recibido:", file_in.name)  # Log 1

        # Guardar una copia del contenido del archivo
        file_content = file_in.read()
        print("2. Contenido del archivo leído")  # Log 2
        
        # Crear el multipart form data
        multipart_data = MultipartEncoder(
            fields={
                'env': 'sandbox',
                'format': 'pades',
                'username': '1087998',
                'password': 'Kqp#3Hn6',
                'pin': 'abc123**',
                'level': 'BES',
                'billing_username': 'ccg@ccg',
                'billing_password': 't2G9T71O',
                'identifier': 'DS0',
                'img_bookmark': 'uanataca',
                'img_name': 'uanataca.argb',
                'paragraph_format': '[{ "font" : ["Universal",10]," align ":" right","format ":[" Firmado digitalmente por: $(CN)s","O=$(O)s","C=$(C)s","S=$(S)s"]}]',
                'position': '300,100,500,150',
                'npage': '0',
                'reason': 'Pruebilla',
                'location': 'Guatemala',
                'file_in': (file_in.name, file_content, 'application/pdf')
            }
        )

        headers = {
            'Content-Type': multipart_data.content_type
        }

        try:
            # Usar requests.request() como en Postman
            response = requests.post(
                "http://192.168.0.27/api/sign",
                headers=headers,
                data=multipart_data,
                timeout=10
            )

            print("Respuesta del api: ", response.text)

            if response.status_code == 200:
                # Parsear la respuesta en formato key=value
                api_id = response.text.split('=')[1].strip()
                print("3. API ID recibido:", api_id)  # Log 3
                
                # Crear un nuevo InMemoryUploadedFile con el contenido original
                from django.core.files.uploadedfile import InMemoryUploadedFile
                import io
                
                # Crear un nuevo archivo en memoria con el contenido original
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
                    # Intentar crear y guardar el objeto
                    firma = FirmaElectronica(
                        archivo=new_file,
                        api_id=api_id,
                        usuario=request.user  # Añadir el usuario actual
                    )
                    print("5. Objeto FirmaElectronica creado")  # Log 5
                    
                    firma.save()
                    print("6. Objeto guardado en la base de datos")  # Log 6
                    
                    # Verificar que se guardó correctamente
                    saved_firma = FirmaElectronica.objects.get(api_id=api_id)
                    print("7. Objeto verificado en la base de datos:", saved_firma)  # Log 7
                    
                except Exception as db_error:
                    print("Error al guardar en la base de datos:", str(db_error))
                    return render(request, 'firmaElectronica/firma_home.html', {
                        'error': f'Error al guardar en la base de datos: {str(db_error)}'
                    })

                return render(request, 'firmaElectronica/firma_home.html', {
                    'response': 'Firma guardada exitosamente',
                    'api_id': api_id
                })
            
            else:
                return render(request, 'firmaElectronica/firma_home.html', {
                    'error': f'Error en la API. Código de estado: {response.status_code}. Respuesta: {response.text}'
                })

        except Timeout:
            return render(request, 'firmaElectronica/firma_home.html', {
                'error': 'La solicitud a la API ha excedido el tiempo de espera.'
            })
        except requests.RequestException as e:
            return render(request, 'firmaElectronica/firma_home.html', {
                'error': f'Se produjo un error en la solicitud: {str(e)}'
            })
        except Exception as e:
            print("Error al guardar:", str(e))  # Para debugging
            return render(request, 'firmaElectronica/firma_home.html', {
                'error': f'Error inesperado: {str(e)}'
            })

    return render(request, 'firmaElectronica/firma_home.html')