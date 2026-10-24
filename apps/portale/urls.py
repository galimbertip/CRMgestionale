from django.urls import path

from . import views

app_name = "portale"

urlpatterns = [
    path("", views.apri_ticket, name="apri_ticket"),
    path("i-miei-ticket/", views.miei_ticket, name="miei_ticket"),
    path("ritrova/", views.cerca_ticket, name="cerca_ticket"),
    path("t/<uuid:token>/", views.ticket_dettaglio, name="ticket_dettaglio"),
    path("t/<uuid:token>/ricevuto/", views.ticket_creato, name="ticket_creato"),
    path("t/<uuid:token>/allegato/<int:msg_id>/", views.allegato, name="allegato"),
]
