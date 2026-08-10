# android-backup-mac

Toolkit per fare il backup locale di uno smartphone Android su macOS, senza passare
dal cloud, e per prepararlo a un reset di fabbrica con cambio di account Google.

Funziona con **qualsiasi dispositivo Android** che supporti adb: le cartelle che
copia (`DCIM`, `Pictures`, `Download`, `Movies`, `Music`, `Documents`) sono quelle
standard di Android, e i comandi usati sono AOSP, non specifici di una marca.

Le note che valgono solo per un produttore stanno a parte: per i Samsung, in
[docs/vendor-samsung.md](docs/vendor-samsung.md).

---

## Il problema

macOS non parla nativamente con Android. Android File Transfer di Google è
abbandonato e problematico sui Mac recenti. Le alternative grafiche esistono ma non
sono automatizzabili. Questo repo risolve entrambe le cose:

- **installazione** degli strumenti giusti con un solo script
- **backup incrementale** da terminale, ripetibile e schedulabile

## Cosa contiene

```
android-backup-mac/
├── README.md
├── LICENSE
├── AGENTS.md                       # vincoli e convenzioni del progetto
├── scripts/
│   ├── setup-android-mac.sh        # installa Homebrew, OpenMTP, adb
│   └── backup-android.sh           # backup incrementale via adb
├── launchd/
│   └── local.backup-android.plist   # schedulazione settimanale
├── mcp/
│   ├── server.py                   # server MCP, in sola lettura
│   └── tests/                      # suite pytest, gira senza telefono
└── docs/
    ├── wallpaper-recovery.md       # come recuperare sfondo e lock screen
    ├── mcp-verifica-manuale.md     # cosa provare col telefono collegato
    ├── pre-reset-checklist.md      # cosa fare PRIMA del factory reset
    └── vendor-samsung.md           # note valide solo per i Galaxy (opzionale)
```

---

## Avvio rapido

```bash
git clone https://github.com/albertorugnone/android-backup-mac.git
cd android-backup-mac
chmod +x scripts/*.sh

# 1. Installa gli strumenti
./scripts/setup-android-mac.sh

# 2. Sul telefono: abilita le Opzioni sviluppatore e il Debug USB
#    (Impostazioni > Info sul telefono > Informazioni software
#     > tocca "Numero build" 7 volte, poi Opzioni sviluppatore > Debug USB)

# 3. Collega il cavo, sblocca lo schermo, autorizza il Mac
adb devices

# 4. Prova a vuoto, poi lancia sul serio
DRY_RUN=1 ./scripts/backup-android.sh
./scripts/backup-android.sh ~/Backup-Android
```

## Le due strade, e quando usarle

| | adb (`backup-android.sh`) | OpenMTP |
|---|---|---|
| Cosa salva | file multimediali e documenti | quello che trascini |
| Automatizzabile | ✅ | ❌ solo GUI |
| Incrementale | ✅ | ❌ |
| Quando | backup ricorrente | copie occasionali |

Nessuna delle due copre SMS, contatti, impostazioni e dati delle app: quelli stanno
in `/data/`, fuori portata senza root. Per averli serve l'utility del produttore
(su Samsung è Smart Switch), che è GUI-only e in formato proprietario — quindi
fuori dal perimetro di questo toolkit.

### ⚠️ Utility dei produttori e MTP

Alcune utility desktop dei produttori installano un'estensione di sistema che
intercetta MTP e **impedisce a OpenMTP di vedere il telefono**. `setup-android-mac.sh`
le rileva e lo segnala. Il caso documentato è Smart Switch di Samsung, descritto in
[docs/vendor-samsung.md](docs/vendor-samsung.md) insieme alla precauzione da
prendere con adb.

Il backup via adb, che è la strada principale di questo repo, **non è toccato** dal
problema.

---

## Backup automatico settimanale

```bash
mkdir -p ~/Scripts ~/Library/Logs
cp scripts/backup-android.sh ~/Scripts/
chmod +x ~/Scripts/backup-android.sh

# il sed va fatto sulla COPIA, non sul file versionato
cp launchd/local.backup-android.plist ~/Library/LaunchAgents/
sed -i '' "s|TUONOME|$USER|g" ~/Library/LaunchAgents/local.backup-android.plist

launchctl load ~/Library/LaunchAgents/local.backup-android.plist
```

