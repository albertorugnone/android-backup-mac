#!/usr/bin/env python3
"""Server MCP in sola lettura per il backup di un Samsung Galaxy su macOS.

Espone cinque operazioni tipizzate al posto dell'accesso a bash. Il punto non è
dare nuove capacità a un assistente — gli script si lanciano già da terminale —
ma restringere ciò che può fare: niente esecuzione arbitraria sul telefono.

Questo server è un wrapper sottile. Tutta la logica di backup resta in
scripts/backup-android.sh, che viene invocato come sottoprocesso: lo script deve
continuare a funzionare da solo, da terminale e da launchd, senza Python.

Invarianti di sicurezza, valide in ogni percorso di codice:
  - nessun sottoprocesso viene mai lanciato con shell=True
  - nessuna stringa fornita dal modello finisce in `adb shell`
  - il server non scrive mai sul telefono
  - i nomi dei file del telefono sono dati non fidati: non vengono interpolati
    in comandi né usati per decidere il flusso
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from mcp import MCPError
from mcp.server.mcpserver import MCPServer
from mcp.types import INVALID_PARAMS, INTERNAL_ERROR

# --------------------------------------------------------------- Percorsi ---

RADICE_REPO = Path(__file__).resolve().parent.parent
SCRIPT_BACKUP = RADICE_REPO / "scripts" / "backup-android.sh"

CARTELLA_STATO = Path.home() / ".galaxy-backup"
CARTELLA_JOB = CARTELLA_STATO / "jobs"
CARTELLA_SCHERMATE = CARTELLA_STATO / "screenshots"

# launchd e Claude Desktop non ereditano il PATH della shell: adb installato da
# Homebrew non verrebbe trovato. È lo stesso problema che affligge l'agent
# launchd di questo repo, e va risolto allo stesso modo.
PERCORSI_ADB = ("/opt/homebrew/bin/adb", "/usr/local/bin/adb")

# Un elenco di file non deve mai saturare il contesto del modello.
MAX_ELEMENTI = 50

# Il primo backup di una libreria grande può durare a lungo: l'enumerazione via
# USB è lenta. I comandi rapidi hanno invece timeout stretti.
TIMEOUT_RAPIDO = 20
TIMEOUT_ENUMERAZIONE = 600

mcp = MCPServer("galaxy-backup")


class ErroreUtente(Exception):
    """Errore da mostrare all'utente: il messaggio dice cosa fare, non cosa è fallito."""


# ------------------------------------------------------------- Utilità -------


def _esegui(args: Sequence[str], timeout: float, env: dict[str, str] | None = None):
    """Lancia un comando. Mai shell=True, sempre una lista di argomenti."""
    return subprocess.run(  # noqa: S603 - lista di argomenti, nessuna shell
        list(args),
        capture_output=True,
        timeout=timeout,
        check=False,
        stdin=subprocess.DEVNULL,
        env=env,
    )


def _testo(dati: bytes) -> str:
    """Decodifica l'output di adb. `errors="replace"` perché i nomi dei file sul
    telefono possono non essere UTF-8 validi e questo non deve far crollare nulla."""
    return dati.decode("utf-8", errors="replace").replace("\r", "")


def _trova_adb() -> str:
    percorso = shutil.which("adb")
    if percorso:
        return percorso
    for candidato in PERCORSI_ADB:
        if os.access(candidato, os.X_OK):
            return candidato
    raise ErroreUtente(
        "adb non è installato. Aprilo da terminale nella cartella del progetto "
        "e lancia ./scripts/setup-android-mac.sh, poi riprova."
    )


def _ambiente_con_adb() -> dict[str, str]:
    """Ambiente per i sottoprocessi, con la cartella di adb garantita nel PATH."""
    ambiente = dict(os.environ)
    cartella_adb = str(Path(_trova_adb()).parent)
    percorsi = ambiente.get("PATH", "").split(os.pathsep)
    if cartella_adb not in percorsi:
        ambiente["PATH"] = os.pathsep.join([cartella_adb, *percorsi])
    return ambiente


def _stato_connessione() -> str:
    """Restituisce 'device', 'unauthorized' o 'absent'."""
    adb = _trova_adb()
    _esegui([adb, "start-server"], timeout=TIMEOUT_RAPIDO)
    esito = _esegui([adb, "get-state"], timeout=TIMEOUT_RAPIDO)
    stato = _testo(esito.stdout).strip()
    if stato == "device":
        return "device"
    if "unauthorized" in stato or "unauthorized" in _testo(esito.stderr):
        return "unauthorized"
    return "absent"


