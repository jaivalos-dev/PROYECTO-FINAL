# firmaElectronica/views.py
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from .models import FirmaElectronica
import requests
from requests.exceptions import Timeout
from requests_toolbelt.multipart.encoder import MultipartEncoder
from usuarios.decorators import permiso_firma_requerido
from django.conf import settings
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from django.utils import timezone
import io
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.views.decorators.http import require_GET


def _build_endpoint_with_id(base: str, pattern: str, api_id: str) -> str:
    base = base.rstrip("/")
    if "{id}" in pattern:
        return f"{base}{pattern.format(id=api_id)}"
    pattern = pattern.lstrip("/")
    # soporta también patrón que termina en "/" -> /api/result/ + id
    if pattern.endswith("/"):
        return f"{base}/{pattern}{api_id}"
    # fallback: querystring ?id=
    sep = "&" if "?" in pattern else "?"
    return f"{base}/{pattern}{sep}id={api_id}"

def _parse_job_text(txt: str):
    # Acepta "state=done&type=sign" o JSON {"state":"done","type":"sign"}
    state = typ = ""
    t = txt.strip()
    try:
        data = requests.models.complexjson.loads(t)  # intenta JSON
        state = (data.get("state") or "").lower()
        typ = (data.get("type") or "").lower()
        return state, typ
    except Exception:
        pass
    for part in t.split("&"):
        if part.startswith("state="):
            state = part.split("=", 1)[1].lower()
        elif part.startswith("type="):
            typ = part.split("=", 1)[1].lower()
    return state, typ

def _signbox_job_status(api_id: str):
    url = _build_endpoint_with_id(settings.SIGNBOX_BASE_URL, settings.SIGNBOX_JOB_ENDPOINT, api_id)
    r = requests.get(url, timeout=10)      # <-- GET
    state, typ = _parse_job_text(r.text)
    return {"state": state, "type": typ, "raw": r.text, "status_code": r.status_code}

def _signbox_fetch_result(api_id: str) -> bytes:
    url = _build_endpoint_with_id(settings.SIGNBOX_BASE_URL, settings.SIGNBOX_RESULT_ENDPOINT, api_id)
    r = requests.get(url, timeout=30)      # <-- GET
    r.raise_for_status()
    return r.content


@require_GET
def sign_status(request):
    """
    Cliente (JS) nos pregunta periódicamente por el estado.
    Si el job ya terminó, descargamos el PDF desde result y lo guardamos en archivo_firmado.
    Devuelve JSON con: {ready:bool, state:str, url?:str, error?:str}
    """
    ref = request.GET.get('ref')
    if not ref:
        return JsonResponse({'ready': False, 'state': 'error', 'error': 'Falta ref'}, status=400)

    try:
        firma = FirmaElectronica.objects.get(ref=ref)
    except FirmaElectronica.DoesNotExist:
        return JsonResponse({'ready': False, 'state': 'error', 'error': 'Ref no encontrada'}, status=404)

    # ¿Ya listo?
    if firma.archivo_firmado:
        return JsonResponse({'ready': True, 'state': 'done', 'url': firma.archivo_firmado.url})

    if not firma.api_id:
        return JsonResponse({'ready': False, 'state': 'waiting', 'error': 'Sin api_id aún'})

    # 1) Consulta estado del job
    job = _signbox_job_status(firma.api_id)
    state = (job.get('state') or '').lower()

    if state in ('done', 'success', 'completed'):
        # 2) Descarga el PDF firmado desde result y guarda en el modelo
        try:
            pdf_bytes = _signbox_fetch_result(firma.api_id)
            filename = f"signed_{firma.api_id}.pdf"
            firma.archivo_firmado.save(filename, ContentFile(pdf_bytes))
            firma.estado = FirmaElectronica.Estados.FIRMADO
            firma.save(update_fields=['archivo_firmado','estado'])
            return JsonResponse({'ready': True, 'state': 'done', 'url': firma.archivo_firmado.url})
        except Exception as e:
            firma.estado = FirmaElectronica.Estados.ERROR
            firma.error_msg = f'Falló result: {str(e)}'
            firma.save(update_fields=['estado','error_msg'])
            return JsonResponse({'ready': False, 'state': 'error', 'error': f'Falló result: {e}'}, status=500)

    if state in ('failed', 'error'):
        firma.estado = FirmaElectronica.Estados.ERROR
        # deja trazabilidad
        raw = job.get('raw','')[:200]
        firma.error_msg = f'Job failed: {raw}'
        firma.save(update_fields=['estado','error_msg'])
        return JsonResponse({'ready': False, 'state': 'failed', 'error': firma.error_msg})

    # sigue procesando
    return JsonResponse({'ready': False, 'state': state or 'processing'})



