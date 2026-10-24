from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.anagrafica.models import Cliente, Contatto
from apps.assistenza.models import Apparato, Rapportino, RigaRicambio
from apps.commesse.models import Commessa
from apps.core.models import Utente
from apps.magazzino.models import (Articolo, DistintaBase, Movimento, OrdineProduzione, RicambioRiparazione,
                                   RigaDistinta, Riparazione)
from apps.preventivi.models import Preventivo, RigaPreventivo


@pytest.fixture
def cliente(db):
    c = Cliente.objects.create(ragione_sociale="ACME", codice="ACME", email="info@acme.it")
    Contatto.objects.create(cliente=c, nome="Ada", email="ada@acme.it")
    return c


@pytest.fixture
def articoli(db):
    A = Articolo.objects.create
    return {
        "loc": A(codice="LOC", descrizione="Locker", tipo="prodotto", a_matricola=True, prezzo=1000),
        "sch": A(codice="SCH", descrizione="Scheda", tipo="componente", costo=100, prezzo=200, scorta_minima=2),
        "ser": A(codice="SER", descrizione="Serratura", tipo="ricambio", costo=10, prezzo=25),
        "man": A(codice="MAN", descrizione="Manodopera", tipo="servizio", unita="h", prezzo=50),
    }


def carica(art, q):
    Movimento.objects.create(articolo=art, causale="carico_acquisto", quantita=q)


def test_segno_dei_movimenti_e_giacenze(articoli):
    carica(articoli["ser"], 10)
    Movimento.objects.create(articolo=articoli["ser"], causale="scarico_vendita", quantita=3)
    Movimento.objects.create(articolo=articoli["ser"], causale="rettifica", quantita=-1)
    assert articoli["ser"].giacenza() == 6
    a = Articolo.objects.con_giacenze().get(pk=articoli["ser"].pk)
    assert a.giacenza_nuovo == 6 and a.impegnato == 0


def test_servizi_non_movimentano(articoli):
    m = Movimento(articolo=articoli["man"], causale="carico_acquisto", quantita=1)
    with pytest.raises(ValidationError):
        m.full_clean()


def test_distinta_impegna_e_produzione_scarica(cliente, articoli):
    carica(articoli["sch"], 3)
    carica(articoli["ser"], 30)
    db = DistintaBase.objects.create(prodotto=articoli["loc"])
    RigaDistinta.objects.create(distinta=db, componente=articoli["sch"], quantita=1)
    RigaDistinta.objects.create(distinta=db, componente=articoli["ser"], quantita=12)
    cm = Commessa.objects.create(cliente=cliente, titolo="Fornitura")
    op = OrdineProduzione.objects.create(commessa=cm, distinta=db, quantita=2,
                                         matricole_prodotte="LOC-001\nLOC-002")
    assert articoli["ser"].disponibile() == 30  # bozza: niente impegno
    op.conferma()
    assert articoli["ser"].disponibile() == 6 and articoli["sch"].disponibile() == 1
    assert op.mancanti() == []
    # un secondo ordine non trova abbastanza schede
    op2 = OrdineProduzione.objects.create(distinta=db, quantita=2)
    op2.conferma()
    assert [a.codice for a, _ in op2.mancanti()] == ["SCH", "SER"]
    op2.annulla()
    assert articoli["sch"].disponibile() == 1
    op.completa()
    assert articoli["ser"].giacenza() == 6 and articoli["ser"].disponibile() == 6
    assert articoli["sch"].giacenza() == 1
    assert articoli["loc"].giacenza() == 2
    assert set(Apparato.objects.filter(commessa=cm).values_list("matricola", flat=True)) == {"LOC-001", "LOC-002"}
    with pytest.raises(ValidationError):
        op.annulla()


