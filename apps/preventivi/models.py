import uuid
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Numeratore, Timestamped

CENT = Decimal("0.01")


def arrotonda(v):
    return Decimal(v).quantize(CENT, rounding=ROUND_HALF_UP)


class Preventivo(Timestamped):
    class Tipo(models.TextChoices):
        INSTALLAZIONE = "installazione", "Nuova installazione / fornitura"
        RIPARAZIONE = "riparazione", "Riparazione"
        INTERVENTO = "intervento", "Intervento di assistenza"
        CONTRATTO = "contratto", "Contratto di assistenza"
        ALTRO = "altro", "Altro"

    class Stato(models.TextChoices):
        BOZZA = "bozza", "Bozza"
        INVIATO = "inviato", "Inviato al cliente"
        ACCETTATO = "accettato", "Accettato"
        RIFIUTATO = "rifiutato", "Rifiutato"
        SCADUTO = "scaduto", "Scaduto"
        ANNULLATO = "annullato", "Annullato"

    numero = models.CharField(max_length=20, unique=True, blank=True)
    revisione = models.PositiveSmallIntegerField(default=0)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.INSTALLAZIONE)
    stato = models.CharField(max_length=20, choices=Stato.choices, default=Stato.BOZZA)
    cliente = models.ForeignKey("anagrafica.Cliente", on_delete=models.PROTECT, related_name="preventivi")
    contatto = models.ForeignKey("anagrafica.Contatto", null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="+", help_text="Destinatario: riceve il link per accettarlo")
    oggetto = models.CharField(max_length=200)
    introduzione = models.TextField(blank=True, help_text="Testo in apertura del preventivo")

    commessa = models.ForeignKey("commesse.Commessa", null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="preventivi")
    ticket = models.ForeignKey("assistenza.Ticket", null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="preventivi")
    riparazione = models.ForeignKey("magazzino.Riparazione", null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="preventivi")
    sopralluogo = models.ForeignKey("commesse.Sopralluogo", null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="preventivi")

    data = models.DateField(default=timezone.localdate)
    validita_giorni = models.PositiveIntegerField("validità (giorni)", default=30)
    sconto_globale = models.DecimalField("sconto globale %", max_digits=5, decimal_places=2, default=0)
    aliquota_iva = models.DecimalField("IVA %", max_digits=5, decimal_places=2, default=22)
    pagamento = models.CharField(max_length=200, blank=True, default="Bonifico 30 gg data fattura")
    tempi_consegna = models.CharField(max_length=200, blank=True)
    garanzia = models.CharField(max_length=200, blank=True)
    note = models.TextField("note e condizioni", blank=True)
    autore = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="+", limit_choices_to={"ruolo__in": ["admin", "tecnico"]})

    inviato_il = models.DateTimeField(null=True, blank=True)
    risposta_il = models.DateTimeField(null=True, blank=True)
    accettato_da = models.CharField(max_length=120, blank=True)
    riferimento_ordine = models.CharField("vostro riferimento d'ordine", max_length=80, blank=True)
    motivo_rifiuto = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "preventivi"
        ordering = ["-data", "-id"]

    def __str__(self):
        return f"{self.codice} – {self.oggetto}"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = Numeratore.prossimo("PV", self.data.year, cifre=4)
        super().save(*args, **kwargs)

    @property
    def codice(self):
        return f"{self.numero}" + (f" rev.{self.revisione}" if self.revisione else "")

    @property
    def scadenza(self):
        return self.data + timedelta(days=self.validita_giorni)

    @property
    def scaduto(self):
        return self.stato == self.Stato.INVIATO and timezone.localdate() > self.scadenza

    @property
    def accettabile(self):
        return self.stato == self.Stato.INVIATO and not self.scaduto

    @property
    def modificabile(self):
        return self.stato == self.Stato.BOZZA

    # -- importi

    @property
    def imponibile_righe(self):
        return arrotonda(sum((r.totale for r in self.righe.all()), Decimal(0)))

    @property
    def sconto_importo(self):
        return arrotonda(self.imponibile_righe * self.sconto_globale / 100)

    @property
    def imponibile(self):
        return self.imponibile_righe - self.sconto_importo

    @property
    def iva(self):
        return arrotonda(self.imponibile * self.aliquota_iva / 100)

    @property
    def totale(self):
        return self.imponibile + self.iva

    # -- link per il cliente

    def get_absolute_url(self):
        return reverse("portale:preventivo", args=[self.token])

    def url_pubblico(self):
        return settings.PUBLIC_BASE_URL + self.get_absolute_url()

    @property
    def email_destinatario(self):
        if self.contatto and self.contatto.email:
            return self.contatto.email
        if self.ticket:
            return self.ticket.richiedente_email
        return self.cliente.email

    # -- flusso

    def invia(self):
        from . import notifiche

        if self.stato not in (self.Stato.BOZZA, self.Stato.INVIATO):
            raise ValueError("Il preventivo non è in uno stato inviabile")
        self.stato = self.Stato.INVIATO
        self.inviato_il = timezone.now()
        self.save(update_fields=["stato", "inviato_il"])
        notifiche.preventivo_inviato(self)

    @transaction.atomic
    def accetta(self, nome, riferimento="", utente=None):
        from . import effetti, notifiche

        self.stato = self.Stato.ACCETTATO
        self.risposta_il = timezone.now()
        self.accettato_da = nome
        self.riferimento_ordine = riferimento
        self.save()
        effetti.su_accettazione(self, utente)
        notifiche.risposta_cliente(self)

    def rifiuta(self, motivo=""):
        from . import effetti, notifiche

        self.stato = self.Stato.RIFIUTATO
        self.risposta_il = timezone.now()
        self.motivo_rifiuto = motivo
        self.save()
        effetti.su_rifiuto(self)
        notifiche.risposta_cliente(self)

    @transaction.atomic
    def nuova_revisione(self):
        """Riporta in bozza un preventivo inviato/rifiutato per modificarlo, con numero di revisione +1."""
        self.revisione += 1
        self.stato = self.Stato.BOZZA
        self.inviato_il = self.risposta_il = None
        self.accettato_da = self.motivo_rifiuto = ""
        self.token = uuid.uuid4()  # il vecchio link non vale più
        self.save()


