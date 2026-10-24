"""Viste da campo per i tecnici: raccolta firma su tablet/telefono e stampa dei documenti."""
import base64
import binascii
import uuid

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.files.base import ContentFile
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.commesse.models import Collaudo, Sopralluogo

from .models import Rapportino

DOCUMENTI = {
    "rapportino": (Rapportino, "Rapportino d'intervento", "admin:assistenza_rapportino_change"),
    "sopralluogo": (Sopralluogo, "Verbale di sopralluogo", "admin:commesse_sopralluogo_change"),
    "collaudo": (Collaudo, "Verbale di collaudo", "admin:commesse_collaudo_change"),
}


def _documento(tipo, pk):
    if tipo not in DOCUMENTI:
        raise Http404
    model, titolo, url_admin = DOCUMENTI[tipo]
    return get_object_or_404(model, pk=pk), titolo, url_admin


@staff_member_required
def firma(request, tipo, pk):
    obj, titolo, url_admin = _documento(tipo, pk)
    if request.method == "POST":
        nome = request.POST.get("firmatario", "").strip()
        dati = request.POST.get("firma", "")
        if not nome or not dati.startswith("data:image/png;base64,"):
            messages.error(request, "Servono il nome del firmatario e la firma.")
        else:
            try:
                png = base64.b64decode(dati.split(",", 1)[1], validate=True)
            except (binascii.Error, ValueError):
                png = b""
            if not png.startswith(b"\x89PNG") or len(png) > 2_000_000:
                messages.error(request, "Firma non valida, riprova.")
            else:
                if obj.firma:
                    obj.firma.delete(save=False)
                obj.firma.save(f"{obj.numero}-{uuid.uuid4().hex[:8]}.png", ContentFile(png), save=False)
                obj.firmatario = nome
                obj.firmato_il = timezone.now()
                obj.save()
                messages.success(request, f"{titolo} {obj.numero} firmato da {nome}.")
                return redirect(reverse(url_admin, args=[obj.pk]))
    return render(request, "campo/firma.html", {"obj": obj, "titolo": titolo, "tipo": tipo,
                                                "url_admin": reverse(url_admin, args=[obj.pk])})


@staff_member_required
def stampa(request, tipo, pk):
    obj, titolo, url_admin = _documento(tipo, pk)
    return render(request, f"campo/stampa_{tipo}.html", {"obj": obj, "titolo": titolo})
