from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from apps.commesse.admin import link_campo

from . import notifiche
from .models import (Apparato, Contratto, EventoTicket, LivelloSLA, MessaggioTicket, Rapportino, RegolaSLA,
                     RigaRicambio, Ticket)

COLORI_SLA = {
    "ok": ("#0f766e", "In tempo"),
    "attenzione": ("#b45309", "In scadenza"),
    "scaduto": ("#b91c1c", "Scaduto"),
    "rispettato": ("#15803d", "Rispettato"),
    "violato": ("#b91c1c", "Violato"),
}


def badge_sla(stato, scadenza):
    if not stato:
        return "—"
    colore, testo = COLORI_SLA[stato]
    quando = timezone.localtime(scadenza).strftime("%d/%m %H:%M") if scadenza else ""
    return format_html('<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;'
                       'white-space:nowrap">{} · {}</span>', colore, testo, quando)


# ---------------------------------------------------------------- SLA / contratti


class RegolaInline(admin.TabularInline):
    model = RegolaSLA
    extra = 0


@admin.register(LivelloSLA)
class LivelloSLAAdmin(admin.ModelAdmin):
    list_display = ("nome", "solo_orario_lavorativo", "ora_inizio", "ora_fine", "predefinito")
    inlines = [RegolaInline]


@admin.register(Contratto)
class ContrattoAdmin(admin.ModelAdmin):
    list_display = ("numero", "cliente", "tipo", "livello_sla", "data_inizio", "data_fine", "scadenza", "attivo")
    list_filter = ("tipo", "livello_sla", "attivo")
    search_fields = ("numero", "cliente__ragione_sociale")
    autocomplete_fields = ("cliente", "commessa")
    readonly_fields = ("ore_consumate_display",)

    @admin.display(description="Scadenza")
    def scadenza(self, obj):
        if obj.scaduto:
            return format_html('<b style="color:#b91c1c">Scaduto</b>')
        if obj.in_scadenza:
            return format_html('<b style="color:#b45309">Tra {} gg</b>', obj.giorni_alla_scadenza)
        return f"Tra {obj.giorni_alla_scadenza} gg"

    @admin.display(description="Ore consumate (rapportini)")
    def ore_consumate_display(self, obj):
        if not obj.pk:
            return "—"
        tot = obj.ore_consumate()
        return f"{tot} h" + (f" su {obj.ore_incluse} h incluse" if obj.ore_incluse else "")


# ---------------------------------------------------------------- parco installato


class TicketApparatoInline(admin.TabularInline):
    model = Ticket
    fk_name = "apparato"
    fields = ("codice", "oggetto", "stato", "creato_il")
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True


class RapportinoApparatoInline(admin.TabularInline):
    model = Rapportino
    fk_name = "apparato"
    fields = ("numero", "data", "tecnico", "esito")
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True


@admin.register(Apparato)
class ApparatoAdmin(admin.ModelAdmin):
    list_display = ("matricola", "modello", "cliente", "sede", "stato", "data_installazione", "garanzia",
                     "contratto")
    list_filter = ("stato", "modello")
    search_fields = ("matricola", "modello", "identificativo_remoto", "cliente__ragione_sociale")
    autocomplete_fields = ("cliente", "sede", "commessa", "contratto")
    inlines = [TicketApparatoInline, RapportinoApparatoInline]

    @admin.display(description="Garanzia", boolean=True)
    def garanzia(self, obj):
        return obj.in_garanzia


# ---------------------------------------------------------------- ticket


class MessaggioInline(admin.StackedInline):
    model = MessaggioTicket
    extra = 1
    fields = ("testo", "interno", "allegato", "info")
    readonly_fields = ("info",)

    @admin.display(description="Autore")
    def info(self, obj):
        if not obj.pk:
            return "—"
        tipo = "nota interna" if obj.interno else ("cliente" if obj.da_cliente else "assistenza")
        return f"{obj.nome_visualizzato} · {timezone.localtime(obj.creato_il):%d/%m/%Y %H:%M} · {tipo}"


