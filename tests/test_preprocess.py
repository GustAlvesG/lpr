"""Testes do pré-processamento de frames."""
import numpy as np

from src.config import PreprocessConfig
from src.preprocess import FramePreprocessor


def _img():
    # imagem BGR sintética com gradiente (simula iluminação irregular)
    h, w = 48, 64
    base = np.tile(np.linspace(0, 255, w, dtype=np.uint8), (h, 1))
    return np.stack([base, base // 2, base // 3], axis=-1)


def test_desabilitado_retorna_mesmo_frame():
    img = _img()
    out = FramePreprocessor(PreprocessConfig(enabled=False)).process(img)
    assert out is img


def test_grayscale_mantem_3_canais_e_dimensoes():
    img = _img()
    out = FramePreprocessor(PreprocessConfig(grayscale=True, clahe=True)).process(img)
    assert out.shape == img.shape          # mesma altura/largura, 3 canais
    # cinza replicado: os 3 canais ficam iguais
    assert np.array_equal(out[:, :, 0], out[:, :, 1])
    assert np.array_equal(out[:, :, 1], out[:, :, 2])


def test_color_clahe_preserva_shape():
    img = _img()
    out = FramePreprocessor(PreprocessConfig(grayscale=False, clahe=True)).process(img)
    assert out.shape == img.shape


def test_gamma_clareia():
    img = _img()
    cfg = PreprocessConfig(grayscale=True, clahe=False, gamma=2.0)  # >1 clareia
    out = FramePreprocessor(cfg).process(img)
    # região não saturada deve ficar, em média, mais clara
    assert out.mean() > img.mean()
