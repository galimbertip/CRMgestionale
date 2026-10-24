# Changelog

Tutte le modifiche rilevanti a GPverse CRM sono registrate qui.
Formato: versioni `V.maior.minor.patch` (Semantic Versioning).

- **maior**: cambi incompatibili (dati, flussi, API)
- **minor**: nuove funzioni compatibili
- **patch**: correzioni

## [0.3.0] - 2026-10-24

### Aggiunto
- Preventivi per nuova installazione, riparazione, intervento e contratto, con righe da articoli, sconti, IVA e stampa PDF.
- Accettazione o rifiuto del preventivo dal portale cliente; l'accettazione porta la commessa in produzione (o la crea) e approva la riparazione.
- Revisioni del preventivo con nuovo link al cliente.
- Magazzino in sede con area nuovo e area riparazioni (merce del cliente), movimenti, giacenze e scorte minime.
- Distinta base e ordini di produzione: la conferma impegna il materiale, il completamento scarica i componenti, carica il prodotto e crea gli apparati della commessa.
- Riparazioni a matricola con stati, ricambi scaricati dal magazzino, scheda stampabile e preventivo di riparazione in un clic.
- I ricambi del rapportino d'intervento scelti da articolo vengono scaricati dal magazzino.
- Cruscotto con preventivi in attesa, riparazioni in corso, articoli da riordinare e produzione in corso.

## [0.2.0] - 2026-10-24

### Aggiunto
- Gestione utenti a tre livelli: admin, tecnico, cliente, con permessi applicati automaticamente dal livello.
- Menu Utenti riservato agli admin; creazione utenti con o senza password e invio automatico del link per impostarla.
- I clienti possono essere limitati a vedere solo i propri ticket invece di tutti quelli dell'azienda.
- Nei campi tecnico/assegnato a si scelgono solo utenti interni.

## [0.1.0] - 2026-10-24

### Aggiunto
- Prima release del CRM gestionale per l'assistenza tecnica sotto etichetta GPverse.
- Anagrafica clienti con sedi e contatti.
- Commesse con fasi prevendita, produzione e post-vendita, anche ereditate da terzi.
- Modulo sopralluogo prevendita con checklist da modello, foto ed esito di fattibilità.
- Modulo collaudo installazione con checklist, esito e firma del cliente.
- Parco installato: apparati con matricola, sede, commessa e contratto collegati.
- Contratti di assistenza con livelli SLA per priorità e avviso di scadenza.
- Ticket con calcolo automatico delle scadenze SLA (presa in carico e risoluzione).
- Rapportino d'intervento con ore, viaggio, km, ricambi, firma cliente e stampa PDF.
- Portale cliente: apertura ticket da form pubblico, link di consultazione senza account,
  storico dei ticket dell'azienda per gli utenti registrati, risposte ai ticket.
- Cruscotto tecnico con ticket ordinati per scadenza SLA.
- Numero di versione nel piè di pagina e registro versioni consultabile nell'app.
- Comando `bump_version` per incrementare la versione e aprire la voce di changelog.
- Deploy Docker per PC Linux e Raspberry Pi (arm64).
