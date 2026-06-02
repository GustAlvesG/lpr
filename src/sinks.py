"""Destinos de registro das leituras (sinks).

- FileSink: grava cada leitura em um arquivo de texto.

(O envio para a API deixou de ser um sink: virou o autorizador em
``authorizer.py``, pois a resposta da API decide o acionamento do GPIO.)
"""
from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from .config import FileSinkConfig

logger = logging.getLogger(__name__)


class RecordSink(ABC):
    @abstractmethod
    def emit(self, camera: str, plate: str, timestamp: datetime, confidence: float) -> None:
        ...

    def close(self) -> None:  # opcional; sobrescrito quando há recurso a liberar
        pass


class FileSink(RecordSink):
    """Acrescenta cada leitura em um arquivo de texto. Seguro entre threads."""

    def __init__(self, cfg: FileSinkConfig) -> None:
        self._path = Path(cfg.path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Mantém o arquivo aberto em modo append, com flush a cada escrita.
        self._fh = self._path.open("a", encoding="utf-8")
        self._lock = threading.Lock()

    def emit(self, camera: str, plate: str, timestamp: datetime, confidence: float) -> None:
        line = (
            f"{timestamp.isoformat(timespec='seconds')} | {camera} | "
            f"{plate} | conf={confidence:.2f}\n"
        )
        with self._lock:
            self._fh.write(line)
            self._fh.flush()

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:  # noqa: BLE001 - fechamento best-effort
            pass


def build_sinks(file_cfg: FileSinkConfig) -> list[RecordSink]:
    """Instancia os sinks de registro habilitados na configuração."""
    sinks: list[RecordSink] = []
    if file_cfg.enabled:
        sinks.append(FileSink(file_cfg))
    return sinks
