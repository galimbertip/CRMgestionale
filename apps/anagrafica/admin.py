from django.contrib import admin, messages
from django.utils.crypto import get_random_string

from apps.core.admin import invia_link_password
from apps.core.models import Utente

from .models import Cliente, Contatto, Sede


class SedeInline(admin.StackedInline):
    model = Sede
    extra = 0


class ContattoInline(admin.TabularInline):
    model = Contatto
    extra = 0
    fields = ("nome", "cognome", "ruolo", "email", "telefono", "principale")


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("codice", "ragione_sociale", "citta", "telefono", "contratto", "n_apparati", "attivo")
    list_filter = ("attivo",)
    search_fields = ("ragione_sociale", "codice", "partita_iva", "email")
    inlines = [SedeInline, ContattoInline]

    @admin.display(description="Contratto attivo")
    def contratto(self, obj):
        c = obj.contratto_attivo()
        return f"{c.numero} ({c.livello_sla})" if c else "—"

    @admin.display(description="Apparati")
    def n_apparati(self, obj):
        return obj.apparati.count()


@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ("nome", "cliente", "citta", "referente", "telefono")
    search_fields = ("nome", "citta", "cliente__ragione_sociale")
    autocomplete_fields = ("cliente",)


@admin.register(Contatto)
class ContattoAdmin(admin.ModelAdmin):
    list_display = ("__str__", "cliente", "ruolo", "email", "telefono", "accesso_portale")
    search_fields = ("nome", "cognome", "email", "cliente__ragione_sociale")
    autocomplete_fields = ("cliente",)
    actions = ["crea_accesso_portale"]

    def has_gestione_utenti_permission(self, request):
        return getattr(request.user, "is_admin_crm", False)

    @admin.display(description="Portale", boolean=True)
    def accesso_portale(self, obj):
        return bool(obj.email) and Utente.objects.filter(email__iexact=obj.email, ruolo="cliente").exists()

    @admin.action(description="Crea accesso al portale e invia link password", permissions=["gestione_utenti"])
    def crea_accesso_portale(self, request, queryset):
        nuovi = []
        for c in queryset:
            if not c.email:
                messages.warning(request, f"{c}: manca l'email, saltato.")
                continue
            u = Utente.objects.filter(email__iexact=c.email).first()
            if u and u.ruolo != Utente.Ruolo.CLIENTE:
                messages.warning(request, f"{c.email} è già un utente interno, saltato.")
                continue
            if not u:
                u = Utente(username=c.email.lower(), email=c.email.lower(), first_name=c.nome,
                           last_name=c.cognome, ruolo=Utente.Ruolo.CLIENTE)
                u.set_password(get_random_string(32))
            u.cliente = c.cliente
            u.save()
            nuovi.append(u.pk)
        if nuovi:
            invia_link_password(self, request, Utente.objects.filter(pk__in=nuovi))
