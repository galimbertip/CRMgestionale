"""Popola il database con dati di esempio per provare il CRM (da NON usare in produzione)."""
from datetime import date, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.test import override_settings

from apps.anagrafica.models import Cliente, Contatto, Sede
from apps.assistenza.models import Apparato, Contratto, LivelloSLA, MessaggioTicket, Rapportino, Ticket
from apps.commesse.models import Collaudo, Commessa, Sopralluogo
from apps.core.models import Utente
from apps.magazzino.models import (Articolo, DistintaBase, Movimento, OrdineProduzione, RicambioRiparazione,
                                   RigaDistinta, Riparazione)
from apps.preventivi.models import Preventivo, RigaPreventivo


class Command(BaseCommand):
    help = "Crea dati demo con un utente per livello: admin, tecnico, cliente"

    @transaction.atomic
    def handle(self, **opts):
        if Cliente.objects.filter(codice="DEMO1").exists():
            self.stdout.write("Dati demo già presenti.")
            return
        oggi = date.today()
        admin = Utente.objects.create_user("admin", "admin@example.com", "demo-admin-2026",
                                           first_name="Paolo", ruolo="admin")
        tec = Utente.objects.create_user("tecnico", "tecnico@example.com", "demo-tecnico-2026",
                                         first_name="Luca", last_name="Verdi", ruolo="tecnico")

        c1 = Cliente.objects.create(ragione_sociale="Logistica Rapida Srl", codice="DEMO1", citta="Milano",
                                    email="info@logisticarapida.example")
        c2 = Cliente.objects.create(ragione_sociale="Condominio Le Querce", codice="DEMO2", citta="Monza")
        s1 = Sede.objects.create(cliente=c1, nome="Hub Nord", indirizzo="Via dei Trasporti 12", citta="Milano",
                                 orari_accesso="Lun-Ven 7-19")
        s2 = Sede.objects.create(cliente=c2, nome="Androne scala B", indirizzo="Via delle Querce 4", citta="Monza")
        Contatto.objects.create(cliente=c1, nome="Giulia", cognome="Neri", email="giulia@logisticarapida.example",
                                ruolo="Facility manager", principale=True)
        Utente.objects.create_user("giulia@logisticarapida.example", "giulia@logisticarapida.example",
                                   "demo-cliente-2026", first_name="Giulia", last_name="Neri", ruolo="cliente",
                                   cliente=c1)

        cm1 = Commessa.objects.create(cliente=c1, titolo="Fornitura 3 locker 24 vani", stato="postvendita",
                                      responsabile=admin, valore=42000)
        cm2 = Commessa.objects.create(cliente=c2, titolo="Locker condominiale (ex altro fornitore)",
                                      stato="postvendita", ereditata=True, origine="Fornitore precedente",
                                      fase_prevendita=False, fase_produzione=False,
                                      data_presa_in_carico=oggi - timedelta(days=60))
        cm3 = Commessa.objects.create(cliente=c1, titolo="Ampliamento Hub Sud", stato="prevendita")

        std = LivelloSLA.objects.get(nome="Standard")
        k1 = Contratto.objects.create(numero="CA-2026-001", cliente=c1, commessa=cm1, livello_sla=std,
                                      tipo="full", data_inizio=oggi - timedelta(days=300),
                                      data_fine=oggi + timedelta(days=45), canone_annuo=3600, ore_incluse=40)
        Contratto.objects.create(numero="CA-2026-002", cliente=c2, commessa=cm2,
                                 livello_sla=LivelloSLA.objects.get(nome="Base"), tipo="manutenzione",
                                 data_inizio=oggi - timedelta(days=60), data_fine=oggi + timedelta(days=305))

        apparati = [Apparato.objects.create(cliente=c1, sede=s1, commessa=cm1, contratto=k1, modello="Locker L-24",
                                            matricola=f"GPL24-00{i}", versione_firmware="2.3.1",
                                            identificativo_remoto=f"locker-hubnord-{i}",
                                            data_installazione=oggi - timedelta(days=290),
                                            fine_garanzia=oggi + timedelta(days=440)) for i in (1, 2, 3)]
        Apparato.objects.create(cliente=c2, sede=s2, commessa=cm2, modello="Locker condominiale 12",
                                matricola="XQ12-7781", stato="guasto")

        Sopralluogo.objects.create(commessa=cm3, sede=s1, tecnico=tec, esito="con_opere",
                                   opere_preliminari="Portare linea 230 V dedicata a 15 m dal quadro.")
        col = Collaudo.objects.create(commessa=cm1, sede=s1, tecnico=tec, esito="superato",
                                      data=oggi - timedelta(days=290))
        col.apparati.set(apparati)
        col.righe.update(esito="ok")

        t1 = Ticket.objects.create(cliente=c1, apparato=apparati[1], richiedente_nome="Giulia Neri",
                                   richiedente_email="giulia@logisticarapida.example", oggetto="Vano 7 non si apre",
                                   descrizione="Dal mattino il vano 7 resta chiuso, il display mostra errore E12.",
                                   priorita="alta", stato="in_lavorazione", assegnato_a=tec)
        MessaggioTicket.objects.create(ticket=t1, autore=tec, testo="Ricevuto, controlliamo da remoto la scheda serrature.")
        MessaggioTicket.objects.create(ticket=t1, autore=tec, interno=True, testo="Log: timeout bus RS485 su modulo 2.")
        Ticket.objects.create(cliente=c2, richiedente_nome="Amministratore", richiedente_email="amm@querce.example",
                              oggetto="Locker spento", descrizione="Il locker è completamente spento.",
                              priorita="critica")
        Ticket.objects.create(richiedente_nome="Sig. Bianchi", richiedente_email="bianchi@sconosciuto.example",
                              azienda_dichiarata="Bianchi Trasporti", matricola_dichiarata="ZZ-999",
                              oggetto="Informazioni su nuova installazione", descrizione="Vorrei un preventivo.",
                              categoria="commerciale", priorita="bassa")
        Rapportino.objects.create(cliente=c1, sede=s1, ticket=t1, tecnico=tec, data=oggi - timedelta(days=3),
                                  ora_inizio=time(9), ora_fine=time(11, 30), km=38, ore_viaggio=1,
                                  problema="Errore E12 su vano 7", lavoro_svolto="Sostituito cablaggio RS485 modulo 2.",
                                  esito="parziale")
        self._magazzino(oggi, admin, tec, c1, c2, cm1, cm3, apparati, t1)
        self.stdout.write(self.style.SUCCESS(
            "Demo pronta. Back-office: admin / demo-admin-2026 · tecnico / demo-tecnico-2026 · "
            "Portale: giulia@logisticarapida.example / demo-cliente-2026"))

    def _magazzino(self, oggi, admin, tec, c1, c2, cm1, cm3, apparati, t1):
        A = Articolo.objects.create
        locker = A(codice="LCK-L24", descrizione="Locker L-24 (24 vani)", tipo="prodotto", a_matricola=True,
                   costo=5200, prezzo=11800)
        comp = {
            "CTRL": A(codice="CMP-CTRL", descrizione="Scheda controller (Raspberry Pi + I/O)", tipo="componente",
                      a_matricola=True, costo=180, prezzo=390, scorta_minima=4, ubicazione="A1"),
            "SERR": A(codice="CMP-SERR", descrizione="Serratura elettrica 12V", tipo="ricambio", costo=14,
                      prezzo=38, scorta_minima=50, ubicazione="A2"),
            "RS485": A(codice="CMP-RS485", descrizione="Modulo serrature RS485 (12 canali)", tipo="ricambio",
                       a_matricola=True, costo=65, prezzo=150, scorta_minima=4, ubicazione="A3"),
            "LTE": A(codice="CMP-LTE", descrizione="Modem LTE industriale", tipo="componente", costo=95,
                     prezzo=210, scorta_minima=3, ubicazione="B1"),
            "DISP": A(codice="CMP-DISP", descrizione="Display touch 10\"", tipo="componente", costo=140,
                      prezzo=290, scorta_minima=2, ubicazione="B2"),
            "PSU": A(codice="CMP-PSU", descrizione="Alimentatore 12V 10A", tipo="ricambio", costo=32, prezzo=75,
                     scorta_minima=5, ubicazione="B3"),
            "STR": A(codice="CMP-STR24", descrizione="Struttura metallica 24 vani", tipo="componente", costo=2100,
                     prezzo=0, ubicazione="Piazzale"),
            "CAV": A(codice="CON-CAVO", descrizione="Cavo multipolare 4x0.5", tipo="consumabile", unita="m",
                     costo=1.2, prezzo=3, scorta_minima=100),
        }
        mano = A(codice="SRV-MANO", descrizione="Manodopera tecnico specializzato", tipo="servizio", unita="h",
                 prezzo=48)
        A(codice="SRV-KM", descrizione="Rimborso chilometrico", tipo="servizio", unita="km", prezzo=0.6)
        giacenze = {"CTRL": 3, "SERR": 120, "RS485": 2, "LTE": 2, "DISP": 4, "PSU": 8, "STR": 1, "CAV": 400}
        for k, q in giacenze.items():
            Movimento.objects.create(articolo=comp[k], causale="carico_acquisto", quantita=q, utente=admin,
                                     documento="DDT fornitore 118/2026")

        db = DistintaBase.objects.create(prodotto=locker, versione="2")
        for k, q in [("STR", 1), ("CTRL", 1), ("RS485", 2), ("SERR", 24), ("LTE", 1), ("DISP", 1), ("PSU", 1),
                     ("CAV", 30)]:
            RigaDistinta.objects.create(distinta=db, componente=comp[k], quantita=q)

        p1 = Preventivo.objects.create(cliente=c1, commessa=cm3, tipo="installazione", autore=admin,
                                       oggetto="Fornitura e installazione 2 locker L-24 – Hub Sud",
                                       tempi_consegna="6 settimane dall'ordine", garanzia="24 mesi on-site",
                                       contatto=c1.contatti.first())
        RigaPreventivo.objects.create(preventivo=p1, ordine=1, articolo=locker, quantita=2, sconto=5)
        RigaPreventivo.objects.create(preventivo=p1, ordine=2, articolo=mano, quantita=16,
                                      descrizione="Installazione, configurazione e collaudo")
        RigaPreventivo.objects.create(preventivo=p1, ordine=3, descrizione="Trasporto e scarico", quantita=1,
                                      prezzo_unitario=350)
        with override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            p1.invia()

        op = OrdineProduzione.objects.create(commessa=cm1, distinta=db, quantita=2, data_prevista=oggi,
                                             note="Due locker aggiuntivi per Hub Nord")
        op.conferma()  # impegna: le schede controller e i moduli RS485 non bastano -> "mancano"

        rp = Riparazione.objects.create(cliente=c1, ticket=t1, apparato=apparati[1], articolo=comp["RS485"],
                                        descrizione_pezzo="Modulo serrature RS485", matricola="RS-22-0417",
                                        difetto_dichiarato="Canale 7 non comanda la serratura", tecnico=tec,
                                        stato="diagnosi", diagnosi="Relè canale 7 bruciato, pista danneggiata.",
                                        ore_lavoro=1.5, ddt_ingresso="DDT cliente 55")
        RicambioRiparazione.objects.create(riparazione=rp, articolo=comp["SERR"], quantita=1)
