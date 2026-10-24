"""Magazzino in sede con due aree, distinta base, produzione e riparazioni.

- Area NUOVO: materiale nostro (componenti, ricambi, prodotti finiti).
- Area RIPARAZIONI: merce di proprietà del cliente ricevuta in conto riparazione.

Le giacenze non si scrivono mai a mano: sono la somma dei movimenti.
Disponibile (nuovo) = giacenza - impegnato dagli ordini di produzione aperti.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import DecimalField, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.core.models import Numeratore, Timestamped

ZERO = Decimal("0")
INTERNI = {"ruolo__in": ["admin", "tecnico"]}


class Area(models.TextChoices):
    NUOVO = "nuovo", "Nuovo (nostro)"
    RIPARAZIONI = "riparazioni", "Riparazioni (merce cliente)"


# ---------------------------------------------------------------- articoli


class ArticoloQuerySet(models.QuerySet):
    def con_giacenze(self):
        def somma(area):
            sq = (Movimento.objects.filter(articolo=OuterRef("pk"), area=area).values("articolo")
                  .annotate(t=Sum("quantita")).values("t"))
            return Coalesce(Subquery(sq), Value(ZERO), output_field=DecimalField(max_digits=12, decimal_places=2))

        imp = (Impegno.objects.filter(articolo=OuterRef("pk"), ordine__stato__in=OrdineProduzione.STATI_IMPEGNANTI)
               .values("articolo").annotate(t=Sum("quantita_residua")).values("t"))
        return self.annotate(
            giacenza_nuovo=somma(Area.NUOVO),
            giacenza_riparazioni=somma(Area.RIPARAZIONI),
            impegnato=Coalesce(Subquery(imp), Value(ZERO), output_field=DecimalField(max_digits=12, decimal_places=2)),
        )


class Articolo(Timestamped):
    class Tipo(models.TextChoices):
        PRODOTTO = "prodotto", "Prodotto finito"
        COMPONENTE = "componente", "Componente / semilavorato"
        RICAMBIO = "ricambio", "Ricambio"
        CONSUMABILE = "consumabile", "Materiale di consumo"
        SERVIZIO = "servizio", "Servizio / manodopera (non a magazzino)"

    codice = models.CharField(max_length=40, unique=True)
    descrizione = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.COMPONENTE)
    unita = models.CharField("unità di misura", max_length=10, default="pz")
    a_matricola = models.BooleanField("gestito a matricola", default=False,
                                      help_text="Ogni pezzo ha un numero di serie (schede, moduli, prodotti finiti)")
    costo = models.DecimalField("costo (€)", max_digits=10, decimal_places=2, default=0)
    prezzo = models.DecimalField("prezzo di vendita (€)", max_digits=10, decimal_places=2, default=0)
    scorta_minima = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fornitore = models.CharField(max_length=120, blank=True)
    codice_fornitore = models.CharField(max_length=60, blank=True)
    ubicazione = models.CharField(max_length=60, blank=True, help_text="Scaffale / ripiano")
    attivo = models.BooleanField(default=True)
    note = models.TextField(blank=True)

    objects = ArticoloQuerySet.as_manager()

    class Meta:
        verbose_name_plural = "articoli"
        ordering = ["codice"]

    def __str__(self):
        return f"{self.codice} – {self.descrizione}"

    @property
    def a_magazzino(self):
        return self.tipo != self.Tipo.SERVIZIO

    def giacenza(self, area=Area.NUOVO):
        return self.movimenti.filter(area=area).aggregate(t=Sum("quantita"))["t"] or ZERO

    def impegnato_totale(self):
        return (Impegno.objects.filter(articolo=self, ordine__stato__in=OrdineProduzione.STATI_IMPEGNANTI)
                .aggregate(t=Sum("quantita_residua"))["t"] or ZERO)

    def disponibile(self):
        return self.giacenza() - self.impegnato_totale()


# ---------------------------------------------------------------- movimenti


class Movimento(models.Model):
    class Causale(models.TextChoices):
        CARICO_ACQUISTO = "carico_acquisto", "Carico da acquisto"
        CARICO_PRODUZIONE = "carico_produzione", "Carico da produzione"
        RESO = "reso", "Reso / rientro"
        SCARICO_INTERVENTO = "scarico_intervento", "Scarico per intervento"
        SCARICO_PRODUZIONE = "scarico_produzione", "Prelievo per produzione"
        SCARICO_RIPARAZIONE = "scarico_riparazione", "Ricambio usato in riparazione"
        SCARICO_VENDITA = "scarico_vendita", "Scarico per vendita / consegna"
        INGRESSO_RIPARAZIONE = "ingresso_riparazione", "Ricevuto in riparazione"
        USCITA_RIPARAZIONE = "uscita_riparazione", "Restituito al cliente"
        ROTTAMAZIONE = "rottamazione", "Rottamazione"
        RETTIFICA = "rettifica", "Rettifica inventario"

    USCITE = {"scarico_intervento", "scarico_produzione", "scarico_riparazione", "scarico_vendita",
              "uscita_riparazione", "rottamazione"}

    data = models.DateTimeField(default=timezone.now)
    articolo = models.ForeignKey(Articolo, on_delete=models.PROTECT, related_name="movimenti")
    area = models.CharField(max_length=20, choices=Area.choices, default=Area.NUOVO)
    causale = models.CharField(max_length=30, choices=Causale.choices)
    quantita = models.DecimalField("quantità", max_digits=12, decimal_places=2,
                                   help_text="Inserisci il valore positivo: il segno lo decide la causale")
    matricola = models.CharField(max_length=80, blank=True)
    cliente = models.ForeignKey("anagrafica.Cliente", null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="movimenti_magazzino")
    rapportino = models.ForeignKey("assistenza.Rapportino", null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="movimenti")
    ordine = models.ForeignKey("OrdineProduzione", null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="movimenti")
    riparazione = models.ForeignKey("Riparazione", null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="movimenti")
    documento = models.CharField("documento esterno", max_length=60, blank=True, help_text="DDT, fattura fornitore…")
    utente = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="+")
    note = models.CharField(max_length=250, blank=True)

    class Meta:
        verbose_name_plural = "movimenti"
        ordering = ["-data", "-id"]

    def __str__(self):
        return f"{self.get_causale_display()} {self.quantita} × {self.articolo.codice}"

    def clean(self):
        if self.articolo_id and not self.articolo.a_magazzino:
            raise ValidationError("I servizi non si movimentano a magazzino.")
        if self.causale in ("ingresso_riparazione", "uscita_riparazione") and self.area != Area.RIPARAZIONI:
            raise ValidationError({"area": "La merce in riparazione va nell'area Riparazioni."})

    def save(self, *args, **kwargs):
        if self.causale != self.Causale.RETTIFICA:
            q = abs(self.quantita)
            self.quantita = -q if self.causale in self.USCITE else q
        super().save(*args, **kwargs)


def movimenta(articolo, causale, quantita, area=Area.NUOVO, **kw):
    if not articolo or not articolo.a_magazzino or not quantita:
        return None
    return Movimento.objects.create(articolo=articolo, causale=causale, quantita=quantita, area=area, **kw)


# ---------------------------------------------------------------- distinta base e produzione


class DistintaBase(Timestamped):
    prodotto = models.ForeignKey(Articolo, on_delete=models.PROTECT, related_name="distinte",
                                 limit_choices_to={"tipo__in": ["prodotto", "componente"]})
    versione = models.CharField(max_length=20, default="1")
    attiva = models.BooleanField(default=True)
    note = models.TextField(blank=True)

    class Meta:
        verbose_name = "distinta base"
        verbose_name_plural = "distinte base"
        unique_together = ("prodotto", "versione")

    def __str__(self):
        return f"DB {self.prodotto.codice} v{self.versione}"

    def costo_materiali(self):
        return sum((r.quantita * r.componente.costo for r in self.righe.select_related("componente")), ZERO)


class RigaDistinta(models.Model):
    distinta = models.ForeignKey(DistintaBase, on_delete=models.CASCADE, related_name="righe")
    componente = models.ForeignKey(Articolo, on_delete=models.PROTECT, related_name="usato_in",
                                   limit_choices_to=~Q(tipo="servizio"))
    quantita = models.DecimalField("quantità per unità", max_digits=10, decimal_places=3)
    note = models.CharField(max_length=120, blank=True)

    class Meta:
        verbose_name = "componente"
        verbose_name_plural = "componenti"

    def __str__(self):
        return f"{self.quantita} × {self.componente}"


class OrdineProduzione(Timestamped):
    class Stato(models.TextChoices):
        BOZZA = "bozza", "Bozza"
        CONFERMATO = "confermato", "Confermato – materiale impegnato"
        IN_LAVORAZIONE = "in_lavorazione", "In lavorazione"
        COMPLETATO = "completato", "Completato"
        ANNULLATO = "annullato", "Annullato"

    STATI_IMPEGNANTI = ["confermato", "in_lavorazione"]

    numero = models.CharField(max_length=20, unique=True, blank=True)
    commessa = models.ForeignKey("commesse.Commessa", null=True, blank=True, on_delete=models.PROTECT,
                                 related_name="ordini_produzione")
    distinta = models.ForeignKey(DistintaBase, on_delete=models.PROTECT, related_name="ordini")
    quantita = models.DecimalField("quantità da produrre", max_digits=10, decimal_places=2, default=1)
    stato = models.CharField(max_length=20, choices=Stato.choices, default=Stato.BOZZA)
    data_prevista = models.DateField("consegna prevista", null=True, blank=True)
    completato_il = models.DateTimeField(null=True, blank=True)
    matricole_prodotte = models.TextField(blank=True, help_text="Una per riga: diventano apparati della commessa")
    note = models.TextField(blank=True)

    class Meta:
        verbose_name = "ordine di produzione"
        verbose_name_plural = "ordini di produzione"
        ordering = ["-id"]

    def __str__(self):
        return f"{self.numero} – {self.quantita} × {self.distinta.prodotto.codice}"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = Numeratore.prossimo("OP", timezone.localdate().year, cifre=4)
        super().save(*args, **kwargs)

    def mancanti(self):
        """Componenti per cui il disponibile non copre l'impegno di questo ordine."""
        out = []
        for i in self.impegni.select_related("articolo"):
            # disponibile esclusi gli impegni di questo stesso ordine
            libero = i.articolo.disponibile() + (i.quantita_residua if self.stato in self.STATI_IMPEGNANTI else 0)
            if libero < i.quantita_residua:
                out.append((i.articolo, i.quantita_residua - libero))
        return out

    @transaction.atomic
    def conferma(self):
        """Bozza -> confermato: crea gli impegni sul magazzino nuovo dalla distinta."""
        if self.stato != self.Stato.BOZZA:
            raise ValidationError("Solo un ordine in bozza può essere confermato.")
        self.impegni.all().delete()
        for r in self.distinta.righe.select_related("componente"):
            q = r.quantita * self.quantita
            Impegno.objects.create(ordine=self, articolo=r.componente, quantita=q, quantita_residua=q)
        self.stato = self.Stato.CONFERMATO
        self.save(update_fields=["stato"])

    @transaction.atomic
    def preleva(self, utente=None):
        """Scarica dal nuovo tutti i componenti ancora da prelevare."""
        for i in self.impegni.select_related("articolo").filter(quantita_residua__gt=0):
            movimenta(i.articolo, Movimento.Causale.SCARICO_PRODUZIONE, i.quantita_residua, ordine=self,
                      utente=utente, note=f"Prelievo {self.numero}")
            i.quantita_residua = 0
            i.save(update_fields=["quantita_residua"])
        if self.stato == self.Stato.CONFERMATO:
            self.stato = self.Stato.IN_LAVORAZIONE
            self.save(update_fields=["stato"])

    @transaction.atomic
    def completa(self, utente=None):
        if self.stato not in self.STATI_IMPEGNANTI:
            raise ValidationError("L'ordine deve essere confermato prima di essere completato.")
        self.preleva(utente)
        prodotto = self.distinta.prodotto
        matricole = [m.strip() for m in self.matricole_prodotte.splitlines() if m.strip()]
        if prodotto.a_matricola and matricole:
            for m in matricole:
                movimenta(prodotto, Movimento.Causale.CARICO_PRODUZIONE, 1, ordine=self, matricola=m, utente=utente)
        else:
            movimenta(prodotto, Movimento.Causale.CARICO_PRODUZIONE, self.quantita, ordine=self, utente=utente)
        # le matricole prodotte su commessa diventano apparati da installare
        if self.commessa_id and matricole:
            from apps.assistenza.models import Apparato

            for m in matricole:
                Apparato.objects.get_or_create(matricola=m, defaults=dict(
                    cliente=self.commessa.cliente, commessa=self.commessa, modello=prodotto.descrizione,
                    stato=Apparato.Stato.IN_ATTESA))
        self.stato = self.Stato.COMPLETATO
        self.completato_il = timezone.now()
        self.save(update_fields=["stato", "completato_il"])

    @transaction.atomic
    def annulla(self):
        if self.stato == self.Stato.COMPLETATO:
            raise ValidationError("Un ordine completato non si annulla.")
        self.stato = self.Stato.ANNULLATO  # gli impegni smettono di contare
        self.save(update_fields=["stato"])


