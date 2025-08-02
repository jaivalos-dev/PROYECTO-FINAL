from django.shortcuts import render
from django.http import HttpResponse

def home(request):
    return render(request, 'core/home.html')



def error_404_view(request, exception):
    import traceback
    print("🔴 EXCEPCIÓN 404:")
    traceback.print_exception(type(exception), exception, exception.__traceback__)

    # Probar si se rompe al renderizar
    try:
        return render(request, 'core/404.html', status=404)
    except Exception as e:
        print("⚠️ Error al renderizar 404.html:", e)
        return HttpResponse(
            "<h1>Error 500</h1><p>No se pudo cargar la plantilla 404.html</p><p>Error: " + str(e) + "</p>",
            status=500
        )