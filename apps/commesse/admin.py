from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (Collaudo, Commessa, FotoSopralluogo, ModelloChecklist, RigaCollaudo, RigaSopralluogo,
                     Sopralluogo, VoceModello)


def link_campo(tipo, obj):
    """Pulsanti Firma / Stampa per i documenti compilati sul campo."""
    if not obj or not obj.pk:
        return "Salva il documento per poter firmare e stampare."
    firma = reverse("firma", args=[tipo, obj.pk])
    stampa = reverse("stampa", args=[tipo, obj.pk])
    etichetta = "Firmato ✔ – rifai firma" if obj.firmato else "✍ Raccogli firma cliente"
    return format_html('<a class="button" href="{}">{}</a>&nbsp; <a class="button" href="{}" target="_blank">'
                       '🖨 Stampa / PDF</a>', firma, etichetta, stampa)


class VoceInline(admin.TabularInline):
    model = VoceModello
    extra = 1


@admin.register(ModelloChecklist)
class ModelloChecklistAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "attivo", "predefinito")
    list_filter = ("tipo",)
    inlines = [VoceInline]


class SopralluogoInline(admin.TabularInline):
    model = Sopralluogo
    extra = 0
    fields = ("numero", "data", "tecnico", "esito")
    readonly_fields = fields
    show_change_link = True
    can_delete = False


class CollaudoInline(SopralluogoInline):
    model = Collaudo


@admin.register(Commessa)
class CommessaAdmin(admin.ModelAdmin):
    list_display = ("codice", "titolo", "cliente", "stato", "fasi_gestite", "ereditata", "data_apertura")
    list_filter = ("stato", "ereditata", "fase_prevendita", "fase_produzione", "fase_postvendita")
    search_fields = ("codice", "titolo", "cliente__ragione_sociale")
    autocomplete_fields = ("cliente", "responsabile")
    readonly_fields = ("codice",)
    inlines = [SopralluogoInline, CollaudoInline]
    fieldsets = (
        (None, {"fields": ("codice", "cliente", "titolo", "descrizione", "stato", "responsabile", "valore")}),
        ("Fasi gestite", {"fields": ("fase_prevendita", "fase_produzione", "fase_postvendita"),
                          "description": "Non tutte le commesse passano da tutte le fasi."}),
        ("Commessa ereditata", {"fields": ("ereditata", "origine", "data_presa_in_carico"),
                                "classes": ("collapse",)}),
        ("Date", {"fields": ("data_apertura", "data_chiusura")}),
    )

    @admin.display(description="Fasi")
    def fasi_gestite(self, obj):
        return " · ".join(obj.fasi)


class RigaSopralluogoInline(admin.TabularInline):
    model = RigaSopralluogo
    extra = 0
    fields = ("gruppo", "testo", "obbligatoria", "esito", "valore", "note")


class FotoInline(admin.TabularInline):
    model = FotoSopralluogo
    extra = 1


class DocumentoCampoAdmin(admin.ModelAdmin):
    TIPO = ""
    list_display = ("numero", "commessa", "cliente", "data", "tecnico", "esito", "firmato_flag")
    list_filter = ("esito", "data")
    search_fields = ("numero", "commessa__codice", "commessa__cliente__ragione_sociale")
    autocomplete_fields = ("commessa", "sede", "tecnico")
    readonly_fields = ("numero", "azioni", "firmato_il")
    date_hierarchy = "data"

    @admin.display(description="Firmato", boolean=True)
    def firmato_flag(self, obj):
        return obj.firmato

    @admin.display(description="Azioni sul campo")
    def azioni(self, obj):
        return link_campo(self.TIPO, obj)

    def get_changeform_initial_data(self, request):
        data = super().get_changeform_initial_data(request)
        data.setdefault("tecnico", request.user.pk)
        return data


@admin.register(Sopralluogo)
class SopralluogoAdmin(DocumentoCampoAdmin):
    TIPO = "sopralluogo"
    inlines = [RigaSopralluogoInline, FotoInline]
    fieldsets = (
        (None, {"fields": ("numero", "azioni", "commessa", "sede", "data", "tecnico", "referente_presente",
                           "modello")}),
        ("Esito", {"fields": ("esito", "opere_preliminari", "note")}),
        ("Firma", {"fields": ("firmatario", "firmato_il")}),
    )


class RigaCollaudoInline(RigaSopralluogoInline):
    model = RigaCollaudo


@admin.register(Collaudo)
class CollaudoAdmin(DocumentoCampoAdmin):
    TIPO = "collaudo"
    inlines = [RigaCollaudoInline]
    filter_horizontal = ("apparati",)
    fieldsets = (
        (None, {"fields": ("numero", "azioni", "commessa", "sede", "data", "tecnico", "modello", "apparati")}),
        ("Esito", {"fields": ("esito", "riserve", "note")}),
        ("Firma", {"fields": ("firmatario", "firmato_il")}),
    )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        obj = form.instance
        # collaudo superato: gli apparati entrano in servizio
        if obj.esito in (Collaudo.EsitoCollaudo.SUPERATO, Collaudo.EsitoCollaudo.CON_RISERVA):
            for a in obj.apparati.all():
                a.stato = a.Stato.IN_SERVIZIO
                a.data_installazione = a.data_installazione or obj.data
                a.save(update_fields=["stato", "data_installazione"])
