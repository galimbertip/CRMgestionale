"""Livelli di accesso del CRM e relativi permessi.

- admin    → back-office completo, gestione utenti, SLA, contratti, modelli di checklist
- tecnico  → lavoro operativo: ticket, rapportini, sopralluoghi, collaudi, parco installato;
             contratti e SLA in sola lettura, nessuna cancellazione, nessuna gestione utenti
- cliente  → solo portale assistenza (mai il back-office)

I gruppi Django corrispondenti vengono creati/aggiornati a ogni `migrate`, e ogni utente
viene messo nel gruppo giusto quando si salva: il ruolo è l'unica cosa da impostare.
"""
from django.db import transaction

GRUPPO_ADMIN = "Amministratori CRM"
GRUPPO_TECNICO = "Tecnici"

APP_CRM = ["core", "anagrafica", "commesse", "assistenza"]

V, A, C, D = "view", "add", "change", "delete"

PERMESSI_TECNICO = {
    "anagrafica": {"cliente": [V, A, C], "sede": [V, A, C], "contatto": [V, A, C]},
    "commesse": {
        "commessa": [V, A, C],
        "sopralluogo": [V, A, C], "rigasopralluogo": [V, A, C, D], "fotosopralluogo": [V, A, C, D],
        "collaudo": [V, A, C], "rigacollaudo": [V, A, C, D],
        "modellochecklist": [V], "vocemodello": [V],
    },
    "assistenza": {
        "ticket": [V, A, C], "messaggioticket": [V, A, C], "eventoticket": [V],
        "rapportino": [V, A, C], "rigaricambio": [V, A, C, D],
        "apparato": [V, A, C],
        "contratto": [V], "livellosla": [V], "regolasla": [V],
    },
    # serve per scegliere tecnico/assegnatario nei campi a ricerca; la gestione resta agli admin
    "core": {"utente": [V]},
}


def _permessi(spec):
    from django.contrib.auth.models import Permission

    codenames = []
    for app, modelli in spec.items():
        for modello, azioni in modelli.items():
            codenames += [(app, f"{a}_{modello}") for a in azioni]
    perms = []
    for app, codename in codenames:
        p = Permission.objects.filter(content_type__app_label=app, codename=codename).first()
        if p:
            perms.append(p)
    return perms


@transaction.atomic
def configura_gruppi():
    from django.contrib.auth.models import Group, Permission

    admin, _ = Group.objects.get_or_create(name=GRUPPO_ADMIN)
    admin.permissions.set(Permission.objects.filter(content_type__app_label__in=APP_CRM))
    tecnico, _ = Group.objects.get_or_create(name=GRUPPO_TECNICO)
    tecnico.permissions.set(_permessi(PERMESSI_TECNICO))
    return admin, tecnico


def gruppo_per_ruolo(ruolo):
    from django.contrib.auth.models import Group

    nome = {"admin": GRUPPO_ADMIN, "tecnico": GRUPPO_TECNICO}.get(ruolo)
    if not nome:
        return None
    gruppo = Group.objects.filter(name=nome).first()
    if gruppo is None:
        configura_gruppi()
        gruppo = Group.objects.get(name=nome)
    return gruppo


def allinea_gruppi(utente):
    """Mette l'utente nel solo gruppo del suo ruolo (lascia stare eventuali altri gruppi personalizzati)."""
    from django.contrib.auth.models import Group

    nostri = Group.objects.filter(name__in=[GRUPPO_ADMIN, GRUPPO_TECNICO])
    utente.groups.remove(*nostri)
    g = gruppo_per_ruolo(utente.ruolo)
    if g:
        utente.groups.add(g)


def post_migrate(sender, **kwargs):
    # i permessi delle app vengono creati app per app: rieseguendo per ognuna delle nostre
    # (operazione idempotente) dopo l'ultima i gruppi sono completi
    if not sender.name.startswith("apps."):
        return
    configura_gruppi()
    from django.contrib.auth import get_user_model

    for u in get_user_model().objects.exclude(ruolo="cliente"):
        allinea_gruppi(u)
