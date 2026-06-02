"""Testes do parser de câmeras do config."""
import pytest

from src.config import _parse_cameras


def test_lista_de_cameras():
    raw = {
        "cameras": [
            {"name": "entrada", "source": "rtsp://a"},
            {"name": "saida", "source": "rtsp://b"},
        ]
    }
    cams = _parse_cameras(raw)
    assert [(c.name, c.source) for c in cams] == [
        ("entrada", "rtsp://a"),
        ("saida", "rtsp://b"),
    ]


def test_nome_default_quando_ausente():
    cams = _parse_cameras({"cameras": [{"source": "rtsp://a"}, {"source": "rtsp://b"}]})
    assert [c.name for c in cams] == ["cam1", "cam2"]


def test_retrocompat_source_unico():
    cams = _parse_cameras({"source": "rtsp://a"})
    assert len(cams) == 1
    assert cams[0].name == "cam1"
    assert cams[0].source == "rtsp://a"


def test_nomes_duplicados_falham():
    raw = {"cameras": [{"name": "x", "source": "rtsp://a"}, {"name": "x", "source": "rtsp://b"}]}
    with pytest.raises(ValueError):
        _parse_cameras(raw)


def test_camera_sem_source_falha():
    with pytest.raises(ValueError):
        _parse_cameras({"cameras": [{"name": "x"}]})


def test_sem_cameras_falha():
    with pytest.raises(ValueError):
        _parse_cameras({})
