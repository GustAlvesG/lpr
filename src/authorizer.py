"""Cliente da API de autorização.

Envia placa + horário (e câmera) e interpreta a resposta para decidir se o
acesso deve ser liberado — decisão que aciona (ou não) o GPIO.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import requests

from .config import ApiConfig

logger = logging.getLogger(__name__)


@dataclass
class AuthDecision:
    authorized: bool
    detail: str  # texto curto para log (motivo / status)


def interpret_response(
    status_ok: bool,
    body: dict | None,
    auth_field: str,
    auth_value: object,
) -> AuthDecision:
    """Decide a autorização a partir da resposta (função pura, testável).

    - Se `auth_field` for vazio: autoriza com base apenas no status HTTP 2xx.
    - Caso contrário: autoriza se body[auth_field] == auth_value.
    """
    if not status_ok:
        return AuthDecision(False, "HTTP de erro")
    if not auth_field:
        return AuthDecision(True, "HTTP 2xx")
    if not isinstance(body, dict) or auth_field not in body:
        return AuthDecision(False, f"campo '{auth_field}' ausente na resposta")
    actual = body[auth_field]
    if actual == auth_value:
        return AuthDecision(True, f"{auth_field}={actual}")
    return AuthDecision(False, f"{auth_field}={actual}")


class Authorizer:
    def __init__(self, cfg: ApiConfig) -> None:
        self._cfg = cfg
        self._headers = {"Content-Type": "application/json"}
        if cfg.api_key:
            self._headers["Authorization"] = f"Bearer {cfg.api_key}"

    def authorize(self, camera: str, plate: str, timestamp: datetime) -> AuthDecision:
        payload = {
            "placa": plate,
            "camera": camera,
            "momento": timestamp.isoformat(timespec="seconds"),
        }
        try:
            resp = requests.post(
                self._cfg.url, json=payload, headers=self._headers, timeout=self._cfg.timeout
            )
            try:
                body = resp.json()
            except ValueError:
                body = None
            return interpret_response(
                status_ok=resp.ok,
                body=body,
                auth_field=self._cfg.auth_field,
                auth_value=self._cfg.auth_value,
            )
        except requests.RequestException as exc:
            # Falha de rede/timeout: nega por segurança e não derruba o pipeline.
            logger.error("Falha ao consultar a API para a placa %s: %s", plate, exc)
            return AuthDecision(False, f"erro de conexão: {exc.__class__.__name__}")
