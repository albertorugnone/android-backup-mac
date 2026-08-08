#!/usr/bin/env bash
#
# backup-android.sh
# Backup incrementale delle cartelle multimediali di un Samsung Galaxy su Mac,
# tramite adb. Copia solo i file mancanti o rimasti incompleti, quindi puoi
# rilanciarlo tutte le volte che vuoi senza riscaricare tutto.
#
# Uso:
#   ./backup-android.sh                      -> backup in ~/Backup-Galaxy
#   ./backup-android.sh /Volumi/Disco/Backup -> backup nella cartella indicata
#   ./backup-android.sh --list-dirs          -> stampa le cartelle sorgente ed esce
#   DRY_RUN=1 ./backup-android.sh            -> mostra cosa farebbe, senza copiare
#
# Variabili d'ambiente:
#   DRY_RUN=1        non copia nulla, mostra solo cosa farebbe
#   STATUS_FILE=path scrive l'avanzamento in JSON nel file indicato, aggiornato a
#                    ogni cartella completata. Se non impostata, lo script si
#                    comporta esattamente come se questa funzione non esistesse.
#
# Codice di uscita: 1 se almeno una copia è fallita, 0 altrimenti. Serve a launchd
# per accorgersi di un backup andato male.
#
# Prerequisiti: adb installato, Debug USB attivo, telefono autorizzato.
#

set -uo pipefail

# Cartelle da salvare. Aggiungine o toglierne a piacere.
# Sono ammesse anche radici diverse da /sdcard (per esempio una microSD montata
# su /storage/XXXX-XXXX): finiscono in locale sotto la cartella "esterno/", così
# non si sovrappongono alla memoria interna.
REMOTE_DIRS=(
  "/sdcard/DCIM"                          # foto e video della fotocamera + screenshot
  "/sdcard/Pictures"                      # immagini salvate, editing, social
  "/sdcard/Download"
  "/sdcard/Movies"
  "/sdcard/Music"
  "/sdcard/Documents"
  "/sdcard/Android/media/com.whatsapp"    # media WhatsApp (Android 11+)
)

# --list-dirs: stampa le cartelle sorgente ed esce, senza toccare adb. Serve a
# chi integra questo script (il server MCP) per conoscere l'elenco senza doverlo
# duplicare altrove, e deve funzionare anche a telefono staccato.
if [[ "${1:-}" == "--list-dirs" ]]; then
  for remote_dir in "${REMOTE_DIRS[@]}"; do
    printf '%s\n' "$remote_dir"
  done
  exit 0
fi

DEST="${1:-$HOME/Backup-Galaxy}"
DRY_RUN="${DRY_RUN:-0}"
STATUS_FILE="${STATUS_FILE:-}"

TMP=""
AVVIATO=""
CARTELLE_FATTE=0
CARTELLA_CORRENTE=""
STATO_SCRITTO=""
total_new=0
total_diff=0
total_skip=0
total_err=0

info() { printf '\033[1;34m==>\033[0m %s\n' "$1"; }
ok()   { printf '\033[1;32m[ok]\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[errore]\033[0m %s\n' "$1" >&2; exit 1; }

