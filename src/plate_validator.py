"""Validação e normalização de placas de veículos brasileiras.

Formatos aceitos:
- Antiga:   ABC-1234  ->  3 letras + 4 dígitos
- Mercosul: ABC1D23   ->  3 letras + dígito + letra + 2 dígitos
"""
from __future__ import annotations

import re

# Mantém apenas letras e dígitos; usado para limpar hífen, espaços, etc.
_CLEANUP_RE = re.compile(r"[^A-Z0-9]")

_ANTIGA_RE = re.compile(r"^[A-Z]{3}[0-9]{4}$")
_MERCOSUL_RE = re.compile(r"^[A-Z]{3}[0-9][A-Z][0-9]{2}$")


def normalize(plate: str) -> str:
    """Coloca em maiúsculas e remove tudo que não for letra/dígito (hífen, espaços)."""
    if plate is None:
        return ""
    return _CLEANUP_RE.sub("", plate.upper())


def is_valid_br(plate: str) -> bool:
    """Retorna True se a placa (já ou ainda não normalizada) tem formato BR válido."""
    normalized = normalize(plate)
    return bool(_ANTIGA_RE.match(normalized) or _MERCOSUL_RE.match(normalized))
