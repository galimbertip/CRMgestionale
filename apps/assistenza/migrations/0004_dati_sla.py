"""Livelli SLA di partenza (ore: presa in carico / risoluzione). Modificabili dall'admin."""
from django.db import migrations

LIVELLI = [
    # nome, solo_lavorativo, predefinito, {priorita: (presa, risoluzione)}
    ("Senza contratto", True, True,
     {"critica": (8, None), "alta": (16, None), "media": (24, None), "bassa": (40, None)}),
    ("Base", True, False,
     {"critica": (4, 24), "alta": (8, 40), "media": (16, 80), "bassa": (24, 120)}),
    ("Standard", True, False,
     {"critica": (2, 8), "alta": (4, 16), "media": (8, 40), "bassa": (16, 80)}),
    ("Premium 24/7", False, False,
     {"critica": (1, 4), "alta": (2, 8), "media": (4, 24), "bassa": (8, 72)}),
]


def crea(apps, schema_editor):
    Livello = apps.get_model("assistenza", "LivelloSLA")
    Regola = apps.get_model("assistenza", "RegolaSLA")
    for nome, lavorativo, predefinito, regole in LIVELLI:
        liv = Livello.objects.create(nome=nome, solo_orario_lavorativo=lavorativo, predefinito=predefinito)
        for prio, (presa, ris) in regole.items():
            Regola.objects.create(livello=liv, priorita=prio, ore_presa_in_carico=presa, ore_risoluzione=ris)


class Migration(migrations.Migration):
    dependencies = [("assistenza", "0003_initial")]
    operations = [migrations.RunPython(crea, migrations.RunPython.noop)]
