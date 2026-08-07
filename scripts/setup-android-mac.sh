#!/usr/bin/env bash
#
# setup-android-mac.sh
# Installa gli strumenti per gestire un Samsung Galaxy da macOS:
#   - Homebrew (se mancante)
#   - OpenMTP        -> sfoglia/copia file dal telefono via GUI
#   - platform-tools -> adb, per i backup automatizzati da terminale
#
# Uso:  chmod +x setup-android-mac.sh && ./setup-android-mac.sh
#

set -euo pipefail

info()  { printf '\033[1;34m==>\033[0m %s\n' "$1"; }
warn()  { printf '\033[1;33m[!]\033[0m %s\n' "$1"; }
ok()    { printf '\033[1;32m[ok]\033[0m %s\n' "$1"; }
die()   { printf '\033[1;31m[errore]\033[0m %s\n' "$1" >&2; exit 1; }

[[ "$(uname -s)" == "Darwin" ]] || die "Questo script gira solo su macOS."

# ---------------------------------------------------------------- Homebrew ---
if ! command -v brew >/dev/null 2>&1; then
  info "Homebrew non trovato: lo installo (ti chiederà la password di sistema)."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

  # Aggiunge brew al PATH della sessione corrente (percorso diverso Intel/Apple Silicon)
  for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [[ -x "$candidate" ]] && eval "$("$candidate" shellenv)" && break
  done
  command -v brew >/dev/null 2>&1 || die "Homebrew installato ma non nel PATH. Riapri il Terminale e rilancia."
else
  ok "Homebrew già presente ($(brew --version | head -n1))."
fi

info "Aggiorno gli indici di Homebrew..."
brew update

# --------------------------------------------------------------- Pacchetti ---
install_cask() {
  local cask="$1" label="$2"
  if brew list --cask "$cask" >/dev/null 2>&1; then
    ok "$label già installato."
  else
    info "Installo $label..."
    brew install --cask "$cask"
    ok "$label installato."
  fi
}

install_cask openmtp                "OpenMTP"
install_cask android-platform-tools "Android platform-tools (adb)"

# --------------------------------------------------- Smart Switch (manuale) ---
SMARTSWITCH_URL="https://www.samsung.com/it/apps/smart-switch/"

echo
if [[ -d "/Applications/Smart Switch.app" ]]; then
  warn "Smart Switch risulta installato."
  warn "Attenzione: Smart Switch installa un'estensione di sistema che intercetta"
  warn "il protocollo MTP e può impedire a OpenMTP di vedere il telefono."
  warn "Se OpenMTP non rileva il dispositivo, disinstalla Smart Switch e riprova."
else
  info "Smart Switch non ha un pacchetto Homebrew: va scaricato dal sito Samsung."
  read -r -p "    Apro ora la pagina di download nel browser? [s/N] " reply
  [[ "$reply" =~ ^[SsYy]$ ]] && open "$SMARTSWITCH_URL"
fi

# ------------------------------------------------------------------ Verifica --
echo
info "Verifica finale:"
command -v adb >/dev/null 2>&1 \
  && ok "adb disponibile: $(adb version | head -n1)" \
  || warn "adb non nel PATH. Riapri il Terminale."
[[ -d "/Applications/OpenMTP.app" ]] \
  && ok "OpenMTP presente in /Applications." \
  || warn "OpenMTP non trovato in /Applications."

cat <<'EOF'

--------------------------------------------------------------------------
PROSSIMI PASSI SUL TELEFONO (una tantum, per usare adb)

  1. Impostazioni > Info sul telefono > Informazioni software
     -> tocca "Numero build" 7 volte finché non compare
        "Modalità sviluppatore attivata".
  2. Impostazioni > Opzioni sviluppatore -> attiva "Debug USB".
  3. Collega il telefono al Mac col cavo e SBLOCCA lo schermo.
  4. Nel Terminale:  adb devices
     Sul telefono comparirà "Consentire debug USB?" -> spunta
     "Consenti sempre da questo computer" e conferma.
  5. Se `adb devices` mostra il seriale seguito da "device", sei pronto:
     lancia ./backup-android.sh

  Ricordati di DISATTIVARE il debug USB quando hai finito.
--------------------------------------------------------------------------
EOF
