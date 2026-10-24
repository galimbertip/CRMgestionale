from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class UtenteManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra):
        extra.setdefault("ruolo", "admin")
        return super().create_superuser(username, email, password, **extra)


class Utente(AbstractUser):
    class Ruolo(models.TextChoices):
        ADMIN = "admin", "Amministratore"
        TECNICO = "tecnico", "Tecnico"
        CLIENTE = "cliente", "Cliente (solo portale)"

    ruolo = models.CharField(
        "livello", max_length=20, choices=Ruolo.choices, default=Ruolo.CLIENTE,
        help_text="Amministratore: tutto, compresa la gestione utenti. Tecnico: lavoro operativo, "
                  "senza cancellazioni né gestione di utenti, contratti e SLA. Cliente: solo portale.",
    )
    cliente = models.ForeignKey(
        "anagrafica.Cliente",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="utenti_portale",
        help_text="Solo per i clienti: l'azienda di cui vedono ticket e apparati.",
    )
    vede_ticket_azienda = models.BooleanField(
        "vede tutti i ticket dell'azienda", default=True,
        help_text="Se disattivato, il cliente vede solo i ticket aperti da lui.",
    )
    telefono = models.CharField(max_length=40, blank=True)

    objects = UtenteManager()

    class Meta:
        verbose_name = "utente"
        verbose_name_plural = "utenti"

    def save(self, *args, **kwargs):
        # il livello decide l'accesso: non si gestiscono flag e permessi a mano
        if self.is_superuser:
            self.ruolo = self.Ruolo.ADMIN
        if self.ruolo == self.Ruolo.CLIENTE:
            self.is_staff = False
        else:
            self.is_staff = True
            self.cliente = None
        super().save(*args, **kwargs)
        from .ruoli import allinea_gruppi

        allinea_gruppi(self)

    @property
    def is_cliente(self):
        return self.ruolo == self.Ruolo.CLIENTE

    @property
    def is_tecnico(self):
        return self.ruolo == self.Ruolo.TECNICO

    @property
    def is_admin_crm(self):
        return self.ruolo == self.Ruolo.ADMIN or self.is_superuser

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