def _pretendi_dispositivo() -> str:
    """Verifica che il telefono sia utilizzabile, con messaggi che dicono cosa fare."""
    stato = _stato_connessione()
    if stato == "device":
        return _trova_adb()
    if stato == "unauthorized":
        raise ErroreUtente(
            "Il telefono è collegato ma non autorizzato. Sblocca lo schermo, "
            "accetta il popup «Consentire debug USB?» e spunta «Consenti sempre "
            "da questo computer», poi riprova."
        )
    raise ErroreUtente(
        "Nessun telefono collegato. Controlla che il cavo sia un cavo dati e non "
        "di sola ricarica, che lo schermo sia sbloccato e che il Debug USB sia "
        "attivo (Impostazioni > Opzioni sviluppatore)."
    )


def _leggi_json(percorso: Path) -> dict[str, Any] | None:
    """Legge un JSON tollerando file mancanti, troncati o corrotti: lo stato di un
    job può essere letto mentre viene riscritto, e non deve mai far fallire il tool."""
    try:
        with percorso.open(encoding="utf-8") as f:
            dati = json.load(f)
    except (OSError, ValueError):
        return None
    return dati if isinstance(dati, dict) else None


def _leggibile(byte: int | None) -> str | None:
    if byte is None:
        return None
    valore = float(byte)
    for unita in ("B", "KB", "MB", "GB", "TB"):
        if valore < 1024 or unita == "TB":
            return f"{valore:.1f} {unita}" if unita != "B" else f"{int(valore)} B"
        valore /= 1024
    return None


def _adesso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------ Cartelle sorgente ----

_cache_cartelle: list[str] | None = None


def _cartelle_remote() -> list[str]:
    """Chiede l'elenco allo script, che resta l'unica fonte di verità.

    Non fa il parsing del sorgente: se un giorno REMOTE_DIRS cambia forma, qui
    non si rompe niente."""
    global _cache_cartelle
    if _cache_cartelle is not None:
        return _cache_cartelle
    esito = _esegui([str(SCRIPT_BACKUP), "--list-dirs"], timeout=TIMEOUT_RAPIDO)
    if esito.returncode != 0:
        raise ErroreUtente(
            f"Non riesco a leggere l'elenco delle cartelle da {SCRIPT_BACKUP.name}. "
            "Verifica che lo script esista e sia eseguibile (chmod +x scripts/*.sh)."
        )
    _cache_cartelle = [r for r in _testo(esito.stdout).splitlines() if r.strip()]
    return _cache_cartelle


def _valida_cartella(remote_dir: str | None) -> list[str]:
    """Nessun percorso arbitrario: solo uguaglianza esatta con l'elenco dello script."""
    cartelle = _cartelle_remote()
    if remote_dir is None:
        return cartelle
    if remote_dir not in cartelle:
        raise MCPError(
            INVALID_PARAMS,
            f"«{remote_dir}» non è una delle cartelle previste. "
            f"Quelle ammesse sono: {', '.join(cartelle)}",
        )
    return [remote_dir]


# --------------------------------------------------------- Destinazione -----


def _valida_destinazione(destination: str | None) -> Path:
    """La destinazione deve essere un percorso assoluto sotto $HOME.

    Il percorso reale si risolve PRIMA di controllare il prefisso: un symlink
    che punta fuori da $HOME passerebbe un controllo fatto sulla stringa."""
    if destination is None:
        return Path.home() / "Backup-Galaxy"

    candidato = Path(destination)
    if not candidato.is_absolute():
        raise MCPError(
            INVALID_PARAMS,
            "La destinazione deve essere un percorso assoluto, per esempio "
            f"{Path.home()}/Backup-Galaxy",
        )

    reale = candidato.expanduser().resolve()
    casa = Path.home().resolve()
    if casa not in reale.parents:
        raise MCPError(
            INVALID_PARAMS,
            f"La destinazione deve trovarsi dentro {casa}. "
            f"«{destination}» punta a {reale}, che è fuori.",
        )
    return reale


# ------------------------------------------------------------------ Job -----


def _file_meta(job_id: str) -> Path:
    return CARTELLA_JOB / f"{job_id}.json"


def _file_progresso(job_id: str) -> Path:
    return CARTELLA_JOB / f"{job_id}.progress.json"


def _file_log(job_id: str) -> Path:
    return CARTELLA_JOB / f"{job_id}.log"


