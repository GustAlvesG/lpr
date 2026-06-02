"""Wrapper do fast-alpr: detecção de placa + OCR, com filtro de confiança."""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from fast_alpr import ALPR

logger = logging.getLogger(__name__)


@dataclass
class PlateReading:
    text: str
    confidence: float


def _scalar_confidence(confidence) -> float:
    """OcrResult.confidence pode ser float ou lista (por caractere) — reduz a um escalar."""
    if isinstance(confidence, (list, tuple)):
        return sum(confidence) / len(confidence) if confidence else 0.0
    return float(confidence)


class PlateRecognizer:
    def __init__(self, detector_model: str, ocr_model: str, min_confidence: float) -> None:
        self.min_confidence = min_confidence
        # Inferência serializada por lock: em CPU, rodar dois predict() em
        # paralelo só oversubscreve os núcleos. Uma instância de modelo é
        # compartilhada por todas as câmeras.
        self._lock = threading.Lock()
        logger.info("Carregando modelos ALPR (pode baixar no primeiro uso)...")
        self._alpr = ALPR(detector_model=detector_model, ocr_model=ocr_model)
        logger.info("Modelos ALPR prontos.")

    def recognize(self, frame) -> list[PlateReading]:
        """Retorna as leituras com confiança >= min_confidence."""
        readings: list[PlateReading] = []
        with self._lock:
            results = self._alpr.predict(frame)
        for result in results:
            ocr = result.ocr
            if ocr is None or not ocr.text:
                continue
            conf = _scalar_confidence(ocr.confidence)
            if conf < self.min_confidence:
                continue
            readings.append(PlateReading(text=ocr.text, confidence=conf))
        return readings
