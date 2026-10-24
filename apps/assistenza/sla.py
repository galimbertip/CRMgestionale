"""Calcolo delle scadenze SLA, in ore solari o in orario lavorativo."""
from datetime import datetime, time, timedelta

from django.utils import timezone


def add_ore(inizio, ore, solo_lavorative=False, ora_inizio=8, ora_fine=18, giorni=(0, 1, 2, 3, 4)):
    """Restituisce inizio + `ore`. Se solo_lavorative, conta solo le ore nei giorni/orari indicati."""
    if ore is None:
        return None
    if not solo_lavorative:
        return inizio + timedelta(hours=ore)

    tz = timezone.get_current_timezone()
    t = timezone.localtime(inizio, tz)
    restanti = timedelta(hours=ore)
    for _ in range(3660):  # limite di sicurezza (~10 anni di giorni)
        giorno_inizio = datetime.combine(t.date(), time(ora_inizio), tzinfo=tz)
        giorno_fine = datetime.combine(t.date(), time(ora_fine), tzinfo=tz)
        if t.weekday() in giorni and t < giorno_fine:
            t = max(t, giorno_inizio)
            disponibile = giorno_fine - t
            if restanti <= disponibile:
                return t + restanti
            restanti -= disponibile
        t = datetime.combine(t.date() + timedelta(days=1), time(ora_inizio), tzinfo=tz)
    raise ValueError("Calendario SLA senza giorni lavorativi")


def stato_scadenza(scadenza, completato_il=None, inizio=None, adesso=None):
    """'ok' | 'attenzione' (ultimo 25% del tempo) | 'scaduto' | 'rispettato' | 'violato' | None."""
    if not scadenza:
        return None
    if completato_il:
        return "rispettato" if completato_il <= scadenza else "violato"
    adesso = adesso or timezone.now()
    if adesso > scadenza:
        return "scaduto"
    if inizio and (scadenza - adesso) <= (scadenza - inizio) * 0.25:
        return "attenzione"
    return "ok"
