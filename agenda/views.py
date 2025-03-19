from django.shortcuts import render

# Create your views here.
def agenda_home(request):
    return render(request, 'agenda/agenda_home.html')