# ------------------------------------------------------------- Stato JSON ----
# Scrive l'avanzamento solo se STATUS_FILE è impostata. La scrittura è atomica
# (temporaneo + mv) perché il lettore può arrivare in qualsiasi istante e non
# deve mai trovare un JSON a metà.
#
# Qui finiscono solo contatori e valori presi da REMOTE_DIRS, che è una lista
# fissa scritta nel codice: nessun nome di file proveniente dal telefono, quindi
# non serve alcun escaping JSON (che in bash 3.2 sarebbe fragile).
#
# Non scrive mai su stdout e ingoia i propri errori: un STATUS_FILE non
# scrivibile non deve disturbare il backup né sporcarne l'output.
scrivi_stato() {
  [[ -z "$STATUS_FILE" ]] && return 0

  local stato="$1"
  local codice="${2:-null}"
  local corrente="null"
  local dry="false"

  [[ -n "$CARTELLA_CORRENTE" ]] && corrente="\"$CARTELLA_CORRENTE\""
  [[ "$DRY_RUN" == "1" ]] && dry="true"

  {
    printf '{"stato":"%s","avviato":"%s","aggiornato":"%s","dry_run":%s,' \
      "$stato" "$AVVIATO" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$dry"
    printf '"cartelle_totali":%s,"cartelle_completate":%s,"cartella_corrente":%s,' \
      "${#REMOTE_DIRS[@]}" "$CARTELLE_FATTE" "$corrente"
    printf '"nuovi":%s,"ricopiati":%s,"saltati":%s,"errori":%s,"exit_code":%s}\n' \
      "$total_new" "$total_diff" "$total_skip" "$total_err" "$codice"
  } > "$STATUS_FILE.tmp" 2>/dev/null && mv -f "$STATUS_FILE.tmp" "$STATUS_FILE" 2>/dev/null

  STATO_SCRITTO="$stato"
  return 0
}

# Pulizia e, se lo script muore prima di dichiarare un esito (die sui controlli
# iniziali, kill, crash), stato "interrotto": chi legge non deve restare
# convinto che il backup sia ancora in corso.
# shellcheck disable=SC2329  # invocata dal trap qui sotto, non da una chiamata diretta
alla_uscita() {
  local codice=$?
  [[ -n "$TMP" ]] && rm -rf "$TMP"
  case "$STATO_SCRITTO" in
    completato|fallito) : ;;
    *) scrivi_stato "interrotto" "$codice" ;;
  esac
}
trap alla_uscita EXIT

[[ -n "$STATUS_FILE" ]] && AVVIATO="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
scrivi_stato "in_corso"

# --------------------------------------------------------------- Controlli ---
command -v adb >/dev/null 2>&1 || die "adb non trovato. Lancia prima setup-android-mac.sh"

info "Cerco il dispositivo..."
adb start-server >/dev/null 2>&1

state="$(adb get-state 2>/dev/null || true)"
case "$state" in
  device) : ;;
  unauthorized)
    die "Dispositivo non autorizzato. Sblocca il telefono e accetta il popup 'Consentire debug USB?'." ;;
  *)
    die "Nessun dispositivo collegato. Controlla il cavo, sblocca lo schermo e verifica che il Debug USB sia attivo." ;;
esac

model="$(adb exec-out getprop ro.product.model 2>/dev/null | tr -d '\r')"
ok "Collegato a: ${model:-dispositivo sconosciuto}"

mkdir -p "$DEST" || die "Non riesco a creare $DEST"
# Path assoluto: sotto launchd la directory di lavoro è /, e il log deve restare
# raggiungibile anche se è stato passato un percorso relativo.
DEST="$(cd "$DEST" && pwd)" || die "Non riesco a raggiungere $DEST"
LOG="$DEST/backup.log"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/backup-galaxy.XXXXXX")" || die "Non riesco a creare una cartella temporanea."

printf '\n===== %s =====\n' "$(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG"

[[ "$DRY_RUN" == "1" ]] && warn "MODALITÀ DRY-RUN: nessun file verrà copiato."

# ------------------------------------------------------- Verifica integrità ---
# Se la toybox del telefono sa fare "stat -c", ci facciamo dare anche la
# dimensione di ogni file: così un file rimasto a metà da un pull interrotto
# viene riconosciuto e ricopiato, invece di restare troncato per sempre.
con_dimensioni=1
prova="$(adb exec-out find /sdcard -maxdepth 0 -exec stat -c '%s|%n' {} + 2>/dev/null | tr -d '\r' | head -n1)"
if [[ ! "$prova" =~ ^[0-9]+\|. ]]; then
  con_dimensioni=0
  warn "Il dispositivo non supporta 'stat -c': confronto per sola presenza del file."
  warn "I file rimasti incompleti da una copia interrotta non verranno rilevati."
