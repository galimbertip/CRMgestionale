from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import PasswordResetForm

from .models import Numeratore, Utente
from .versioning import display_version

admin.site.site_header = f"GPverse CRM · {display_version()}"
admin.site.site_title = "GPverse CRM"
admin.site.index_title = "Back-office assistenza tecnica"
admin.site.site_url = "/"


def invia_link_password(modeladmin, request, queryset, use_https=None):
    inviati = 0
    for u in queryset.exclude(email=""):
        form = PasswordResetForm({"email": u.email})
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


@admin.register(Utente)
class UtenteAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "email", "ruolo", "cliente", "is_active", "is_staff")
    list_filter = ("ruolo", "is_active", "is_staff")
    search_fields = ("username", "first_name", "last_name", "email", "cliente__ragione_sociale")
    autocomplete_fields = ("cliente",)
    actions = [invia_link_password]
    fieldsets = UserAdmin.fieldsets + (("GPverse", {"fields": ("ruolo", "cliente", "telefono")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("GPverse", {"fields": ("email", "first_name", "last_name", "ruolo", "cliente")}),
    )

    def save_model(self, request, obj, form, change):
        # i clienti non entrano mai nel back-office
        if obj.ruolo == Utente.Ruolo.CLIENTE:
            obj.is_staff = False
            obj.is_superuser = False
        super().save_model(request, obj, form, change)


@admin.register(Numeratore)
class NumeratoreAdmin(admin.ModelAdmin):
    list_display = ("prefisso", "anno", "ultimo")
