# galaxy-backup-mac

Toolkit per fare il backup locale di uno smartphone Samsung Galaxy su macOS, senza
passare dal cloud, e per prepararlo a un reset di fabbrica con cambio di account Google.

Nato per un **Galaxy A31**, ma funziona con qualsiasi Galaxy (e in generale con
qualsiasi dispositivo Android che supporti adb).

---

## Il problema

macOS non parla nativamente con Android. Android File Transfer di Google è
abbandonato e problematico sui Mac recenti. Le alternative grafiche esistono ma non
sono automatizzabili. Questo repo risolve entrambe le cose:

- **installazione** degli strumenti giusti con un solo script
- **backup incrementale** da terminale, ripetibile e schedulabile

## Cosa contiene

```
galaxy-backup-mac/
├── README.md
├── LICENSE
├── AGENTS.md                       # vincoli e convenzioni del progetto
├── scripts/
│   ├── setup-android-mac.sh        # installa Homebrew, OpenMTP, adb
│   └── backup-android.sh           # backup incrementale via adb
├── launchd/
│   └── local.backup-galaxy.plist   # schedulazione settimanale
├── mcp/
│   ├── server.py                   # server MCP, in sola lettura
│   └── tests/                      # suite pytest, gira senza telefono
└── docs/
    ├── device-galaxy-a31.md        # scheda del dispositivo, limiti noti
    ├── wallpaper-recovery.md       # come recuperare sfondo e lock screen
    ├── mcp-verifica-manuale.md     # cosa provare col telefono collegato
    └── pre-reset-checklist.md      # cosa fare PRIMA del factory reset
```

---

## Avvio rapido

```bash
git clone https://github.com/albertorugnone/galaxy-backup-mac.git
cd galaxy-backup-mac
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
./scripts/backup-android.sh ~/Backup-Galaxy
```

## Le due strade, e quando usarle

| | Samsung Smart Switch | adb (`backup-android.sh`) | OpenMTP |
|---|---|---|---|
| Cosa salva | tutto: SMS, contatti, impostazioni, app | file multimediali e documenti | quello che trascini |
| Automatizzabile | ❌ solo GUI, formato proprietario | ✅ | ❌ solo GUI |
| Incrementale | ❌ | ✅ | ❌ |
| Quando | una volta, prima del reset | backup ricorrente | copie occasionali |

**Ordine consigliato:** backup completo con Smart Switch → disinstalla Smart Switch →
installa OpenMTP → usa `backup-android.sh` per la routine.

### ⚠️ Smart Switch e OpenMTP sono incompatibili

Smart Switch installa un'estensione di sistema che intercetta il protocollo MTP e
impedisce a OpenMTP di rilevare il dispositivo. Gli sviluppatori di OpenMTP
raccomandano di disinstallarlo. Vedi
<https://github.com/ganeshrvel/openmtp#troubleshooting>.

Smart Switch **non** è disponibile su Homebrew: va scaricato manualmente da
<https://www.samsung.com/it/apps/smart-switch/>.

---

## Backup automatico settimanale

```bash
mkdir -p ~/Scripts ~/Library/Logs
cp scripts/backup-android.sh ~/Scripts/
chmod +x ~/Scripts/backup-android.sh

# il sed va fatto sulla COPIA, non sul file versionato
cp launchd/local.backup-galaxy.plist ~/Library/LaunchAgents/
sed -i '' "s|TUONOME|$USER|g" ~/Library/LaunchAgents/local.backup-galaxy.plist

launchctl load ~/Library/LaunchAgents/local.backup-galaxy.plist
```

Per disattivarlo: `launchctl unload ~/Library/LaunchAgents/local.backup-galaxy.plist`

Per provarlo subito senza aspettare domenica:

```bash
launchctl kickstart -p gui/$(id -u)/local.backup-galaxy
cat ~/Library/Logs/backup-galaxy.err
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
claude mcp add galaxy-backup -- "$PWD/mcp/.venv/bin/python" "$PWD/mcp/server.py"
```

### Claude Desktop

Il file di configurazione su macOS sta in
`~/Library/Application Support/Claude/claude_desktop_config.json`. I percorsi
devono essere **assoluti**: sostituisci `/PERCORSO/DEL/REPO` con l'output di `pwd`
eseguito nella cartella del progetto.

```json
{
  "mcpServers": {
    "galaxy-backup": {
      "command": "/PERCORSO/DEL/REPO/mcp/.venv/bin/python",
      "args": ["/PERCORSO/DEL/REPO/mcp/server.py"]
    }
  }
}
```

Riavvia Claude Desktop dopo la modifica.

### Stato dei backup

I job vivono in `~/.galaxy-backup/jobs/` come file JSON, quindi sopravvivono al
riavvio del server. Un backup avviato via MCP continua anche se il server viene
chiuso. Le schermate catturate finiscono in `~/.galaxy-backup/screenshots/`.

---

## Requisiti

macOS (Intel o Apple Silicon) · Homebrew · cavo USB dati (non solo ricarica) ·
Debug USB attivo sul telefono

Per il server MCP, in più: Python 3.10+ e uv.

## Licenza

MIT
