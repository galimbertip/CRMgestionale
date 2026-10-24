"""Modelli di checklist predefiniti per sopralluogo e collaudo (modificabili dall'admin)."""
from django.db import migrations

SOPRALLUOGO = [
    ("Accesso", "Percorso di consegna e movimentazione (porte, scale, ascensori, rampe)"),
    ("Accesso", "Orari e vincoli di accesso al sito per l'installazione"),
    ("Spazio", "Misure area disponibile (L × P × H)"),
    ("Spazio", "Pavimentazione piana e portante"),
    ("Spazio", "Distanza da vie di fuga, ostacoli e passaggi"),
    ("Elettrico", "Linea 230 V disponibile e distanza dal punto di installazione"),
    ("Elettrico", "Linea dedicata con protezioni (magnetotermico/differenziale)"),
    ("Rete", "Copertura rete mobile (operatore e livello segnale)"),
    ("Rete", "Rete cablata o Wi-Fi disponibile e porte/firewall richiesti"),
    ("Ambiente", "Installazione interna/esterna, esposizione a sole e pioggia"),
    ("Ambiente", "Temperatura e umidità dell'ambiente"),
    ("Fissaggio", "Possibilità di ancoraggio a muro e/o pavimento"),
    ("Sicurezza", "Illuminazione e videosorveglianza dell'area"),
]

COLLAUDO = [
    ("Meccanica", "Apparato livellato e ancorato"),
    ("Meccanica", "Integrità estetica, nessun danno da trasporto"),
    ("Elettrico", "Alimentazione collegata e protezioni verificate"),
    ("Elettrico", "Messa a terra verificata"),
    ("Rete", "Connessione dati attiva e stabile"),
    ("Rete", "Apparato raggiungibile da remoto (VPN / monitoraggio)"),
    ("Funzionale", "Avvio sistema e versione software corretta"),
    ("Funzionale", "Test apertura/chiusura di tutti i vani e attuatori"),
    ("Funzionale", "Test display, lettori e periferiche"),
    ("Funzionale", "Test di un'operazione completa end-to-end"),
    ("Consegna", "Formazione del referente cliente"),
    ("Consegna", "Consegna documentazione e contatti assistenza"),
    ("Consegna", "Etichetta matricola e QR assistenza applicati"),
]


def crea(apps, schema_editor):
    Modello = apps.get_model("commesse", "ModelloChecklist")
    Voce = apps.get_model("commesse", "VoceModello")
    for nome, tipo, voci in [
        ("Sopralluogo standard", "sopralluogo", SOPRALLUOGO),
        ("Collaudo standard", "collaudo", COLLAUDO),
    ]:
        m = Modello.objects.create(nome=nome, tipo=tipo, attivo=True, predefinito=True)
        Voce.objects.bulk_create(
            [Voce(modello=m, ordine=(i + 1) * 10, gruppo=g, testo=t) for i, (g, t) in enumerate(voci)]
        )


class Migration(migrations.Migration):
    dependencies = [("commesse", "0002_initial")]
    operations = [migrations.RunPython(crea, migrations.RunPython.noop)]
