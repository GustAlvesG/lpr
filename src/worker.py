"""Worker de uma câmera: roda em sua própria thread.

Cada worker lê o stream da sua câmera, reconhece placas (motor compartilhado),
valida, deduplica (por câmera) e emite para os sinks (compartilhados).
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime

from . import plate_validator
from .authorizer import Authorizer
from .config import CameraConfig, Config
from .dedupe import TimeWindowDedup
from .gpio import GateController
from .preprocess import FramePreprocessor
from .recognizer import PlateRecognizer
from .sinks import RecordSink
from .stream import RTSPStream

logger = logging.getLogger(__name__)


class CameraWorker(threading.Thread):
    def __init__(
        self,
        camera: CameraConfig,
        cfg: Config,
        recognizer: PlateRecognizer,
        sinks: list[RecordSink],
        authorizer: Authorizer | None,
        gate: GateController,
    ) -> None:
        super().__init__(name=f"cam-{camera.name}", daemon=True)
        self.camera = camera
        self.cfg = cfg
        self.recognizer = recognizer
        self.sinks = sinks
        self.authorizer = authorizer
        self.gate = gate
        self.preprocessor = FramePreprocessor(cfg.preprocess)
        # Deduplicação independente por câmera: a mesma placa vista na "entrada"
        # e na "saida" são eventos distintos.
        self.dedup = TimeWindowDedup(cfg.dedup_window_seconds)
        self.stream = RTSPStream(
            source=camera.source,
            frame_skip=cfg.frame_skip,
            reconnect_delay_seconds=cfg.reconnect_delay_seconds,
        )

    def run(self) -> None:
        logger.info("[%s] Iniciando captura: %s", self.camera.name, self.camera.source)
        try:
            for frame in self.stream.frames():
                self._process(frame)
        except Exception:  # noqa: BLE001 - uma câmera não pode derrubar as outras
            logger.exception("[%s] Worker encerrado por erro inesperado.", self.camera.name)
        finally:
            self.stream.close()
            logger.info("[%s] Captura finalizada.", self.camera.name)

    def _process(self, frame) -> None:
        frame = self.preprocessor.process(frame)
        for reading in self.recognizer.recognize(frame):
            plate = plate_validator.normalize(reading.text)

            if self.cfg.validate_br_format and not plate_validator.is_valid_br(plate):
                logger.debug("[%s] Ignorada (formato inválido): %s", self.camera.name, reading.text)
                continue

            if not self.dedup.should_emit(plate):
                continue

            now = datetime.now()
            logger.info(
                "[%s] Placa registrada: %s (conf=%.2f)",
                self.camera.name,
                plate,
                reading.confidence,
            )
            for sink in self.sinks:
                sink.emit(self.camera.name, plate, now, reading.confidence)

            self._authorize_and_act(plate, now)

    def _authorize_and_act(self, plate: str, when: datetime) -> None:
        """Consulta a API e, se autorizado, aciona o GPIO."""
        if self.authorizer is None:
            return
        decision = self.authorizer.authorize(self.camera.name, plate, when)
        if decision.authorized:
            logger.info("[%s] Acesso AUTORIZADO para %s (%s).", self.camera.name, plate, decision.detail)
            self.gate.trigger()
        else:
            logger.info("[%s] Acesso NEGADO para %s (%s).", self.camera.name, plate, decision.detail)

    def stop(self) -> None:
        self.stream.stop()
