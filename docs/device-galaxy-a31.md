# Samsung Galaxy A31 — scheda e limiti noti

Annunciato marzo 2020, in commercio da aprile 2020. Modello `SM-A315F` (variante
europea).

## Specifiche essenziali

| | |
|---|---|
| Display | 6,4" Super AMOLED, 1080 x 2400 |
| SoC | MediaTek Helio P65 |
| RAM / Storage | 4 o 6 GB / 64 o 128 GB, microSD |
| Batteria | 5000 mAh, ricarica 15W |
| Fotocamere | 48 MP + 8 MP ultragrandangolo + 5 MP macro + 5 MP profondità; 20 MP frontale |
| Altro | jack 3,5 mm, lettore d'impronte ottico sotto il display, NFC dipendente dal mercato |

## Software

| Versione | Quando |
|---|---|
| Android 10 / One UI 2.1 | di fabbrica |
| Android 11 / One UI 3.1 | aprile 2021 |
| Android 12 / One UI 4.1 | maggio 2022 (ultimo major update) |
| Fine patch di sicurezza | maggio 2024 |

Il ciclo previsto era di 2 major update e 4 anni di patch: entrambi esauriti.

## Pregi

- Display AMOLED di qualità superiore alla media della fascia
- Autonomia molto buona grazie ai 5000 mAh
- microSD e jack cuffie
- Costruzione solida

## Difetti

- SoC lento già all'epoca, oggi molto evidente
- Lettore d'impronte ottico lento e impreciso (difetto più segnalato nelle recensioni)
- Ricarica 15W: quasi 2 ore per una batteria da 5000 mAh
- Fotocamere secondarie mediocri, macro da 5 MP di fatto inutile
- Nessuna stabilizzazione ottica, modalità notte assente o debole
- Nessuna certificazione di resistenza a polvere e acqua

## Implicazioni per questo progetto

- Android 12 → i media delle app stanno in `Android/media/<package>`, accessibili;
  i dati in `Android/data/` **non** lo sono (restrizione introdotta con Android 11).
- Nessun supporto software attivo: non aspettarti fix a eventuali bug MTP o adb.
- Storage espandibile: se usi una microSD, il percorso è tipicamente
  `/storage/XXXX-XXXX`, non `/sdcard`. Aggiungilo a mano in `REMOTE_DIRS`:
  `backup-android.sh` lo gestisce e lo salva sotto `esterno/` nella cartella di
  backup, così non si sovrappone alla memoria interna.
