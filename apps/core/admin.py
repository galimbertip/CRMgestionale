from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.contrib.auth.models import Group
from django.utils.html import format_html

from .forms import ImpostaPasswordForm
from .models import Numeratore, Utente
from .versioning import display_version

admin.site.site_header = f"GPverse CRM · {display_version()}"
admin.site.site_title = "GPverse CRM"
admin.site.index_title = "Back-office assistenza tecnica"
admin.site.site_url = "/"


def invia_link_password(modeladmin, request, queryset):
    inviati = 0
    for u in queryset.exclude(email="").filter(is_active=True):
        form = ImpostaPasswordForm({"email": u.email})
        if form.is_valid():
            form.save(
                request=request,
                use_https=settings.PUBLIC_BASE_URL.startswith("https"),
                email_template_name="registration/password_reset_email.html",
                subject_template_name="registration/password_reset_subject.txt",
                domain_override=settings.PUBLIC_BASE_URL.split("://")[-1],
            )
            inviati += 1
    messages.success(request, f"Link per impostare la password inviato a {inviati} utenti.")


invia_link_password.short_description = "Invia link per impostare la password"


class LivelloMixin:
    """Validazioni comuni ai form di creazione e modifica utente."""

    def clean(self):
        data = super().clean()
        ruolo, cliente = data.get("ruolo"), data.get("cliente")
        if ruolo == Utente.Ruolo.CLIENTE and not cliente:
            self.add_error("cliente", "Per un utente cliente indica l'azienda.")
        if ruolo == Utente.Ruolo.CLIENTE and not data.get("email"):
            self.add_error("email", "Il cliente deve avere un'email (serve per i ticket e la password).")
        return data


class UtenteChangeForm(LivelloMixin, UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Utente


class UtenteCreationForm(LivelloMixin, AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = Utente
        fields = ("username", "email", "first_name", "last_name", "ruolo", "cliente", "vede_ticket_azienda")


COLORI_LIVELLO = {"admin": "#8d7dff", "tecnico": "#0aa9c0", "cliente": "#64748b"}


@admin.register(Utente)
class UtenteAdmin(UserAdmin):
    form = UtenteChangeForm
    add_form = UtenteCreationForm
    list_display = ("username", "nome", "email", "livello", "cliente", "is_active", "last_login")
    list_filter = ("ruolo", "is_active", "cliente")
    search_fields = ("username", "first_name", "last_name", "email", "cliente__ragione_sociale")
    autocomplete_fields = ("cliente",)
    ordering = ("ruolo", "last_name", "username")
    actions = [invia_link_password, "attiva", "disattiva"]
    readonly_fields = ("last_login", "date_joined")

    fieldsets_base = (
        (None, {"fields": ("username", "password")}),
        ("Dati personali", {"fields": ("first_name", "last_name", "email", "telefono")}),
        ("Livello di accesso", {
            "fields": ("ruolo", "is_active", "cliente", "vede_ticket_azienda"),
            "description": "Il livello imposta da solo l'accesso al back-office e i permessi. "
                           "Azienda e visibilità valgono solo per i clienti.",
        }),
        ("Date", {"fields": ("last_login", "date_joined"), "classes": ("collapse",)}),
    )
    fieldsets_superuser = fieldsets_base + (
        ("Avanzate (solo superuser)", {"fields": ("is_superuser", "groups", "user_permissions"),
                                       "classes": ("collapse",)}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "first_name", "last_name", "ruolo", "cliente", "vede_ticket_azienda",
                       "usable_password", "password1", "password2"),
            "description": "Scegli il livello. Se crei l'utente senza password e c'è l'email, "
                           "gli inviamo un link per impostarla da solo.",
        }),
    )

    # -- visualizzazione

    @admin.display(description="Nome", ordering="last_name")
    def nome(self, obj):
        return obj.get_full_name() or "—"

    @admin.display(description="Livello", ordering="ruolo")
    def livello(self, obj):
        testo = {"admin": "Admin", "tecnico": "Tecnico", "cliente": "Cliente"}.get(obj.ruolo, obj.ruolo) + (
            " · superuser" if obj.is_superuser else "")
        return format_html('<span style="background:{};color:#fff;padding:2px 9px;border-radius:10px;'
                           'white-space:nowrap">{}</span>', COLORI_LIVELLO.get(obj.ruolo, "#64748b"), testo)

    def get_fieldsets(self, request, obj=None):
        if not obj:
            return self.add_fieldsets
        return self.fieldsets_superuser if request.user.is_superuser else self.fieldsets_base

    def get_readonly_fields(self, request, obj=None):
        ro = list(self.readonly_fields)
        if obj and obj.pk == request.user.pk:
            ro += ["ruolo", "is_active"]  # nessuno si toglie da solo l'accesso
        return ro

    # -- chi può fare cosa: la gestione utenti è degli amministratori

    def _admin(self, request):
        return getattr(request.user, "is_admin_crm", False)

    def has_module_permission(self, request):
        return self._admin(request)

    def has_view_permission(self, request, obj=None):
        if self._admin(request):
            return True
        # i tecnici possono solo cercare colleghi nei campi "tecnico" / "assegnato a"
        match = getattr(request, "resolver_match", None)
        return bool(match and match.url_name == "autocomplete" and super().has_view_permission(request, obj))

    def has_change_permission(self, request, obj=None):
        if not self._admin(request):
            return False
        if obj and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj) or request.user.is_superuser

    def has_add_permission(self, request):
        return self._admin(request) and (super().has_add_permission(request) or request.user.is_superuser)

    def has_delete_permission(self, request, obj=None):
        if obj and (obj.pk == request.user.pk or (obj.is_superuser and not request.user.is_superuser)):
            return False
        return self._admin(request) and super().has_delete_permission(request, obj)

    def get_search_results(self, request, queryset, search_term):
        qs, dup = super().get_search_results(request, queryset, search_term)
        if not self._admin(request):
            qs = qs.filter(ruolo__in=[Utente.Ruolo.ADMIN, Utente.Ruolo.TECNICO], is_active=True)
        return qs, dup

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.is_superuser = obj.is_superuser if change else False
        super().save_model(request, obj, form, change)
        if not change and obj.email and not obj.has_usable_password():
            invia_link_password(self, request, Utente.objects.filter(pk=obj.pk))

    # -- azioni

    @admin.action(description="Attiva utenti selezionati")
    def attiva(self, request, queryset):
        n = queryset.update(is_active=True)
        messages.success(request, f"{n} utenti attivati.")

    @admin.action(description="Disattiva utenti selezionati (blocca l'accesso)")
    def disattiva(self, request, queryset):
        qs = queryset.exclude(pk=request.user.pk)
        if not request.user.is_superuser:
            qs = qs.exclude(is_superuser=True)
        n = qs.update(is_active=False)
        messages.success(request, f"{n} utenti disattivati.")


# I gruppi sono gestiti dal sistema in base al livello: visibili solo al superuser
admin.site.unregister(Group)


@admin.register(Group)
class GruppoAdmin(GroupAdmin):
    def has_module_permission(self, request):
        return request.user.is_superuser


@admin.register(Numeratore)
class NumeratoreAdmin(admin.ModelAdmin):
    list_display = ("prefisso", "anno", "ultimo")

    def has_module_permission(self, request):
        return request.user.is_superuser
