from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html

from apps.core.admin_utils import AzioniMixin

from .models import Preventivo, RigaPreventivo


def euro(v):
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€ {s}"


class RigaInline(admin.TabularInline):
    model = RigaPreventivo
    extra = 1
    autocomplete_fields = ("articolo",)
    fields = ("ordine", "articolo", "descrizione", "quantita", "unita", "prezzo_unitario", "sconto", "totale_riga")
    readonly_fields = ("totale_riga",)

    @admin.display(description="Totale")
    def totale_riga(self, obj):
        return euro(obj.totale) if obj.pk else "—"

    def _bloccato(self, obj):
        return obj is not None and not obj.modificabile

    def has_add_permission(self, request, obj=None):
        return not self._bloccato(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return not self._bloccato(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return not self._bloccato(obj) and super().has_delete_permission(request, obj)


@admin.register(Preventivo)
class PreventivoAdmin(AzioniMixin, admin.ModelAdmin):
    list_display = ("numero", "revisione", "oggetto", "cliente", "tipo", "stato_col", "data", "totale_col")
    list_filter = ("stato", "tipo", "autore")
    search_fields = ("numero", "oggetto", "cliente__ragione_sociale", "riferimento_ordine")
    autocomplete_fields = ("cliente", "contatto", "commessa", "ticket", "riparazione", "sopralluogo", "autore")
    inlines = [RigaInline]
    date_hierarchy = "data"
    readonly_fields = ("numero", "revisione", "stato", "riepilogo", "esito", "link_cliente")
    fieldsets = (
        (None, {"fields": (("numero", "revisione", "stato"), "tipo", ("cliente", "contatto"), "oggetto",
                           "introduzione", "autore")}),
        ("Collegamenti", {"fields": (("commessa", "sopralluogo"), ("ticket", "riparazione")),
                          "classes": ("collapse",)}),
        ("Condizioni", {"fields": (("data", "validita_giorni"), ("sconto_globale", "aliquota_iva"), "pagamento",
                                   "tempi_consegna", "garanzia", "note")}),
        ("Totali ed esito", {"fields": ("riepilogo", "link_cliente", "esito")}),
    )

    @admin.display(description="Stato", ordering="stato")
    def stato_col(self, obj):
        colori = {"bozza": "#64748b", "inviato": "#0aa9c0", "accettato": "#15803d", "rifiutato": "#b91c1c",
                  "annullato": "#64748b"}
        testo = "Scaduto" if obj.scaduto else obj.get_stato_display()
        colore = "#b45309" if obj.scaduto else colori.get(obj.stato, "#64748b")
        return format_html('<span style="background:{};color:#fff;padding:2px 9px;border-radius:10px">{}</span>',
                           colore, testo)

    @admin.display(description="Totale")
    def totale_col(self, obj):
        return euro(obj.totale)

    @admin.display(description="Riepilogo")
    def riepilogo(self, obj):
        if not obj.pk:
            return "Salva per vedere i totali."
        return format_html(
            "Imponibile righe {} · sconto {} · <b>imponibile {}</b> · IVA {} · <b>totale {}</b><br>"
            "Valido fino al {}", euro(obj.imponibile_righe), euro(obj.sconto_importo), euro(obj.imponibile),
            euro(obj.iva), euro(obj.totale), obj.scadenza.strftime("%d/%m/%Y"))

    @admin.display(description="Link per il cliente")
    def link_cliente(self, obj):
        if not obj.pk or obj.stato == obj.Stato.BOZZA:
            return "Disponibile dopo l'invio."
        return format_html('<a href="{0}" target="_blank">{0}</a><br>Destinatario: {1}', obj.url_pubblico(),
                           obj.email_destinatario or "— manca un'email")

    @admin.display(description="Esito")
    def esito(self, obj):
        if obj.stato == obj.Stato.ACCETTATO:
            return format_html("Accettato da <b>{}</b> il {}{}", obj.accettato_da,
                               obj.risposta_il.strftime("%d/%m/%Y %H:%M"),
                               f" · rif. ordine {obj.riferimento_ordine}" if obj.riferimento_ordine else "")
        if obj.stato == obj.Stato.RIFIUTATO:
            return format_html("Rifiutato il {}: {}", obj.risposta_il.strftime("%d/%m/%Y"), obj.motivo_rifiuto or "—")
        return "—"

    def get_readonly_fields(self, request, obj=None):
        if obj and not obj.modificabile:
            return [f.name for f in Preventivo._meta.fields] + list(self.readonly_fields)
        return self.readonly_fields

    def get_changeform_initial_data(self, request):
        data = super().get_changeform_initial_data(request)
        data.setdefault("autore", request.user.pk)
        return data

    # -- azioni

    def azioni(self, request, obj):
        S = obj.Stato
        a = [("stampa", "🖨 Stampa / PDF")]
        if obj.stato == S.BOZZA:
            a.insert(0, ("invia", "✉ Invia al cliente"))
        if obj.stato == S.INVIATO:
            a += [("reinvia", "Reinvia email"), ("accetta", "Registra accettazione (telefono/email)"),
                  ("rifiuta", "Registra rifiuto")]
        if obj.stato in (S.INVIATO, S.RIFIUTATO, S.SCADUTO):
            a.append(("revisione", "Nuova revisione"))
        if obj.stato in (S.BOZZA, S.INVIATO):
            a.append(("annulla", "Annulla"))
        return a

    def azione_stampa(self, request, obj):
        return HttpResponseRedirect(reverse("stampa", args=["preventivo", obj.pk]))

    def azione_invia(self, request, obj):
        if not obj.righe.exists():
            raise ValueError("Aggiungi almeno una riga prima di inviare.")
        if not obj.email_destinatario:
            raise ValueError("Manca l'email del destinatario (contatto o cliente).")
        obj.invia()
        return f"{obj.codice} inviato a {obj.email_destinatario}."

    def azione_reinvia(self, request, obj):
        obj.invia()
        return "Email reinviata."

    def azione_accetta(self, request, obj):
        obj.accetta(nome=f"registrato da {request.user}", utente=request.user)
        msg = f"{obj.codice} accettato."
        if obj.commessa_id:
            msg += f" Commessa {obj.commessa.codice} in produzione."
        return msg

    def azione_rifiuta(self, request, obj):
        obj.rifiuta("Registrato dall'ufficio")
        return f"{obj.codice} segnato come rifiutato."

    def azione_revisione(self, request, obj):
        obj.nuova_revisione()
        return f"Ora puoi modificare {obj.codice}: il link precedente non è più valido."

    def azione_annulla(self, request, obj):
        obj.stato = obj.Stato.ANNULLATO
        obj.save(update_fields=["stato"])
        return "Preventivo annullato."
