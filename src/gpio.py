"""Controle do pino GPIO do Raspberry Pi (ex.: abrir um portão/relé).

Usa `gpiozero` no Raspberry Pi. Fora do Pi (ex.: máquina de desenvolvimento
Windows) ou com o GPIO desabilitado, cai num controlador no-op que apenas
registra a ação — assim o sistema roda em qualquer ambiente.
"""
from __future__ import annotations

import logging
import threading
import time

from .config import GpioConfig

logger = logging.getLogger(__name__)


class GateController:
    """Interface do controlador de acionamento."""

    def trigger(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self) -> None:
        pass


class NoopGateController(GateController):
    """Não aciona hardware; só registra. Usado em dev ou quando desabilitado."""

    def __init__(self, reason: str) -> None:
        logger.warning("GPIO inativo (%s) — acionamentos serão apenas simulados.", reason)

    def trigger(self) -> None:
        logger.info("[GPIO simulado] Acionaria o portão agora.")


class GpioGateController(GateController):
    """Aciona um pino GPIO via gpiozero, com pulso de duração configurável."""

    def __init__(self, cfg: GpioConfig) -> None:
        from gpiozero import OutputDevice  # import tardio: só existe no Pi

        self._device = OutputDevice(
            cfg.pin, active_high=cfg.active_high, initial_value=False
        )
        self._pulse = cfg.pulse_seconds
        # Serializa acionamentos vindos de câmeras diferentes (uma porta só).
        self._lock = threading.Lock()
        logger.info(
            "GPIO ativo no pino BCM %d (active_high=%s, pulso=%.1fs).",
            cfg.pin,
            cfg.active_high,
            cfg.pulse_seconds,
        )

    def trigger(self) -> None:
        with self._lock:
            self._device.on()
            time.sleep(self._pulse)
            self._device.off()

    def close(self) -> None:
        try:
            self._device.close()
        except Exception:  # noqa: BLE001 - fechamento best-effort
            pass


def build_gate_controller(cfg: GpioConfig) -> GateController:
    """Cria o controlador adequado ao ambiente/configuração."""
    if not cfg.enabled:
        return NoopGateController(reason="desabilitado no config")
    try:
        return GpioGateController(cfg)
    except Exception as exc:  # noqa: BLE001 - sem hardware/lib disponível
        return NoopGateController(reason=f"gpiozero indisponível: {exc}")
