from django import template
from django.utils import timezone
from django.utils.html import format_html

register = template.Library()

ETICHETTE = {"ok": "In tempo", "attenzione": "In scadenza", "scaduto": "Scaduto",
             "rispettato": "Rispettato", "violato": "Fuori SLA"}


@register.simple_tag
def sla_badge(ticket):
    if ticket.aperto:
        scad, stato = ticket.sla_corrente
    else:
        scad, stato = ticket.scadenza_risoluzione, ticket.sla_risoluzione
    if not stato:
        return ""
    quando = timezone.localtime(scad).strftime("%d/%m %H:%M") if scad else ""
    return format_html('<span class="sla {}" title="Scadenza {}">{} · {}</span>', stato, quando,
                       ETICHETTE[stato], quando)
