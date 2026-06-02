"""Carga e validação do arquivo de configuração (config.yaml)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class FileSinkConfig:
    enabled: bool = True
    path: str = "output/placas.txt"


@dataclass
class ApiConfig:
    """API de autorização: recebe placa+horário e responde se libera o acesso."""
    enabled: bool = False
    url: str = ""
    timeout: int = 5
    api_key: str = ""
    # Como interpretar a resposta JSON. Se auth_field for vazio, considera
    # autorizado qualquer resposta HTTP 2xx.
    auth_field: str = "autorizado"
    auth_value: object = True


@dataclass
class GpioConfig:
    """Acionamento de pino GPIO no Raspberry Pi quando o acesso é autorizado."""
    enabled: bool = False
    pin: int = 17               # número do pino no esquema BCM
    active_high: bool = True    # nível que aciona o relé/portão
    pulse_seconds: float = 2.0  # tempo que mantém acionado por leitura


@dataclass
class PreprocessConfig:
    """Melhora a imagem antes do reconhecimento (útil contra farol/glare)."""
    enabled: bool = True
    grayscale: bool = True      # converte para tons de cinza (mantém 3 canais p/ o detector)
    clahe: bool = True          # equalização adaptativa de contraste (recupera detalhe no estouro)
    clahe_clip: float = 2.0     # limite de contraste do CLAHE
    clahe_grid: int = 8         # tamanho da grade do CLAHE (tiles)
    gamma: float = 1.0          # 1.0 = sem ajuste; >1 clareia; <1 escurece


@dataclass
class CameraConfig:
    name: str
    source: str


@dataclass
class Config:
    cameras: list[CameraConfig]
    frame_skip: int = 5
    min_confidence: float = 0.80
    dedup_window_seconds: int = 30
    validate_br_format: bool = True
    reconnect_delay_seconds: int = 5
    detector_model: str = "yolo-v9-t-384-license-plate-end2end"
    ocr_model: str = "cct-xs-v2-global-model"
    file_sink: FileSinkConfig = field(default_factory=FileSinkConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    gpio: GpioConfig = field(default_factory=GpioConfig)
    preprocess: PreprocessConfig = field(default_factory=PreprocessConfig)


def _parse_cameras(raw: dict) -> list[CameraConfig]:
    """Lê a lista 'cameras'. Aceita também o formato antigo de 'source' único."""
    cameras_raw = raw.get("cameras")

    if not cameras_raw:
        # Retrocompatibilidade: um único 'source' vira uma câmera chamada "cam1".
        source = raw.get("source")
        if source:
            return [CameraConfig(name="cam1", source=str(source))]
        raise ValueError("Informe ao menos uma câmera em 'cameras' (ou um 'source').")

    if not isinstance(cameras_raw, list):
        raise ValueError("'cameras' deve ser uma lista.")

    cameras: list[CameraConfig] = []
    seen_names: set[str] = set()
    for i, cam in enumerate(cameras_raw):
        cam = cam or {}
        source = cam.get("source")
        if not source:
            raise ValueError(f"Câmera #{i + 1} sem 'source' no config.yaml.")
        name = str(cam.get("name") or f"cam{i + 1}")
        if name in seen_names:
            raise ValueError(f"Nome de câmera duplicado: '{name}'. Use nomes únicos.")
        seen_names.add(name)
        cameras.append(CameraConfig(name=name, source=str(source)))
    return cameras


def load_config(path: str = "config.yaml") -> Config:
    """Lê o YAML, valida campos essenciais e retorna um objeto Config."""
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {config_path}")

    with config_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    cameras = _parse_cameras(raw)

    sinks = raw.get("sinks", {}) or {}
    file_raw = sinks.get("file", {}) or {}
    api_raw = raw.get("api", {}) or {}
    gpio_raw = raw.get("gpio", {}) or {}
    pre_raw = raw.get("preprocess", {}) or {}

    cfg = Config(
        cameras=cameras,
        frame_skip=max(1, int(raw.get("frame_skip", 5))),
        min_confidence=float(raw.get("min_confidence", 0.80)),
        dedup_window_seconds=int(raw.get("dedup_window_seconds", 30)),
        validate_br_format=bool(raw.get("validate_br_format", True)),
        reconnect_delay_seconds=int(raw.get("reconnect_delay_seconds", 5)),
        detector_model=str(raw.get("detector_model", "yolo-v9-t-384-license-plate-end2end")),
        ocr_model=str(raw.get("ocr_model", "cct-xs-v2-global-model")),
        file_sink=FileSinkConfig(
            enabled=bool(file_raw.get("enabled", True)),
            path=str(file_raw.get("path", "output/placas.txt")),
        ),
        api=ApiConfig(
            enabled=bool(api_raw.get("enabled", False)),
            url=str(api_raw.get("url", "")),
            timeout=int(api_raw.get("timeout", 5)),
            api_key=str(api_raw.get("api_key", "")),
            auth_field=str(api_raw.get("auth_field", "autorizado")),
            auth_value=api_raw.get("auth_value", True),
        ),
        gpio=GpioConfig(
            enabled=bool(gpio_raw.get("enabled", False)),
            pin=int(gpio_raw.get("pin", 17)),
            active_high=bool(gpio_raw.get("active_high", True)),
            pulse_seconds=float(gpio_raw.get("pulse_seconds", 2.0)),
        ),
        preprocess=PreprocessConfig(
            enabled=bool(pre_raw.get("enabled", True)),
            grayscale=bool(pre_raw.get("grayscale", True)),
            clahe=bool(pre_raw.get("clahe", True)),
            clahe_clip=float(pre_raw.get("clahe_clip", 2.0)),
            clahe_grid=int(pre_raw.get("clahe_grid", 8)),
            gamma=float(pre_raw.get("gamma", 1.0)),
        ),
    )

    if not 0.0 <= cfg.min_confidence <= 1.0:
        raise ValueError("'min_confidence' deve estar entre 0.0 e 1.0.")
    if cfg.api.enabled and not cfg.api.url:
        raise ValueError("API habilitada, mas 'url' não foi informada.")
    if cfg.gpio.enabled and not cfg.api.enabled:
        raise ValueError("GPIO depende da API: habilite 'api' para acionar o GPIO.")

    return cfg
