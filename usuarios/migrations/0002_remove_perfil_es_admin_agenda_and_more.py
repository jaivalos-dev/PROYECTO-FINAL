# Generated by Django 5.1.6 on 2025-05-16 02:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='perfil',
            name='es_admin_agenda',
        ),
        migrations.RemoveField(
            model_name='perfil',
            name='es_admin_firma',
        ),
        migrations.RemoveField(
            model_name='perfil',
            name='permiso_agenda',
        ),
        migrations.RemoveField(
            model_name='perfil',
            name='permiso_firma',
        ),
        migrations.AddField(
            model_name='perfil',
            name='tipo_permiso',
            field=models.CharField(choices=[('full', 'Acceso Completo'), ('agenda', 'Solo Agenda'), ('firma', 'Solo Firma Electrónica'), ('ninguno', 'Sin Acceso')], default='ninguno', max_length=10),
        ),
    ]
