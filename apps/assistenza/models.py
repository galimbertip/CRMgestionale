import uuid
from datetime import datetime, timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Numeratore, Timestamped

from . import sla


class Priorita(models.TextChoices):
    BASSA = "bassa", "Bassa"
    MEDIA = "media", "Media"
    ALTA = "alta", "Alta"
    CRITICA = "critica", "Critica – fermo impianto"


# ---------------------------------------------------------------- SLA e contratti


class LivelloSLA(models.Model):
    nome = models.CharField(max_length=80, unique=True, help_text="Es. Base, Standard, Premium 24/7")
    solo_orario_lavorativo = models.BooleanField(default=True)
    ora_inizio = models.PositiveSmallIntegerField(default=8)
    ora_fine = models.PositiveSmallIntegerField(default=18)
    sabato_lavorativo = models.BooleanField(default=False)
    predefinito = models.BooleanField(
        "usato senza contratto", default=False,
        help_text="Livello applicato ai ticket di clienti senza contratto attivo.",
    )

    class Meta:
        verbose_name = "livello SLA"
        verbose_name_plural = "livelli SLA"

    def __str__(self):
        return self.nome

    def regola(self, priorita):
        return self.regole.filter(priorita=priorita).first()

    def scadenze(self, inizio, priorita):
        r = self.regola(priorita)
        if not r:
            return None, None
        giorni = (0, 1, 2, 3, 4, 5) if self.sabato_lavorativo else (0, 1, 2, 3, 4)
        kw = dict(solo_lavorative=self.solo_orario_lavorativo, ora_inizio=self.ora_inizio,
                  ora_fine=self.ora_fine, giorni=giorni)
        return sla.add_ore(inizio, r.ore_presa_in_carico, **kw), sla.add_ore(inizio, r.ore_risoluzione, **kw)


class RegolaSLA(models.Model):
    livello = models.ForeignKey(LivelloSLA, on_delete=models.CASCADE, related_name="regole")
    priorita = models.CharField(max_length=10, choices=Priorita.choices)
    ore_presa_in_carico = models.PositiveIntegerField(null=True, blank=True)
    ore_risoluzione = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("livello", "priorita")
        verbose_name = "regola SLA"
        verbose_name_plural = "tempi per priorità"

    def __str__(self):
        return f"{self.livello} / {self.get_priorita_display()}"


class Contratto(Timestamped):
    class Tipo(models.TextChoices):
        GARANZIA = "garanzia", "Garanzia"
        MANUTENZIONE = "manutenzione", "Manutenzione programmata"
        FULL = "full", "Full service"
        CHIAMATA = "chiamata", "A chiamata / pacchetto ore"

    numero = models.CharField(max_length=30, unique=True)
    cliente = models.ForeignKey("anagrafica.Cliente", on_delete=models.PROTECT, related_name="contratti")
    commessa = models.ForeignKey("commesse.Commessa", null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="contratti")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.MANUTENZIONE)
    livello_sla = models.ForeignKey(LivelloSLA, on_delete=models.PROTECT, related_name="contratti")
    data_inizio = models.DateField()
    data_fine = models.DateField()
    rinnovo_automatico = models.BooleanField(default=False)
    preavviso_giorni = models.PositiveIntegerField("preavviso disdetta (giorni)", default=60)
    canone_annuo = models.DecimalField("canone annuo (€)", max_digits=10, decimal_places=2, null=True, blank=True)
    ore_incluse = models.PositiveIntegerField("ore incluse", null=True, blank=True)
    visite_programmate_anno = models.PositiveIntegerField(null=True, blank=True)
    attivo = models.BooleanField(default=True)
    note = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "contratti"
        ordering = ["data_fine"]

    def __str__(self):
        return f"{self.numero} – {self.cliente}"

    @property
    def giorni_alla_scadenza(self):
        return (self.data_fine - timezone.localdate()).days

    @property
    def in_scadenza(self):
        return self.attivo and 0 <= self.giorni_alla_scadenza <= max(self.preavviso_giorni, 30)

    @property
    def scaduto(self):
        return self.giorni_alla_scadenza < 0

    def ore_consumate(self):
        tot = 0
        for r in self.rapportini.all():
            tot += r.ore_lavoro
        return round(tot, 2)


# ---------------------------------------------------------------- parco installato


