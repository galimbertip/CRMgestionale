# Changelog

Tutte le modifiche rilevanti a GPverse CRM sono registrate qui.
Formato: versioni `V.maior.minor.patch` (Semantic Versioning).

- **maior**: cambi incompatibili (dati, flussi, API)
- **minor**: nuove funzioni compatibili
- **patch**: correzioni

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