def test_riparazione_entra_ed_esce_dall_area_riparazioni(cliente, articoli):
    carica(articoli["ser"], 5)
    rp = Riparazione.objects.create(cliente=cliente, articolo=articoli["sch"], descrizione_pezzo="Scheda",
                                    matricola="SN9", difetto_dichiarato="Non parte")
    assert rp.numero.startswith("RP-")
    assert articoli["sch"].giacenza("riparazioni") == 1 and articoli["sch"].giacenza() == 0
    r = RicambioRiparazione.objects.create(riparazione=rp, articolo=articoli["ser"], quantita=2)
    assert articoli["ser"].giacenza() == 3
    r.quantita = 1
    r.save()
    assert articoli["ser"].giacenza() == 4
    rp.stato = "riconsegnato"
    rp.save()
    assert articoli["sch"].giacenza("riparazioni") == 0 and rp.data_riconsegna
    rp.save()  # nessun doppio movimento
    assert articoli["sch"].movimenti.count() == 2


def test_ricambio_rapportino_scarica(cliente, articoli):
    carica(articoli["ser"], 4)
    from datetime import time

    r = Rapportino.objects.create(cliente=cliente, ora_inizio=time(9), ora_fine=time(10), lavoro_svolto="x")
    riga = RigaRicambio.objects.create(rapportino=r, articolo=articoli["ser"], quantita=2)
    assert riga.descrizione == "Serratura" and articoli["ser"].giacenza() == 2
    riga.delete()
    assert articoli["ser"].giacenza() == 4


def _preventivo(cliente, articoli, **kw):
    p = Preventivo.objects.create(cliente=cliente, oggetto="Due locker", contatto=cliente.contatti.first(), **kw)
    RigaPreventivo.objects.create(preventivo=p, articolo=articoli["loc"], quantita=2, sconto=10)
    RigaPreventivo.objects.create(preventivo=p, articolo=articoli["man"], quantita=3)
    return p


def test_importi_preventivo(cliente, articoli):
    p = _preventivo(cliente, articoli, sconto_globale=5)
    assert p.righe.get(articolo=articoli["man"]).prezzo_unitario == 50
    assert p.imponibile_righe == Decimal("1950.00")
    assert p.imponibile == Decimal("1852.50")
    assert p.iva == Decimal("407.55") and p.totale == Decimal("2260.05")
    assert p.numero.startswith("PV-")


def test_accettazione_dal_portale_crea_commessa(client, cliente, articoli, mailoutbox):
    p = _preventivo(cliente, articoli)
    assert client.get(reverse("portale:preventivo", args=[p.token])).status_code == 404  # bozza: invisibile
    p.invia()
    assert mailoutbox[-1].to == ["ada@acme.it"] and "€ 2.379,00" in mailoutbox[-1].body
    html = client.get(p.get_absolute_url()).content.decode()
    assert "Accetta il preventivo" in html
    client.post(p.get_absolute_url(), {"azione": "accetta", "nome": "Ada Rossi", "riferimento": "ODA 77"})
    p.refresh_from_db()
    assert p.stato == "inviato"  # manca la conferma
    client.post(p.get_absolute_url(), {"azione": "accetta", "nome": "Ada Rossi", "riferimento": "ODA 77",
                                       "conferma": "on"})
    p.refresh_from_db()
    assert p.stato == "accettato" and p.accettato_da == "Ada Rossi" and p.riferimento_ordine == "ODA 77"
    assert p.commessa and p.commessa.stato == "produzione" and p.commessa.valore == p.imponibile
    client.post(p.get_absolute_url(), {"azione": "rifiuta"})
    p.refresh_from_db()
    assert p.stato == "accettato"  # non si torna indietro
    assert client.get(reverse("portale:preventivo_stampa", args=[p.token])).status_code == 200


def test_preventivo_scaduto_non_accettabile(client, cliente, articoli):
    p = _preventivo(cliente, articoli, data=timezone.localdate() - timedelta(days=40))
    p.invia()
    client.post(p.get_absolute_url(), {"azione": "accetta", "nome": "X", "conferma": "on"})
    p.refresh_from_db()
    assert p.stato == "inviato" and p.scaduto


