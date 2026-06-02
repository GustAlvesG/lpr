"""Pré-processamento de frames para melhorar o reconhecimento sob luz difícil.

Foco em mitigar farol/glare e iluminação irregular:
- escala de cinza (mantendo 3 canais, exigência do detector YOLO);
- CLAHE (equalização adaptativa de contraste) para recuperar detalhe no estouro;
- correção de gamma opcional.

Cada câmera usa sua própria instância (o objeto CLAHE do OpenCV não é
compartilhável entre threads com segurança).
"""
from __future__ import annotations

import cv2
import numpy as np

from .config import PreprocessConfig


def _build_gamma_lut(gamma: float) -> np.ndarray | None:
    if gamma == 1.0:
        return None
    inv = 1.0 / max(gamma, 1e-6)
    table = np.array([((i / 255.0) ** inv) * 255 for i in range(256)], dtype=np.uint8)
    return table


class FramePreprocessor:
    def __init__(self, cfg: PreprocessConfig) -> None:
        self.cfg = cfg
        self._clahe = (
            cv2.createCLAHE(clipLimit=cfg.clahe_clip, tileGridSize=(cfg.clahe_grid, cfg.clahe_grid))
            if cfg.clahe
            else None
        )
        self._gamma_lut = _build_gamma_lut(cfg.gamma)

    def process(self, frame: np.ndarray) -> np.ndarray:
        if not self.cfg.enabled:
            return frame

        if self.cfg.grayscale:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if self._clahe is not None:
                gray = self._clahe.apply(gray)
            if self._gamma_lut is not None:
                gray = cv2.LUT(gray, self._gamma_lut)
            # Replica em 3 canais: o detector espera entrada BGR.
            return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        # Mantém cor: aplica CLAHE no canal de luminância (L do LAB).
        out = frame
        if self._clahe is not None:
            lab = cv2.cvtColor(out, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            l = self._clahe.apply(l)
            out = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
        if self._gamma_lut is not None:
            out = cv2.LUT(out, self._gamma_lut)
        return out