class RigaPreventivo(models.Model):
    preventivo = models.ForeignKey(Preventivo, on_delete=models.CASCADE, related_name="righe")
    ordine = models.PositiveIntegerField(default=0)
    articolo = models.ForeignKey("magazzino.Articolo", null=True, blank=True, on_delete=models.PROTECT,
                                 related_name="+", help_text="Facoltativo: compila descrizione e prezzo")
    descrizione = models.CharField(max_length=250, blank=True)
    quantita = models.DecimalField("q.tà", max_digits=10, decimal_places=2, default=1)
    unita = models.CharField("u.m.", max_length=10, blank=True)
    prezzo_unitario = models.DecimalField("prezzo un. (€)", max_digits=10, decimal_places=2, null=True, blank=True)
    sconto = models.DecimalField("sconto %", max_digits=5, decimal_places=2, default=0)

    class Meta:
        ordering = ["ordine", "id"]
        verbose_name = "riga"
        verbose_name_plural = "righe"

    def save(self, *args, **kwargs):
        if self.articolo_id:
            self.descrizione = self.descrizione or self.articolo.descrizione
            self.unita = self.unita or self.articolo.unita
            if self.prezzo_unitario is None:
                self.prezzo_unitario = self.articolo.prezzo
        self.unita = self.unita or "pz"
        if self.prezzo_unitario is None:
            self.prezzo_unitario = Decimal(0)
        super().save(*args, **kwargs)

    @property
    def totale(self):
        if self.prezzo_unitario is None:
            return Decimal(0)
        return arrotonda(self.quantita * self.prezzo_unitario * (1 - self.sconto / 100))

    def __str__(self):
        return self.descrizione
