#!/usr/bin/env bash
#
# Finto adb per i test: risponde con output registrati, senza telefono.
# Va messo in PATH col nome "adb" (lo fa la fixture in conftest.py).
#
# Variabili che ne pilotano il comportamento:
#   FAKE_SD        cartella locale che finge /sdcard
#   FAKE_STATE     device (default) | unauthorized | absent
#   FAKE_NO_STAT   1 = la toybox non supporta "stat -c"
#   FAKE_FAIL_ON   sottostringa: i pull dei file che la contengono falliscono
#   FAKE_PNG       file PNG da restituire a screencap
#
# Non esegue MAI nulla che provenga dai nomi dei file: li tratta come dati.

set -uo pipefail

FAKE_STATE="${FAKE_STATE:-device}"

# path sul "telefono" -> path locale
traduci() {
  case "$1" in
    /sdcard)   printf '%s\n' "$FAKE_SD" ;;
    /sdcard/*) printf '%s\n' "$FAKE_SD/${1#/sdcard/}" ;;
    *)         printf '%s\n' "/dev/null/inesistente" ;;
  esac
}

comando="${1:-}"
shift 2>/dev/null || true

case "$comando" in
  start-server)
    exit 0 ;;

  get-state)
    case "$FAKE_STATE" in
      device)       echo "device"; exit 0 ;;
      unauthorized) echo "unauthorized" >&2; exit 1 ;;
      *)            echo "error: no devices/emulators found" >&2; exit 1 ;;
    esac ;;

  shell)
    # atteso: adb shell "[ -d '/sdcard/DCIM' ]"
    arg="${1:-}"
    percorso="${arg#*\'}"
    percorso="${percorso%%\'*}"
    [ -d "$(traduci "$percorso")" ] && exit 0
    exit 1 ;;

  exec-out)
    sub="${1:-}"
    shift 2>/dev/null || true
    case "$sub" in
      getprop)
        case "${1:-}" in
          ro.product.model)          echo "SM-A315F" ;;
          ro.build.version.release)  echo "12" ;;
          *)                         echo "" ;;
        esac
        exit 0 ;;

      df)
        echo "Filesystem     1K-blocks     Used Available Use% Mounted on"
        echo "/dev/fuse       52428800 31457280  20971520  60% /storage/emulated"
        exit 0 ;;

      screencap)
        [ -n "${FAKE_PNG:-}" ] && [ -f "$FAKE_PNG" ] && cat "$FAKE_PNG" && exit 0
        exit 1 ;;

      find)
        dir="${1:-}"
        reale="$(traduci "$dir")"
        tutti="$*"

        # sonda di supporto a stat -c usata da backup-android.sh
        case "$tutti" in
          *"-maxdepth 0"*)
            [ "${FAKE_NO_STAT:-0}" = "1" ] && exit 1
            echo "4096|$dir"
            exit 0 ;;
        esac

        [ -d "$reale" ] || exit 1

        case "$tutti" in
          *stat*)
            [ "${FAKE_NO_STAT:-0}" = "1" ] && exit 1
            # due formati: "%s|%n" (script di backup) e "%s" (inventario)
            case "$tutti" in
              *'%s|%n'*)
                find "$reale" -type f -exec stat -f '%z|%N' {} + 2>/dev/null \
                  | sed "s|$FAKE_SD|/sdcard|" ;;
              *)
                find "$reale" -type f -exec stat -f '%z' {} + 2>/dev/null ;;
            esac ;;
          *)
            find "$reale" -type f 2>/dev/null | sed "s|$FAKE_SD|/sdcard|" ;;
        esac
        exit 0 ;;

      *) exit 1 ;;
    esac ;;

  pull)
    [ "${1:-}" = "-a" ] && shift
    remoto="${1:-}"
    locale_="${2:-}"
    if [ -n "${FAKE_FAIL_ON:-}" ]; then
      case "$remoto" in
        *"$FAKE_FAIL_ON"*) exit 1 ;;
      esac
    fi
    reale="$(traduci "$remoto")"
    [ -f "$reale" ] || exit 1
    cp "$reale" "$locale_" || exit 1
    exit 0 ;;

  *) exit 1 ;;
esac