class Apparato(Timestamped):
    class Stato(models.TextChoices):
        IN_ATTESA = "in_attesa", "Da installare"
        IN_SERVIZIO = "in_servizio", "In servizio"
        GUASTO = "guasto", "Guasto / fermo"
        DISMESSO = "dismesso", "Dismesso"

    cliente = models.ForeignKey("anagrafica.Cliente", on_delete=models.PROTECT, related_name="apparati")
    sede = models.ForeignKey("anagrafica.Sede", null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="apparati")
    commessa = models.ForeignKey("commesse.Commessa", null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="apparati")
    contratto = models.ForeignKey(Contratto, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="apparati")
    modello = models.CharField(max_length=120)
    matricola = models.CharField(max_length=80, unique=True)
    versione_firmware = models.CharField("versione firmware/software", max_length=40, blank=True)
    identificativo_remoto = models.CharField(
        max_length=120, blank=True, help_text="Hostname, ID VPN/Tailscale, IMEI modem..."
    )
    ubicazione = models.CharField(max_length=200, blank=True, help_text="Posizione precisa nella sede")
    data_installazione = models.DateField(null=True, blank=True)
    fine_garanzia = models.DateField(null=True, blank=True)
    stato = models.CharField(max_length=20, choices=Stato.choices, default=Stato.IN_SERVIZIO)
    note = models.TextField(blank=True)

    class Meta:
        verbose_name = "apparato"
        verbose_name_plural = "parco installato"
        ordering = ["cliente", "matricola"]

    def __str__(self):
        return f"{self.modello} – {self.matricola}"

    @property
    def in_garanzia(self):
        return bool(self.fine_garanzia and self.fine_garanzia >= timezone.localdate())


# ---------------------------------------------------------------- ticket


class Ticket(Timestamped):
    class Stato(models.TextChoices):
        NUOVO = "nuovo", "Nuovo"
        PRESO = "preso_in_carico", "Preso in carico"
        LAVORAZIONE = "in_lavorazione", "In lavorazione"
        ATTESA_CLIENTE = "attesa_cliente", "In attesa del cliente"
        RISOLTO = "risolto", "Risolto"
        CHIUSO = "chiuso", "Chiuso"

    STATI_APERTI = [Stato.NUOVO, Stato.PRESO, Stato.LAVORAZIONE, Stato.ATTESA_CLIENTE]

    class Categoria(models.TextChoices):
        GUASTO = "guasto", "Guasto / malfunzionamento"
        CONFIGURAZIONE = "configurazione", "Configurazione / modifica"
        INFORMAZIONI = "informazioni", "Richiesta informazioni"
        MANUTENZIONE = "manutenzione", "Manutenzione programmata"
        COMMERCIALE = "commerciale", "Richiesta commerciale"
        ALTRO = "altro", "Altro"

    class Canale(models.TextChoices):
        PORTALE = "portale", "Portale web"
        EMAIL = "email", "Email"
        TELEFONO = "telefono", "Telefono"
        INTERNO = "interno", "Interno / proattivo"

    codice = models.CharField(max_length=20, unique=True, blank=True)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    cliente = models.ForeignKey("anagrafica.Cliente", null=True, blank=True, on_delete=models.PROTECT,
                                related_name="ticket", help_text="Vuoto = da smistare (cliente non riconosciuto)")
    apparato = models.ForeignKey(Apparato, null=True, blank=True, on_delete=models.SET_NULL, related_name="ticket")
    commessa = models.ForeignKey("commesse.Commessa", null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="ticket")
    contratto = models.ForeignKey(Contratto, null=True, blank=True, on_delete=models.SET_NULL, related_name="ticket")
    livello_sla = models.ForeignKey(LivelloSLA, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    utente_portale = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                       related_name="ticket_aperti")
    richiedente_nome = models.CharField(max_length=120)
    richiedente_email = models.EmailField()
    richiedente_telefono = models.CharField(max_length=40, blank=True)
    azienda_dichiarata = models.CharField(max_length=200, blank=True)
    matricola_dichiarata = models.CharField(max_length=80, blank=True)

    oggetto = models.CharField(max_length=200)
    descrizione = models.TextField()
    categoria = models.CharField(max_length=20, choices=Categoria.choices, default=Categoria.GUASTO)
    priorita = models.CharField("priorità", max_length=10, choices=Priorita.choices, default=Priorita.MEDIA)
    canale = models.CharField(max_length=10, choices=Canale.choices, default=Canale.PORTALE)
    stato = models.CharField(max_length=20, choices=Stato.choices, default=Stato.NUOVO)
    assegnato_a = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    limit_choices_to={"ruolo__in": ["admin", "tecnico"]},
                                    related_name="ticket_assegnati")

    scadenza_presa_in_carico = models.DateTimeField(null=True, blank=True)
    scadenza_risoluzione = models.DateTimeField(null=True, blank=True)
    preso_in_carico_il = models.DateTimeField(null=True, blank=True)
    risolto_il = models.DateTimeField(null=True, blank=True)
    chiuso_il = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "ticket"
        ordering = ["-creato_il"]

    def __str__(self):
        return f"{self.codice} – {self.oggetto}"

    # -- logica

    def save(self, *args, **kwargs):
        nuovo = self._state.adding
        if not self.codice:
            self.codice = Numeratore.prossimo("TK", timezone.localdate().year)
        if self.apparato_id and not self.cliente_id:
            self.cliente_id = self.apparato.cliente_id
        if self.apparato_id and not self.contratto_id and self.apparato.contratto_id:
            self.contratto_id = self.apparato.contratto_id
        if self.cliente_id and not self.contratto_id:
            self.contratto = self.cliente.contratto_attivo()
        if nuovo or not self.scadenza_risoluzione:
            self.ricalcola_sla(salva=False)
        self._aggiorna_date_stato()
        super().save(*args, **kwargs)

    def ricalcola_sla(self, salva=True):
        livello = (self.contratto.livello_sla if self.contratto_id else None) or \
            LivelloSLA.objects.filter(predefinito=True).first()
        self.livello_sla = livello
        inizio = self.creato_il or timezone.now()
        if livello:
            self.scadenza_presa_in_carico, self.scadenza_risoluzione = livello.scadenze(inizio, self.priorita)
        if salva:
            self.save(update_fields=["livello_sla", "scadenza_presa_in_carico", "scadenza_risoluzione"])

    def _aggiorna_date_stato(self):
        adesso = timezone.now()
        if self.stato != self.Stato.NUOVO and not self.preso_in_carico_il:
            self.preso_in_carico_il = adesso
        if self.stato in (self.Stato.RISOLTO, self.Stato.CHIUSO) and not self.risolto_il:
            self.risolto_il = adesso
        if self.stato == self.Stato.CHIUSO and not self.chiuso_il:
            self.chiuso_il = adesso
        if self.stato not in (self.Stato.RISOLTO, self.Stato.CHIUSO):
            self.risolto_il = None
            self.chiuso_il = None

    @property
    def aperto(self):
        return self.stato in self.STATI_APERTI

    @property
    def sla_presa_in_carico(self):
        return sla.stato_scadenza(self.scadenza_presa_in_carico, self.preso_in_carico_il, self.creato_il)

    @property
    def sla_risoluzione(self):
        return sla.stato_scadenza(self.scadenza_risoluzione, self.risolto_il, self.creato_il)

    @property
    def sla_corrente(self):
        """La scadenza che conta adesso: presa in carico finché è nuovo, poi risoluzione."""
        if self.stato == self.Stato.NUOVO:
            return self.scadenza_presa_in_carico, self.sla_presa_in_carico
        return self.scadenza_risoluzione, self.sla_risoluzione

    def get_absolute_url(self):
        return reverse("portale:ticket_dettaglio", args=[self.token])

    def url_pubblico(self):
        return settings.PUBLIC_BASE_URL + self.get_absolute_url()


