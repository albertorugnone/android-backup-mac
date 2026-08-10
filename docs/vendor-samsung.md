# Note per i dispositivi Samsung Galaxy

**Pagina opzionale.** Il toolkit è per Android generico e non dipende da nulla di
quanto segue: se il tuo telefono non è un Samsung, salta questa pagina.

Qui sta tutto ciò che vale solo per i Galaxy: il conflitto fra Smart Switch e MTP,
l'account Samsung e la scheda del Galaxy A31, che è il dispositivo per cui questo
progetto è nato.

---

## Smart Switch

È lo strumento ufficiale Samsung per il backup completo (SMS, contatti,
impostazioni, app). Copre cose che `backup-android.sh` **non** può copiare, perché
stanno in `/data/` e servirebbe il root.

|  | Smart Switch | `backup-android.sh` |
|---|---|---|
| Cosa salva | tutto: SMS, contatti, impostazioni, app | file multimediali e documenti |
| Automatizzabile | ❌ solo GUI, formato proprietario | ✅ |
| Incrementale | ❌ | ✅ |
| Quando | una volta, prima del reset | backup ricorrente |

Non è su Homebrew: va scaricato da
<https://www.samsung.com/it/apps/smart-switch/>. Il backup finisce in
`~/Documenti/Samsung/SmartSwitch/`.

### ⚠️ Smart Switch rompe MTP per le altre app

Questo è **documentato e certo**. Smart Switch installa un'estensione di sistema
che intercetta il protocollo MTP e impedisce a OpenMTP di rilevare il dispositivo;
gli sviluppatori di OpenMTP raccomandano di disinstallarlo. Vedi il
[troubleshooting di OpenMTP](https://github.com/ganeshrvel/openmtp#troubleshooting).

Samsung stessa avverte inoltre che Smart Switch **non convive con Android File
Transfer**: se hai l'app di Google installata, Smart Switch non parte finché non la
rimuovi ([FAQ ufficiale](https://www.samsung.com/au/apps/smart-switch/faq-smart-switch-pc-or-mac)).

**Ordine consigliato:** backup completo con Smart Switch → disinstalla Smart Switch
→ installa OpenMTP → usa `backup-android.sh` per la routine.

### Smart Switch e adb

Sull'interazione con **adb** non esiste documentazione ufficiale, in nessuna delle
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

#### La verifica che chiuderebbe la questione

Richiede il telefono collegato e Smart Switch installato, quindi non è stata
eseguita:

```bash
adb devices                 # deve mostrare il seriale + "device"
# installa Smart Switch, aprilo, chiudilo
adb kill-server && adb devices
```

- [ ] Con Smart Switch **installato ma chiuso**, `adb devices` vede ancora il telefono?
- [ ] Con Smart Switch **aperto**, `adb devices` lo vede ancora?
- [ ] Al contrario: con un demone adb attivo (`adb start-server`), Smart Switch
      riesce a rilevare il telefono?

Qualunque sia l'esito, annotalo qui sostituendo la formula prudenziale con il
fatto accertato.

---

## Account Samsung

È indipendente dall'account Google, e questo è utile in un cambio di account
Google: **acquisti e temi Samsung sopravvivono**, perché sono legati all'account
Samsung.

Prima di un factory reset:

- [ ] Annota email e password dell'account Samsung — ti serviranno dopo
- [ ] Disattiva "Trova dispositivo personale" (la voce Samsung, oltre a quella Google)

Dopo il reset:

- [ ] Riaccedi all'account Samsung per recuperare temi e sfondi

### Sfondi da Galaxy Themes

Se lo sfondo viene dallo store Samsung, annota il nome del tema o dello sfondo:
dopo il reset lo riscarichi gratis accedendo con lo **stesso account Samsung**.
Vedi [wallpaper-recovery.md](wallpaper-recovery.md) per gli altri metodi.

### Percorsi dei menu su One UI

Le voci indicate in [pre-reset-checklist.md](pre-reset-checklist.md) seguono One UI.
Su altre marche i nomi cambiano, la sostanza no:

| Cosa | Dove su One UI |
|---|---|
| Rimuovere l'account Google | Impostazioni > Account e backup > Gestisci account |
| Factory reset | Impostazioni > Gestione generale > Ripristino > Ripristina dati di fabbrica |
| Sfondo a schermo intero | Impostazioni > Sfondo e stile > tocca lo sfondo attuale |
| Opzioni sviluppatore | Impostazioni > Info sul telefono > Informazioni software > 7 tocchi su "Numero build" |

---

## Galaxy A31 — il dispositivo di riferimento

Annunciato marzo 2020, modello `SM-A315F` (variante europea). È il telefono per cui
questo toolkit è nato.

| | |
|---|---|
| Display | 6,4" Super AMOLED, 1080 x 2400 |
| SoC | MediaTek Helio P65 |
| RAM / Storage | 4 o 6 GB / 64 o 128 GB, microSD |
| Batteria | 5000 mAh, ricarica 15W |
| Fotocamere | 48 MP + 8 MP ultragrandangolo + 5 MP macro + 5 MP profondità; 20 MP frontale |

### Software

| Versione | Quando |
|---|---|
| Android 10 / One UI 2.1 | di fabbrica |
| Android 11 / One UI 3.1 | aprile 2021 |
| Android 12 / One UI 4.1 | maggio 2022 (ultimo major update) |
| Fine patch di sicurezza | maggio 2024 |

Il ciclo previsto era di 2 major update e 4 anni di patch: entrambi esauriti.

### Cosa comporta per il backup

- Android 12 → i media delle app stanno in `Android/media/<package>`, accessibili;
  i dati in `Android/data/` **non** lo sono (restrizione introdotta con Android 11)
- Nessun supporto software attivo: non aspettarti fix a eventuali bug MTP o adb
- Storage espandibile: se usi una microSD il percorso è tipicamente
  `/storage/XXXX-XXXX`, non `/sdcard`. Aggiungilo a mano in `REMOTE_DIRS`:
  `backup-android.sh` lo gestisce e lo salva sotto `esterno/` nella cartella di
  backup, così non si sovrappone alla memoria interna

### Nota di sicurezza

Niente patch dal maggio 2024. Il telefono funziona, ma valuta di non usarlo per
home banking o account critici.
