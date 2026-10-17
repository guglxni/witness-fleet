import pytest
from pydantic import ValidationError

from witness_fleet.config import Settings


def test_network_services_must_be_loopback_only():
    with pytest.raises(ValidationError):
        Settings(simulator_url="http://evil.example:8091")


def test_defaults_do_not_enable_model_or_public_control():
    cfg = Settings()
    assert cfg.model_mode == "disabled"
    assert cfg.graph_host == "127.0.0.1"
    assert cfg.graph_port == 6380


def test_budgets_ticks_and_tenant_cannot_be_invalid():
    for field, value in [("tick_hz",0),("tick_hz",True),("inspection_budget",-1),("tenant_id","other"),("model_mode","authority")]:
        with pytest.raises(ValidationError):
            Settings(**{field: value})
