from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, F, Q
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.assistenza.models import Apparato, Contratto, Ticket
from apps.commesse.models import Collaudo, Commessa, Sopralluogo

from .versioning import get_changelog


def home(request):
    if not request.user.is_authenticated:
        return redirect("portale:apri_ticket")
    if not request.user.is_staff:
        return redirect("portale:miei_ticket")
    return dashboard(request)


@staff_member_required
def dashboard(request):
    oggi = timezone.localdate()
    aperti = list(
        Ticket.objects.filter(stato__in=Ticket.STATI_APERTI)
        .select_related("cliente", "assegnato_a", "apparato")
    )

    def chiave(t):
        scad, _ = t.sla_corrente
        return scad or timezone.now() + timedelta(days=3650)

    aperti.sort(key=chiave)
    conteggio_sla = {"scaduto": 0, "attenzione": 0}
    for t in aperti:
        _, stato = t.sla_corrente
        if stato in conteggio_sla:
            conteggio_sla[stato] += 1

    ctx = {
        "ticket_aperti": aperti,
        "n_da_smistare": sum(1 for t in aperti if not t.cliente_id),
        "n_miei": sum(1 for t in aperti if t.assegnato_a_id == request.user.id),
        "conteggio_sla": conteggio_sla,
        "contratti_in_scadenza": [c for c in Contratto.objects.filter(attivo=True, data_fine__gte=oggi,
                                                                       data_fine__lte=oggi + timedelta(days=90))
                                  .select_related("cliente") if c.in_scadenza],
        "commesse_per_stato": Commessa.objects.exclude(stato__in=["chiusa", "persa"]).values("stato")
        .annotate(n=Count("id")).order_by("stato"),
        "sopralluoghi": Sopralluogo.objects.select_related("commessa__cliente")[:5],
        "collaudi": Collaudo.objects.select_related("commessa__cliente")[:5],
        "apparati_guasti": Apparato.objects.filter(stato=Apparato.Stato.GUASTO).count(),
        "apparati_totali": Apparato.objects.exclude(stato=Apparato.Stato.DISMESSO).count(),
        "risolti_30gg": Ticket.objects.filter(risolto_il__gte=timezone.now() - timedelta(days=30)).aggregate(
            tot=Count("id"),
            violati=Count("id", filter=Q(scadenza_risoluzione__isnull=False,
                                         risolto_il__gt=F("scadenza_risoluzione"))),
        ),
    }
    from apps.magazzino.models import Articolo, OrdineProduzione, Riparazione
    from apps.preventivi.models import Preventivo

    in_attesa = [p for p in Preventivo.objects.filter(stato="inviato").select_related("cliente") if not p.scaduto]
    articoli = Articolo.objects.con_giacenze().exclude(tipo="servizio").filter(attivo=True)
    ctx.update({
        "preventivi_in_attesa": in_attesa,
        "valore_in_attesa": sum((p.imponibile for p in in_attesa), 0),
        "preventivi_bozza": Preventivo.objects.filter(stato="bozza").count(),
        "riparazioni_aperte": Riparazione.objects.filter(stato__in=Riparazione.APERTE).count(),
        "riparazioni_pronte": Riparazione.objects.filter(stato="riparato").count(),
        "sotto_scorta": [a for a in articoli if a.scorta_minima and a.giacenza_nuovo - a.impegnato < a.scorta_minima],
        "ordini_aperti": OrdineProduzione.objects.filter(stato__in=OrdineProduzione.STATI_IMPEGNANTI)
        .select_related("distinta__prodotto", "commessa"),
    })
    return render(request, "core/dashboard.html", ctx)


def changelog(request):
    return render(request, "core/changelog.html", {"releases": get_changelog()})
