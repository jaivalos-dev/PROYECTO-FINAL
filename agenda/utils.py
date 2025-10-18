# agenda/utils.py
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

def destinatarios_evento(evento, incluir_actor=False, actor=None, extras=None):

    emails = set()

    # ajusta según tu modelo: .creado_por o .usuario (propietario)
    owner = getattr(evento, "creador", None) or getattr(evento, "usuario", None)
    if owner and owner.email:
        emails.add(owner.email)

    if incluir_actor and actor and getattr(actor, "email", ""):
        emails.add(actor.email)

    for e in (extras or []):
        if e:
            emails.add(e)

    return list(emails)

def notificar_evento(evento, accion, actor=None, extras=None, incluir_actor=False):
    """
    accion: 'creado' | 'editado' | 'cancelado' (texto libre para el asunto)
    """
    asunto = f"[Agenda] Evento {accion}: {evento.titulo}"
    linea_actor = f"\nAcción realizada por: {actor.get_username()}" if actor else ""
    mensaje = (
        f"Hola,\n\n"
        f"El evento '{evento.titulo}' ha sido {accion}.\n"
        f"Fecha/hora: {evento.fecha_inicio} - {getattr(evento, 'fecha_fin', '')}\n"
        f"Lugar: {getattr(evento, 'ubicacion', 'N/D')}\n"
        f"{linea_actor}\n\n"
        f"Saludos."
    )

    destinatarios = destinatarios_evento(
        evento,
        incluir_actor=incluir_actor,
        actor=actor,
        extras=extras
    )

    if not destinatarios:
        return 0

    # Enviar únicamente cuando la transacción actual confirme el commit
    def _send():
        send_mail(
            asunto,
            mensaje,
            getattr(settings, "DEFAULT_FROM_EMAIL", None),
            destinatarios,
            fail_silently=False
        )
    transaction.on_commit(_send)
    return len(destinatarios)
