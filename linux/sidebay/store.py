"""模块与设置持久化。JSON 存储，对齐原版 UserDefaults 语义。"""

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class AppModule:
    module_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = ""
    custom_data: str = ""
    height_pct: float | None = None


@dataclass
class Settings:
    position: str = "left"
    width: float = 0.0
    opacity: float = 1.0
    language: str = "zh"
    launch_at_login: bool = False


class Store:
    DEFAULT_TYPES = ["CPU", "GPU", "Memory", "Disk", "Fan", "Network",
                     "Stock", "Countdown", "Stopwatch", "Screen Record"]

    def __init__(self, path: str | None = None):
        self.path = Path(path or (Path.home() / ".config" / "sidebay" / "config.json"))
        self.modules: list[AppModule] = []
        self.settings = Settings()
        self.load()

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError):
            self.modules = [AppModule(type=ty) for ty in self.DEFAULT_TYPES]
            return
        self.modules = [AppModule(**m) for m in raw.get("modules", [])]
        self.settings = Settings(**raw.get("settings", {}))
        if not self.modules:
            self.modules = [AppModule(type=ty) for ty in self.DEFAULT_TYPES]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "modules": [asdict(m) for m in self.modules],
            "settings": asdict(self.settings),
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    def add(self, type_: str, custom_data: str = "") -> AppModule:
        module = AppModule(type=type_, custom_data=custom_data)
        self.modules.append(module)
        self.save()
        return module

    def remove(self, module_id: str) -> None:
        self.modules = [m for m in self.modules if m.module_id != module_id]
        self.save()

    def move(self, from_index: int, to_index: int) -> None:
        if not 0 <= from_index < len(self.modules):
            return
        module = self.modules.pop(from_index)
        self.modules.insert(max(0, min(to_index, len(self.modules))), module)
        self.save()

    def set_custom_data(self, module_id: str, data: str) -> None:
        for m in self.modules:
            if m.module_id == module_id:
                m.custom_data = data
                self.save()
                return

    def set_height_pct(self, module_id: str, pct: float | None) -> None:
        for m in self.modules:
            if m.module_id == module_id:
                m.height_pct = pct if pct and pct > 0 else None
                self.save()
                return
