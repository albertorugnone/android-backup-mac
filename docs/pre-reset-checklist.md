# Checklist prima del factory reset

Obiettivo: resettare il telefono e associarlo a un **account Google diverso** da
quello attualmente in uso. Da fare in quest'ordine.

## 1. Backup

- [ ] Backup completo con Samsung Smart Switch (`~/Documenti/Samsung/SmartSwitch/`)
- [ ] **Chiudi Smart Switch e lancia `adb kill-server`** prima di passare al punto
      successivo — e viceversa, prima di riaprire Smart Switch (vedi nota qui sotto)
- [ ] Backup dei media con `./scripts/backup-android.sh`
- [ ] Screenshot dello sfondo e della schermata di blocco → vedi
      [wallpaper-recovery.md](wallpaper-recovery.md)
- [ ] Verifica che il backup sia leggibile **prima** di resettare: apri qualche foto
      dal Mac, non fidarti del "completato" a schermo

### Non usare Smart Switch e adb nello stesso momento

Sono due programmi che vogliono lo stesso telefono sulla stessa porta USB. Una
sola cosa è **documentata con certezza**: Smart Switch installa un'estensione di
sistema che intercetta MTP e impedisce a OpenMTP di vedere il dispositivo — per
questo il README consiglia di disinstallarlo prima di passare a OpenMTP. Samsung
stessa avverte inoltre che Smart Switch non convive con Android File Transfer.

Sull'interazione con **adb** non esiste documentazione ufficiale in nessuna delle
due direzioni. Qualche fonte di scarsa qualità sostiene che un demone adb attivo
tenga occupata la porta e impedisca a Smart Switch di rilevare il telefono: non è
dimostrato, ma il demone adb *resta davvero in esecuzione* dopo ogni backup, e la
precauzione non costa nulla.

Quindi, per prudenza e non perché sia un fatto accertato:

```bash
adb kill-server      # prima di aprire Smart Switch
```

Se dopo aver usato Smart Switch `adb devices` non vedesse più il telefono,
scollega e ricollega il cavo, e in caso disinstalla Smart Switch: il backup dei
media non ne ha bisogno.

## 2. Dati che non sopravvivono al cambio di account

| Dato | Perché si perde | Cosa fare prima |
|---|---|---|
| Backup WhatsApp | è legato al Drive del vecchio account | backup locale in-app + copia di `Android/media/com.whatsapp/WhatsApp/Databases` (vedi nota) |
| Codici 2FA (Authenticator) | legati al dispositivo, non all'account | esporta i codici sul nuovo telefono/account prima del reset |
| Acquisti Play Store | legati all'account Google | non recuperabili sul nuovo account: valuta se serve rifarli |
| Contatti su account Google | restano sul vecchio account | esporta in VCF: Contatti > Gestisci contatti > Esporta |
| SMS | non sincronizzati su Google | inclusi nel backup Smart Switch |

Nota: gli **acquisti e i temi Samsung** restano disponibili, perché sono legati
all'account Samsung, che è indipendente da quello Google.

### Nota sui database WhatsApp

I file `msgstore.db.crypt14` che copi da `Android/media/com.whatsapp/` sono
cifrati, e la chiave sta in `/data/data/com.whatsapp/`: senza root non è
copiabile. **Quei file da soli non sono ripristinabili.** Il ripristino vero
passa dal backup locale creato dall'app (Impostazioni > Chat > Backup delle chat),
che WhatsApp sa rileggere al reinstall sullo stesso numero. Considera la copia dei
`Databases` solo una rete di sicurezza, non un backup utilizzabile.

## 3. Sblocchi da fare (il passo più critico)

- [ ] **Rimuovi l'account Google:** Impostazioni > Account e backup > Gestisci
      account > seleziona l'account > Rimuovi account

  Se resetti **senza** farlo, scatta la *Factory Reset Protection*: al riavvio il
  telefono chiede le credenziali del vecchio account Google e resta bloccato finché
  non le inserisci. È la causa numero uno di telefoni resi inutilizzabili.

- [ ] Disattiva "Trova dispositivo personale" (Samsung e Google)
- [ ] Annota email e password dell'**account Samsung** (ti servirà dopo)
- [ ] Revoca le autorizzazioni adb: Opzioni sviluppatore > "Revoca autorizzazioni
      debug USB"
- [ ] Disattiva il Debug USB
- [ ] Rimuovi fisicamente la microSD se non vuoi che venga toccata

## 4. Reset

Impostazioni > Gestione generale > Ripristino > Ripristina dati di fabbrica

## 5. Dopo il reset

- [ ] Al primo avvio inserisci il **nuovo** account Google
- [ ] Riaccedi all'account Samsung per recuperare temi e sfondi
- [ ] Ricopia gli sfondi salvati dal Mac al telefono (OpenMTP o `adb push`)
- [ ] Ripristina i media che ti servono

## Nota di sicurezza

Il Galaxy A31 non riceve patch di sicurezza dal maggio 2024 (fine del supporto
quadriennale). Il telefono funziona, ma valuta di non usarlo per home banking o
account critici.
