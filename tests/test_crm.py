from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.anagrafica.models import Cliente, Contatto
from apps.assistenza import sla
from apps.assistenza.models import Apparato, Contratto, LivelloSLA, MessaggioTicket, Rapportino, Ticket
from apps.commesse.models import Collaudo, Commessa, Sopralluogo
from apps.core import versioning
from apps.core.models import Utente

ROMA = ZoneInfo("Europe/Rome")


# ------------------------------------------------------------- versioning

def test_bump():
    assert versioning.bump("1.4.7", "patch") == "1.4.8"
    assert versioning.bump("1.4.7", "minor") == "1.5.0"
    assert versioning.bump("1.4.7", "major") == "2.0.0"


def test_changelog_parsing():
    rel = versioning.parse_changelog("# T\n\n## [1.1.0] - 2026-11-01\n### Aggiunto\n- uno\n- due\n\n## [1.0.0]\n- x\n")
    assert [r.version for r in rel] == ["1.1.0", "1.0.0"]
    assert rel[0].sections["Aggiunto"] == ["uno", "due"]
    assert rel[0].label == "V1.1.0"


def test_versione_nel_footer_e_changelog(client):
    r = client.get(reverse("changelog"))
    assert r.status_code == 200
    v = versioning.display_version()
    assert v in r.content.decode()
    assert versioning.get_changelog()[0].version == versioning.get_version(), "CHANGELOG non allineato a VERSION"


# ------------------------------------------------------------- SLA

def test_ore_lavorative_scavallano_weekend():
    venerdi_17 = datetime(2026, 10, 23, 17, 0, tzinfo=ROMA)
    fine = sla.add_ore(venerdi_17, 4, solo_lavorative=True)
    assert fine == datetime(2026, 10, 26, 11, 0, tzinfo=ROMA)  # lunedì 11:00


def test_ore_solari():
    t = datetime(2026, 10, 24, 22, 0, tzinfo=ROMA)
    assert sla.add_ore(t, 4) == t + timedelta(hours=4)


def test_stato_scadenza():
    ora = timezone.now()
    assert sla.stato_scadenza(ora - timedelta(minutes=1)) == "scaduto"
    assert sla.stato_scadenza(ora + timedelta(hours=1), inizio=ora - timedelta(hours=9)) == "attenzione"
    assert sla.stato_scadenza(ora + timedelta(hours=5), inizio=ora - timedelta(hours=1)) == "ok"


@pytest.fixture
def cliente(db):
    return Cliente.objects.create(ragione_sociale="ACME Spa", codice="ACME")


@pytest.fixture
def contratto(cliente):
    return Contratto.objects.create(numero="C-1", cliente=cliente, livello_sla=LivelloSLA.objects.get(nome="Premium 24/7"),
                                    data_inizio=date.today() - timedelta(days=10),
                                    data_fine=date.today() + timedelta(days=20))


def test_ticket_prende_sla_dal_contratto(contratto):
    t = Ticket.objects.create(cliente=contratto.cliente, richiedente_nome="a", richiedente_email="a@x.it",
                              oggetto="o", descrizione="d", priorita="critica")
    assert t.codice.startswith("TK-")
    assert t.contratto == contratto
    assert t.livello_sla.nome == "Premium 24/7"
    assert t.scadenza_risoluzione - t.creato_il < timedelta(hours=4, minutes=1)


def test_ticket_senza_contratto_usa_livello_predefinito(cliente):
    t = Ticket.objects.create(cliente=cliente, richiedente_nome="a", richiedente_email="a@x.it",
                              oggetto="o", descrizione="d")
    assert t.livello_sla.predefinito
    assert t.scadenza_presa_in_carico and t.scadenza_risoluzione is None


def test_contratto_in_scadenza(contratto):
    assert contratto.in_scadenza


# ------------------------------------------------------------- portale

def _dati(**kw):
    d = {"nome": "Mario Rossi", "email": "mario@acme.it", "telefono": "", "azienda": "ACME", "matricola": "",
         "categoria": "guasto", "priorita": "alta", "oggetto": "Vano bloccato",
         "descrizione": "Il vano 3 non si apre", "privacy": "on", "sito_web": ""}
    d.update(kw)
    return d


def test_ticket_anonimo_riconosce_cliente_da_contatto(client, cliente):
    Contatto.objects.create(cliente=cliente, nome="Mario", email="mario@acme.it")
    ap = Apparato.objects.create(cliente=cliente, modello="L-24", matricola="SN001")
    r = client.post(reverse("portale:apri_ticket"), _dati(matricola="sn001"))
    assert r.status_code == 302
    t = Ticket.objects.get()
    assert t.cliente == cliente and t.apparato == ap
    assert any("TK-" in m.subject for m in mail.outbox)


def test_matricola_di_altri_non_viene_collegata(client, cliente):
    Apparato.objects.create(cliente=cliente, modello="L-24", matricola="SN001")
    client.post(reverse("portale:apri_ticket"), _dati(email="estraneo@altro.it", matricola="SN001"))
    t = Ticket.objects.get()
    assert t.cliente is None and t.apparato is None and t.matricola_dichiarata == "SN001"


def test_honeypot_blocca_spam(client, db):
    client.post(reverse("portale:apri_ticket"), _dati(sito_web="http://spam"))
    assert not Ticket.objects.exists()


