from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.anagrafica.models import Contatto
from apps.assistenza import notifiche
from apps.assistenza.models import Apparato, EventoTicket, MessaggioTicket, Ticket
from apps.core.models import Utente

from .forms import ApriTicketForm, RispostaForm


def _riconosci_cliente(email):
    """Associa un richiedente anonimo a un cliente tramite l'email di un contatto o utente del portale."""
    u = Utente.objects.filter(email__iexact=email, ruolo=Utente.Ruolo.CLIENTE, cliente__isnull=False).first()
    if u:
        return u.cliente
    c = Contatto.objects.filter(email__iexact=email).select_related("cliente").first()
    return c.cliente if c else None


def apri_ticket(request):
    utente = request.user if request.user.is_authenticated else None
    portale = bool(utente and utente.is_cliente)
    if request.method == "POST":
        form = ApriTicketForm(request.POST, request.FILES, utente=utente)
        if form.is_valid():
            d = form.cleaned_data
            if portale:
                nome, email = utente.get_full_name() or utente.username, utente.email
                cliente = utente.cliente
                azienda = cliente.ragione_sociale if cliente else ""
            else:
                nome, email, azienda = d["nome"], d["email"], d["azienda"]
                cliente = _riconosci_cliente(email)

            apparato = None
            matricola = d["matricola"].strip()
            if matricola and cliente:
                # la matricola viene collegata solo se appartiene al cliente riconosciuto
                apparato = Apparato.objects.filter(matricola__iexact=matricola, cliente=cliente).first()

            ticket = Ticket.objects.create(
                cliente=cliente, apparato=apparato, utente_portale=utente if portale else None,
                richiedente_nome=nome, richiedente_email=email, richiedente_telefono=d["telefono"],
                azienda_dichiarata=azienda, matricola_dichiarata=matricola,
                categoria=d["categoria"], priorita=d["priorita"], oggetto=d["oggetto"],
                descrizione=d["descrizione"], canale=Ticket.Canale.PORTALE,
            )
            if d.get("allegato"):
                MessaggioTicket.objects.create(ticket=ticket, da_cliente=True, autore=utente if portale else None,
                                               autore_nome=nome, testo="Allegato alla richiesta",
                                               allegato=d["allegato"])
            EventoTicket.objects.create(ticket=ticket, descrizione="Richiesta aperta dal portale")
            notifiche.ticket_creato(ticket)
            request.session["ultimo_ticket"] = str(ticket.token)
            return redirect("portale:ticket_creato", token=ticket.token)
    else:
        form = ApriTicketForm(utente=utente)
    return render(request, "portale/apri_ticket.html", {"form": form, "portale": portale})


def ticket_creato(request, token):
    if request.session.get("ultimo_ticket") != str(token):
        return redirect("portale:ticket_dettaglio", token=token)
    ticket = get_object_or_404(Ticket, token=token)
    return render(request, "portale/ticket_creato.html", {"ticket": ticket})


def ticket_dettaglio(request, token):
    ticket = get_object_or_404(Ticket.objects.select_related("cliente", "apparato"), token=token)
    form = RispostaForm()
    if request.method == "POST":
        azione = request.POST.get("azione")
        utente = request.user if request.user.is_authenticated else None
        if ticket.stato == Ticket.Stato.CHIUSO:
            messages.info(request, "Il ticket è chiuso: per un nuovo problema apri una nuova richiesta.")
            return redirect(ticket)
        if azione == "conferma_risoluzione" and ticket.stato == Ticket.Stato.RISOLTO:
            ticket.stato = Ticket.Stato.CHIUSO
            ticket.save()
            EventoTicket.objects.create(ticket=ticket, utente=utente, descrizione="Risoluzione confermata dal cliente")
            messages.success(request, "Grazie! Il ticket è stato chiuso.")
            return redirect(ticket)
        form = RispostaForm(request.POST, request.FILES)
        if form.is_valid():
            msg = MessaggioTicket.objects.create(
                ticket=ticket, da_cliente=True, autore=utente,
                autore_nome="" if utente else ticket.richiedente_nome,
                testo=form.cleaned_data["testo"], allegato=form.cleaned_data.get("allegato"),
            )
            if ticket.stato in (Ticket.Stato.ATTESA_CLIENTE, Ticket.Stato.RISOLTO):
                ticket.stato = Ticket.Stato.LAVORAZIONE
                ticket.save()
                EventoTicket.objects.create(ticket=ticket, utente=utente,
                                            descrizione="Il cliente ha risposto: ticket riaperto in lavorazione")
            notifiche.risposta_cliente(msg)
            messages.success(request, "Messaggio inviato.")
            return redirect(ticket)

    timeline = [("msg", m.creato_il, m) for m in ticket.messaggi.filter(interno=False).select_related("autore")]
    timeline += [("evento", e.quando, e) for e in ticket.eventi.filter(visibile_cliente=True)]
    timeline.sort(key=lambda x: x[1])
    return render(request, "portale/ticket_dettaglio.html", {"ticket": ticket, "timeline": timeline, "form": form})


