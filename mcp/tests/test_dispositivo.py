"""Stato del dispositivo e cattura schermo, nei vari stati di connessione."""

from __future__ import annotations

import asyncio

import pytest
from mcp import MCPError


def esegui(coro):
    return asyncio.run(coro)


def test_dispositivo_collegato(amb):
    esito = esegui(amb.server.device_status())
    assert esito["collegato"] is True
    assert esito["stato"] == "device"
    assert esito["modello"] == "SM-A315F"
    assert esito["android"] == "12"
    # 20971520 blocchi da 1K nell'output finto di df
    assert esito["spazio_libero_bytes"] == 20971520 * 1024
    assert "GB" in esito["spazio_libero"]


def test_dispositivo_non_autorizzato(amb, monkeypatch):
    monkeypatch.setenv("FAKE_STATE", "unauthorized")
    esito = esegui(amb.server.device_status())
    assert esito["collegato"] is False
    assert esito["stato"] == "unauthorized"
    # il messaggio deve dire cosa fare, non cosa è fallito
    assert "sblocca" in esito["messaggio"].lower()
    assert "debug usb" in esito["messaggio"].lower()


def test_dispositivo_assente(amb, monkeypatch):
    monkeypatch.setenv("FAKE_STATE", "absent")
    esito = esegui(amb.server.device_status())
    assert esito["collegato"] is False
    assert esito["stato"] == "absent"
    assert "cavo" in esito["messaggio"].lower()


def test_adb_non_installato(amb, monkeypatch):
    """Senza adb il tool non deve esplodere: deve spiegare come installarlo."""
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    esito = esegui(amb.server.device_status())
    assert esito["collegato"] is False
    assert esito["stato"] == "adb_assente"
    assert "setup-android-mac.sh" in esito["messaggio"]


def test_cattura_schermo(amb):
    esito = esegui(amb.server.capture_screen())
    percorso = amb.casa / ".galaxy-backup" / "screenshots"
    assert esito["percorso"].startswith(str(percorso))
    assert esito["byte"] == len(amb.png_atteso)
    # il PNG viene salvato su disco, i byte non finiscono nella risposta
    assert "byte_immagine" not in esito
    from pathlib import Path
    assert Path(esito["percorso"]).read_bytes() == amb.png_atteso


def test_cattura_schermo_senza_dispositivo(amb, monkeypatch):
    monkeypatch.setenv("FAKE_STATE", "absent")
    with pytest.raises(MCPError) as e:
        esegui(amb.server.capture_screen())
    assert "cavo" in str(e.value).lower()
