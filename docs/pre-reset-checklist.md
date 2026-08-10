# Checklist prima del factory reset

Obiettivo: resettare il telefono e associarlo a un **account Google diverso** da
quello attualmente in uso. Da fare in quest'ordine.

I percorsi dei menu variano da marca a marca: qui sono indicati in forma generica.
Per le voci di One UI e per quanto riguarda l'account Samsung, vedi
[vendor-samsung.md](vendor-samsung.md).

## 1. Backup

- [ ] Backup completo con l'utility del produttore, se ne usi una — copre SMS,
      contatti e impostazioni, che `backup-android.sh` non può leggere. Non
      tenerla aperta insieme ad adb: vedi [vendor-samsung.md](vendor-samsung.md)
- [ ] Backup dei media con `./scripts/backup-android.sh`
- [ ] Screenshot dello sfondo e della schermata di blocco → vedi
      [wallpaper-recovery.md](wallpaper-recovery.md)
- [ ] Verifica che il backup sia leggibile **prima** di resettare: apri qualche foto
      dal Mac, non fidarti del "completato" a schermo

## 2. Dati che non sopravvivono al cambio di account

| Dato | Perché si perde | Cosa fare prima |
|---|---|---|
| Backup WhatsApp | è legato al Drive del vecchio account | backup locale in-app + copia di `Android/media/com.whatsapp/WhatsApp/Databases` (vedi nota) |
| Codici 2FA (Authenticator) | legati al dispositivo, non all'account | esporta i codici sul nuovo telefono/account prima del reset |
| Acquisti Play Store | legati all'account Google | non recuperabili sul nuovo account: valuta se serve rifarli |
| Contatti su account Google | restano sul vecchio account | esporta in VCF: Contatti > Gestisci contatti > Esporta |
| SMS | non sincronizzati su Google | inclusi nel backup dell'utility del produttore |

Nota: se il produttore ha un proprio account (per Samsung è il caso), acquisti e
temi legati a **quello** sopravvivono al cambio di account Google, perché sono
indipendenti. Vedi [vendor-samsung.md](vendor-samsung.md).

### Nota sui database WhatsApp

I file `msgstore.db.crypt14` che copi da `Android/media/com.whatsapp/` sono
cifrati, e la chiave sta in `/data/data/com.whatsapp/`: senza root non è
copiabile. **Quei file da soli non sono ripristinabili.** Il ripristino vero
passa dal backup locale creato dall'app (Impostazioni > Chat > Backup delle chat),
che WhatsApp sa rileggere al reinstall sullo stesso numero. Considera la copia dei
`Databases` solo una rete di sicurezza, non un backup utilizzabile.

## 3. Sblocchi da fare (il passo più critico)

- [ ] **Rimuovi l'account Google:** Impostazioni > Account (su One UI: Account e
      backup > Gestisci account) > seleziona l'account > Rimuovi account

  Se resetti **senza** farlo, scatta la *Factory Reset Protection*: al riavvio il
  telefono chiede le credenziali del vecchio account Google e resta bloccato finché
  non le inserisci. È la causa numero uno di telefoni resi inutilizzabili.

- [ ] Disattiva "Trova il mio dispositivo" — quello di Google **e** quello del
      produttore, se esiste
- [ ] Annota le credenziali dell'eventuale account del produttore: ti serviranno
      dopo il reset per recuperare temi e acquisti
- [ ] Revoca le autorizzazioni adb: Opzioni sviluppatore > "Revoca autorizzazioni
      debug USB"
- [ ] Disattiva il Debug USB
- [ ] Rimuovi fisicamente la microSD se non vuoi che venga toccata

## 4. Reset

Impostazioni > Sistema > Ripristino (su One UI: Gestione generale > Ripristino) >
Ripristina dati di fabbrica

## 5. Dopo il reset

- [ ] Al primo avvio inserisci il **nuovo** account Google
- [ ] Riaccedi all'eventuale account del produttore per recuperare temi e sfondi
- [ ] Ricopia gli sfondi salvati dal Mac al telefono (OpenMTP o `adb push`)
- [ ] Ripristina i media che ti servono

## Nota di sicurezza

Verifica fino a quando il tuo modello riceve patch di sicurezza: i telefoni di
fascia media escono dal supporto dopo pochi anni. Un dispositivo senza patch
funziona benissimo, ma valuta di non usarlo per home banking o account critici.
Per il Galaxy A31 le date sono in [vendor-samsung.md](vendor-samsung.md).