class Impegno(models.Model):
    ordine = models.ForeignKey(OrdineProduzione, on_delete=models.CASCADE, related_name="impegni")
    articolo = models.ForeignKey(Articolo, on_delete=models.PROTECT, related_name="impegni")
    quantita = models.DecimalField("impegnata", max_digits=12, decimal_places=3)
    quantita_residua = models.DecimalField("da prelevare", max_digits=12, decimal_places=3)

    class Meta:
        verbose_name = "materiale impegnato"
        verbose_name_plural = "materiale impegnato"

    def __str__(self):
        return f"{self.articolo.codice}: {self.quantita_residua}/{self.quantita}"


# ---------------------------------------------------------------- riparazioni


class Riparazione(Timestamped):
    class Stato(models.TextChoices):
        RICEVUTO = "ricevuto", "Ricevuto"
        DIAGNOSI = "diagnosi", "In diagnosi"
        ATTESA_OK = "attesa_ok", "In attesa di approvazione preventivo"
        IN_RIPARAZIONE = "in_riparazione", "In riparazione"
        RIPARATO = "riparato", "Riparato – pronto per la riconsegna"
        NON_RIPARABILE = "non_riparabile", "Non riparabile"
        RICONSEGNATO = "riconsegnato", "Riconsegnato al cliente"
        ROTTAMATO = "rottamato", "Rottamato"

    APERTE = ["ricevuto", "diagnosi", "attesa_ok", "in_riparazione", "riparato", "non_riparabile"]

    numero = models.CharField(max_length=20, unique=True, blank=True)
    cliente = models.ForeignKey("anagrafica.Cliente", on_delete=models.PROTECT, related_name="riparazioni")
    ticket = models.ForeignKey("assistenza.Ticket", null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="riparazioni")
    apparato = models.ForeignKey("assistenza.Apparato", null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="riparazioni", help_text="Apparato da cui proviene il pezzo")
    articolo = models.ForeignKey(Articolo, null=True, blank=True, on_delete=models.PROTECT,
                                 related_name="riparazioni", help_text="Tipo di pezzo (scheda, modulo…)")
    descrizione_pezzo = models.CharField(max_length=200)
    matricola = models.CharField(max_length=80)
    stato = models.CharField(max_length=20, choices=Stato.choices, default=Stato.RICEVUTO)
    in_garanzia = models.BooleanField(default=False)
    difetto_dichiarato = models.TextField()
    diagnosi = models.TextField(blank=True)
    lavoro_eseguito = models.TextField(blank=True)
    tecnico = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="+", limit_choices_to=INTERNI)
    data_ricezione = models.DateField(default=timezone.localdate)
    ddt_ingresso = models.CharField("DDT di ingresso", max_length=60, blank=True)
    data_riconsegna = models.DateField(null=True, blank=True)
    ddt_uscita = models.CharField("DDT di uscita", max_length=60, blank=True)
    ore_lavoro = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    class Meta:
        verbose_name_plural = "riparazioni"
        ordering = ["-data_ricezione", "-id"]

    def __str__(self):
        return f"{self.numero} – {self.descrizione_pezzo} {self.matricola}"

    @transaction.atomic
    def save(self, *args, **kwargs):
        nuovo = self._state.adding
        precedente = None if nuovo else Riparazione.objects.filter(pk=self.pk).values_list("stato", flat=True).first()
        if not self.numero:
            self.numero = Numeratore.prossimo("RP", self.data_ricezione.year, cifre=4)
        if self.apparato_id and not self.cliente_id:
            self.cliente_id = self.apparato.cliente_id
        if self.stato in (self.Stato.RICONSEGNATO, self.Stato.ROTTAMATO) and not self.data_riconsegna:
            self.data_riconsegna = timezone.localdate()
        super().save(*args, **kwargs)
        # il pezzo entra ed esce dall'area riparazioni seguendo lo stato
        if nuovo:
            movimenta(self.articolo, Movimento.Causale.INGRESSO_RIPARAZIONE, 1, area=Area.RIPARAZIONI,
                      riparazione=self, cliente=self.cliente, matricola=self.matricola, documento=self.ddt_ingresso)
        uscita = {self.Stato.RICONSEGNATO: Movimento.Causale.USCITA_RIPARAZIONE,
                  self.Stato.ROTTAMATO: Movimento.Causale.ROTTAMAZIONE}
        if precedente not in uscita and self.stato in uscita and not nuovo:
            movimenta(self.articolo, uscita[self.stato], 1, area=Area.RIPARAZIONI, riparazione=self,
                      cliente=self.cliente, matricola=self.matricola, documento=self.ddt_uscita)

    @property
    def aperta(self):
        return self.stato in self.APERTE

    def costo_ricambi(self):
        return sum((r.quantita * r.articolo.prezzo for r in self.ricambi.select_related("articolo")), ZERO)


class RicambioRiparazione(models.Model):
    riparazione = models.ForeignKey(Riparazione, on_delete=models.CASCADE, related_name="ricambi")
    articolo = models.ForeignKey(Articolo, on_delete=models.PROTECT, related_name="+",
                                 limit_choices_to=~Q(tipo="servizio"))
    quantita = models.DecimalField("quantità", max_digits=10, decimal_places=2, default=1)
    movimento = models.OneToOneField(Movimento, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="+", editable=False)

    class Meta:
        verbose_name = "ricambio usato"
        verbose_name_plural = "ricambi usati (scaricati dal nuovo)"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.movimento_id:
            self.movimento = movimenta(self.articolo, Movimento.Causale.SCARICO_RIPARAZIONE, self.quantita,
                                       riparazione=self.riparazione, note=self.riparazione.numero)
            super().save(update_fields=["movimento"])
        elif self.movimento.quantita != -abs(self.quantita):
            self.movimento.quantita = self.quantita
            self.movimento.save()

    def delete(self, *args, **kwargs):
        if self.movimento_id:
            self.movimento.delete()  # il ricambio torna disponibile
        return super().delete(*args, **kwargs)