@permiso_firma_requerido
def firma_home(request):
    if request.method == 'POST':
        sign_user = request.POST.get('sign_user', '').strip()
        sign_password = request.POST.get('sign_password', '').strip()
        sign_pin = request.POST.get('sign_pin', '').strip()

        files = request.FILES.getlist('file_in')
        if not files:
            return JsonResponse({'ok': False, 'error': 'No se recibieron archivos.'}, status=400)

        results = []
        for f in files:
            try:
                # 1) Leemos bytes una vez y construimos un File para guardar
                file_content = f.read()
                file_io = io.BytesIO(file_content)
                django_file = InMemoryUploadedFile(
                    file_io, 'file_in', f.name, 'application/pdf', len(file_content), None
                )

                # 2) Creamos registro EN PROCESO y emitimos token/ref para callbacks
                firma = FirmaElectronica(
                    archivo=django_file,
                    nombre_original=f.name,
                    usuario=request.user,
                    estado=FirmaElectronica.Estados.EN_PROCESO,
                )
                firma.issue_token()
                firma.save()

                use_webhooks = getattr(settings, "USE_SIGNBOX_WEBHOOKS", False)

                # === 1) Campos base SIN webhooks ===
                fields = {
                    'env': settings.SIGNBOX_ENV,
                    'format': settings.SIGNBOX_FORMAT,
                    'username': sign_user,
                    'password': sign_password,
                    'pin': sign_pin,
                    'level': settings.SIGNBOX_LEVEL,
                    'billing_username': settings.SIGNBOX_BILLING_USERNAME,
                    'billing_password': settings.SIGNBOX_BILLING_PASSWORD,
                    'identifier': 'DS0',
                    'paragraph_format': '[{"font":["Universal",10],"align":"right","format":[" Firmado digitalmente por: $(CN)s","O=$(O)s","C=$(C)s","S=$(S)s"]}]',
                    'position': settings.SIGNBOX_POSITION,
                    'npage': str(settings.SIGNBOX_NPAGE),
                    'reason': settings.SIGNBOX_REASON,
                    'location': settings.SIGNBOX_LOCATION,
                    'file_in': (f.name, file_content, 'application/pdf'),
                }

                # === 2) SOLO si habilitas webhooks, añadimos urlback/url_out ===
                if use_webhooks:
                    from django.urls import reverse, NoReverseMatch
                    base_url = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/")
                    if not base_url:
                        base_url = request.build_absolute_uri('/').rstrip('/')
                    try:
                        fields['urlback'] = f"{base_url}{reverse('signbox_urlback')}?ref={firma.ref}&token={firma.cb_token}"
                        fields['url_out']  = f"{base_url}{reverse('signbox_url_out')}?ref={firma.ref}&token={firma.cb_token}"
                    except NoReverseMatch:
                        pass  # no rompemos si aún no están esas rutas

                # === 3) Enviar a SignBox ===
                multipart_data = MultipartEncoder(fields=fields)
                headers = {'Content-Type': multipart_data.content_type}
                endpoint = f"{settings.SIGNBOX_BASE_URL}{settings.SIGNBOX_SIGN_ENDPOINT}"

                resp = requests.post(endpoint, headers=headers, data=multipart_data, timeout=10)
                print(f"[API] {f.name}: {resp.status_code} -> {resp.text}")

                # === 4) Parsear respuesta y devolver ref para el polling ===
                if resp.status_code == 200 and 'id=' in resp.text:
                    api_id = resp.text.split('=', 1)[1].strip()
                    firma.api_id = api_id
                    firma.save(update_fields=['api_id'])
                    results.append({'filename': f.name, 'api_id': api_id, 'status': 'ok', 'ref': str(firma.ref)})
                else:
                    firma.estado = FirmaElectronica.Estados.ERROR
                    firma.error_msg = f'API {resp.status_code}: {resp.text[:200]}'
                    firma.save(update_fields=['estado', 'error_msg'])
                    results.append({'filename': f.name, 'api_id': None, 'status': 'error',
                                    'error': f'API {resp.status_code}: {resp.text[:200]}'})
    
            except Timeout:
                firma.estado = FirmaElectronica.Estados.ERROR
                firma.error_msg = 'Tiempo de espera excedido'
                firma.save(update_fields=['estado', 'error_msg'])
                results.append({'filename': f.name, 'api_id': None, 'status': 'error', 'error': 'Tiempo de espera excedido'})
            except requests.RequestException as e:
                firma.estado = FirmaElectronica.Estados.ERROR
                firma.error_msg = f'Error de red: {str(e)}'
                firma.save(update_fields=['estado', 'error_msg'])
                results.append({'filename': f.name, 'api_id': None, 'status': 'error', 'error': f'Error de red: {str(e)}'})
            except Exception as e:
                # Cualquier error inesperado deja traza en el registro ya creado
                firma.estado = FirmaElectronica.Estados.ERROR
                firma.error_msg = f'Error inesperado: {str(e)}'
                firma.save(update_fields=['estado', 'error_msg'])
                results.append({'filename': f.name, 'api_id': None, 'status': 'error', 'error': f'Error inesperado: {str(e)}'})

        any_ok = any(r.get('status') == 'ok' for r in results)
        return JsonResponse({'ok': any_ok, 'results': results})

    return render(request, 'firmaElectronica/firma_home.html')

