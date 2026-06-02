"""Deduplicação de leituras por janela de tempo.

Evita registrar a mesma placa repetidas vezes enquanto o veículo aparece em
vários frames seguidos.
"""
from __future__ import annotations

from datetime import datetime, timedelta


class TimeWindowDedup:
    def __init__(self, window_seconds: int) -> None:
        self._window = timedelta(seconds=window_seconds)
        self._last_seen: dict[str, datetime] = {}

    def should_emit(self, plate: str, now: datetime | None = None) -> bool:
        """Retorna True se a placa deve ser registrada agora.

        É True quando a placa nunca foi vista ou quando já se passou a janela
        desde a última emissão. Atualiza o cache quando retorna True.
        """
        now = now or datetime.now()
        last = self._last_seen.get(plate)
        if last is not None and (now - last) < self._window:
            return False
        self._last_seen[plate] = now
        return True
