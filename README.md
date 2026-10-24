# GPverse CRM

CRM gestionale per un reparto di assistenza tecnica che segue un prodotto **dalla prevendita alla
produzione all'assistenza post-vendita** — anche quando una commessa arriva già venduta da altri e
se ne prende in carico solo l'assistenza. Un prodotto dell'etichetta software **GPverse**.

Versione corrente: vedi [`VERSION`](VERSION) · registro modifiche: [`CHANGELOG.md`](CHANGELOG.md)
(consultabile anche nell'app alla pagina **/versioni/**, il numero è nel piè di pagina).

## Cosa fa

| Fase | Moduli |
|---|---|
| Prevendita | Commessa, **sopralluogo** con checklist da modello, foto, esito di fattibilità e opere preliminari |
| Produzione | **Collaudo installazione** con checklist, apparati collaudati, esito/riserve, firma cliente |
| Post-vendita | **Ticket** con SLA, **rapportino d'intervento** (ore, viaggio, km, ricambi, firma), contratti |
| Trasversale | Anagrafica clienti/sedi/contatti, **parco installato** per matricola, **contratti di assistenza** con livelli SLA, cruscotto tecnico |

**Portale cliente** (`/assistenza/`)
- chiunque apre un ticket dal form pubblico (con antispam) e riceve via email codice e link personale;
- dal link segue lo stato, legge le risposte (le note interne restano nascoste), risponde, conferma la risoluzione;
- il cliente registrato vede lo **storico dei ticket della propria azienda** e il proprio parco installato;
- i richiedenti anonimi vengono associati al cliente tramite l'email dei contatti; la matricola viene
  collegata solo se appartiene a quel cliente, altrimenti il ticket finisce "da smistare".

**SLA**: ogni livello definisce i tempi di presa in carico e risoluzione per priorità, in orario
lavorativo (lun–ven 8–18, configurabile) o 24/7. Il ticket eredita il livello dal contratto attivo
del cliente o dell'apparato; senza contratto usa il livello "Senza contratto".

**Sul campo** il tecnico apre il rapportino/collaudo/sopralluogo dal telefono, fa firmare il cliente
col dito (*Raccogli firma cliente*) e stampa o salva il PDF dal browser.

## Prova in locale (2 minuti)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py demo          # dati di esempio
python manage.py runserver
```

- Back-office / cruscotto: http://localhost:8000 → `admin` / `demo-admin-2026`
- Portale cliente: http://localhost:8000/assistenza/ → `giulia@logisticarapida.example` / `demo-cliente-2026`

Test: `pytest`

## Installazione su PC di casa o Raspberry Pi

Requisiti: Raspberry Pi 4/5 con **sistema a 64 bit** (o qualsiasi PC Linux) e Docker.

```bash
curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker $USER   # poi ri-accedi
git clone https://github.com/galimbertip/CRMgestionale.git && cd CRMgestionale
cp .env.example .env && nano .env      # SECRET_KEY, DB_PASSWORD, admin, email
docker compose up -d --build
```

L'app è su `http://<ip>:8000`. Il database PostgreSQL e i file caricati stanno in volumi Docker;
il servizio `backup` salva un dump giornaliero in `./backup` (14 giorni). Consiglio: copia
periodicamente `./backup` fuori dal Pi (la scheda SD è il punto debole: meglio un SSD USB).

### Renderlo raggiungibile

- **Tecnici** (cruscotto/back-office): via **Tailscale**, senza aprire porte sul router.
- **Clienti** (portale pubblico): via **Cloudflare Tunnel** verso un tuo dominio, che dà anche l'HTTPS:
  `cloudflared tunnel --url http://localhost:8000` per una prova, poi un tunnel nominato su
  `crm.tuodominio.it`. Imposta `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` e `PUBLIC_BASE_URL` di conseguenza.
- Solo rete locale/Tailscale in http: metti `SECURE_COOKIES=false`.

### Aggiornare

```bash
git pull && docker compose up -d --build     # le migrazioni partono da sole
```

## Versioni

Schema **V.maior.minor.patch**: maior = cambi incompatibili, minor = nuove funzioni, patch = correzioni.
Per rilasciare:

```bash
python manage.py bump_version minor --nota "Aggiunto export Excel dei rapportini"
git commit -am "V0.2.0" && git tag v0.2.0 && git push --follow-tags
```

Il comando aggiorna `VERSION` e apre la voce in `CHANGELOG.md`; un test verifica che i due siano allineati.

## Primi passi dopo l'installazione

1. Back-office → **Livelli SLA**: rivedi i tempi proposti (Base, Standard, Premium 24/7, Senza contratto).
2. **Modelli di checklist**: adatta le voci di sopralluogo e collaudo ai tuoi prodotti.
3. Crea clienti, sedi, contatti; per dare l'accesso al portale seleziona i contatti e usa l'azione
   *Crea accesso al portale* (parte un'email per impostare la password).
4. **Utenti** interni: ruolo Tecnico/Responsabile, flag "staff" e i permessi sui moduli.

## Struttura

```
apps/core        utenti, numerazione documenti, versioning, cruscotto
apps/anagrafica  clienti, sedi, contatti
apps/commesse    commesse, sopralluoghi, collaudi, modelli checklist
apps/assistenza  SLA, contratti, parco installato, ticket, rapportini, firma/stampa
apps/portale     form pubblico, storico ticket, consultazione via link
```
