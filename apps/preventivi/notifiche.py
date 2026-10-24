from django.conf import settings

from apps.assistenza.notifiche import _firma, _invia


def euro(v):
    return "€ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def preventivo_inviato(p):
    _invia(
        f"Preventivo {p.codice}: {p.oggetto}",
        f"Gentile cliente,\n\nle inviamo il preventivo {p.codice} «{p.oggetto}», "
        f"totale {euro(p.totale)} IVA inclusa, valido fino al {p.scadenza:%d/%m/%Y}.\n\n"
        f"Può consultarlo, stamparlo e accettarlo o rifiutarlo online qui:\n{p.url_pubblico()}" + _firma(),
        [p.email_destinatario],
    )


def risposta_cliente(p):
    esito = "ACCETTATO" if p.stato == p.Stato.ACCETTATO else "RIFIUTATO"
    dettagli = (f"Accettato da: {p.accettato_da}\nRiferimento ordine: {p.riferimento_ordine or '-'}"
                if esito == "ACCETTATO" else f"Motivo: {p.motivo_rifiuto or '-'}")
    dest = [settings.GPVERSE_SUPPORT_EMAIL, p.autore.email if p.autore else ""]
    _invia(f"[{p.codice}] Preventivo {esito} – {p.cliente}", f"{p.oggetto}\n\n{dettagli}", dest)
