"""Ambiente di test: finto telefono, finta home, adb finto nel PATH.

Tutta la suite gira senza un dispositivo collegato. Nessun test tocca la home
vera dell'utente né il vero adb: la fixture `amb` isola entrambi.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

CARTELLA_TEST = Path(__file__).resolve().parent
CARTELLA_MCP = CARTELLA_TEST.parent
RADICE_REPO = CARTELLA_MCP.parent
STUB_ADB = CARTELLA_TEST / "fixtures" / "adb_stub.sh"

# Basta la firma PNG: il server valida i primi quattro byte, non decodifica
# l'immagine. Meglio un finto dichiarato che un binario opaco nel repo.
PNG_FINTO = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

sys.path.insert(0, str(CARTELLA_MCP))


@pytest.fixture
def amb(tmp_path, monkeypatch):
    """Telefono finto, home finta, adb finto. Restituisce i percorsi utili."""
    import server

    casa = tmp_path / "casa"
    casa.mkdir()

    sd = tmp_path / "sdcard"
    (sd / "DCIM" / "Camera").mkdir(parents=True)
    (sd / "DCIM" / "Screenshots").mkdir(parents=True)
    (sd / "Pictures").mkdir(parents=True)
    (sd / "DCIM" / "Camera" / "foto1.jpg").write_bytes(b"a" * 5000)
    (sd / "DCIM" / "Camera" / "foto con spazi.jpg").write_bytes(b"b" * 7000)
    (sd / "DCIM" / "Screenshots" / "schermata.png").write_bytes(b"c" * 3000)
    (sd / "Pictures" / "sfondo.jpg").write_bytes(b"d" * 2000)

    binari = tmp_path / "bin"
    binari.mkdir()
    adb = binari / "adb"
    shutil.copy(STUB_ADB, adb)
    adb.chmod(0o755)

    png = tmp_path / "schermata.png"
    png.write_bytes(PNG_FINTO)

    monkeypatch.setenv("HOME", str(casa))
    monkeypatch.setenv("PATH", os.pathsep.join([str(binari), "/usr/bin", "/bin"]))
    monkeypatch.setenv("FAKE_SD", str(sd))
    monkeypatch.setenv("FAKE_PNG", str(png))
    for variabile in ("FAKE_STATE", "FAKE_NO_STAT", "FAKE_FAIL_ON", "STATUS_FILE", "DRY_RUN"):
        monkeypatch.delenv(variabile, raising=False)

    stato = casa / ".galaxy-backup"
    monkeypatch.setattr(server, "CARTELLA_STATO", stato)
    monkeypatch.setattr(server, "CARTELLA_JOB", stato / "jobs")
    monkeypatch.setattr(server, "CARTELLA_SCHERMATE", stato / "screenshots")
    monkeypatch.setattr(server, "_cache_cartelle", None)
    # Senza questo, non trovando adb nel PATH il server ripiegherebbe sull'adb
    # vero installato sulla macchina, e i test non sarebbero più isolati.
    monkeypatch.setattr(server, "PERCORSI_ADB", ())

    return SimpleNamespace(
        server=server,
        casa=casa,
        sd=sd,
        binari=binari,
        adb=adb,
        png_atteso=PNG_FINTO,
        script=RADICE_REPO / "scripts" / "backup-android.sh",
    )
