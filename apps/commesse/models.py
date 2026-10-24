from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import Numeratore, Timestamped


class Commessa(Timestamped):
    class Stato(models.TextChoices):
        PREVENDITA = "prevendita", "Prevendita"
        PRODUZIONE = "produzione", "In produzione / installazione"
        POSTVENDITA = "postvendita", "In assistenza post-vendita"
        CHIUSA = "chiusa", "Chiusa"
        PERSA = "persa", "Persa / annullata"

    codice = models.CharField(max_length=20, unique=True, blank=True)
    cliente = models.ForeignKey("anagrafica.Cliente", on_delete=models.PROTECT, related_name="commesse")
    titolo = models.CharField(max_length=200)
    descrizione = models.TextField(blank=True)
    stato = models.CharField(max_length=20, choices=Stato.choices, default=Stato.PREVENDITA)

    # Fasi gestite da noi: non tutte le commesse le hanno tutte
    fase_prevendita = models.BooleanField("gestiamo la prevendita", default=True)
    fase_produzione = models.BooleanField("gestiamo produzione/installazione", default=True)
    fase_postvendita = models.BooleanField("gestiamo il post-vendita", default=True)

    ereditata = models.BooleanField(
        "presa in carico da terzi",
        default=False,
        help_text="Prodotto venduto/installato da altri, di cui prendiamo in carico l'assistenza.",
    )
    origine = models.CharField(
        "venduto/installato da", max_length=200, blank=True, help_text="Solo per commesse ereditate"
    )
    data_presa_in_carico = models.DateField(null=True, blank=True)

    responsabile = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        limit_choices_to={"ruolo__in": ["admin", "tecnico"]},
    )
    valore = models.DecimalField("valore (€)", max_digits=12, decimal_places=2, null=True, blank=True)
    data_apertura = models.DateField(default=timezone.localdate)
    data_chiusura = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "commesse"
        ordering = ["-data_apertura", "-id"]

    def save(self, *args, **kwargs):
        if not self.codice:
            self.codice = Numeratore.prossimo("CM", timezone.localdate().year, cifre=4)
        if self.ereditata and not self.fase_postvendita:
            self.fase_postvendita = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codice} – {self.titolo}"

    @property
    def fasi(self):
        f = []
        if self.fase_prevendita:
            f.append("Prevendita")
        if self.fase_produzione:
            f.append("Produzione")
        if self.fase_postvendita:
            f.append("Post-vendita")
        return f


class ModelloChecklist(models.Model):
    class Tipo(models.TextChoices):
        SOPRALLUOGO = "sopralluogo", "Sopralluogo prevendita"
        COLLAUDO = "collaudo", "Collaudo installazione"

    nome = models.CharField(max_length=120)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    attivo = models.BooleanField(default=True)
    predefinito = models.BooleanField(default=False)

    class Meta:
        verbose_name = "modello di checklist"
        verbose_name_plural = "modelli di checklist"

    def __str__(self):
        return f"{self.get_tipo_display()}: {self.nome}"


class VoceModello(models.Model):
    modello = models.ForeignKey(ModelloChecklist, on_delete=models.CASCADE, related_name="voci")
    ordine = models.PositiveIntegerField(default=0)
    gruppo = models.CharField(max_length=80, blank=True, help_text="Es. Elettrico, Rete, Meccanica")
    testo = models.CharField(max_length=250)
    obbligatoria = models.BooleanField(default=True)

    class Meta:
        ordering = ["ordine", "id"]
        verbose_name = "voce"
        verbose_name_plural = "voci"

    def __str__(self):
        return self.testo


class Esito(models.TextChoices):
    OK = "ok", "OK"
    KO = "ko", "Non conforme"
    NA = "na", "Non applicabile"
    DAF = "", "Da verificare"


