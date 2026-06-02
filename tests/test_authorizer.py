"""Testes da interpretação de resposta da API e do controlador de GPIO."""
from src.authorizer import interpret_response
from src.config import GpioConfig
from src.gpio import NoopGateController, build_gate_controller


# ---------- interpret_response ----------

def test_autoriza_por_campo():
    d = interpret_response(True, {"autorizado": True}, "autorizado", True)
    assert d.authorized is True


def test_nega_por_campo_falso():
    d = interpret_response(True, {"autorizado": False}, "autorizado", True)
    assert d.authorized is False


def test_nega_quando_campo_ausente():
    d = interpret_response(True, {"outro": 1}, "autorizado", True)
    assert d.authorized is False


def test_nega_quando_http_erro():
    d = interpret_response(False, {"autorizado": True}, "autorizado", True)
    assert d.authorized is False


def test_auth_field_vazio_usa_status_http():
    assert interpret_response(True, None, "", True).authorized is True
    assert interpret_response(False, None, "", True).authorized is False


def test_valor_customizado():
    assert interpret_response(True, {"status": "OK"}, "status", "OK").authorized is True
    assert interpret_response(True, {"status": "NEG"}, "status", "OK").authorized is False


# ---------- gate controller ----------

def test_gate_desabilitado_vira_noop():
    gate = build_gate_controller(GpioConfig(enabled=False))
    assert isinstance(gate, NoopGateController)
    gate.trigger()  # não deve lançar
    gate.close()


def test_gate_sem_hardware_cai_para_noop():
    # Em ambiente sem gpiozero/Pi, mesmo habilitado deve cair para no-op.
    gate = build_gate_controller(GpioConfig(enabled=True, pin=17))
    assert isinstance(gate, NoopGateController)
    gate.trigger()