def test_storico_solo_della_propria_azienda(client, cliente):
    altro = Cliente.objects.create(ragione_sociale="Altra", codice="ALT")
    mio = Ticket.objects.create(cliente=cliente, richiedente_nome="a", richiedente_email="a@acme.it",
                                oggetto="MIO", descrizione="d")
    Ticket.objects.create(cliente=altro, richiedente_nome="b", richiedente_email="b@alt.it",
                          oggetto="ALTRUI", descrizione="d")
    u = Utente.objects.create_user("c@acme.it", "c@acme.it", "pw-123456!", ruolo="cliente", cliente=cliente)
    client.force_login(u)
    html = client.get(reverse("portale:miei_ticket") + "?filtro=tutti").content.decode()
    assert "MIO" in html and "ALTRUI" not in html
    assert mio.codice in html


def test_cliente_registrato_apre_ticket_a_suo_nome(client, cliente):
    u = Utente.objects.create_user("c@acme.it", "c@acme.it", "pw-123456!", ruolo="cliente", cliente=cliente,
                                   first_name="Carla")
    client.force_login(u)
    client.post(reverse("portale:apri_ticket"), _dati(nome="", email="", azienda="", privacy=""))
    t = Ticket.objects.get()
    assert t.cliente == cliente and t.utente_portale == u and t.richiedente_email == "c@acme.it"


def test_note_interne_invisibili_e_risposta_riapre(client, cliente):
    t = Ticket.objects.create(cliente=cliente, richiedente_nome="a", richiedente_email="a@acme.it",
                              oggetto="o", descrizione="d", stato="attesa_cliente")
    MessaggioTicket.objects.create(ticket=t, testo="SEGRETO interno", interno=True)
    MessaggioTicket.objects.create(ticket=t, testo="Provi a riavviare")
    html = client.get(t.get_absolute_url()).content.decode()
    assert "SEGRETO" not in html and "Provi a riavviare" in html
    client.post(t.get_absolute_url(), {"testo": "Fatto, non va"})
    t.refresh_from_db()
    assert t.stato == "in_lavorazione"


def test_conferma_risoluzione_chiude(client, cliente):
    t = Ticket.objects.create(cliente=cliente, richiedente_nome="a", richiedente_email="a@acme.it",
                              oggetto="o", descrizione="d", stato="risolto")
    client.post(t.get_absolute_url(), {"azione": "conferma_risoluzione"})
    t.refresh_from_db()
    assert t.stato == "chiuso" and t.chiuso_il


def test_clienti_non_entrano_nel_backoffice(client, cliente):
    u = Utente.objects.create_user("c@acme.it", "c@acme.it", "pw-123456!", ruolo="cliente", cliente=cliente)
    client.force_login(u)
    assert client.get(reverse("dashboard")).status_code == 302
    assert client.get("/media/firme/x.png").status_code == 302


def test_login_con_email(client, cliente):
    Utente.objects.create_user("mrossi", "mario@acme.it", "pw-123456!", ruolo="cliente", cliente=cliente)
    r = client.post(reverse("login"), {"username": "mario@acme.it", "password": "pw-123456!"})
    assert r.status_code == 302


# ------------------------------------------------------------- campo

@pytest.fixture
def staff(db):
    return Utente.objects.create_user("tec", "tec@gp.it", "pw-123456!", is_staff=True, is_superuser=True)


def test_sopralluogo_e_collaudo_copiano_checklist(cliente, staff):
    cm = Commessa.objects.create(cliente=cliente, titolo="Installazione locker")
    s = Sopralluogo.objects.create(commessa=cm, tecnico=staff)
    c = Collaudo.objects.create(commessa=cm, tecnico=staff)
    assert s.numero.startswith("SL-") and c.numero.startswith("CL-") and cm.codice.startswith("CM-")
    assert s.righe.count() > 5 and c.righe.count() > 5
    assert s.voci_mancanti().count() == s.righe.count()


def test_commessa_ereditata_ha_postvendita(cliente):
    cm = Commessa.objects.create(cliente=cliente, titolo="Ex fornitore", ereditata=True, fase_postvendita=False,
                                 fase_prevendita=False, fase_produzione=False)
    assert cm.fasi == ["Post-vendita"]


def test_rapportino_ore_e_firma(client, cliente, staff, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    r = Rapportino.objects.create(cliente=cliente, tecnico=staff, ora_inizio=time(9, 0), ora_fine=time(12, 30),
                                  pausa_minuti=30, lavoro_svolto="Sostituita scheda")
    assert r.ore_lavoro == 3.0 and r.numero.startswith("RI-")
    client.force_login(staff)
    png = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    resp = client.post(reverse("firma", args=["rapportino", r.pk]), {"firmatario": "Luigi Bianchi", "firma": png})
    assert resp.status_code == 302
    r.refresh_from_db()
    assert r.firmato and r.firmatario == "Luigi Bianchi"
    assert client.get(reverse("stampa", args=["rapportino", r.pk])).status_code == 200


def test_cruscotto_e_admin(client, staff, contratto):
    Ticket.objects.create(cliente=contratto.cliente, richiedente_nome="a", richiedente_email="a@x.it",
                          oggetto="Coda test", descrizione="d")
    client.force_login(staff)
    assert "Coda test" in client.get(reverse("dashboard")).content.decode()
    for nome in ["assistenza_ticket", "assistenza_rapportino", "assistenza_apparato", "assistenza_contratto",
                 "commesse_commessa", "commesse_sopralluogo", "commesse_collaudo", "anagrafica_cliente",
                 "core_utente"]:
        assert client.get(reverse(f"admin:{nome}_changelist")).status_code == 200, nome
        assert client.get(reverse(f"admin:{nome}_add")).status_code == 200, nome