class MessaggioTicket(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messaggi")
    autore = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="+")
    autore_nome = models.CharField(max_length=120, blank=True)
    da_cliente = models.BooleanField(default=False)
    interno = models.BooleanField("nota interna (non visibile al cliente)", default=False)
    testo = models.TextField()
    allegato = models.FileField(upload_to="ticket/%Y/%m/", null=True, blank=True)
    creato_il = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["creato_il"]
        verbose_name = "messaggio"
        verbose_name_plural = "messaggi"

    def __str__(self):
        return f"{self.ticket.codice} · {self.creato_il:%d/%m %H:%M}"

    @property
    def nome_visualizzato(self):
        if self.autore:
            return str(self.autore)
        return self.autore_nome or ("Cliente" if self.da_cliente else "Assistenza")


class EventoTicket(models.Model):
    """Storico automatico dei cambi di stato/priorità/assegnazione."""

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="eventi")
    quando = models.DateTimeField(default=timezone.now)
    utente = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="+")
    descrizione = models.CharField(max_length=250)
    visibile_cliente = models.BooleanField(default=True)

    class Meta:
        ordering = ["quando"]
        verbose_name_plural = "eventi"


# ---------------------------------------------------------------- rapportino


class Rapportino(Timestamped):
    class Tipo(models.TextChoices):
        GARANZIA = "garanzia", "In garanzia"
        CONTRATTO = "contratto", "Coperto da contratto"
        PAGAMENTO = "pagamento", "A pagamento"
        INSTALLAZIONE = "installazione", "Installazione (commessa)"

    class EsitoIntervento(models.TextChoices):
        RISOLTO = "risolto", "Risolto"
        PARZIALE = "parziale", "Parzialmente risolto"
        DA_COMPLETARE = "da_completare", "Da completare (nuovo intervento)"

    numero = models.CharField(max_length=20, unique=True, blank=True)
    cliente = models.ForeignKey("anagrafica.Cliente", on_delete=models.PROTECT, related_name="rapportini")
    sede = models.ForeignKey("anagrafica.Sede", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    ticket = models.ForeignKey(Ticket, null=True, blank=True, on_delete=models.SET_NULL, related_name="rapportini")
    commessa = models.ForeignKey("commesse.Commessa", null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="rapportini")
    contratto = models.ForeignKey(Contratto, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="rapportini")
    apparato = models.ForeignKey(Apparato, null=True, blank=True, on_delete=models.SET_NULL, related_name="rapportini")
    tecnico = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                limit_choices_to={"ruolo__in": ["admin", "tecnico"]}, related_name="rapportini")
    data = models.DateField(default=timezone.localdate)
    ora_inizio = models.TimeField()
    ora_fine = models.TimeField()
    pausa_minuti = models.PositiveIntegerField(default=0)
    ore_viaggio = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    km = models.PositiveIntegerField("km percorsi", default=0)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.CONTRATTO)
    problema = models.TextField("problema riscontrato", blank=True)
    lavoro_svolto = models.TextField()
    esito = models.CharField(max_length=20, choices=EsitoIntervento.choices, default=EsitoIntervento.RISOLTO)
    note_cliente = models.TextField("osservazioni del cliente", blank=True)
    firmatario = models.CharField("nome firmatario cliente", max_length=120, blank=True)
    firma = models.ImageField(upload_to="firme/%Y/", null=True, blank=True)
    firmato_il = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "rapportino d'intervento"
        verbose_name_plural = "rapportini d'intervento"
        ordering = ["-data", "-id"]

    def __str__(self):
        return f"{self.numero} – {self.cliente}"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = Numeratore.prossimo("RI", self.data.year, cifre=4)
        if self.ticket_id:
            self.cliente_id = self.cliente_id or self.ticket.cliente_id
            self.apparato_id = self.apparato_id or self.ticket.apparato_id
            self.contratto_id = self.contratto_id or self.ticket.contratto_id
        if self.apparato_id and not self.contratto_id:
            self.contratto_id = self.apparato.contratto_id
        super().save(*args, **kwargs)

    @property
    def ore_lavoro(self):
        if not (self.ora_inizio and self.ora_fine):
            return 0
        d = datetime.combine(self.data, self.ora_fine) - datetime.combine(self.data, self.ora_inizio)
        if d < timedelta(0):  # intervento a cavallo della mezzanotte
            d += timedelta(days=1)
        return round(max(d.total_seconds() / 3600 - self.pausa_minuti / 60, 0), 2)

    @property
    def firmato(self):
        return bool(self.firma)


