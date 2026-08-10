# Contesto per assistenti di sviluppo AI

Istruzioni e vincoli di progetto per chi lavora su questo repository con l'ausilio
di un assistente di codice.

## Cos'è questo progetto

Toolkit bash per macOS che automatizza il backup locale di uno smartphone Android
e la preparazione a un factory reset con cambio di account Google.

**Il nucleo è Android generico e deve restare tale.** Le cartelle in `REMOTE_DIRS`
sono le costanti standard di Android e i comandi adb usati sono AOSP: non
introdurre dipendenze da una marca specifica in `scripts/`, `mcp/` o nel README.
Ciò che vale per un solo produttore va in una pagina a parte — per Samsung,
`docs/vendor-samsung.md` — e va marcato come opzionale.

Il dispositivo di riferimento su cui è nato il progetto è un Galaxy A31 su Mac,
con l'obiettivo di resettarlo e associarvi un account Google diverso da quello
attuale: la scheda del dispositivo sta nella pagina vendor.

## Vincoli tecnici da rispettare

Questi non sono preferenze, sono limiti reali dell'ambiente. Non proporre soluzioni
che li ignorano.

1. **macOS non supporta MTP nativamente.** Non esiste un mount del filesystem del
   telefono. `libmtp` e `simple-mtpfs` su macOS richiedono macFUSE, che su Apple
   Silicon con SIP attivo è fragile: evitali.
2. **adb è l'unica via affidabile per lo scripting.** Ogni automazione passa da lì.
3. **Le utility dei produttori non hanno CLI.** Smart Switch e simili fanno backup
   GUI-only in formato proprietario: non sono automatizzabili. Non scrivere script
   che pretendono di pilotarle.
4. **Alcune di quelle utility rompono MTP per le altre app**, installando
   un'estensione di sistema che intercetta il protocollo. Il backup via adb non ne
   è toccato. Dettagli in `docs/vendor-samsung.md`.
5. **Niente root.** Il dispositivo non è rootato. Tutto ciò che sta in
   `/data/data/` e `/data/system/` è fuori portata.
6. **`adb shell` introduce CRLF.** Usare `adb exec-out` per l'output da parsare, con
   `tr -d '\r'` come rete di sicurezza.

## Convenzioni del codice

- **Python è ammesso solo dentro `mcp/`.** Tutto il resto del progetto è e resta
  bash: gli script devono funzionare da terminale e da launchd senza interprete
  Python installato.
- **Il server MCP non deve mai reimplementare la logica di backup.** È un wrapper
  sottile che invoca `scripts/backup-android.sh` come sottoprocesso. Una sola
  fonte di verità: se al server serve un dato dallo script (per esempio l'elenco
  delle cartelle), si aggiunge una flag allo script, non una copia nel server.
- **Mai creare `mcp/__init__.py`.** Renderebbe `mcp/` un package regolare che
  oscurerebbe l'SDK omonimo installato nel venv, rompendo ogni import.
- Bash, target `/usr/bin/env bash`. macOS ha bash 3.2 come `/bin/bash`: **non usare
  array associativi, `${var^^}` o altre feature bash 4+.**
- `set -euo pipefail` negli script di setup; negli script di backup si usa
  `set -uo pipefail` senza `-e`, perché un singolo `adb pull` fallito non deve
  abortire l'intero backup.
- Funzioni di output colorato: `info` / `ok` / `warn` / `die`. Riusale, non
  reinventarle.
- Messaggi utente **in italiano**. Commenti nel codice in italiano.
- Ogni operazione distruttiva o lenta deve rispettare `DRY_RUN=1`.
- Quotare sempre le variabili nei path: i nomi file possono contenere spazi.

## Verifica delle modifiche

La parte bash non ha test propri; il server MCP sì, e coprono anche il contratto
con gli script. Prima di considerare finito un intervento:

```bash
bash -n scripts/*.sh              # controllo sintassi
shellcheck scripts/*.sh           # se disponibile
mcp/.venv/bin/python -m pytest mcp      # suite MCP, NON richiede il telefono
DRY_RUN=1 ./scripts/backup-android.sh   # richiede un telefono collegato
```

La suite in `mcp/tests/` copre anche il contratto fra server e script bash
(`--list-dirs`, `STATUS_FILE`) usando un adb finto: se tocchi
`backup-android.sh`, rilanciala.

Gli script vanno testati su macOS con un dispositivo reale: in CI non è possibile.
Quello che richiede il telefono è elencato in `docs/mcp-verifica-manuale.md`.
Se non puoi testare, dichiaralo esplicitamente invece di dare per riuscito.

## Idee di sviluppo

- [x] Server MCP in sola lettura per pilotare i backup da un assistente — fatto:
      cinque tool tipizzati in `mcp/server.py`, wrapper sottile sugli script
- [ ] Indice del backup (`$DEST/.android-backup-index.tsv`) scritto a fine giro:
      **additivo**, mai autorità sui salti. La scansione del filesystem deve
      restare la fonte di verità, altrimenti un indice divergente fa perdere file
      in silenzio. Serve da base per `--mirror` e per la deduplica per hash
- [ ] Modalità `--mirror` che segnala (senza cancellare) i file spariti dal telefono
- [ ] Deduplica per hash invece che per sola esistenza del path
- [x] Verifica di integrità post-copia (confronto dimensione o checksum) — fatto:
      confronto per dimensione via `comm`, con fallback se il device non ha `stat -c`
- [ ] Batch dei `adb pull` via `tar` su `exec-out` per velocizzare il primo backup
- [ ] Notifica macOS a fine backup (`osascript -e 'display notification ...'`)
- [ ] Supporto backup su volume esterno con controllo che sia montato
- [ ] Variante wireless con `adb connect` su rete locale

## Cosa NON fare

- **Non esporre dal server MCP tool generici di esecuzione comandi** (`run_command`,
  `adb_raw` e simili), né passare ad `adb shell` stringhe fornite dal modello.
  Sarebbe la negazione del motivo per cui il server esiste. Restano fuori
  perimetro anche `adb push`, `adb install`, la cancellazione di file, la revoca
  delle autorizzazioni e il factory reset: se sembrano servire, chiedere prima.
- Non aggiungere dipendenze da app a pagamento (MacDroid, AnyTrans e simili).
- Non suggerire il caricamento automatico su cloud: il punto del progetto è che il
  backup resti locale.
- Non scrivere codice che assuma il root o l'accesso a `/data/`.
- Non lasciare attivo il Debug USB come raccomandazione permanente: va revocato a
  fine lavoro, e la documentazione deve dirlo.
