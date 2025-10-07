# firmaElectronica/views.py
import os
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse, FileResponse, Http404
from .models import FirmaElectronica, DescargaDocumento
import requests
from requests.exceptions import Timeout
from requests.adapters import HTTPAdapter
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
from urllib3.util.retry import Retry
import random
import time
from django.contrib.auth.decorators import login_required
from django.utils.encoding import smart_str
from django.db.models import Q, Sum, Case, When, Count, IntegerField, Max
import mimetypes
from usuarios.decorators import permiso_firma_requerido
from django.core.paginator import Paginator
from django.core.files.storage import default_storage
from django.contrib import messages
from urllib.parse import quote
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.apps import apps
from django.template.loader import render_to_string
from django.template import TemplateDoesNotExist



# Sesión global con pooling + retries
def _build_session():
    retry = Retry(
        total=getattr(settings, "SIGNBOX_MAX_RETRIES", 3),
        backoff_factor=getattr(settings, "SIGNBOX_BACKOFF_FACTOR", 0.6),
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "POST"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(
        pool_connections=getattr(settings, "SIGNBOX_POOL_CONNECTIONS", 20),
        pool_maxsize=getattr(settings, "SIGNBOX_POOL_MAXSIZE", 50),
        max_retries=retry,
    )
    s = requests.Session()
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s

_SESSION = _build_session()
_REQ_TIMEOUT = getattr(settings, "SIGNBOX_REQUEST_TIMEOUT", 20)
_RES_TIMEOUT = getattr(settings, "SIGNBOX_RESULT_TIMEOUT", 40)


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
    r = _SESSION.get(url, timeout=_REQ_TIMEOUT)
    state, typ = _parse_job_text(r.text)
    return {"state": state, "type": typ, "raw": r.text, "status_code": r.status_code}

def _signbox_fetch_result(api_id: str) -> bytes:
    url = _build_endpoint_with_id(settings.SIGNBOX_BASE_URL, settings.SIGNBOX_RESULT_ENDPOINT, api_id)
    r = _SESSION.get(url, timeout=_RES_TIMEOUT)
    r.raise_for_status()
    return r.content


@require_GET
def sign_status(request):
    ref = request.GET.get('ref')
    if not ref:
        return JsonResponse({'ready': False, 'state': 'error', 'error': 'Falta ref'}, status=400)

    try:
        firma = FirmaElectronica.objects.get(ref=ref)
    except FirmaElectronica.DoesNotExist:
        return JsonResponse({'ready': False, 'state': 'error', 'error': 'Ref no encontrada'}, status=404)

    # Si ya está guardado el PDF firmado, listo
    if firma.archivo_firmado:
        return JsonResponse({'ready': True, 'state': 'done', 'url': firma.archivo_firmado.url})

    # 🔴 NUEVO: con webhooks activos no consultamos a SignBox
    if getattr(settings, "USE_SIGNBOX_WEBHOOKS", False):
        if firma.estado == FirmaElectronica.Estados.ERROR:
            return JsonResponse({'ready': False, 'state': 'failed', 'error': firma.error_msg or 'Error'})
        # Aún procesando; esperamos a que llegue url_out
        return JsonResponse({'ready': False, 'state': 'processing'})

    # --- Modo polling (webhooks desactivados): flujo actual ---
    if not firma.api_id:
        return JsonResponse({'ready': False, 'state': 'waiting', 'error': 'Sin api_id aún'})

    job = _signbox_job_status(firma.api_id)
    state = (job.get('state') or '').lower()

    if state in ('done', 'success', 'completed'):
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
        raw = job.get('raw','')[:200]
        firma.error_msg = f'Job failed: {raw}'
        firma.save(update_fields=['estado','error_msg'])
        return JsonResponse({'ready': False, 'state': 'failed', 'error': firma.error_msg})

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

        if len(files) > 5:
            return JsonResponse(
                {'ok': False, 'error': 'Máximo 5 archivos por lote.'},
                status=400
            )

        results = []

        for f in files:
            try:
                # 1) GUARDAR SIN LEER A MEMORIA
                firma = FirmaElectronica(
                    nombre_original=f.name,
                    usuario=request.user,
                    estado=FirmaElectronica.Estados.EN_PROCESO,
                )
                firma.issue_token()
                # Guardar el archivo subido directamente
                firma.archivo.save(f.name, f)   # <--- esto persiste el upload
                firma.save()

                use_webhooks = getattr(settings, "USE_SIGNBOX_WEBHOOKS", False)

                # 2) CAMPOS BASE
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
                }

                # 3) archivo para el multipart como STREAM (no bytes en RAM)
                fh = firma.archivo.open('rb')  # <<-- handle de lectura
                fields['file_in'] = (firma.nombre_original or f.name, fh, 'application/pdf')

                # 4) WEBHOOKS (si corresponde)
                if use_webhooks:
                    from django.urls import reverse, NoReverseMatch
                    base_url = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/") or request.build_absolute_uri('/').rstrip('/')
                    try:
                        fields['urlback'] = f"{base_url}{reverse('signbox_urlback')}?ref={firma.ref}&token={firma.cb_token}"
                        fields['url_out'] = f"{base_url}{reverse('signbox_url_out')}?ref={firma.ref}&token={firma.cb_token}"
                    except NoReverseMatch:
                        pass

                # 5) Enviar
                multipart_data = MultipartEncoder(fields=fields)
                headers = {'Content-Type': multipart_data.content_type}
                endpoint = f"{settings.SIGNBOX_BASE_URL}{settings.SIGNBOX_SIGN_ENDPOINT}"

                resp = _SESSION.post(endpoint, headers=headers, data=multipart_data, timeout=_REQ_TIMEOUT)
                if resp.status_code == 429:
                    time.sleep(0.5 + random.random())
                    resp = _SESSION.post(endpoint, headers=headers, data=multipart_data, timeout=_REQ_TIMEOUT)

                print(f"[API] {firma.nombre_original or f.name}: {resp.status_code} -> {resp.text}")

                if resp.status_code == 200 and 'id=' in resp.text:
                    api_id = resp.text.split('=', 1)[1].strip()
                    firma.api_id = api_id
                    firma.save(update_fields=['api_id'])
                    results.append({'filename': firma.nombre_original or f.name, 'api_id': api_id, 'status': 'ok', 'ref': str(firma.ref)})
                else:
                    firma.estado = FirmaElectronica.Estados.ERROR
                    firma.error_msg = f'API {resp.status_code}: {resp.text[:200]}'
                    firma.save(update_fields=['estado', 'error_msg'])
                    results.append({'filename': firma.nombre_original or f.name, 'api_id': None, 'status': 'error',
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
                firma.estado = FirmaElectronica.Estados.ERROR
                firma.error_msg = f'Error inesperado: {str(e)}'
                firma.save(update_fields=['estado', 'error_msg'])
                results.append({'filename': f.name, 'api_id': None, 'status': 'error', 'error': f'Error inesperado: {str(e)}'})
            finally:
                # Cerrar el handle si lo abrimos
                try:
                    fh.close()
                except Exception:
                    pass


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


@permiso_firma_requerido
def historial_firmados(request):
    es_admin = request.user.is_staff or request.user.is_superuser

    base = FirmaElectronica.objects.select_related('usuario')
    if not es_admin:
        base = base.filter(usuario=request.user)

    # Filtros generales
    fecha_ini = request.GET.get('fecha_ini')  # YYYY-MM-DD
    fecha_fin = request.GET.get('fecha_fin')
    estado    = request.GET.get('estado')     # ok | error | pendiente | None
    q         = request.GET.get('q')
    usuario_q = request.GET.get('usuario')

    base = FirmaElectronica.objects.select_related('usuario')
    if not es_admin:
        base = base.filter(usuario=request.user)
    elif usuario_q:
        base = base.filter(
            Q(usuario__username__icontains=usuario_q) |
            Q(usuario__id__iexact=usuario_q)
        )

    scope = base
    if fecha_ini:
        scope = scope.filter(fecha_creacion__date__gte=fecha_ini)
    if fecha_fin:
        scope = scope.filter(fecha_creacion__date__lte=fecha_fin)
    if q:
        scope = scope.filter(
            Q(nombre_original__icontains=q) |
            Q(archivo_firmado__icontains=q) |
            Q(error_msg__icontains=q)
        )

    # KPIs (sobre el scope ya filtrado por fechas/búsqueda/rol)
    q_firmado   = scope.filter(archivo_firmado__isnull=False).exclude(archivo_firmado='')
    q_error     = scope.filter(error_msg__isnull=False).exclude(error_msg='')
    q_pendiente = scope.filter(
        Q(archivo_firmado__isnull=True) | Q(archivo_firmado=''),
    ).filter(
        Q(error_msg__isnull=True) | Q(error_msg='')
    )

    kpis = {
        'total':      scope.count(),
        'firmados':   q_firmado.count(),
        'pendientes': q_pendiente.count(),
        'errores':    q_error.count(),
    }

    # Lista (aplica filtro de estado, si viene)
    qs = scope
    if estado == 'ok':
        qs = q_firmado
    elif estado == 'error':
        qs = q_error
    elif estado == 'pendiente':
        qs = q_pendiente

    page_obj = Paginator(qs.order_by('-fecha_creacion'), 20).get_page(request.GET.get('page'))

    return render(request, 'firmaElectronica/historial_firmados.html', {
        'page_obj': page_obj,
        'es_admin': es_admin,
        'fecha_ini': fecha_ini or '',
        'fecha_fin': fecha_fin or '',
        'estado': estado or '',
        'q': q or '',
        'kpis': kpis,  # <- NUEVO
    })

def _normalize_media_name(name: str) -> str:
    """
    Devuelve un nombre RELATIVO para usar con default_storage.
    Quita prefijos MEDIA_URL y convierte absolutos bajo MEDIA_ROOT a relativos.
    """
    if not name:
        return ""
    name = str(name)

    # Si viene con MEDIA_URL al inicio, quitarlo
    if settings.MEDIA_URL and name.startswith(settings.MEDIA_URL):
        name = name[len(settings.MEDIA_URL):]

    # Si viene absoluto dentro de MEDIA_ROOT, convertir a relativo
    try:
        media_root = os.path.abspath(settings.MEDIA_ROOT)
        abs_name = os.path.abspath(name)
        if abs_name.startswith(media_root):
            name = os.path.relpath(abs_name, media_root)
    except Exception:
        pass

    # Normalizar separadores
    return name.replace("\\", "/")

@permiso_firma_requerido
def descargar_documento_firmado(request, pk):
    doc = get_object_or_404(FirmaElectronica, pk=pk)

    es_admin = request.user.is_staff or request.user.is_superuser
    if not es_admin and doc.usuario_id != request.user.id:
        raise Http404("No tiene permiso para descargar este documento.")

    f = getattr(doc, 'archivo_firmado', None)
    if not f:
        raise Http404("Archivo no disponible.")

    # --- Abrir archivo desde el storage (soporta FieldFile o cadena ruta) ---
    try:
        if hasattr(f, 'open') and hasattr(f, 'name'):  # Caso A: FieldFile
            storage = getattr(f, 'storage', None) or default_storage
            name = f.name  # <-- ¡era f.name, no f.filename!
            if not name or not storage.exists(name):
                raise FileNotFoundError
            fh = storage.open(name, 'rb')
        else:  # Caso B: cadena (ruta relativa/absoluta)
            name = _normalize_media_name(str(f))
            if not name or not default_storage.exists(name):
                raise FileNotFoundError
            fh = default_storage.open(name, 'rb')

        filename_fs = os.path.basename(name)  # nombre físico en el FS
    except FileNotFoundError:
        messages.error(
            request,
            "El archivo firmado no está disponible en el repositorio de medios "
            "(pudo haberse movido/eliminado o no se generó correctamente)."
        )
        return redirect('firma:historial')

    # --- Nombre de descarga: priorizar el nombre_original guardado en BBDD ---
    desired = getattr(doc, 'nombre_original', None) or filename_fs
    root, ext = os.path.splitext(desired)
    if not ext:
        desired = desired + '.pdf'

    mime_type, _ = mimetypes.guess_type(desired)
    resp = FileResponse(fh, content_type=mime_type or 'application/pdf')
    # Content-Disposition compatible con UTF-8 (RFC 5987) + fallback
    resp['Content-Disposition'] = (
        f"attachment; filename*=UTF-8''{quote(desired)}; filename=\"{smart_str(desired)}\""
    )

    # Log de descarga (no bloquear si falla)
    try:
        DescargaDocumento.objects.create(
            documento=doc,
            usuario=request.user,
            ip=(request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                or request.META.get('REMOTE_ADDR')),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:512],
        )
    except Exception:
        pass

    return resp

@permiso_firma_requerido
def reportes_firma(request):
    es_admin  = request.user.is_staff or request.user.is_superuser

    fecha_ini = request.GET.get('fecha_ini')
    fecha_fin = request.GET.get('fecha_fin')
    usuario_q = request.GET.get('usuario')  # username o ID

    scope = FirmaElectronica.objects.select_related('usuario')
    if not es_admin:
        scope = scope.filter(usuario=request.user)
    elif usuario_q:
        scope = scope.filter(
            Q(usuario__username__icontains=usuario_q) | Q(usuario__id__iexact=usuario_q)
        )

    if fecha_ini:
        scope = scope.filter(fecha_creacion__date__gte=fecha_ini)
    if fecha_fin:
        scope = scope.filter(fecha_creacion__date__lte=fecha_fin)

    cond_firmado   = Q(archivo_firmado__isnull=False) & ~Q(archivo_firmado='')
    cond_error     = Q(error_msg__isnull=False) & ~Q(error_msg='')
    cond_pendiente = (Q(archivo_firmado__isnull=True) | Q(archivo_firmado='')) & (Q(error_msg__isnull=True) | Q(error_msg=''))

    kpis = {
        'total':      scope.count(),
        'firmados':   scope.filter(cond_firmado).count(),
        'pendientes': scope.filter(cond_pendiente).count(),
        'errores':    scope.filter(cond_error).count(),
    }

    agrupado = (
        scope
        .values('usuario__id','usuario__username','usuario__first_name','usuario__last_name')
        .annotate(
            firmados=Sum(Case(When(cond_firmado, then=1), default=0, output_field=IntegerField())),
            pendientes=Sum(Case(When(cond_pendiente, then=1), default=0, output_field=IntegerField())),
            errores=Sum(Case(When(cond_error, then=1), default=0, output_field=IntegerField())),
            total=Count('id'),
            ultima_firma=Max('fecha_creacion', filter=cond_firmado),
        )
        .order_by('-total','-firmados','usuario__username')
    )

    page_obj = Paginator(agrupado, 20).get_page(request.GET.get('page'))

    return render(request, 'firmaElectronica/reportes.html', {
        'page_obj': page_obj,
        'es_admin': es_admin,
        'fecha_ini': fecha_ini or '',
        'fecha_fin': fecha_fin or '',
        'usuario_q': usuario_q or '',
        'kpis': kpis,
    })

def _try_signed_datetime(doc):
    """Intenta inferir la fecha de 'firmado' a partir del archivo almacenado."""
    f = getattr(doc, 'archivo_firmado', None)
    try:
        if hasattr(f, 'name') and f.name:
            storage = getattr(f, 'storage', None) or default_storage
            if storage.exists(f.name):
                # get_modified_time no está en TODOS los storages, por eso el try/except
                return storage.get_modified_time(f.name)
        elif isinstance(f, str) and f:
            if default_storage.exists(f):
                return default_storage.get_modified_time(f)
    except Exception:
        pass
    return None

@permiso_firma_requerido
def historial_detalle(request, pk):
    doc = get_object_or_404(FirmaElectronica, pk=pk)

    es_admin = request.user.is_staff or request.user.is_superuser
    if not es_admin and doc.usuario_id != request.user.id:
        raise Http404("No tiene permiso para ver este detalle.")

    # Obtener el modelo DescargaDocumento de forma segura (por si no está importado/creado)
    DescargaDocumentoModel = apps.get_model('firmaElectronica', 'DescargaDocumento')
    if DescargaDocumentoModel:
        descargas = (DescargaDocumentoModel.objects
                     .filter(documento=doc)
                     .select_related('usuario')
                     .order_by('-fecha_descarga'))
    else:
        descargas = []

    # Fecha "firmado" aproximada según el archivo en storage (si existe)
    firmado_en = _try_signed_datetime(doc) if '_try_signed_datetime' in globals() else None

    ctx = {
        'doc': doc,
        'descargas': descargas,
        'firmado_en': firmado_en,
        'es_admin': es_admin,
    }

    # Render seguro a HTML parcial (evita 500 si falta la plantilla)
    try:
        html = render_to_string('firmaElectronica/_detalle_documento.html', ctx, request=request)
        return HttpResponse(html)
    except TemplateDoesNotExist:
        return HttpResponse(
            '<div style="padding:12px;color:#8a1c1c;background:#fde2e2;'
            'border:1px solid #f7c9c9;border-radius:8px">'
            'No se encontró la plantilla <code>firmaElectronica/_detalle_documento.html</code>.'
            '</div>',
            status=200
        )
    except Exception as e:
        # Evita 500 y muestra mensaje legible
        return HttpResponse(
            f'<div style="padding:12px;color:#8a1c1c;background:#fde2e2;'
            f'border:1px solid #f7c9c9;border-radius:8px">'
            f'Error al cargar el detalle: {e}</div>',
            status=200
        )
