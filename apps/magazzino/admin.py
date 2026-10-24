from decimal import Decimal

from django import forms
from django.contrib import admin
from django.db.models import F
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html

from apps.core.admin_utils import AzioniMixin

from .models import (Area, Articolo, DistintaBase, Impegno, Movimento, OrdineProduzione, RicambioRiparazione,
                     RigaDistinta, Riparazione)


def num(v):
    v = Decimal(v or 0)
    return f"{v.normalize():f}" if v == v.to_integral() else f"{v:.2f}"


# ---------------------------------------------------------------- articoli


class SottoScortaFilter(admin.SimpleListFilter):
    title = "scorta"
    parameter_name = "scorta"

    def lookups(self, request, model_admin):
        return [("sotto", "Sotto scorta minima"), ("negativo", "Disponibile negativo (da ordinare)")]

    def queryset(self, request, qs):
        if self.value() == "sotto":
            return qs.filter(scorta_minima__gt=0,
                             giacenza_nuovo__lt=F("scorta_minima") + F("impegnato")).exclude(tipo="servizio")
        if self.value() == "negativo":
            return qs.filter(giacenza_nuovo__lt=F("impegnato"))
        return qs


class MovimentiInline(admin.TabularInline):
    model = Movimento
    classes = ("gp-noorig",)
    fields = ("data", "area", "causale", "quantita", "matricola", "riferimento", "utente")
    readonly_fields = fields
    extra = 0
    max_num = 0
    can_delete = False
    ordering = ("-data",)
    verbose_name_plural = "ultimi movimenti"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("ordine", "riparazione", "rapportino", "utente")

    @admin.display(description="Riferimento")
    def riferimento(self, obj):
        rif = obj.ordine or obj.riparazione or obj.rapportino
        return rif.numero if rif else (obj.documento or obj.note)


