from django.conf import settings
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.static import serve

from apps.assistenza import views as campo
from apps.core import views as core
from apps.core.forms import ImpostaPasswordForm

urlpatterns = [
    path("", core.home, name="home"),
    path("cruscotto/", core.dashboard, name="dashboard"),
    path("versioni/", core.changelog, name="changelog"),
    path("campo/<str:tipo>/<int:pk>/firma/", campo.firma, name="firma"),
    path("campo/<str:tipo>/<int:pk>/stampa/", campo.stampa, name="stampa"),
    path("assistenza/", include("apps.portale.urls")),
    path("account/password_reset/", auth_views.PasswordResetView.as_view(form_class=ImpostaPasswordForm),
         name="password_reset"),
    path("account/", include("django.contrib.auth.urls")),
    path("admin/", admin.site.urls),
]

# File caricati (firme, foto, allegati): mai pubblici. Solo il personale interno li apre direttamente;
# gli allegati dei ticket per i clienti passano dalla vista del portale che controlla il token.
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", staff_member_required(serve), {"document_root": settings.MEDIA_ROOT}),
]