@login_required
def miei_ticket(request):
    u = request.user
    if u.is_staff:
        return redirect("home")
    if u.cliente_id:
        qs = Ticket.objects.filter(cliente_id=u.cliente_id)
    else:
        qs = Ticket.objects.filter(Q(utente_portale=u) | Q(richiedente_email__iexact=u.email))
    filtro = request.GET.get("filtro", "aperti")
    if filtro == "aperti":
        qs = qs.filter(stato__in=Ticket.STATI_APERTI)
    elif filtro == "chiusi":
        qs = qs.exclude(stato__in=Ticket.STATI_APERTI)
    if not u.vede_ticket_azienda or request.GET.get("solo_miei"):
        qs = qs.filter(Q(utente_portale=u) | Q(richiedente_email__iexact=u.email))
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(codice__icontains=q) | Q(oggetto__icontains=q) | Q(matricola_dichiarata__icontains=q))
    apparati = Apparato.objects.filter(cliente_id=u.cliente_id) if u.cliente_id else Apparato.objects.none()
    from apps.preventivi.models import Preventivo

    preventivi = (Preventivo.objects.filter(cliente_id=u.cliente_id, stato__in=["inviato", "accettato", "rifiutato"])
                  if u.cliente_id and u.vede_ticket_azienda else Preventivo.objects.none())
    return render(request, "portale/miei_ticket.html", {
        "tickets": qs.select_related("apparato").order_by("-creato_il")[:200],
        "filtro": filtro, "q": q, "solo_miei": bool(request.GET.get("solo_miei")), "apparati": apparati,
        "preventivi": preventivi[:50],
    })


def cerca_ticket(request):
    """Ritrova un ticket da codice + email (per chi ha perso il link)."""
    if request.method == "POST":
        codice = request.POST.get("codice", "").strip().upper()
        email = request.POST.get("email", "").strip()
        t = Ticket.objects.filter(codice=codice, richiedente_email__iexact=email).first()
        if t:
            notifiche.link_ticket(t)
        # stessa risposta in ogni caso: non riveliamo se il ticket esiste
        messages.info(request, "Se codice ed email corrispondono, riceverai a breve il link via email.")
        return redirect("portale:cerca_ticket")
    return render(request, "portale/cerca_ticket.html")


def allegato(request, token, msg_id):
    """Scarica un allegato di un messaggio visibile al cliente, solo con il link segreto del ticket."""
    from django.http import FileResponse, Http404

    msg = get_object_or_404(MessaggioTicket, pk=msg_id, ticket__token=token, interno=False)
    if not msg.allegato:
        raise Http404
    return FileResponse(msg.allegato.open("rb"), as_attachment=True,
                        filename=msg.allegato.name.rsplit("/", 1)[-1])


def _preventivo_visibile(token):
    from apps.preventivi.models import Preventivo

    return get_object_or_404(Preventivo.objects.select_related("cliente", "contatto"), token=token,
                             stato__in=["inviato", "accettato", "rifiutato", "scaduto"])


def preventivo(request, token):
    """Il cliente consulta il preventivo e lo accetta o rifiuta, tramite link segreto."""
    p = _preventivo_visibile(token)
    utente = request.user if request.user.is_authenticated else None
    if request.method == "POST":
        if not p.accettabile:
            messages.info(request, "Questo preventivo non può più essere modificato.")
        elif request.POST.get("azione") == "accetta":
            nome = request.POST.get("nome", "").strip()
            if not nome or not request.POST.get("conferma"):
                messages.error(request, "Per accettare servono il nome e la conferma.")
            else:
                p.accetta(nome=nome[:120], riferimento=request.POST.get("riferimento", "").strip()[:80],
                          utente=utente)
                messages.success(request, "Preventivo accettato. Grazie!")
        elif request.POST.get("azione") == "rifiuta":
            p.rifiuta(request.POST.get("motivo", "").strip()[:2000])
            messages.info(request, "Abbiamo registrato la vostra risposta.")
        return redirect("portale:preventivo", token=token)
    nome = (utente.get_full_name() if utente and utente.is_cliente else "") or (str(p.contatto) if p.contatto else "")
    return render(request, "portale/preventivo.html", {"p": p, "nome_suggerito": nome})


def preventivo_stampa(request, token):
    p = _preventivo_visibile(token)
    return render(request, "campo/stampa_preventivo.html", {"obj": p, "titolo": "Preventivo", "pubblico": True})