def test_rifiuto_riparazione_e_revisione(cliente, articoli):
    rp = Riparazione.objects.create(cliente=cliente, descrizione_pezzo="Scheda", matricola="S1",
                                    difetto_dichiarato="x", stato="attesa_ok")
    p = _preventivo(cliente, articoli, tipo="riparazione", riparazione=rp)
    p.invia()
    vecchio = p.token
    p.rifiuta("Troppo caro")
    rp.refresh_from_db()
    assert rp.stato == "non_riparabile"
    p.nuova_revisione()
    assert p.stato == "bozza" and p.revisione == 1 and p.token != vecchio and p.codice.endswith("rev.1")


def test_admin_crea_preventivo_da_riparazione(client, cliente, articoli):
    admin = Utente.objects.create_user("capo", "capo@gp.it", "pw-123456!", ruolo="admin")
    rp = Riparazione.objects.create(cliente=cliente, descrizione_pezzo="Scheda", matricola="S1",
                                    difetto_dichiarato="x", ore_lavoro=2)
    carica(articoli["ser"], 5)
    RicambioRiparazione.objects.create(riparazione=rp, articolo=articoli["ser"], quantita=2)
    client.force_login(admin)
    url = reverse("admin:magazzino_riparazione_change", args=[rp.pk])
    form = client.get(url).context["adminform"].form
    data = {k: v for k, v in form.initial.items() if v is not None}
    data.update({"cliente": cliente.pk, "data_ricezione": rp.data_ricezione.isoformat(), "stato": "diagnosi",
                 "ricambi-TOTAL_FORMS": "1", "ricambi-INITIAL_FORMS": "1", "ricambi-MIN_NUM_FORMS": "0",
                 "ricambi-MAX_NUM_FORMS": "1000", "ricambi-0-id": rp.ricambi.first().pk,
                 "ricambi-0-riparazione": rp.pk, "ricambi-0-articolo": articoli["ser"].pk,
                 "ricambi-0-quantita": "2", "_azione_preventivo": "1"})
    r = client.post(url, data)
    assert r.status_code == 302, r.content.decode()[:3000]
    p = Preventivo.objects.get(riparazione=rp)
    assert p.tipo == "riparazione" and p.righe.count() == 2
    rp.refresh_from_db()
    assert rp.stato == "attesa_ok"


def test_tecnico_su_magazzino(client, articoli):
    t = Utente.objects.create_user("t", "t@gp.it", "pw-123456!", ruolo="tecnico")
    assert t.has_perm("magazzino.add_movimento") and t.has_perm("preventivi.add_preventivo")
    assert not t.has_perm("magazzino.change_distintabase") and not t.has_perm("preventivi.delete_preventivo")
    client.force_login(t)
    for nome in ["magazzino_articolo", "magazzino_movimento", "magazzino_ordineproduzione",
                 "magazzino_riparazione", "preventivi_preventivo"]:
        assert client.get(reverse(f"admin:{nome}_changelist")).status_code == 200, nome
    assert client.get(reverse("admin:magazzino_distintabase_add")).status_code == 403


def test_pagine_admin_e_cruscotto_admin(client, cliente, articoli):
    su = Utente.objects.create_superuser("root", "r@x.it", "pw-123456!")
    p = _preventivo(cliente, articoli)
    client.force_login(su)
    for nome in ["magazzino_articolo", "magazzino_movimento", "magazzino_distintabase",
                 "magazzino_ordineproduzione", "magazzino_riparazione", "preventivi_preventivo"]:
        assert client.get(reverse(f"admin:{nome}_changelist")).status_code == 200, nome
        assert client.get(reverse(f"admin:{nome}_add")).status_code == 200, nome
    assert client.get(reverse("admin:magazzino_articolo_changelist") + "?scorta=sotto").status_code == 200
    assert client.get(reverse("admin:preventivi_preventivo_change", args=[p.pk])).status_code == 200
    assert client.get(reverse("stampa", args=["preventivo", p.pk])).status_code == 200
    assert client.get(reverse("dashboard")).status_code == 200