class DocumentoCampo(Timestamped):
    """Base comune per i moduli compilati sul campo (sopralluogo, collaudo)."""

    PREFISSO = "XX"

    numero = models.CharField(max_length=20, unique=True, blank=True)
    commessa = models.ForeignKey(Commessa, on_delete=models.PROTECT, related_name="%(class)ss")
    sede = models.ForeignKey("anagrafica.Sede", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    data = models.DateField(default=timezone.localdate)
    tecnico = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        limit_choices_to={"ruolo__in": ["admin", "tecnico"]},
    )
    modello = models.ForeignKey(
        ModelloChecklist, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="Alla prima creazione le voci del modello vengono copiate nella checklist.",
    )
    note = models.TextField(blank=True)
    firmatario = models.CharField("nome firmatario cliente", max_length=120, blank=True)
    firma = models.ImageField(upload_to="firme/%Y/", null=True, blank=True)
    firmato_il = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ["-data", "-id"]

    def save(self, *args, **kwargs):
        nuovo = self._state.adding
        if not self.numero:
            self.numero = Numeratore.prossimo(self.PREFISSO, self.data.year, cifre=4)
        if nuovo and not self.modello_id:
            tipo = ModelloChecklist.Tipo.SOPRALLUOGO if self.PREFISSO == "SL" else ModelloChecklist.Tipo.COLLAUDO
            self.modello = ModelloChecklist.objects.filter(tipo=tipo, attivo=True, predefinito=True).first()
        super().save(*args, **kwargs)
        if nuovo and self.modello_id and not self.righe.exists():
            self.righe.bulk_create(
                [
                    self.righe.model(documento=self, ordine=v.ordine, gruppo=v.gruppo, testo=v.testo,
                                     obbligatoria=v.obbligatoria)
                    for v in self.modello.voci.all()
                ]
            )

    @property
    def cliente(self):
        return self.commessa.cliente

    @property
    def firmato(self):
        return bool(self.firma)

    def voci_mancanti(self):
        return self.righe.filter(obbligatoria=True, esito="")

    def __str__(self):
        return f"{self.numero} – {self.commessa.cliente}"


class RigaChecklistBase(models.Model):
    ordine = models.PositiveIntegerField(default=0)
    gruppo = models.CharField(max_length=80, blank=True)
    testo = models.CharField(max_length=250)
    obbligatoria = models.BooleanField(default=True)
    esito = models.CharField(max_length=2, choices=Esito.choices, blank=True, default="")
    valore = models.CharField(max_length=120, blank=True, help_text="Misura o valore rilevato")
    note = models.CharField(max_length=250, blank=True)

    class Meta:
        abstract = True
        ordering = ["ordine", "id"]

    def __str__(self):
        return self.testo


class Sopralluogo(DocumentoCampo):
    PREFISSO = "SL"

    class EsitoFattibilita(models.TextChoices):
        DA_VALUTARE = "da_valutare", "Da valutare"
        FATTIBILE = "fattibile", "Fattibile"
        CON_OPERE = "con_opere", "Fattibile con opere preliminari"
        NON_FATTIBILE = "non_fattibile", "Non fattibile"

    esito = models.CharField(max_length=20, choices=EsitoFattibilita.choices, default=EsitoFattibilita.DA_VALUTARE)
    opere_preliminari = models.TextField(
        blank=True, help_text="Lavori a carico cliente prima dell'installazione (elettrico, rete, opere murarie...)"
    )
    referente_presente = models.CharField("referente cliente presente", max_length=120, blank=True)

    class Meta(DocumentoCampo.Meta):
        verbose_name = "sopralluogo"
        verbose_name_plural = "sopralluoghi"


class RigaSopralluogo(RigaChecklistBase):
    documento = models.ForeignKey(Sopralluogo, on_delete=models.CASCADE, related_name="righe")

    class Meta(RigaChecklistBase.Meta):
        verbose_name = "voce checklist"
        verbose_name_plural = "checklist"


class FotoSopralluogo(models.Model):
    sopralluogo = models.ForeignKey(Sopralluogo, on_delete=models.CASCADE, related_name="foto")
    immagine = models.ImageField(upload_to="sopralluoghi/%Y/")
    didascalia = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "foto"
        verbose_name_plural = "foto"


class Collaudo(DocumentoCampo):
    PREFISSO = "CL"

    class EsitoCollaudo(models.TextChoices):
        IN_CORSO = "in_corso", "In corso"
        SUPERATO = "superato", "Superato"
        CON_RISERVA = "con_riserva", "Superato con riserva"
        NON_SUPERATO = "non_superato", "Non superato"

    apparati = models.ManyToManyField("assistenza.Apparato", blank=True, related_name="collaudi")
    esito = models.CharField(max_length=20, choices=EsitoCollaudo.choices, default=EsitoCollaudo.IN_CORSO)
    riserve = models.TextField(blank=True, help_text="Punti aperti da chiudere in caso di esito con riserva")

    class Meta(DocumentoCampo.Meta):
        verbose_name = "collaudo"
        verbose_name_plural = "collaudi"


class RigaCollaudo(RigaChecklistBase):
    documento = models.ForeignKey(Collaudo, on_delete=models.CASCADE, related_name="righe")

    class Meta(RigaChecklistBase.Meta):
        verbose_name = "voce checklist"
        verbose_name_plural = "checklist"