Per disattivarlo: `launchctl unload ~/Library/LaunchAgents/local.backup-android.plist`

Per provarlo subito senza aspettare domenica:

```bash
launchctl kickstart -p gui/$(id -u)/local.backup-android
cat ~/Library/Logs/backup-android.err
```

Il plist imposta esplicitamente `PATH` con i percorsi di Homebrew: launchd non
eredita il PATH della shell e senza quella chiave `adb` non verrebbe trovato.

---

## Limiti noti

- **Lo sfondo e la schermata di blocco applicati non sono copiabili.** Android li
  conserva in `/data/system/users/0/`, accessibile solo con root. Vedi
  [docs/wallpaper-recovery.md](docs/wallpaper-recovery.md) per l'aggiramento.
- `adb pull` viene eseguito un file alla volta: il primo backup di una libreria
  grande può richiedere parecchio tempo. I successivi sono rapidi.
- I dati delle app (`/data/data/`) non sono accessibili senza root. Per WhatsApp usa
  il backup locale dell'app più la copia di `Android/media/com.whatsapp`.
- Lo script non cancella nulla: è un backup additivo, non un mirror.
- Il confronto è per nome **e dimensione**: un file rimasto a metà da una copia
  interrotta viene riconosciuto e riscaricato. Se la toybox del telefono non
  supporta `stat -c`, lo script lo segnala e ricade sul confronto per sola
  presenza del file.
- `backup-android.sh` esce con codice 1 se almeno una copia è fallita, così il
  backup schedulato può essere monitorato.

---

## Server MCP (opzionale)

`mcp/server.py` espone il backup a un assistente AI attraverso cinque operazioni
tipizzate: `device_status`, `backup_inventory`, `backup_start`, `backup_status`,
`capture_screen`.

**È in sola lettura sul telefono.** Non può cancellare file, non può installare o
rimuovere app, non espone `adb shell` né alcun tool generico di esecuzione
comandi. Il backup lo avvia soltanto verso una destinazione dentro la tua
cartella utente.

Il senso non è dare nuove capacità — gli script si lanciano già da terminale — ma
*restringere* ciò che un assistente può fare: senza MCP, un agente con accesso a
bash ha di fatto `adb shell`, cioè esecuzione arbitraria sul dispositivo.

> **Nota onesta sul confinamento.** La restrizione vale solo dove l'assistente non
> ha *anche* un accesso a bash. In un client che espone un tool shell (come Claude
> Code nella configurazione predefinita) l'MCP è una comodità, non una barriera:
> per ottenere il confinamento vero va negato l'accesso a bash, oppure va usato un
> client che non ce l'ha, come Claude Desktop.

### Installazione

Richiede Python 3.10+ e [uv](https://docs.astral.sh/uv/). Le dipendenze stanno in
un virtualenv locale al progetto, niente installazioni globali:

```bash
uv venv --python 3.12 mcp/.venv
VIRTUAL_ENV=mcp/.venv uv pip install mcp==2.0.0 pytest==9.1.1
mcp/.venv/bin/python -m pytest mcp      # 56 test, non serve il telefono
```

### Claude Code

```bash
claude mcp add android-backup -- "$PWD/mcp/.venv/bin/python" "$PWD/mcp/server.py"
```

### Claude Desktop

Il file di configurazione su macOS sta in
`~/Library/Application Support/Claude/claude_desktop_config.json`. I percorsi
devono essere **assoluti**: sostituisci `/PERCORSO/DEL/REPO` con l'output di `pwd`
eseguito nella cartella del progetto.

```json
{
  "mcpServers": {
    "android-backup": {
      "command": "/PERCORSO/DEL/REPO/mcp/.venv/bin/python",
      "args": ["/PERCORSO/DEL/REPO/mcp/server.py"]
    }
  }
}
```

Riavvia Claude Desktop dopo la modifica.

### Stato dei backup

I job vivono in `~/.android-backup/jobs/` come file JSON, quindi sopravvivono al
riavvio del server. Un backup avviato via MCP continua anche se il server viene
chiuso. Le schermate catturate finiscono in `~/.android-backup/screenshots/`.

---

## Requisiti

macOS (Intel o Apple Silicon) · Homebrew · cavo USB dati (non solo ricarica) ·
Debug USB attivo sul telefono

Per il server MCP, in più: Python 3.10+ e uv.

## Licenza

MIT