class EventoInline(admin.TabularInline):
    model = EventoTicket
    extra = 0
    fields = ("quando", "utente", "descrizione")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("codice", "oggetto", "cliente_o_dichiarato", "priorita", "stato", "assegnato_a", "sla",
                    "creato_il")
    list_filter = ("stato", "priorita", "categoria", "canale", "assegnato_a", ("cliente", admin.EmptyFieldListFilter))
    search_fields = ("codice", "oggetto", "descrizione", "richiedente_email", "richiedente_nome",
                     "azienda_dichiarata", "matricola_dichiarata", "cliente__ragione_sociale", "apparato__matricola")
    autocomplete_fields = ("cliente", "apparato", "commessa", "contratto", "assegnato_a")
    readonly_fields = ("codice", "link_pubblico", "livello_sla", "scadenze", "preso_in_carico_il", "risolto_il",
                       "chiuso_il", "creato_il")
    inlines = [MessaggioInline, EventoInline]
    actions = ["prendi_in_carico", "segna_risolto", "ricalcola_sla"]
    list_select_related = ("cliente", "assegnato_a")
    fieldsets = (
        (None, {"fields": ("codice", "oggetto", "descrizione", ("categoria", "priorita"), ("stato", "assegnato_a"))}),
        ("Cliente e apparato", {"fields": ("cliente", "apparato", "commessa", "contratto",
                                           ("azienda_dichiarata", "matricola_dichiarata"))}),
        ("Richiedente", {"fields": (("richiedente_nome", "richiedente_email", "richiedente_telefono"), "canale",
                                    "link_pubblico")}),
        ("SLA", {"fields": ("livello_sla", "scadenze", ("preso_in_carico_il", "risolto_il", "chiuso_il"),
                            "creato_il")}),
    )

    @admin.display(description="Cliente")
    def cliente_o_dichiarato(self, obj):
        if obj.cliente:
            return obj.cliente
        return format_html('<i style="color:#b45309">da smistare: {}</i>', obj.azienda_dichiarata or obj.richiedente_email)

    @admin.display(description="SLA")
    def sla(self, obj):
        if not obj.aperto:
            return badge_sla(obj.sla_risoluzione, obj.scadenza_risoluzione)
        scad, stato = obj.sla_corrente
        return badge_sla(stato, scad)

    @admin.display(description="Scadenze SLA")
    def scadenze(self, obj):
        return format_html("Presa in carico: {}<br>Risoluzione: {}",
                           badge_sla(obj.sla_presa_in_carico, obj.scadenza_presa_in_carico),
                           badge_sla(obj.sla_risoluzione, obj.scadenza_risoluzione))

    @admin.display(description="Link per il cliente")
    def link_pubblico(self, obj):
        if not obj.pk:
            return "—"
        return format_html('<a href="{0}" target="_blank">{0}</a>', obj.url_pubblico())

    def get_changeform_initial_data(self, request):
        data = super().get_changeform_initial_data(request)
        data.setdefault("canale", Ticket.Canale.TELEFONO)
        return data

    def save_model(self, request, obj, form, change):
        cambi = []
        if change:
            for campo in ("stato", "priorita", "assegnato_a", "cliente"):
                if campo in form.changed_data:
                    nuovo = getattr(obj, f"get_{campo}_display", lambda o=obj, c=campo: getattr(o, c))()
                    cambi.append(f"{obj._meta.get_field(campo).verbose_name.capitalize()}: {nuovo or '—'}")
        if obj.stato != Ticket.Stato.NUOVO and not obj.assegnato_a:
            obj.assegnato_a = request.user
        super().save_model(request, obj, form, change)
        if change and ("priorita" in form.changed_data or "contratto" in form.changed_data
                       or "cliente" in form.changed_data):
            obj.ricalcola_sla()
        if not change:
            EventoTicket.objects.create(ticket=obj, utente=request.user, descrizione="Ticket aperto dall'assistenza")
        for c in cambi:
            EventoTicket.objects.create(ticket=obj, utente=request.user, descrizione=c,
                                        visibile_cliente=not c.startswith("Assegnato"))
        if change and "stato" in form.changed_data:
            notifiche.cambio_stato(obj)

    def save_formset(self, request, form, formset, change):
        istanze = formset.save(commit=False)
        for i in istanze:
            if isinstance(i, MessaggioTicket) and not i.pk:
                i.autore = request.user
                i.save()
                if not i.interno:
                    notifiche.risposta_assistenza(i)
            else:
                i.save()
        for d in formset.deleted_objects:
            d.delete()
        formset.save_m2m()

    @admin.action(description="Prendi in carico (assegna a me)")
    def prendi_in_carico(self, request, queryset):
        n = 0
        for t in queryset.filter(stato=Ticket.Stato.NUOVO):
            t.stato, t.assegnato_a = Ticket.Stato.PRESO, request.user
            t.save()
            EventoTicket.objects.create(ticket=t, utente=request.user, descrizione="Stato: Preso in carico")
            notifiche.cambio_stato(t)
            n += 1
        messages.success(request, f"{n} ticket presi in carico.")

    @admin.action(description="Segna come risolto")
    def segna_risolto(self, request, queryset):
        for t in queryset.exclude(stato__in=[Ticket.Stato.RISOLTO, Ticket.Stato.CHIUSO]):
            t.stato = Ticket.Stato.RISOLTO
            t.assegnato_a = t.assegnato_a or request.user
            t.save()
            EventoTicket.objects.create(ticket=t, utente=request.user, descrizione="Stato: Risolto")
            notifiche.cambio_stato(t)

    @admin.action(description="Ricalcola scadenze SLA")
    def ricalcola_sla(self, request, queryset):
        for t in queryset:
            t.ricalcola_sla()


