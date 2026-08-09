"""Validazione dei percorsi, delle cartelle sorgente e trattamento dei nomi ostili.

I nomi dei file sul telefono sono dati non fidati: qui si verifica che non
possano mai diventare comandi né influenzare il flusso di controllo.
"""

from __future__ import annotations

import asyncio

import pytest
from mcp import MCPError


def esegui(coro):
    return asyncio.run(coro)


# ------------------------------------------------------ destinazione --------


def test_destinazione_predefinita(amb):
    assert amb.server._valida_destinazione(None) == amb.casa / "Backup-Galaxy"


def test_destinazione_valida(amb):
    scelta = amb.casa / "Foto" / "Galaxy"
    assert amb.server._valida_destinazione(str(scelta)) == scelta


def test_destinazione_relativa_rifiutata(amb):
    with pytest.raises(MCPError) as e:
        amb.server._valida_destinazione("Backup-Galaxy")
    assert "assoluto" in str(e.value)


def test_destinazione_fuori_da_home_rifiutata(amb):
    with pytest.raises(MCPError):
        amb.server._valida_destinazione("/etc")


def test_destinazione_con_traversal_rifiutata(amb):
    """`..` deve essere risolto e poi valutato, non filtrato come stringa."""
    with pytest.raises(MCPError):
        amb.server._valida_destinazione(f"{amb.casa}/../../../etc")


def test_destinazione_symlink_che_esce_da_home_rifiutata(amb, tmp_path):
    """Il caso che un controllo sulla stringa lascerebbe passare.

    Il percorso *sembra* dentro casa, ma è un symlink che punta fuori: per
    questo il percorso reale va risolto PRIMA di verificare il prefisso.
    """
    fuori = tmp_path / "fuori"
    fuori.mkdir()
    ponte = amb.casa / "sembra-dentro"
    ponte.symlink_to(fuori)

    assert str(ponte).startswith(str(amb.casa))  # inganna un controllo testuale
    with pytest.raises(MCPError) as e:
        amb.server._valida_destinazione(str(ponte))
    assert "fuori" in str(e.value)


def test_home_stessa_rifiutata(amb):
    """Scrivere il backup direttamente nella home non è «sotto» la home."""
    with pytest.raises(MCPError):
        amb.server._valida_destinazione(str(amb.casa))


# --------------------------------------------------- cartelle sorgente ------


def test_cartelle_lette_dallo_script(amb):
    cartelle = amb.server._cartelle_remote()
    assert "/sdcard/DCIM" in cartelle
    assert len(cartelle) == 7


def test_cartella_arbitraria_rifiutata(amb):
    with pytest.raises(MCPError) as e:
        esegui(amb.server.backup_inventory("/data/data/com.whatsapp"))
    assert "/sdcard/DCIM" in str(e.value)  # elenca quelle ammesse


def test_cartella_con_iniezione_rifiutata(amb):
    with pytest.raises(MCPError):
        esegui(amb.server.backup_inventory("/sdcard/DCIM; rm -rf ~"))


# --------------------------------------------------------- inventario -------


def test_inventario_conta_file_e_byte(amb):
    esito = esegui(amb.server.backup_inventory("/sdcard/DCIM"))
    assert esito["totale_file"] == 3
    assert esito["totale_byte"] == 5000 + 7000 + 3000
    assert esito["nota"] is None


def test_inventario_senza_stat_ripiega_sul_conteggio(amb, monkeypatch):
    monkeypatch.setenv("FAKE_NO_STAT", "1")
    esito = esegui(amb.server.backup_inventory("/sdcard/DCIM"))
    assert esito["totale_file"] == 3
    assert esito["totale_byte"] is None
    assert "stat -c" in esito["nota"]


def test_inventario_non_restituisce_nomi_di_file(amb):
    """L'inventario espone conteggi, mai l'elenco dei nomi: niente da saturare."""
    esito = esegui(amb.server.backup_inventory())
    assert "foto1.jpg" not in str(esito)


# -------------------------------------------------------- nomi ostili -------


@pytest.mark.parametrize(
    "nome",
    [
        "; rm -rf $HOME",
        "$(rm -rf ~)",
        "`id`",
        "file'con\"virgolette.jpg",
        "--strano-che-sembra-una-flag.jpg",
        "accentata-àèìòù-😀.jpg",
    ],
)
def test_nomi_ostili_non_vengono_eseguiti(amb, nome):
    """Un file col nome di un comando resta un file: viene contato, non eseguito."""
    (amb.sd / "Pictures" / nome).write_bytes(b"x" * 100)
    testimone = amb.casa / "non-cancellarmi.txt"
    testimone.write_text("intatto")

    esito = esegui(amb.server.backup_inventory("/sdcard/Pictures"))

    assert esito["totale_file"] == 2  # sfondo.jpg + quello ostile
    assert esito["totale_byte"] == 2000 + 100
    assert testimone.read_text() == "intatto"
    assert amb.casa.is_dir()


def test_nome_con_a_capo_non_rompe_il_conteggio(amb):
    """Un a-capo nel nome spezzerebbe un conteggio fatto per righe.

    Contando le dimensioni (soli interi) il problema non si pone: qui si
    verifica che il conteggio resti corretto.
    """
    (amb.sd / "Pictures" / "riga1\nriga2.jpg").write_bytes(b"y" * 42)
    esito = esegui(amb.server.backup_inventory("/sdcard/Pictures"))
    assert esito["totale_file"] == 2
    assert esito["totale_byte"] == 2000 + 42
