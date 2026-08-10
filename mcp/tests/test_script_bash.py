"""Contratto fra il server e backup-android.sh.

Il server dipende da due comportamenti dello script: `--list-dirs` e il file di
stato JSON. Questi test li fissano, così una futura modifica allo script non può
romperli in silenzio.
"""

from __future__ import annotations

import json
import os
import subprocess

import pytest


def lancia(amb, argomenti, ambiente_extra=None, senza_adb=False):
    ambiente = dict(os.environ)
    if ambiente_extra:
        ambiente.update(ambiente_extra)
    if senza_adb:
        ambiente["PATH"] = "/usr/bin:/bin"
    return subprocess.run(
        [str(amb.script), *argomenti],
        capture_output=True,
        text=True,
        env=ambiente,
        timeout=120,
        check=False,
    )


# ------------------------------------------------------------ --list-dirs ---


def test_list_dirs_funziona_senza_adb(amb):
    """Il server lo chiama anche a telefono staccato: non deve dipendere da adb."""
    esito = lancia(amb, ["--list-dirs"], senza_adb=True)
    assert esito.returncode == 0
    righe = esito.stdout.strip().splitlines()
    assert righe[0] == "/sdcard/DCIM"
    assert len(righe) == 7
    assert all(r.startswith("/") for r in righe)


def test_list_dirs_non_crea_la_destinazione(amb):
    lancia(amb, ["--list-dirs"], senza_adb=True)
    assert not (amb.casa / "Backup-Android").exists()


def test_elenco_dello_script_e_quello_del_server(amb):
    """Unica fonte di verità: il server non deve avere una copia sua."""
    esito = lancia(amb, ["--list-dirs"], senza_adb=True)
    assert esito.stdout.strip().splitlines() == amb.server._cartelle_remote()


# ------------------------------------------------------------ STATUS_FILE ---


def test_stdout_identico_con_e_senza_status_file(amb, tmp_path):
    """L'invariante: attivare STATUS_FILE non deve cambiare l'output leggibile."""
    senza = lancia(amb, [str(tmp_path / "a")])
    con = lancia(amb, [str(tmp_path / "b")],
                 {"STATUS_FILE": str(tmp_path / "stato.json")})

    # le destinazioni differiscono per costruzione: normalizzo prima di confrontare
    normale = senza.stdout.replace(str(tmp_path / "a"), "DEST")
    con_stato = con.stdout.replace(str(tmp_path / "b"), "DEST")

    assert normale == con_stato
    assert senza.stderr == con.stderr
    assert senza.returncode == con.returncode


def test_stato_completato(amb, tmp_path):
    stato = tmp_path / "stato.json"
    esito = lancia(amb, [str(tmp_path / "dest")], {"STATUS_FILE": str(stato)})
    assert esito.returncode == 0

    dati = json.loads(stato.read_text())
    assert dati["stato"] == "completato"
    assert dati["exit_code"] == 0
    assert dati["cartelle_completate"] == dati["cartelle_totali"] == 7
    assert dati["cartella_corrente"] is None
    assert dati["nuovi"] == 4
    assert dati["dry_run"] is False


def test_stato_fallito_quando_una_copia_non_riesce(amb, tmp_path):
    stato = tmp_path / "stato.json"
    esito = lancia(amb, [str(tmp_path / "dest")],
                   {"STATUS_FILE": str(stato), "FAKE_FAIL_ON": "foto1.jpg"})
    assert esito.returncode == 1

    dati = json.loads(stato.read_text())
    assert dati["stato"] == "fallito"
    assert dati["exit_code"] == 1
    assert dati["errori"] == 1


def test_stato_interrotto_se_muore_sui_controlli(amb, tmp_path):
    """Senza adb lo script muore subito: chi legge non deve restare su «in_corso»."""
    stato = tmp_path / "stato.json"
    esito = lancia(amb, [str(tmp_path / "dest")],
                   {"STATUS_FILE": str(stato)}, senza_adb=True)
    assert esito.returncode == 1

    dati = json.loads(stato.read_text())
    assert dati["stato"] == "interrotto"
    assert dati["cartelle_completate"] == 0


def test_stato_dry_run(amb, tmp_path):
    stato = tmp_path / "stato.json"
    lancia(amb, [str(tmp_path / "dest")],
           {"STATUS_FILE": str(stato), "DRY_RUN": "1"})
    dati = json.loads(stato.read_text())
    assert dati["dry_run"] is True
    assert dati["stato"] == "completato"
    assert not (tmp_path / "dest" / "DCIM").exists()


def test_status_file_non_scrivibile_non_disturba(amb, tmp_path):
    """Un percorso di stato impossibile non deve far fallire il backup."""
    esito = lancia(amb, [str(tmp_path / "dest")],
                   {"STATUS_FILE": "/percorso/che/non/esiste/stato.json"})
    assert esito.returncode == 0
    assert "Riepilogo" in esito.stdout


def test_lo_stato_e_sempre_json_valido(amb, tmp_path):
    """Scrittura atomica: nessun lettore deve mai trovare un file a metà."""
    stato = tmp_path / "stato.json"
    lancia(amb, [str(tmp_path / "dest")], {"STATUS_FILE": str(stato)})
    for _ in range(50):
        json.loads(stato.read_text())
    assert not (tmp_path / "stato.json.tmp").exists()
