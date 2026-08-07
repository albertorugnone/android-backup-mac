# Recuperare sfondo e schermata di blocco

## Perché non basta un backup normale

Lo sfondo **applicato** non è un file accessibile. Android lo conserva in
`/data/system/users/0/wallpaper` e `wallpaper_lock`, dentro l'area di sistema:
non è leggibile né via adb né via MTP senza permessi di root. Il file che vedi lì
è comunque già ritagliato e scalato per il display, quindi non sarebbe nemmeno
l'originale.

Verifica (fallirà, ma è utile constatarlo):

```bash
adb shell ls -l /data/system/users/0/wallpaper
# ls: /data/system/users/0/wallpaper: Permission denied
```

## Metodo 1 — cercare l'originale (prova sempre questo per primo)

Apri Galleria e verifica se l'immagine usata come sfondo è ancora tra le tue foto.
Se sì, è già in `DCIM/` o `Pictures/` e viene inclusa dal backup: hai finito.

Ricerca rapida da terminale:

```bash
adb exec-out find /sdcard/Pictures /sdcard/DCIM -type f \
  \( -iname '*wallpaper*' -o -iname '*sfondo*' \) | tr -d '\r'
```

## Metodo 2 — screenshot (funziona sempre)

**Schermata di blocco:** blocca il telefono, accendi lo schermo, premi
Accensione + Volume giù. Cattura lo sfondo con sopra orologio e notifiche.

**Sfondo home (metodo pulito, senza icone):**
Impostazioni > Sfondo e stile > tocca lo sfondo attuale per aprire l'anteprima a
schermo intero > screenshot lì.

Gli screenshot finiscono in `/sdcard/DCIM/Screenshots`, quindi vengono raccolti al
prossimo giro di `backup-android.sh`.

Scorciatoia via adb, senza toccare il telefono se non per portarlo nella schermata
giusta:

```bash
adb exec-out screencap -p > ~/Desktop/sfondo.png
```

## Metodo 3 — sfondi di Galaxy Themes

Se lo sfondo viene dallo store Samsung, annota il nome del tema o dello sfondo.
Dopo il reset lo riscarichi gratis accedendo con lo **stesso account Samsung**:
gli acquisti Samsung non dipendono dall'account Google.

## Rimettere lo sfondo dopo il reset

```bash
adb push ~/Backup-Galaxy/Pictures/sfondo.jpg /sdcard/Pictures/
```

Poi dal telefono: Galleria > apri l'immagine > menu > Imposta come sfondo.
