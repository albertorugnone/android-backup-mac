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
└── docs/
    ├── device-galaxy-a31.md        # scheda del dispositivo, limiti noti
    ├── wallpaper-recovery.md       # come recuperare sfondo e lock screen
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

## Requisiti

macOS (Intel o Apple Silicon) · Homebrew · cavo USB dati (non solo ricarica) ·
Debug USB attivo sul telefono

## Licenza

MIT
