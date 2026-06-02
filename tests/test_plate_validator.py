"""Testes do validador/normalizador de placas brasileiras."""
import datetime

import pytest

from src.plate_validator import is_valid_br, normalize
from src.dedupe import TimeWindowDedup


# ---------- normalize ----------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("abc-1234", "ABC1234"),
        (" ABC1D23 ", "ABC1D23"),
        ("abc 1d23", "ABC1D23"),
        ("ABC-1D23", "ABC1D23"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize(raw, expected):
    assert normalize(raw) == expected


# ---------- is_valid_br ----------

@pytest.mark.parametrize(
    "plate",
    [
        "ABC1234",      # antiga
        "abc-1234",     # antiga com hífen/minúscula
        "ABC1D23",      # Mercosul
        "abc1d23",      # Mercosul minúscula
    ],
)
def test_valid_plates(plate):
    assert is_valid_br(plate) is True


@pytest.mark.parametrize(
    "plate",
    [
        "AB1234",       # poucas letras
        "ABCD123",      # letra demais
        "1234ABC",      # ordem errada
        "ABC12D3",      # Mercosul mal formado
        "ABC-123",      # dígitos de menos
        "",             # vazio
        "ABC12345",     # dígitos demais
    ],
)
def test_invalid_plates(plate):
    assert is_valid_br(plate) is False


# ---------- TimeWindowDedup ----------

def test_dedup_window():
    dedup = TimeWindowDedup(window_seconds=30)
    t0 = datetime.datetime(2026, 6, 1, 12, 0, 0)

    # primeira vez: emite
    assert dedup.should_emit("ABC1D23", now=t0) is True
    # dentro da janela: não emite
    assert dedup.should_emit("ABC1D23", now=t0 + datetime.timedelta(seconds=10)) is False
    # passou a janela: emite de novo
    assert dedup.should_emit("ABC1D23", now=t0 + datetime.timedelta(seconds=31)) is True
    # placa diferente é independente
    assert dedup.should_emit("XYZ4321", now=t0 + datetime.timedelta(seconds=11)) is True
