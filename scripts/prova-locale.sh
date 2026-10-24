#!/usr/bin/env bash
# Installa e avvia GPverse CRM in locale per provarlo (Linux Mint / Ubuntu / Debian).
# Uso:  bash scripts/prova-locale.sh            (dalla cartella del progetto)
#       bash scripts/prova-locale.sh --reset    (ricomincia da un database vuoto con i dati demo)
set -euo pipefail

cd "$(dirname "$0")/.."
echo "== GPverse CRM · prova locale in $(pwd)"

# su Debian/Mint "venv" esiste anche senza il pacchetto python3-venv, ma poi fallisce: controllo ensurepip
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  PYV=$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
  echo "== Installo python3-venv (serve la password di sudo)"
  sudo apt-get update -qq && sudo apt-get install -y python3-venv "python${PYV}-venv"
fi

# un .venv creato a metà da un tentativo precedente va rifatto
if [ -d .venv ] && [ ! -f .venv/bin/activate ]; then
  echo "== Rimuovo un ambiente .venv incompleto"
  rm -rf .venv
fi
if [ ! -d .venv ]; then
  echo "== Creo l'ambiente Python (.venv)"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate

echo "== Installo le dipendenze"
pip install -q --upgrade pip
pip install -q -r requirements-dev.txt

if [ "${1:-}" = "--reset" ]; then
  echo "== Reset: cancello il database di prova"
  rm -f db.sqlite3
  rm -rf media
fi

echo "== Preparo il database"
python manage.py migrate -v0
python manage.py demo

echo "== Eseguo i test automatici"
pytest -q || { echo "!! Alcuni test non passano: mandami l'output qui sopra"; exit 1; }

echo
echo "================================================================"
echo " Pronto! Apri il browser su  http://localhost:8000"
echo
echo "  Admin    : admin    / demo-admin-2026"
echo "  Tecnico  : tecnico  / demo-tecnico-2026"
echo "  Cliente  : giulia@logisticarapida.example / demo-cliente-2026"
echo
echo "  Portale clienti : http://localhost:8000/assistenza/"
echo "  Dal telefono (stessa rete o Tailscale): http://$(hostname -I | awk '{print $1}'):8000"
echo
echo "  Le email (conferme ticket, link password) compaiono in QUESTO terminale."
echo "  Per fermare il server: Ctrl+C"
echo "================================================================"
python manage.py runserver 0.0.0.0:8000
