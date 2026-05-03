from dataclasses import dataclass
from typing import Any, Dict
import yaml


@dataclass
class AppConfig:
    raw: Dict[str, Any]

    @property
    def app(self) -> Dict[str, Any]:
        return self.raw.get("app", {})

    @property
    def camera(self) -> Dict[str, Any]:
        return self.raw.get("camera", {})

    @property
    def model(self) -> Dict[str, Any]:
        return self.raw.get("model", {})

    @property
    def pose(self) -> Dict[str, Any]:
        return self.raw.get("pose", {})

    @property
    def sensor(self) -> Dict[str, Any]:
        return self.raw.get("sensor", {})

    @property
    def reflex(self) -> Dict[str, Any]:
        return self.raw.get("reflex", {})

    @property
    def output(self) -> Dict[str, Any]:
        return self.raw.get("output", {})


def load_config(path: str = "configs/default.yaml") -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return AppConfig(raw=raw)