fi

# ---------------------------------------------------------- Elenco locale ----
# Calcolato una volta sola per tutto il backup. Il confronto avviene poi con
# comm(1): evita una fork di stat per ogni file già presente, che su una
# libreria da decine di migliaia di foto costerebbe minuti a ogni giro.
info "Leggo il backup già presente in $DEST ..."
find "$DEST" -type f -exec stat -f '%z|%N' {} + 2>/dev/null > "$TMP/locale_raw"

while IFS= read -r riga; do
  [[ -z "$riga" ]] && continue
  dimensione="${riga%%|*}"
  percorso="${riga#*|}"
  rel="${percorso:${#DEST}+1}"
  [[ -z "$rel" ]] && continue
  if [[ "$con_dimensioni" == "1" ]]; then
    printf '%s|%s\n' "$dimensione" "$rel"
  else
    printf '%s\n' "$rel"
  fi
done < "$TMP/locale_raw" | LC_ALL=C sort > "$TMP/locale"

# ------------------------------------------------------------------ Backup ---
for remote_dir in "${REMOTE_DIRS[@]}"; do
  CARTELLA_CORRENTE="$remote_dir"

  if ! adb shell "[ -d '$remote_dir' ]" >/dev/null 2>&1; then
    warn "Salto $remote_dir (non esiste o non accessibile)."
    CARTELLE_FATTE=$((CARTELLE_FATTE + 1))
    scrivi_stato "in_corso"
    continue
  fi

  # Come si passa dal path sul telefono al path relativo dentro il backup, e
  # viceversa. /sdcard e /storage/emulated/0 sono la stessa cosa e mantengono il
  # layout storico (DCIM/..., Android/media/...); ogni altra radice finisce sotto
  # "esterno/" per non collidere con la memoria interna.
  esterna=0
  radice=""
  case "$remote_dir" in
    /sdcard|/sdcard/*)                         radice="/sdcard/" ;;
    /storage/emulated/0|/storage/emulated/0/*) radice="/storage/emulated/0/" ;;
    *)                                         esterna=1 ;;
  esac

  info "Analizzo $remote_dir ..."
  # exec-out evita la conversione CRLF del pty; tr -d '\r' è una sicurezza in più
  if [[ "$con_dimensioni" == "1" ]]; then
    elenco="$(adb exec-out find "$remote_dir" -type f -exec stat -c '%s|%n' {} + 2>/dev/null | tr -d '\r')"
  else
    elenco="$(adb exec-out find "$remote_dir" -type f 2>/dev/null | tr -d '\r')"
  fi

  while IFS= read -r riga; do
    [[ -z "$riga" ]] && continue
    if [[ "$con_dimensioni" == "1" ]]; then
      dimensione="${riga%%|*}"
      percorso="${riga#*|}"
    else
      dimensione=""
      percorso="$riga"
    fi

    if [[ "$esterna" == "1" ]]; then
      rel="esterno$percorso"
    else
      rel="${percorso#"$radice"}"
    fi

    if [[ "$con_dimensioni" == "1" ]]; then
      printf '%s|%s\n' "$dimensione" "$rel"
    else
      printf '%s\n' "$rel"
    fi
  done <<< "$elenco" | LC_ALL=C sort > "$TMP/remoto"

  # Presenti sul telefono ma mancanti in locale, o presenti con dimensione
  # diversa: sono esattamente i file da copiare.
  LC_ALL=C comm -23 "$TMP/remoto" "$TMP/locale" > "$TMP/da_copiare"

  dir_totale="$(LC_ALL=C grep -c . "$TMP/remoto")"
  dir_new=0
  dir_diff=0

  while IFS= read -r riga; do
    [[ -z "$riga" ]] && continue
    if [[ "$con_dimensioni" == "1" ]]; then
      rel="${riga#*|}"
    else
      rel="$riga"
    fi

    if [[ "$esterna" == "1" ]]; then
      remote_file="${rel#esterno}"
    else
      remote_file="$radice$rel"
    fi
    local_file="$DEST/$rel"

    # Già presente ma di dimensione diversa: copia interrotta a metà, oppure il
    # file è stato modificato sul telefono. In entrambi i casi va riscaricato.
    if [[ -f "$local_file" ]]; then
      etichetta="diverso"
    else
      etichetta="nuovo"
    fi

    if [[ "$DRY_RUN" == "1" ]]; then
      printf '    [%s] %s\n' "$etichetta" "$rel"
      if [[ "$etichetta" == "diverso" ]]; then
        dir_diff=$((dir_diff + 1))
      else
        dir_new=$((dir_new + 1))
      fi
      continue
    fi

    mkdir -p "$(dirname "$local_file")"
    # </dev/null: il ciclo è alimentato da un redirect, un comando che legge da
    # stdin si mangerebbe il resto dell'elenco.
    if adb pull -a "$remote_file" "$local_file" </dev/null >/dev/null 2>&1; then
      printf '    + %s\n' "$rel"
      printf 'OK   %-8s %s\n' "$etichetta" "$rel" >> "$LOG"
      if [[ "$etichetta" == "diverso" ]]; then
        dir_diff=$((dir_diff + 1))
      else
        dir_new=$((dir_new + 1))
      fi
    else
      warn "  copia fallita: $rel"
      printf 'FAIL %-8s %s\n' "$etichetta" "$rel" >> "$LOG"
      total_err=$((total_err + 1))
    fi
  done < "$TMP/da_copiare"

  dir_skip=$((dir_totale - dir_new - dir_diff))
  if [[ "$dir_diff" -gt 0 ]]; then
    ok "$remote_dir -> $dir_new nuovi, $dir_diff ricopiati, $dir_skip già presenti."
  else
    ok "$remote_dir -> $dir_new nuovi, $dir_skip già presenti."
  fi
  total_new=$((total_new + dir_new))
  total_diff=$((total_diff + dir_diff))
  total_skip=$((total_skip + dir_skip))

  CARTELLE_FATTE=$((CARTELLE_FATTE + 1))
  scrivi_stato "in_corso"
done

CARTELLA_CORRENTE=""

# ------------------------------------------------------------------ Riepilogo -
echo
info "Riepilogo"
echo "    Nuovi file copiati : $total_new"
echo "    Ricopiati (diversi): $total_diff"
echo "    Già presenti       : $total_skip"
echo "    Errori             : $total_err"
echo "    Destinazione       : $DEST"
echo "    Log                : $LOG"

if [[ "$DRY_RUN" != "1" && $((total_new + total_diff)) -gt 0 ]]; then
  size="$(du -sh "$DEST" 2>/dev/null | cut -f1)"
  echo "    Spazio occupato    : ${size:-n/d}"
fi

printf 'Totale: %s nuovi, %s ricopiati, %s saltati, %s errori\n' \
  "$total_new" "$total_diff" "$total_skip" "$total_err" >> "$LOG"

cat <<'EOF'

NOTA: lo sfondo e la schermata di blocco attualmente applicati NON sono file
copiabili: Android li conserva in /data/system/users/0/ , area accessibile solo
con permessi di root. Usa il metodo dello screenshot (Impostazioni > Sfondo e
stile > anteprima a schermo intero) e rilancia questo script: lo screenshot
finisce in DCIM/Screenshots e verrà incluso nel backup.
EOF

if [[ "$total_err" -gt 0 ]]; then
  warn "$total_err file non sono stati copiati. Dettagli in $LOG"
  scrivi_stato "fallito" 1
  exit 1
fi
scrivi_stato "completato" 0
exit 0
