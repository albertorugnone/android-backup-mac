# Contesto per assistenti di sviluppo AI

Istruzioni e vincoli di progetto per chi lavora su questo repository con l'ausilio
di un assistente di codice.

## Cos'è questo progetto

Toolkit bash per macOS che automatizza il backup locale di uno smartphone Samsung
Galaxy e la preparazione a un factory reset con cambio di account Google.

Utente di riferimento: possessore di un Galaxy A31 su Mac, obiettivo finale
resettare il telefono e associarvi un account Google personale diverso da quello
attuale.

## Vincoli tecnici da rispettare

Questi non sono preferenze, sono limiti reali dell'ambiente. Non proporre soluzioni
che li ignorano.

1. **macOS non supporta MTP nativamente.** Non esiste un mount del filesystem del
   telefono. `libmtp` e `simple-mtpfs` su macOS richiedono macFUSE, che su Apple
   Silicon con SIP attivo è fragile: evitali.
2. **adb è l'unica via affidabile per lo scripting.** Ogni automazione passa da lì.
3. **Smart Switch non ha CLI.** Il suo backup è GUI-only e in formato proprietario:
   non è automatizzabile. Non scrivere script che pretendono di pilotarlo.
4. **Smart Switch e OpenMTP non convivono.** Smart Switch installa un'estensione di
   sistema che rompe MTP per le altre app.
5. **Niente root.** Il dispositivo non è rootato. Tutto ciò che sta in
   `/data/data/` e `/data/system/` è fuori portata.
6. **`adb shell` introduce CRLF.** Usare `adb exec-out` per l'output da parsare, con
   `tr -d '\r'` come rete di sicurezza.

## Convenzioni del codice

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

Non c'è una suite di test. Prima di considerare finito un intervento:

```bash
bash -n scripts/*.sh              # controllo sintassi
shellcheck scripts/*.sh           # se disponibile
DRY_RUN=1 ./scripts/backup-android.sh   # richiede un telefono collegato
```

Gli script vanno testati su macOS con un dispositivo reale: in CI non è possibile.
Se non puoi testare, dichiaralo esplicitamente invece di dare per riuscito.

## Idee di sviluppo

- [ ] Modalità `--mirror` che segnala (senza cancellare) i file spariti dal telefono
- [ ] Deduplica per hash invece che per sola esistenza del path
- [x] Verifica di integrità post-copia (confronto dimensione o checksum) — fatto:
      confronto per dimensione via `comm`, con fallback se il device non ha `stat -c`
- [ ] Batch dei `adb pull` via `tar` su `exec-out` per velocizzare il primo backup
- [ ] Notifica macOS a fine backup (`osascript -e 'display notification ...'`)
- [ ] Supporto backup su volume esterno con controllo che sia montato
- [ ] Variante wireless con `adb connect` su rete locale

## Cosa NON fare

- Non aggiungere dipendenze da app a pagamento (MacDroid, AnyTrans e simili).
- Non suggerire il caricamento automatico su cloud: il punto del progetto è che il
  backup resti locale.
- Non scrivere codice che assuma il root o l'accesso a `/data/`.
- Non lasciare attivo il Debug USB come raccomandazione permanente: va revocato a
  fine lavoro, e la documentazione deve dirlo.