# ---------------------------------------------------------------- rapportino


class RicambioInline(admin.TabularInline):
    model = RigaRicambio
    extra = 1


@admin.register(Rapportino)
class RapportinoAdmin(admin.ModelAdmin):
    list_display = ("numero", "data", "cliente", "tecnico", "tipo", "ore", "km", "esito", "firmato_flag")
    list_filter = ("tipo", "esito", "tecnico")
    search_fields = ("numero", "cliente__ragione_sociale", "ticket__codice", "apparato__matricola")
    autocomplete_fields = ("cliente", "sede", "ticket", "commessa", "contratto", "apparato", "tecnico")
    readonly_fields = ("numero", "azioni", "ore", "firmato_il")
    date_hierarchy = "data"
    inlines = [RicambioInline]
    fieldsets = (
        (None, {"fields": ("numero", "azioni", ("cliente", "sede"), ("ticket", "commessa"), ("apparato", "contratto"),
                           ("tecnico", "tipo"))}),
        ("Tempi", {"fields": ("data", ("ora_inizio", "ora_fine", "pausa_minuti"), "ore", ("ore_viaggio", "km"))}),
        ("Intervento", {"fields": ("problema", "lavoro_svolto", "esito", "note_cliente")}),
        ("Firma", {"fields": ("firmatario", "firmato_il")}),
    )

    @admin.display(description="Ore lavoro")
    def ore(self, obj):
        return obj.ore_lavoro if obj.pk else "—"

    @admin.display(description="Firmato", boolean=True)
    def firmato_flag(self, obj):
        return obj.firmato

    @admin.display(description="Azioni sul campo")
    def azioni(self, obj):
        return link_campo("rapportino", obj)

    def get_changeform_initial_data(self, request):
        data = super().get_changeform_initial_data(request)
        data.setdefault("tecnico", request.user.pk)
        return data
