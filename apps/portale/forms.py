from pathlib import Path

from django import forms

from apps.assistenza.models import Priorita, Ticket

ESTENSIONI = {".jpg", ".jpeg", ".png", ".pdf", ".txt", ".log", ".zip", ".heic", ".mp4"}
MAX_MB = 10


def valida_allegato(f):
    if not f:
        return f
    if Path(f.name).suffix.lower() not in ESTENSIONI:
        raise forms.ValidationError("Formato non ammesso. Usa: " + ", ".join(sorted(ESTENSIONI)))
    if f.size > MAX_MB * 1024 * 1024:
        raise forms.ValidationError(f"File troppo grande (massimo {MAX_MB} MB).")
    return f


class ApriTicketForm(forms.Form):
    nome = forms.CharField(label="Nome e cognome", max_length=120)
    email = forms.EmailField()
    telefono = forms.CharField(max_length=40, required=False, help_text="Per essere richiamati più in fretta")
    azienda = forms.CharField(label="Azienda", max_length=200, required=False)
    matricola = forms.CharField(
        label="Matricola apparato", max_length=80, required=False,
        help_text="La trovi sull'etichetta dell'apparato. Se non la conosci lascia vuoto.",
    )
    categoria = forms.ChoiceField(choices=Ticket.Categoria.choices, initial=Ticket.Categoria.GUASTO)
    priorita = forms.ChoiceField(
        label="Urgenza", choices=Priorita.choices, initial=Priorita.MEDIA,
        help_text="«Critica» solo se l'impianto è fermo e il servizio è bloccato.",
    )
    oggetto = forms.CharField(max_length=200, label="In breve")
    descrizione = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 6}), label="Descrizione",
        help_text="Cosa succede, da quando, eventuali messaggi di errore.",
    )
    allegato = forms.FileField(required=False, validators=[valida_allegato],
                               help_text=f"Foto o file, massimo {MAX_MB} MB")
    privacy = forms.BooleanField(label="Acconsento al trattamento dei dati per gestire la richiesta")
    # honeypot anti-spam: deve restare vuoto
    sito_web = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1",
                                                                             "autocomplete": "off"}))

    def __init__(self, *args, utente=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.utente = utente
        if utente and utente.is_authenticated and utente.is_cliente:
            for campo in ("nome", "email", "azienda", "privacy"):
                self.fields[campo].required = False
                self.fields[campo].widget = forms.HiddenInput()

    def clean_sito_web(self):
        if self.cleaned_data.get("sito_web"):
            raise forms.ValidationError("Richiesta non valida.")
        return ""


class RispostaForm(forms.Form):
    testo = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), label="Il tuo messaggio")
    allegato = forms.FileField(required=False, validators=[valida_allegato])
