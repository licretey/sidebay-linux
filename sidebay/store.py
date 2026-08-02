"""模块与设置持久化。JSON 存储，对齐原版 UserDefaults 语义。"""

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class AppModule:
    module_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = ""
    custom_data: str = ""
    height_pct: float | None = None
    # 采集频率（秒）；None = 默认 1s
    refresh_interval: float | None = None


@dataclass
class Settings:
    position: str = "left"
    width: float = 0.0
    opacity: float = 1.0
    language: str = "zh"
    launch_at_login: bool = False
    # 手动定位：pos_x/pos_y 为 None 时维持贴边行为；设置后窗口左上角定位到该坐标
    # （GNOME Wayland 下 XWayland 窗口的 Y 由合成器管理，垂直位置固定顶部）
    pos_x: float | None = None
    pos_y: float | None = None
    # 窗口高度：None = 全屏高度；设置后窗口为指定高度（内容滚动）
    height: float | None = None
    # 样式：字号 small/medium/large；字体族空串 = 系统默认
    font_size: str = "medium"
    font_family: str = ""


# 默认配置（新装/无配置文件时的启动参数）：由用户最新历史运行参数生成
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "default-config.json"


def default_config_path() -> Path:
    """遵循 XDG_CONFIG_HOME（验收流程用临时 HOME/XDG 目录验证持久化）。"""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "sidebay" / "config.json"


class Store:
    DEFAULT_TYPES = ["CPU", "GPU", "Memory", "Disk", "Fan", "Network",
                     "Stock", "Countdown", "Stopwatch", "Screen Record"]

    def __init__(self, path: str | None = None):
        self.path = Path(path or default_config_path())
        self.modules: list[AppModule] = []
        self.settings = Settings()
        self.load()

    @staticmethod
    def _filter_fields(data: dict, cls) -> dict:
        """丢弃 dataclass 未知字段，防止旧版/新版配置漂移导致 TypeError 崩溃。"""
        known = cls.__dataclass_fields__
        return {k: v for k, v in data.items() if k in known}

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text())
            modules = [AppModule(**self._filter_fields(m, AppModule))
                       for m in raw.get("modules", [])]
            settings = Settings(**self._filter_fields(raw.get("settings", {}), Settings))
        except (OSError, json.JSONDecodeError, TypeError, AttributeError, ValueError):
            self._load_defaults()
            return
        self.modules = modules
        self.settings = settings
        if not self.modules:
            self._load_defaults()

    def _load_defaults(self) -> None:
        """无配置文件/损坏/空列表时：优先 default-config.json（随包默认参数），
        文件缺失回退内置 DEFAULT_TYPES。"""
        try:
            raw = json.loads(DEFAULT_CONFIG_PATH.read_text())
            modules = [AppModule(**self._filter_fields(m, AppModule))
                       for m in raw.get("modules", [])]
            if modules:
                self.modules = modules
                self.settings = Settings(**self._filter_fields(raw.get("settings", {}), Settings))
                return
        except (OSError, json.JSONDecodeError, TypeError, AttributeError, ValueError):
            pass
        self.modules = [AppModule(type=ty) for ty in self.DEFAULT_TYPES]
        self.settings = Settings()

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

    def set_refresh_interval(self, module_id: str, interval: float | None) -> None:
        for m in self.modules:
            if m.module_id == module_id:
                m.refresh_interval = interval if interval and interval > 0 else None
                self.save()
                return
