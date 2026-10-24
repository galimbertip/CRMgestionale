"""Pulsanti d'azione nella scheda di modifica dell'admin (es. "Conferma ordine", "Invia al cliente")."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect


class AzioniMixin:
    change_form_template = "admin/gp_change_form.html"

    def azioni(self, request, obj):
        """Lista di (chiave, etichetta) dei pulsanti disponibili per questo oggetto."""
        return []

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra = extra_context or {}
        obj = self.get_object(request, object_id)
        if obj is not None and self.has_change_permission(request, obj):
            extra["azioni_extra"] = self.azioni(request, obj)
        return super().change_view(request, object_id, form_url, extra)

    def response_change(self, request, obj):
        for chiave, _etichetta in self.azioni(request, obj):
            if f"_azione_{chiave}" in request.POST:
                try:
                    esito = getattr(self, f"azione_{chiave}")(request, obj)
                except (ValidationError, ValueError) as e:
                    messages.error(request, "; ".join(getattr(e, "messages", [str(e)])))
                    return HttpResponseRedirect(request.path)
                if isinstance(esito, HttpResponseRedirect):
                    return esito
                if esito:
                    messages.success(request, esito)
                return HttpResponseRedirect(request.path)
        return super().response_change(request, obj)
