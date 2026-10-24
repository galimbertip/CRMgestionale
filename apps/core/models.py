from django.contrib.auth.models import AbstractUser
from django.db import models


class Utente(AbstractUser):
    class Ruolo(models.TextChoices):
        RESPONSABILE = "responsabile", "Responsabile assistenza"
        TECNICO = "tecnico", "Tecnico"
        COMMERCIALE = "commerciale", "Commerciale / prevendita"
        CLIENTE = "cliente", "Cliente (portale)"

    ruolo = models.CharField(max_length=20, choices=Ruolo.choices, default=Ruolo.TECNICO)
    cliente = models.ForeignKey(
        "anagrafica.Cliente",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="utenti_portale",
        help_text="Solo per utenti del portale: l'azienda di cui vedono i ticket.",
    )
    telefono = models.CharField(max_length=40, blank=True)

    class Meta:
        verbose_name = "utente"
        verbose_name_plural = "utenti"

    @property
    def is_cliente(self):
        return self.ruolo == self.Ruolo.CLIENTE

    @property
    def is_interno(self):
        return not self.is_cliente and self.is_active

    def __str__(self):
        return self.get_full_name() or self.username


class Numeratore(models.Model):
    """Contatori progressivi annuali per i codici documento (TK-2026-00001, RI-2026-0001...)."""

    prefisso = models.CharField(max_length=10)
    anno = models.PositiveIntegerField()
    ultimo = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("prefisso", "anno")
        verbose_name_plural = "numeratori"

    @classmethod
    def prossimo(cls, prefisso, anno, cifre=5):
        from django.db import transaction

        with transaction.atomic():
            num, _ = cls.objects.select_for_update().get_or_create(prefisso=prefisso, anno=anno)
            num.ultimo += 1
            num.save(update_fields=["ultimo"])
        return f"{prefisso}-{anno}-{num.ultimo:0{cifre}d}"


class Timestamped(models.Model):
    creato_il = models.DateTimeField(auto_now_add=True)
    aggiornato_il = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
