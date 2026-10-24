from django.db import models

from apps.core.models import Timestamped


class Cliente(Timestamped):
    ragione_sociale = models.CharField(max_length=200)
    codice = models.CharField(max_length=20, unique=True, help_text="Codice cliente interno")
    partita_iva = models.CharField("partita IVA", max_length=20, blank=True)
    codice_fiscale = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    pec = models.EmailField("PEC", blank=True)
    telefono = models.CharField(max_length=40, blank=True)
    indirizzo = models.CharField(max_length=200, blank=True)
    citta = models.CharField("città", max_length=100, blank=True)
    note = models.TextField(blank=True)
    attivo = models.BooleanField(default=True)

    class Meta:
        ordering = ["ragione_sociale"]
        verbose_name_plural = "clienti"

    def __str__(self):
        return self.ragione_sociale

    def contratto_attivo(self, data=None):
        from django.utils import timezone

        data = data or timezone.localdate()
        return (
            self.contratti.filter(attivo=True, data_inizio__lte=data, data_fine__gte=data)
            .select_related("livello_sla")
            .order_by("-data_fine")
            .first()
        )


class Sede(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="sedi")
    nome = models.CharField(max_length=120, help_text="Es. Magazzino Nord, Filiale Milano")
    indirizzo = models.CharField(max_length=200)
    citta = models.CharField("città", max_length=100)
    provincia = models.CharField(max_length=4, blank=True)
    cap = models.CharField("CAP", max_length=10, blank=True)
    referente = models.CharField(max_length=120, blank=True)
    telefono = models.CharField(max_length=40, blank=True)
    orari_accesso = models.CharField("orari di accesso", max_length=200, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "sedi"
        ordering = ["cliente", "nome"]

    def __str__(self):
        return f"{self.cliente} – {self.nome} ({self.citta})"


class Contatto(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="contatti")
    nome = models.CharField(max_length=80)
    cognome = models.CharField(max_length=80, blank=True)
    ruolo = models.CharField(max_length=80, blank=True)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=40, blank=True)
    principale = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "contatti"
        ordering = ["cliente", "-principale", "cognome"]

    def __str__(self):
        return f"{self.nome} {self.cognome}".strip()
