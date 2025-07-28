from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import Perfil

class UsuarioRegistroForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True, label="Nombre")
    last_name = forms.CharField(max_length=30, required=True, label="Apellido")
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']

class PerfilForm(forms.ModelForm):
    class Meta:
        model = Perfil
        fields = ['telefono', 'departamento', 'puesto']
        widgets = {
            'telefono': forms.TextInput(attrs={'placeholder': 'Ej. +502 1234-5678'}),
            'puesto': forms.TextInput(attrs={'placeholder': 'Ej. Gerente de Ventas'})
        }

class PerfilPermisoForm(forms.ModelForm):
    class Meta:
        model = Perfil
        fields = ['tipo_permiso']
        widgets = {
            'tipo_permiso': forms.RadioSelect()
        }
        labels = {
            'tipo_permiso': 'Nivel de acceso'
        }
        help_texts = {
            'tipo_permiso': 'Seleccione el nivel de acceso que tendrá este usuario en el sistema.'
        }

class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Usuario'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Contraseña'}))