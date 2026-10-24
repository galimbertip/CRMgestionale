"""Popola il database con dati di esempio per provare il CRM (da NON usare in produzione)."""
from datetime import date, time, timedelta

from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.anagrafica.models import Cliente, Contatto, Sede
from apps.assistenza.models import Apparato, Contratto, LivelloSLA, MessaggioTicket, Rapportino, Ticket
from apps.commesse.models import Collaudo, Commessa, Sopralluogo
from apps.core.models import Utente


class Command(BaseCommand):
    help = "Crea dati demo: clienti, commesse, apparati, contratti, ticket e utenti (admin/demo, cliente/demo)"

    @transaction.atomic
    def handle(self, **opts):
        if Cliente.objects.filter(codice="DEMO1").exists():
            self.stdout.write("Dati demo già presenti.")
            return
        oggi = date.today()
        admin = Utente.objects.create_superuser("admin", "admin@example.com", "demo-admin-2026",
                                                first_name="Paolo", ruolo="responsabile")
        tec = Utente.objects.create_user("tecnico", "tecnico@example.com", "demo-tecnico-2026", is_staff=True,
                                         first_name="Luca", last_name="Verdi", ruolo="tecnico")
        tec.user_permissions.set(Permission.objects.filter(
            content_type__app_label__in=["anagrafica", "assistenza", "commesse"]))

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
        self.stdout.write(self.style.SUCCESS(
            "Demo pronta. Back-office: admin / demo-admin-2026 · tecnico / demo-tecnico-2026 · "
            "Portale: giulia@logisticarapida.example / demo-cliente-2026"))