@admin.register(Articolo)
class ArticoloAdmin(admin.ModelAdmin):
    list_display = ("codice", "descrizione", "tipo", "in_nuovo", "impegnato_col", "disponibile_col",
                    "in_riparazione", "prezzo", "ubicazione")
    list_filter = ("tipo", SottoScortaFilter, "a_matricola", "attivo")
    search_fields = ("codice", "descrizione", "codice_fornitore", "fornitore")
    inlines = [MovimentiInline]
    readonly_fields = ("situazione",)
    fieldsets = (
        (None, {"fields": ("codice", "descrizione", "tipo", "unita", "a_matricola", "attivo")}),
        ("Magazzino", {"fields": ("situazione", "scorta_minima", "ubicazione")}),
        ("Prezzi e fornitore", {"fields": ("costo", "prezzo", "fornitore", "codice_fornitore")}),
        ("Note", {"fields": ("note",), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).con_giacenze()

    @admin.display(description="Giacenza", ordering="giacenza_nuovo")
    def in_nuovo(self, obj):
        return "—" if not obj.a_magazzino else f"{num(obj.giacenza_nuovo)} {obj.unita}"

    @admin.display(description="Impegnato", ordering="impegnato")
    def impegnato_col(self, obj):
        return num(obj.impegnato) if obj.impegnato else "—"

    @admin.display(description="Disponibile")
    def disponibile_col(self, obj):
        if not obj.a_magazzino:
            return "—"
        disp = obj.giacenza_nuovo - obj.impegnato
        colore = "#b91c1c" if disp < 0 else ("#b45309" if disp < obj.scorta_minima else "#15803d")
        return format_html('<b style="color:{}">{}</b>', colore, num(disp))

    @admin.display(description="In riparazione")
    def in_riparazione(self, obj):
        return num(obj.giacenza_riparazioni) if obj.giacenza_riparazioni else "—"

    @admin.display(description="Situazione")
    def situazione(self, obj):
        if not obj.pk:
            return "—"
        if not obj.a_magazzino:
            return "Servizio: non gestito a magazzino"
        a = Articolo.objects.con_giacenze().get(pk=obj.pk)
        carico = reverse("admin:magazzino_movimento_add") + f"?articolo={obj.pk}&causale=carico_acquisto"
        rett = reverse("admin:magazzino_movimento_add") + f"?articolo={obj.pk}&causale=rettifica"
        return format_html(
            "Giacenza nuovo: <b>{}</b> · impegnato in produzione: <b>{}</b> · disponibile: <b>{}</b>"
            " · in riparazione (clienti): <b>{}</b><br><br>"
            '<a class="button" href="{}">＋ Carico da acquisto</a> <a class="button" href="{}">Rettifica inventario</a>',
            num(a.giacenza_nuovo), num(a.impegnato), num(a.giacenza_nuovo - a.impegnato),
            num(a.giacenza_riparazioni), carico, rett)


# ---------------------------------------------------------------- movimenti


CAUSALI_MANUALI = [c for c in Movimento.Causale.choices if c[0] in (
    "carico_acquisto", "reso", "scarico_vendita", "scarico_intervento", "rettifica", "rottamazione")]


class MovimentoForm(forms.ModelForm):
    causale = forms.ChoiceField(choices=CAUSALI_MANUALI)

    class Meta:
        model = Movimento
        fields = ("articolo", "area", "causale", "quantita", "matricola", "cliente", "documento", "note")
        help_texts = {"quantita": "Valore positivo; per la rettifica indica la differenza (+ o −)."}


@admin.register(Movimento)
class MovimentoAdmin(admin.ModelAdmin):
    form = MovimentoForm
    list_display = ("data", "articolo", "area", "causale", "qta", "matricola", "riferimento", "utente")
    list_filter = ("area", "causale", "data")
    search_fields = ("articolo__codice", "articolo__descrizione", "matricola", "documento", "note")
    autocomplete_fields = ("articolo", "cliente")
    date_hierarchy = "data"
    list_select_related = ("articolo", "ordine", "riparazione", "rapportino", "utente")

    @admin.display(description="Q.tà", ordering="quantita")
    def qta(self, obj):
        colore = "#b91c1c" if obj.quantita < 0 else "#15803d"
        return format_html('<b style="color:{}">{}{}</b>', colore, "+" if obj.quantita > 0 else "", num(obj.quantita))

    @admin.display(description="Riferimento")
    def riferimento(self, obj):
        rif = obj.ordine or obj.riparazione or obj.rapportino
        return rif.numero if rif else obj.documento

    def get_readonly_fields(self, request, obj=None):
        # il registro dei movimenti non si riscrive: si corregge con una rettifica
        return [f.name for f in Movimento._meta.fields] if obj else []

    def has_change_permission(self, request, obj=None):
        return obj is None and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        obj.utente = request.user
        super().save_model(request, obj, form, change)


# ---------------------------------------------------------------- distinta base e produzione


class RigaDistintaInline(admin.TabularInline):
    model = RigaDistinta
    extra = 1
    autocomplete_fields = ("componente",)


@admin.register(DistintaBase)
class DistintaBaseAdmin(admin.ModelAdmin):
    list_display = ("__str__", "prodotto", "versione", "attiva", "n_componenti", "costo")
    list_filter = ("attiva",)
    search_fields = ("prodotto__codice", "prodotto__descrizione")
    autocomplete_fields = ("prodotto",)
    inlines = [RigaDistintaInline]
    readonly_fields = ("costo",)

    @admin.display(description="Componenti")
    def n_componenti(self, obj):
        return obj.righe.count()

    @admin.display(description="Costo materiali (€)")
    def costo(self, obj):
        return f"{obj.costo_materiali():.2f}" if obj.pk else "—"


class ImpegnoInline(admin.TabularInline):
    model = Impegno
    classes = ("gp-noorig",)
    fields = ("articolo", "impegnata", "da_prelevare", "copertura")
    readonly_fields = fields
    extra = 0
    max_num = 0
    can_delete = False

    @admin.display(description="Impegnata")
    def impegnata(self, obj):
        return f"{num(obj.quantita)} {obj.articolo.unita}" if obj.pk else "—"

    @admin.display(description="Da prelevare")
    def da_prelevare(self, obj):
        return num(obj.quantita_residua) if obj.pk else "—"

    @admin.display(description="Copertura")
    def copertura(self, obj):
        if not obj.pk:
            return "—"
        if obj.quantita_residua <= 0:
            return format_html('<span style="color:#15803d">prelevato ✔</span>')
        disp = obj.articolo.disponibile() + obj.quantita_residua
        if disp >= obj.quantita_residua:
            return format_html('<span style="color:#15803d">disponibile ({})</span>', num(disp))
        return format_html('<b style="color:#b91c1c">mancano {}</b>', num(obj.quantita_residua - disp))


@admin.register(OrdineProduzione)
class OrdineProduzioneAdmin(AzioniMixin, admin.ModelAdmin):
    list_display = ("numero", "prodotto", "quantita", "commessa", "stato", "data_prevista", "mancanti_col")
    list_filter = ("stato",)
    search_fields = ("numero", "commessa__codice", "commessa__cliente__ragione_sociale",
                     "distinta__prodotto__codice")
    autocomplete_fields = ("commessa", "distinta")
    readonly_fields = ("numero", "stato", "completato_il")
    inlines = [ImpegnoInline]
    fieldsets = (
        (None, {"fields": ("numero", "stato", "commessa", "distinta", "quantita", "data_prevista")}),
        ("Completamento", {"fields": ("matricole_prodotte", "completato_il", "note")}),
    )

    @admin.display(description="Prodotto")
    def prodotto(self, obj):
        return obj.distinta.prodotto

    @admin.display(description="Materiale")
    def mancanti_col(self, obj):
        if obj.stato not in obj.STATI_IMPEGNANTI:
            return "—"
        m = obj.mancanti()
        if not m:
            return format_html('<span style="color:#15803d">completo</span>')
        return format_html('<b style="color:#b91c1c">mancano {} articoli</b>', len(m))

    def get_readonly_fields(self, request, obj=None):
        ro = list(self.readonly_fields)
        if obj and obj.stato != obj.Stato.BOZZA:
            ro += ["distinta", "quantita"]  # impegni già creati su queste quantità
        return ro

    def azioni(self, request, obj):
        S = obj.Stato
        a = []
        if obj.stato == S.BOZZA:
            a.append(("conferma", "Conferma e impegna il materiale"))
        if obj.stato == S.CONFERMATO:
            a.append(("preleva", "Preleva componenti e avvia"))
        if obj.stato in obj.STATI_IMPEGNANTI:
            a.append(("completa", "Completa: scarica componenti e carica prodotto"))
        if obj.stato not in (S.COMPLETATO, S.ANNULLATO):
            a.append(("annulla", "Annulla ordine"))
        return a

    def azione_conferma(self, request, obj):
        obj.conferma()
        mancanti = obj.mancanti()
        if mancanti:
            from django.contrib import messages

            messages.warning(request, "Attenzione, materiale insufficiente: " + ", ".join(
                f"{a.codice} (mancano {num(q)})" for a, q in mancanti))
        return f"{obj.numero} confermato: materiale impegnato sul magazzino nuovo."

    def azione_preleva(self, request, obj):
        obj.preleva(request.user)
        return "Componenti prelevati dal magazzino."

    def azione_completa(self, request, obj):
        obj.completa(request.user)
        return f"{obj.numero} completato: prodotto caricato a magazzino."

    def azione_annulla(self, request, obj):
        obj.annulla()
        return f"{obj.numero} annullato: impegni rilasciati."


# ---------------------------------------------------------------- riparazioni


class RicambioRiparazioneInline(admin.TabularInline):
    model = RicambioRiparazione
    extra = 1
    autocomplete_fields = ("articolo",)


@admin.register(Riparazione)
class RiparazioneAdmin(AzioniMixin, admin.ModelAdmin):
    list_display = ("numero", "cliente", "descrizione_pezzo", "matricola", "stato", "data_ricezione", "giorni",
                    "in_garanzia")
    list_filter = ("stato", "in_garanzia", "tecnico")
    search_fields = ("numero", "matricola", "descrizione_pezzo", "cliente__ragione_sociale", "ddt_ingresso")
    autocomplete_fields = ("cliente", "ticket", "apparato", "articolo", "tecnico")
    readonly_fields = ("numero", "preventivi_collegati")
    inlines = [RicambioRiparazioneInline]
    date_hierarchy = "data_ricezione"
    fieldsets = (
        (None, {"fields": ("numero", "stato", ("cliente", "ticket"), "apparato", "tecnico")}),
        ("Pezzo", {"fields": ("articolo", "descrizione_pezzo", "matricola", "in_garanzia", "difetto_dichiarato")}),
        ("Lavorazione", {"fields": ("diagnosi", "lavoro_eseguito", "ore_lavoro", "preventivi_collegati")}),
        ("Logistica", {"fields": (("data_ricezione", "ddt_ingresso"), ("data_riconsegna", "ddt_uscita"))}),
    )

    @admin.display(description="Giorni in lab")
    def giorni(self, obj):
        from django.utils import timezone

        fine = obj.data_riconsegna or timezone.localdate()
        return (fine - obj.data_ricezione).days

    @admin.display(description="Preventivi")
    def preventivi_collegati(self, obj):
        if not obj.pk:
            return "—"
        righe = [format_html('<a href="{}">{}</a> ({})', reverse("admin:preventivi_preventivo_change", args=[p.pk]),
                             p.codice, p.get_stato_display()) for p in obj.preventivi.all()]
        return format_html("<br>".join(["{}"] * len(righe)), *righe) if righe else "—"

    def get_changeform_initial_data(self, request):
        data = super().get_changeform_initial_data(request)
        data.setdefault("tecnico", request.user.pk)
        return data

    def azioni(self, request, obj):
        a = [("stampa", "🖨 Ricevuta / scheda riparazione")]
        if obj.aperta and not obj.in_garanzia and not obj.preventivi.exclude(stato__in=["annullato", "rifiutato"]).exists():
            a.insert(0, ("preventivo", "Crea preventivo di riparazione"))
        return a

    def azione_stampa(self, request, obj):
        return HttpResponseRedirect(reverse("stampa", args=["riparazione", obj.pk]))

    def azione_preventivo(self, request, obj):
        from apps.preventivi.models import Preventivo, RigaPreventivo

        p = Preventivo.objects.create(
            tipo=Preventivo.Tipo.RIPARAZIONE, cliente=obj.cliente, riparazione=obj, ticket=obj.ticket,
            oggetto=f"Riparazione {obj.descrizione_pezzo} matr. {obj.matricola}", autore=request.user,
            introduzione=f"Diagnosi: {obj.diagnosi}" if obj.diagnosi else "", validita_giorni=15)
        for i, r in enumerate(obj.ricambi.select_related("articolo"), 1):
            RigaPreventivo.objects.create(preventivo=p, ordine=i, articolo=r.articolo, quantita=r.quantita)
        if obj.ore_lavoro:
            RigaPreventivo.objects.create(preventivo=p, ordine=99, descrizione="Manodopera di laboratorio",
                                          quantita=obj.ore_lavoro, unita="h", prezzo_unitario=0)
        if obj.stato in (obj.Stato.RICEVUTO, obj.Stato.DIAGNOSI):
            obj.stato = obj.Stato.ATTESA_OK
            obj.save()
        from django.contrib import messages

        messages.success(request, f"Creato {p.codice}: controlla i prezzi e invialo al cliente.")
        return HttpResponseRedirect(reverse("admin:preventivi_preventivo_change", args=[p.pk]))