@csrf_exempt
def signbox_urlback(request):
    # Recibe JSON con estado/logs del job
    if request.method != 'POST':
        return HttpResponseBadRequest('POST only')

    ref = request.GET.get('ref')
    token = request.GET.get('token')
    if not ref or not token:
        return HttpResponse(status=204)

    try:
        firma = FirmaElectronica.objects.get(ref=ref, cb_token=token)
    except FirmaElectronica.DoesNotExist:
        return HttpResponse(status=204)

    try:
        payload = request.body.decode('utf-8') or '{}'
        import json
        data = json.loads(payload)
    except Exception:
        data = {}

    # ejemplo genérico: status puede venir en raíz o en "detail"
    new_status = (data.get('detail', {}) or {}).get('status') or data.get('status') or ''
    message = data.get('message') or ''
    jobid = (data.get('detail', {}) or {}).get('jobid') or data.get('jobid')

    if jobid and not firma.api_id:
        firma.api_id = jobid

    if new_status:
        if new_status.lower().startswith('error'):
            firma.estado = FirmaElectronica.Estados.ERROR
        elif new_status.lower() in ('ok','success','completed','firmado'):
            firma.estado = FirmaElectronica.Estados.FIRMADO
        # si no, lo dejamos en proceso

    if message:
        # concatenamos mensajes previos si existiesen
        firma.error_msg = (firma.error_msg + '\n' if firma.error_msg else '') + message

    firma.save(update_fields=['api_id','estado','error_msg'])
    return JsonResponse({'ok': True})


@csrf_exempt
def signbox_url_out(request):
    # Recibe el PDF FIRMADO como binario
    if request.method != 'POST':
        return HttpResponseBadRequest('POST only')

    ref = request.GET.get('ref')
    token = request.GET.get('token')
    if not ref or not token:
        return HttpResponse(status=204)

    try:
        firma = FirmaElectronica.objects.get(ref=ref, cb_token=token)
    except FirmaElectronica.DoesNotExist:
        return HttpResponse(status=204)

    # Guardamos el binario en archivo_firmado
    filename = f"signed_{firma.api_id or firma.ref.hex}_{timezone.now().strftime('%Y%m%d%H%M%S')}.pdf"
    firma.archivo_firmado.save(filename, ContentFile(request.body))

    # Marcamos como firmado (aunque urlback también suele confirmarlo)
    firma.estado = FirmaElectronica.Estados.FIRMADO
    firma.save(update_fields=['archivo_firmado','estado'])
    return JsonResponse({'ok': True})
