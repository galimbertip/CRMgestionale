"""Cosa succede a valle quando il cliente accetta o rifiuta un preventivo."""
from django.utils import timezone


def su_accettazione(p, utente=None):
    from apps.assistenza.models import EventoTicket
    from apps.commesse.models import Commessa
    from apps.magazzino.models import Riparazione

    if p.tipo == p.Tipo.INSTALLAZIONE:
        if p.commessa_id:
            if p.commessa.stato == Commessa.Stato.PREVENDITA:
                p.commessa.stato = Commessa.Stato.PRODUZIONE
                p.commessa.valore = p.imponibile
                p.commessa.save(update_fields=["stato", "valore"])
        else:
            p.commessa = Commessa.objects.create(
                cliente=p.cliente, titolo=p.oggetto, stato=Commessa.Stato.PRODUZIONE, valore=p.imponibile,
                descrizione=f"Nata dall'accettazione del preventivo {p.codice}",
                fase_prevendita=True, fase_produzione=True, fase_postvendita=True,
            )
            p.save(update_fields=["commessa"])

    if p.riparazione_id and p.riparazione.stato in (Riparazione.Stato.ATTESA_OK, Riparazione.Stato.DIAGNOSI,
                                                     Riparazione.Stato.RICEVUTO):
        p.riparazione.stato = Riparazione.Stato.IN_RIPARAZIONE
        p.riparazione.save()

    if p.ticket_id:
        EventoTicket.objects.create(ticket=p.ticket, descrizione=f"Preventivo {p.codice} accettato da {p.accettato_da}")


def su_rifiuto(p):
    from apps.assistenza.models import EventoTicket
    from apps.magazzino.models import Riparazione

    if p.riparazione_id and p.riparazione.stato == Riparazione.Stato.ATTESA_OK:
        p.riparazione.stato = Riparazione.Stato.NON_RIPARABILE
        p.riparazione.diagnosi += f"\n[{timezone.localdate():%d/%m/%Y}] Preventivo {p.codice} rifiutato dal cliente."
        p.riparazione.save()
    if p.ticket_id:
        EventoTicket.objects.create(ticket=p.ticket, descrizione=f"Preventivo {p.codice} rifiutato")
