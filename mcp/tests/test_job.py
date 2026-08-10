"""Ciclo di vita di un job: avvio, unicità, stato, file di stato corrotti."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time

import pytest
from mcp import MCPError


def esegui(coro):
    return asyncio.run(coro)


def attendi_esito(server, job_id, secondi=30):
    """Aspetta che il job raggiunga uno stato terminale."""
    scadenza = time.time() + secondi
    while time.time() < scadenza:
        esito = esegui(server.backup_status(job_id))
        if esito.get("stato") in ("completato", "fallito", "interrotto"):
            return esito
        time.sleep(0.2)
    pytest.fail(f"il job {job_id} non è terminato entro {secondi}s")


def _pid_terminato() -> int:
    """Pid di un processo sicuramente morto, per simulare un job orfano."""
    p = subprocess.Popen(["/usr/bin/true"])
    p.wait()
    return p.pid


def prepara_job(amb, job_id, pid, stato):
    """Scrive a mano i file di un job, per controllarne lo stato senza corse."""
    cartella = amb.server.CARTELLA_JOB
    cartella.mkdir(parents=True, exist_ok=True)
    (cartella / f"{job_id}.json").write_text(
        json.dumps({
            "job_id": job_id,
            "destinazione": str(amb.casa / "Backup-Android"),
            "dry_run": False,
            "pid": pid,
            "avviato": "2026-08-09T10:00:00Z",
            "log": str(cartella / f"{job_id}.log"),
        }),
        encoding="utf-8",
    )
    (cartella / f"{job_id}.progress.json").write_text(
        json.dumps({"stato": stato, "aggiornato": "2026-08-09T10:00:05Z",
                    "cartelle_completate": 1, "cartelle_totali": 7,
                    "nuovi": 3, "ricopiati": 0, "saltati": 0, "errori": 0,
                    "exit_code": None}),
        encoding="utf-8",
    )


# ----------------------------------------------------------- avvio ---------


def test_avvio_e_completamento(amb):
    avvio = esegui(amb.server.backup_start())
    assert avvio["avviato"] is True
    job_id = avvio["job_id"]

    esito = attendi_esito(amb.server, job_id)
    assert esito["stato"] == "completato"
    assert esito["exit_code"] == 0
    assert esito["nuovi"] == 4
    assert esito["cartelle_completate"] == esito["cartelle_totali"] == 7
    # i file sono davvero arrivati
    assert (amb.casa / "Backup-Android" / "DCIM" / "Camera" / "foto1.jpg").exists()


def test_avvio_dry_run_non_copia(amb):
    avvio = esegui(amb.server.backup_start(dry_run=True))
    attendi_esito(amb.server, avvio["job_id"])
    assert avvio["dry_run"] is True
    assert not (amb.casa / "Backup-Android" / "DCIM").exists()


def test_avvio_senza_dispositivo(amb, monkeypatch):
    monkeypatch.setenv("FAKE_STATE", "absent")
    with pytest.raises(MCPError) as e:
        esegui(amb.server.backup_start())
    assert "cavo" in str(e.value).lower()


def test_destinazione_non_scrivibile(amb):
    """Un file al posto della cartella: il messaggio deve parlare di permessi."""
    ostacolo = amb.casa / "Backup-Android"
    ostacolo.write_text("sono un file, non una cartella")
    with pytest.raises(MCPError) as e:
        esegui(amb.server.backup_start())
    assert "scrivere" in str(e.value).lower()


# ------------------------------------------------------- unicità -----------


def test_secondo_job_rifiutato(amb):
    """Con un job vivo, backup_start non ne avvia un secondo."""
    prepara_job(amb, "20260809-100000", os.getpid(), "in_corso")

    esito = esegui(amb.server.backup_start())
    assert esito["avviato"] is False
    assert esito["job_id"] == "20260809-100000"
    assert "già in corso" in esito["messaggio"]


def test_job_morto_non_blocca_per_sempre(amb):
    """Un job 'in_corso' il cui processo è morto viene marcato interrotto."""
    prepara_job(amb, "20260809-090000", _pid_terminato(), "in_corso")

    esito = esegui(amb.server.backup_start())
    assert esito["avviato"] is True
    assert esito["job_id"] != "20260809-090000"

    vecchio = esegui(amb.server.backup_status("20260809-090000"))
    assert vecchio["stato"] == "interrotto"
    attendi_esito(amb.server, esito["job_id"])


# --------------------------------------------------------- stato ----------


def test_stato_senza_job(amb):
    esito = esegui(amb.server.backup_status())
    assert esito["trovato"] is False
    assert "Nessun backup" in esito["messaggio"]


def test_stato_job_inesistente(amb):
    esito = esegui(amb.server.backup_status("20200101-000000"))
    assert esito["trovato"] is False


def test_stato_ultimo_job_se_omesso(amb):
    prepara_job(amb, "20260809-080000", _pid_terminato(), "completato")
    prepara_job(amb, "20260809-090000", _pid_terminato(), "completato")
    esito = esegui(amb.server.backup_status())
    assert esito["job_id"] == "20260809-090000"


@pytest.mark.parametrize("contenuto", ["", "{", '{"stato": ', "non json", "[]"])
def test_stato_corrotto_con_processo_morto_viene_riparato(amb, contenuto):
    """Stato illeggibile + processo morto: il job viene marcato interrotto.

    È più informativo di «sconosciuto»: il processo non c'è più, quindi il job
    è finito male comunque. La riparazione è sicura proprio perché avviene solo
    a processo morto, quando nessuno sta scrivendo quel file.
    """
    prepara_job(amb, "20260809-070000", _pid_terminato(), "completato")
    (amb.server.CARTELLA_JOB / "20260809-070000.progress.json").write_text(contenuto)

    esito = esegui(amb.server.backup_status("20260809-070000"))
    assert esito["trovato"] is True
    assert esito["stato"] == "interrotto"


@pytest.mark.parametrize("contenuto", ["", "{", '{"stato": ', "non json", "[]"])
def test_stato_corrotto_con_processo_vivo(amb, contenuto):
    """Stato illeggibile mentre il backup gira: nessuna eccezione, nessuna riparazione.

    Qui il file potrebbe essere corrotto solo perché lo stiamo leggendo a metà
    scrittura: toccarlo sarebbe sbagliato.
    """
    prepara_job(amb, "20260809-070000", os.getpid(), "in_corso")
    percorso = amb.server.CARTELLA_JOB / "20260809-070000.progress.json"
    percorso.write_text(contenuto)

    esito = esegui(amb.server.backup_status("20260809-070000"))
    assert esito["trovato"] is True
    assert esito["stato"] == "sconosciuto"
    assert "illeggibile" in esito["messaggio"]
    assert percorso.read_text() == contenuto  # non è stato riscritto


def test_errori_recenti_troncati_a_50(amb):
    """Un backup con migliaia di errori non deve saturare il contesto."""
    prepara_job(amb, "20260809-060000", _pid_terminato(), "fallito")
    destinazione = amb.casa / "Backup-Android"
    destinazione.mkdir(parents=True, exist_ok=True)
    righe = [f"FAIL nuovo    DCIM/Camera/foto{n}.jpg" for n in range(200)]
    (destinazione / "backup.log").write_text("\n".join(righe), encoding="utf-8")

    esito = esegui(amb.server.backup_status("20260809-060000"))
    assert len(esito["errori_recenti"]) == 50
    assert esito["errori_totali"] == 200
    assert esito["errori_recenti_troncati"] is True