class RigaRicambio(models.Model):
    rapportino = models.ForeignKey(Rapportino, on_delete=models.CASCADE, related_name="ricambi")
    articolo = models.ForeignKey("magazzino.Articolo", null=True, blank=True, on_delete=models.PROTECT,
                                 related_name="+", help_text="Se indicato, il ricambio viene scaricato dal magazzino")
    codice = models.CharField(max_length=60, blank=True)
    descrizione = models.CharField(max_length=200, blank=True)
    quantita = models.DecimalField("quantità", max_digits=8, decimal_places=2, default=1)
    matricola_installata = models.CharField(max_length=80, blank=True)
    matricola_rimossa = models.CharField(max_length=80, blank=True)
    movimento = models.OneToOneField("magazzino.Movimento", null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="+", editable=False)

    class Meta:
        verbose_name = "ricambio"
        verbose_name_plural = "ricambi utilizzati"

    def __str__(self):
        return self.descrizione or (self.articolo.descrizione if self.articolo else "")

    def save(self, *args, **kwargs):
        from apps.magazzino.models import Movimento, movimenta

        if self.articolo_id:
            self.codice = self.codice or self.articolo.codice
            self.descrizione = self.descrizione or self.articolo.descrizione
        super().save(*args, **kwargs)
        if self.articolo_id and not self.movimento_id:
            r = self.rapportino
            self.movimento = movimenta(self.articolo, Movimento.Causale.SCARICO_INTERVENTO, self.quantita,
                                       rapportino=r, cliente=r.cliente, matricola=self.matricola_installata,
                                       note=r.numero)
            if self.movimento:
                super().save(update_fields=["movimento"])
        elif self.movimento_id and self.movimento.quantita != -abs(self.quantita):
            self.movimento.quantita = self.quantita
            self.movimento.save()

    def delete(self, *args, **kwargs):
        if self.movimento_id:
            self.movimento.delete()
        return super().delete(*args, **kwargs)
