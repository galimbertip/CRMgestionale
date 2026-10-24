# Guida al test di GPverse CRM

Avvio: `bash scripts/prova-locale.sh` (aggiungi `--reset` per ripartire da zero).
Usa una finestra normale per un utente e una **finestra anonima** (Ctrl+Shift+N) per un altro,
così puoi essere admin e cliente contemporaneamente. Le email finiscono nel terminale del server.

## 1. Versione
- [ ] In fondo a ogni pagina c'è **V0.2.0**; cliccandola si apre il registro versioni con 0.2.0 e 0.1.0.

## 2. Cliente anonimo apre un ticket
Finestra anonima, non loggato → http://localhost:8000/assistenza/
- [ ] Compila con email `giulia@logisticarapida.example`, matricola `GPL24-001`, urgenza Critica.
- [ ] Ricevi il codice `TK-…`; nel terminale c'è l'email di conferma con il link.
- [ ] Riprova con un'email sconosciuta e matricola `GPL24-001`: il ticket va "da smistare"
      (la matricola non viene collegata a un cliente che non sei tu).

## 3. Admin gestisce il ticket
Finestra normale → login `admin` → Cruscotto
- [ ] Il ticket critico è in cima alla coda SLA, con la scadenza calcolata.
- [ ] Aprilo, cambia stato in "Preso in carico", scrivi una risposta e una **nota interna**.
- [ ] Nel terminale parte l'email al cliente (solo per la risposta, non per la nota).

## 4. Cliente risponde dal link
Finestra anonima → apri il link del ticket (dall'email nel terminale)
- [ ] Vedi la risposta, **non** vedi la nota interna.
- [ ] Rispondi con un allegato (una foto): il ticket torna "In lavorazione".
- [ ] Da admin segnalo "Risolto" → da cliente premi "Confermo, è risolto" → chiuso.

## 5. Cliente registrato e storico
Finestra anonima → Accedi con `giulia@logisticarapida.example` / `demo-cliente-2026`
- [ ] "I miei ticket" mostra solo i ticket di Logistica Rapida, non quelli del Condominio.
- [ ] In fondo c'è l'elenco dei vostri apparati.
- [ ] Nuova richiesta: nome ed email non vengono chiesti (sei già riconosciuta).
- [ ] Da admin, nella scheda di Giulia togli "vede tutti i ticket dell'azienda":
      ora lei vede solo quelli aperti da lei.

## 6. Livelli utente
Login `tecnico` / `demo-tecnico-2026`
- [ ] Non c'è il menu **Utenti**; Contratti, Livelli SLA e Modelli di checklist sono in sola lettura.
- [ ] Può creare ticket e rapportini ma non cancellare nulla.
- [ ] Nel campo "Assegnato a" compaiono solo admin e tecnici, mai i clienti.

Login `admin` → Utenti → Aggiungi
- [ ] Crea un cliente **senza azienda**: viene rifiutato.
- [ ] Crea un cliente con azienda e "senza password": nel terminale arriva il link per impostarla;
      aprilo, scegli la password e accedi al portale.
- [ ] Crea un tecnico e verifica che entri nel back-office.
- [ ] Nella tua scheda non puoi cambiare il tuo livello né disattivarti.

## 7. Lavoro sul campo (meglio dal telefono)
Dal telefono apri `http://<ip-del-pc>:8000` (stessa Wi-Fi o Tailscale), login `tecnico`
- [ ] Back-office → Rapportini → apri RI-… → **Raccogli firma cliente**: firma col dito e conferma.
- [ ] **Stampa / PDF**: la firma compare nel documento; salva in PDF.
- [ ] Nuovo **sopralluogo** su "Ampliamento Hub Sud": la checklist si compila da sola,
      segna le voci, aggiungi una foto, stampa.
- [ ] Nuovo **collaudo** con 1 apparato ed esito "Superato": l'apparato passa "In servizio".

## 8. Contratti e SLA
- [ ] Cruscotto → "Contratti in scadenza" mostra CA-2026-001 (tra ~45 giorni).
- [ ] Livelli SLA → cambia le ore di "Standard / Alta" → su un ticket usa l'azione
      "Ricalcola scadenze SLA" e verifica la nuova scadenza.

Se qualcosa non torna, annota il punto (es. "5.3") e cosa vedi: lo sistemo nella prossima patch.
