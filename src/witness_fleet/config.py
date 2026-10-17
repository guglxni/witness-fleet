"""Local simulation configuration; never load credentials from tracked files."""
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

PositiveInt = Annotated[int, Field(strict=True, ge=1)]


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    graph_host: Literal["127.0.0.1", "localhost"] = "127.0.0.1"
    graph_port: Annotated[int, Field(strict=True, ge=1, le=65535)] = 6380
    tenant_id: Literal["demo"] = "demo"
    graph_username: str = "wf_ops"
    simulator_url: str = "http://127.0.0.1:8091"
    corpus_url: str = "http://127.0.0.1:8092"
    tick_hz: PositiveInt = 100
    observation_ttl_ticks: PositiveInt = 1500
    model_mode: Literal["disabled", "shadow", "advisory"] = "disabled"
    inspection_budget: PositiveInt = 3
    recovery_budget: PositiveInt = 2
    data_dir: str = "runtime-data"

    @field_validator("simulator_url", "corpus_url")
    @classmethod
    def local_service(cls, value: str) -> str:
        url = urlsplit(value)
        if url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost"} or url.username or url.password or url.query or url.fragment:
            raise ValueError("simulation services must be uncredentialed loopback HTTP")
        return value