def _elenco_job() -> list[str]:
    if not CARTELLA_JOB.is_dir():
        return []
    ids = [
        p.name[: -len(".json")]
        for p in CARTELLA_JOB.glob("*.json")
        if not p.name.endswith(".progress.json")
    ]
    return sorted(ids)


def _processo_vivo(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # esiste, appartiene a un altro utente
    return True


def _job_attivo() -> str | None:
    """job_id di un backup in corso, se ce n'è uno.

    Se un job risulta 'in_corso' ma il processo è morto senza scrivere un esito
    (kill -9, riavvio), lo marca 'interrotto': altrimenti un crash bloccherebbe
    per sempre l'avvio di nuovi backup."""
    for job_id in reversed(_elenco_job()):
        progresso = _leggi_json(_file_progresso(job_id))
        stato = (progresso or {}).get("stato")
        if stato in ("completato", "fallito", "interrotto"):
            continue

        meta = _leggi_json(_file_meta(job_id)) or {}
        if _processo_vivo(meta.get("pid")):
            return job_id

        dati = progresso or {"stato": "interrotto"}
        dati["stato"] = "interrotto"
        dati.setdefault("exit_code", None)
        dati["aggiornato"] = _adesso()
        try:
            _file_progresso(job_id).write_text(
                json.dumps(dati, ensure_ascii=False), encoding="utf-8"
            )
        except OSError:
            pass
    return None


def _errori_recenti(destinazione: Path) -> tuple[list[str], int]:
    """Righe FAIL dal log del backup, troncate.

    Contengono nomi di file che vengono dal telefono: non fidati. Qui vengono
    solo lette e restituite come testo, mai interpolate in un comando."""
    log = destinazione / "backup.log"
    try:
        righe = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return [], 0
    falliti = [r for r in righe if r.startswith("FAIL")]
    return falliti[-MAX_ELEMENTI:], len(falliti)


# ------------------------------------------------------------------ Tool -----


@mcp.tool()
async def device_status() -> dict[str, Any]:
    """Dice se un telefono Android è collegato e utilizzabile via adb.

    Sola lettura, veloce. Restituisce lo stato della connessione, modello,
    versione di Android e spazio libero sul telefono. Non fallisce quando il
    telefono è assente: lo riporta come stato.
    """
    try:
        adb = _trova_adb()
    except ErroreUtente as e:
        return {"collegato": False, "stato": "adb_assente", "messaggio": str(e)}

    stato = _stato_connessione()
    if stato != "device":
        messaggi = {
            "unauthorized": (
                "Telefono collegato ma non autorizzato: sblocca lo schermo e accetta "
                "il popup «Consentire debug USB?»."
            ),
            "absent": (
                "Nessun telefono collegato. Verifica che il cavo sia un cavo dati "
                "e non di sola ricarica, e che il Debug USB sia attivo."
            ),
        }
        return {"collegato": False, "stato": stato, "messaggio": messaggi[stato]}

    def prop(nome: str) -> str | None:
        esito = _esegui([adb, "exec-out", "getprop", nome], timeout=TIMEOUT_RAPIDO)
        valore = _testo(esito.stdout).strip()
        return valore or None

    libero = None
    esito = _esegui([adb, "exec-out", "df", "-k", "/sdcard"], timeout=TIMEOUT_RAPIDO)
    righe = _testo(esito.stdout).strip().splitlines()
    if len(righe) >= 2:
        campi = righe[-1].split()
        if len(campi) >= 4 and campi[3].isdigit():
            libero = int(campi[3]) * 1024

    return {
        "collegato": True,
        "stato": "device",
        "modello": prop("ro.product.model"),
        "android": prop("ro.build.version.release"),
        "spazio_libero_bytes": libero,
        "spazio_libero": _leggibile(libero),
        "messaggio": "Telefono pronto.",
    }


@mcp.tool()
async def backup_inventory(remote_dir: str | None = None) -> dict[str, Any]:
    """Conta file e byte presenti sul telefono, senza copiare nulla.

    Serve a stimare quanto durerà un backup prima di lanciarlo. Sola lettura.
    `remote_dir`, se indicato, deve essere una delle cartelle previste dallo
    script: percorsi arbitrari vengono rifiutati. Se omesso, le esamina tutte.

    Restituisce solo conteggi e dimensioni, mai l'elenco dei nomi dei file.
    """
    try:
        cartelle = _valida_cartella(remote_dir)
        adb = _pretendi_dispositivo()
    except ErroreUtente as e:
        raise MCPError(INTERNAL_ERROR, str(e)) from e

    risultati: list[dict[str, Any]] = []
    totale_file = 0
    totale_byte = 0
    dimensioni_disponibili = True

    for cartella in cartelle:
        esito = _esegui(
            [adb, "exec-out", "find", cartella, "-type", "f",
             "-exec", "stat", "-c", "%s", "{}", "+"],
            timeout=TIMEOUT_ENUMERAZIONE,
        )
        # Accettiamo solo interi: qualsiasi altra cosa (compreso un nome di file
        # ostile finito nell'output) viene scartata senza essere interpretata.
        misure = [r for r in _testo(esito.stdout).split() if r.isdigit()]

        if misure:
            conteggio, byte = len(misure), sum(int(m) for m in misure)
        else:
            # Il device non supporta `stat -c`, oppure la cartella non esiste.
            ripiego = _esegui(
                [adb, "exec-out", "find", cartella, "-type", "f"],
                timeout=TIMEOUT_ENUMERAZIONE,
            )
            righe = [r for r in _testo(ripiego.stdout).splitlines() if r.strip()]
            conteggio, byte = len(righe), None
            if righe:
                dimensioni_disponibili = False

        risultati.append({
            "percorso": cartella,
            "file": conteggio,
            "byte": byte,
            "dimensione": _leggibile(byte),
        })
        totale_file += conteggio
        totale_byte += byte or 0

    nota = None
    if not dimensioni_disponibili:
        nota = ("Il telefono non supporta «stat -c»: posso contare i file ma non "
                "misurarne la dimensione.")

    return {
        "cartelle": risultati,
        "totale_file": totale_file,
        "totale_byte": totale_byte if dimensioni_disponibili else None,
        "totale_dimensione": _leggibile(totale_byte) if dimensioni_disponibili else None,
        "nota": nota,
    }


@mcp.tool()
async def backup_start(
    destination: str | None = None, dry_run: bool = False
) -> dict[str, Any]:
    """Avvia un backup in background e restituisce subito un job_id.

    Non attende la fine: un primo backup può durare oltre mezz'ora. Usa
    `backup_status` per seguirne l'avanzamento.

    `destination` deve essere un percorso assoluto dentro la tua cartella utente;
    se omesso usa ~/Backup-Galaxy. Con `dry_run` lo script elenca cosa copierebbe
    senza copiare nulla.

    Un solo backup alla volta: se ne è già in corso uno, non ne avvia un secondo
    e restituisce il job_id di quello attivo.
    """
    destinazione = _valida_destinazione(destination)

    attivo = _job_attivo()
    if attivo:
        return {
            "avviato": False,
            "job_id": attivo,
            "messaggio": (
                f"Un backup è già in corso (job {attivo}). Attendi che finisca, "
                "oppure controllane lo stato con backup_status."
            ),
        }

    try:
        adb = _pretendi_dispositivo()
    except ErroreUtente as e:
        raise MCPError(INTERNAL_ERROR, str(e)) from e
    del adb  # serviva solo a validare che il telefono ci sia

    try:
        destinazione.mkdir(parents=True, exist_ok=True)
        sonda = destinazione / ".galaxy-backup-scrittura"
        sonda.touch()
        sonda.unlink()
    except OSError as e:
        raise MCPError(
            INTERNAL_ERROR,
            f"Non riesco a scrivere in {destinazione}. Controlla i permessi della "
            f"cartella, o che il disco sia montato. ({e.strerror})",
        ) from e

    CARTELLA_JOB.mkdir(parents=True, exist_ok=True)

    job_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffisso = 2
    while _file_meta(job_id).exists():
        job_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{suffisso}"
        suffisso += 1

    ambiente = _ambiente_con_adb()
    ambiente["STATUS_FILE"] = str(_file_progresso(job_id))
    if dry_run:
        ambiente["DRY_RUN"] = "1"

    log = _file_log(job_id)
    with log.open("wb") as uscita:
        processo = subprocess.Popen(  # noqa: S603 - lista di argomenti, nessuna shell
            [str(SCRIPT_BACKUP), str(destinazione)],
            stdout=uscita,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=ambiente,
            # Sessione nuova: il backup sopravvive alla chiusura di questo server.
            start_new_session=True,
        )

    _file_meta(job_id).write_text(
        json.dumps(
            {
                "job_id": job_id,
                "destinazione": str(destinazione),
                "dry_run": dry_run,
                "pid": processo.pid,
                "avviato": _adesso(),
                "log": str(log),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "avviato": True,
        "job_id": job_id,
        "destinazione": str(destinazione),
        "dry_run": dry_run,
        "messaggio": (
            "Backup avviato in background. Il primo giro su una libreria grande "
            "può durare a lungo: segui l'avanzamento con backup_status."
        ),
    }


@mcp.tool()
async def backup_status(job_id: str | None = None) -> dict[str, Any]:
    """Stato di un backup: quanti file copiati, saltati, quanti errori, a che punto è.

    Senza `job_id` riporta l'ultimo backup avviato. Sola lettura.
    """
    if job_id is None:
        elenco = _elenco_job()
        if not elenco:
            return {
                "trovato": False,
                "messaggio": "Nessun backup è mai stato avviato da questo server.",
            }
        job_id = elenco[-1]

    meta = _leggi_json(_file_meta(job_id))
    if meta is None:
        return {
            "trovato": False,
            "job_id": job_id,
            "messaggio": f"Non esiste un backup con id {job_id}.",
        }

    # Rileva i job morti senza esito prima di rispondere, così lo stato non resta
    # bloccato su "in_corso" per sempre.
    _job_attivo()

    progresso = _leggi_json(_file_progresso(job_id))
    if progresso is None:
        return {
            "trovato": True,
            "job_id": job_id,
            "stato": "sconosciuto",
            "destinazione": meta.get("destinazione"),
            "messaggio": (
                "Il backup è stato avviato ma non ha ancora scritto il suo stato, "
                "oppure il file di stato è illeggibile. Riprova tra qualche secondo."
            ),
        }

    trascorso = None
    avviato = meta.get("avviato")
    aggiornato = progresso.get("aggiornato")
    if avviato and aggiornato:
        try:
            t0 = datetime.strptime(avviato, "%Y-%m-%dT%H:%M:%SZ")
            t1 = datetime.strptime(aggiornato, "%Y-%m-%dT%H:%M:%SZ")
            trascorso = int((t1 - t0).total_seconds())
        except ValueError:
            trascorso = None

    destinazione = Path(meta.get("destinazione", ""))
    errori, errori_totali = _errori_recenti(destinazione)

    return {
        "trovato": True,
        "job_id": job_id,
        "stato": progresso.get("stato"),
        "destinazione": meta.get("destinazione"),
        "dry_run": meta.get("dry_run"),
        "cartella_corrente": progresso.get("cartella_corrente"),
        "cartelle_completate": progresso.get("cartelle_completate"),
        "cartelle_totali": progresso.get("cartelle_totali"),
        "nuovi": progresso.get("nuovi"),
        "ricopiati": progresso.get("ricopiati"),
        "saltati": progresso.get("saltati"),
        "errori": progresso.get("errori"),
        "exit_code": progresso.get("exit_code"),
        "secondi_trascorsi": trascorso,
        "errori_recenti": errori,
        "errori_recenti_troncati": errori_totali > len(errori),
        "errori_totali": errori_totali,
        "log": meta.get("log"),
    }


@mcp.tool()
async def capture_screen() -> dict[str, Any]:
    """Cattura lo schermo attuale del telefono e lo salva come PNG sul Mac.

    Serve al recupero degli sfondi descritto in docs/wallpaper-recovery.md: lo
    sfondo applicato non è un file copiabile, ma se ne può fotografare
    l'anteprima a schermo intero.

    È un'operazione di sola lettura sul dispositivo. Restituisce il percorso del
    file salvato, non i byte dell'immagine.
    """
    try:
        adb = _pretendi_dispositivo()
    except ErroreUtente as e:
        raise MCPError(INTERNAL_ERROR, str(e)) from e

    esito = _esegui([adb, "exec-out", "screencap", "-p"], timeout=TIMEOUT_RAPIDO)
    dati = esito.stdout
    if esito.returncode != 0 or not dati.startswith(b"\x89PNG"):
        raise MCPError(
            INTERNAL_ERROR,
            "La cattura dello schermo non ha prodotto un'immagine valida. "
            "Controlla che lo schermo del telefono sia acceso e sbloccato.",
        )

    CARTELLA_SCHERMATE.mkdir(parents=True, exist_ok=True)
    nome = datetime.now(timezone.utc).strftime("schermata-%Y%m%d-%H%M%S.png")
    percorso = CARTELLA_SCHERMATE / nome
    percorso.write_bytes(dati)

    return {
        "percorso": str(percorso),
        "byte": len(dati),
        "dimensione": _leggibile(len(dati)),
        "messaggio": f"Schermata salvata in {percorso}",
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
