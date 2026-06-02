"""Orquestração do pipeline de reconhecimento de placas (multi-câmera).

Para cada câmera, sobe um worker em sua própria thread. Todos compartilham
um único motor de reconhecimento (serializado por lock, pois é CPU-bound) e
os mesmos sinks (escrita thread-safe).
"""
from __future__ import annotations

import logging
import time

from .authorizer import Authorizer
from .config import load_config
from .gpio import build_gate_controller
from .recognizer import PlateRecognizer
from .sinks import build_sinks
from .worker import CameraWorker

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main(config_path: str = "config.yaml") -> None:
    _setup_logging()
    cfg = load_config(config_path)

    recognizer = PlateRecognizer(
        detector_model=cfg.detector_model,
        ocr_model=cfg.ocr_model,
        min_confidence=cfg.min_confidence,
    )
    sinks = build_sinks(cfg.file_sink)
    if not sinks:
        logger.warning("Nenhum sink habilitado — as leituras não serão registradas.")

    authorizer = Authorizer(cfg.api) if cfg.api.enabled else None
    if authorizer is None:
        logger.info("API de autorização desabilitada — GPIO não será acionado.")
    gate = build_gate_controller(cfg.gpio)

    workers = [
        CameraWorker(cam, cfg, recognizer, sinks, authorizer, gate) for cam in cfg.cameras
    ]

    logger.info("Iniciando %d câmera(s). Ctrl+C para encerrar.", len(workers))
    for w in workers:
        w.start()

    try:
        # Mantém a thread principal viva enquanto houver worker ativo.
        while any(w.is_alive() for w in workers):
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.info("Encerrando por solicitação do usuário (Ctrl+C).")
    finally:
        for w in workers:
            w.stop()
        for w in workers:
            w.join(timeout=cfg.reconnect_delay_seconds + 5)
        for sink in sinks:
            sink.close()
        gate.close()
        logger.info("Pipeline finalizado.")
