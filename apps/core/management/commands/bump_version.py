"""Incrementa la versione e apre la nuova voce nel CHANGELOG.

Uso:  python manage.py bump_version patch|minor|major [--nota "testo"] [--sezione Corretto]
"""
from datetime import date

from django.core.management.base import BaseCommand

from apps.core import versioning

SEZIONI = ["Aggiunto", "Modificato", "Corretto", "Rimosso", "Sicurezza"]


class Command(BaseCommand):
    help = "Incrementa VERSION (maior.minor.patch) e aggiunge la voce nel CHANGELOG.md"

    def add_arguments(self, parser):
        parser.add_argument("parte", choices=["major", "minor", "patch"])
        parser.add_argument("--nota", action="append", default=[], help="Voce di changelog (ripetibile)")
        parser.add_argument("--sezione", choices=SEZIONI, default=None)

    def handle(self, parte, nota, sezione, **opts):
        old = versioning.read_version()
        new = versioning.bump(old, parte)
        sezione = sezione or {"patch": "Corretto", "minor": "Aggiunto", "major": "Modificato"}[parte]
        voci = "\n".join(f"- {n}" for n in nota) or "- (descrivere le modifiche)"
        blocco = f"## [{new}] - {date.today().isoformat()}\n\n### {sezione}\n{voci}\n\n"

        text = versioning.CHANGELOG_FILE.read_text(encoding="utf-8")
        idx = text.find("\n## ")
        text = text + "\n" + blocco if idx == -1 else text[: idx + 1] + blocco + text[idx + 1 :]
        versioning.CHANGELOG_FILE.write_text(text, encoding="utf-8")
        versioning.VERSION_FILE.write_text(new + "\n", encoding="utf-8")
        versioning.get_version.cache_clear()
        self.stdout.write(self.style.SUCCESS(f"V{old} -> V{new}"))
