"""Email verso clienti e assistenza. Gli errori di invio non bloccano mai il flusso."""
import logging

from django.conf import settings
from django.core.mail import send_mail

log = logging.getLogger(__name__)


def _invia(oggetto, testo, destinatari):
    destinatari = [d for d in destinatari if d]
    if not destinatari:
        return
    try:
        send_mail(oggetto, testo, None, destinatari, fail_silently=False)
    except Exception:  # noqa: BLE001
        log.exception("Invio email non riuscito: %s", oggetto)


def _firma():
    return f"\n\n—\n{settings.GPVERSE_PRODUCT} · Assistenza tecnica"


def ticket_creato(ticket):
    _invia(
        f"[{ticket.codice}] Richiesta ricevuta: {ticket.oggetto}",
        f"Gentile {ticket.richiedente_nome},\n\n"
        f"abbiamo ricevuto la sua richiesta di assistenza, registrata con il codice {ticket.codice}.\n"
        f"Può seguirne lo stato e rispondere qui:\n{ticket.url_pubblico()}\n"
        f"Conservi questo link: dà accesso al ticket senza bisogno di credenziali." + _firma(),
        [ticket.richiedente_email],
    )
    _invia(
        f"[{ticket.codice}] Nuovo ticket {ticket.get_priorita_display()}: {ticket.oggetto}",
        f"Cliente: {ticket.cliente or ticket.azienda_dichiarata or 'da riconoscere'}\n"
        f"Richiedente: {ticket.richiedente_nome} <{ticket.richiedente_email}> {ticket.richiedente_telefono}\n"
        f"Matricola: {ticket.apparato or ticket.matricola_dichiarata or '-'}\n"
        f"Scadenza presa in carico: {ticket.scadenza_presa_in_carico or '-'}\n\n{ticket.descrizione}",
        [settings.GPVERSE_SUPPORT_EMAIL],
    )


def risposta_assistenza(messaggio):
    t = messaggio.ticket
    _invia(
        f"[{t.codice}] Aggiornamento sulla sua richiesta",
        f"Gentile {t.richiedente_nome},\n\nc'è un nuovo messaggio dall'assistenza:\n\n{messaggio.testo}\n\n"
        f"Per rispondere: {t.url_pubblico()}" + _firma(),
        [t.richiedente_email],
    )


def risposta_cliente(messaggio):
    t = messaggio.ticket
    dest = t.assegnato_a.email if t.assegnato_a and t.assegnato_a.email else settings.GPVERSE_SUPPORT_EMAIL
    _invia(f"[{t.codice}] Risposta del cliente", f"{messaggio.nome_visualizzato} ha scritto:\n\n{messaggio.testo}",
           [dest])


def cambio_stato(ticket):
    _invia(
        f"[{ticket.codice}] Stato: {ticket.get_stato_display()}",
        f"Gentile {ticket.richiedente_nome},\n\nla sua richiesta «{ticket.oggetto}» è ora in stato: "
        f"{ticket.get_stato_display()}.\n\nDettagli: {ticket.url_pubblico()}" + _firma(),
        [ticket.richiedente_email],
    )


def link_ticket(ticket):
    _invia(
        f"[{ticket.codice}] Link alla sua richiesta",
        f"Ecco il link per consultare la richiesta {ticket.codice}:\n{ticket.url_pubblico()}" + _firma(),
        [ticket.richiedente_email],
    )
