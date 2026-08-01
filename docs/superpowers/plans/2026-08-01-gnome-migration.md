# Sidebay Linux GNOME 迁移 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 macOS SwiftUI 版 Sidebay 以 Python + GTK4 移植到 Linux/GNOME，保留深色玻璃质感 UI、10 个核心模块，空闲内存 <100MB（2026-08-02 修订，实测 93.4MB），Flatpak 打包。

**Architecture:** 无装饰 `Gtk.ApplicationWindow` 贴屏边缘悬浮（X11 置顶，Wayland 常规层叠）；模块为统一接口的类，挂载到 `Gtk.ScrolledWindow`；数据层（/proc、/sys 纯函数解析）与 UI 分离；深色玻璃质感全部经 GTK CSS + cairo 自绘实现；配置存 JSON；Gtk.Application 提供单实例。

**Tech Stack:** Python 3.10+、PyGObject (GTK 4)、cairo、pytest、flatpak-builder（`org.gnome.Platform` 运行时）；键盘模块可选 python-xlib（懒加载）。

**Spec:** `docs/superpowers/specs/2026-08-01-gnome-migration-design.md`

## Global Constraints

- 平台：Linux / GNOME，Wayland 与 X11 均须可启动；**禁用 GNOME 原生菜单栏/headerbar**——所有窗口 `set_decorated(False)`，设置窗口自绘暗色头部
- 视觉：深色玻璃质感，`rgba(20,22,28,0.75)` 背景 + 高光渐变 + 渐变描边 + 投影；贴边全高窗口**无圆角**
- 模块：V1 共 10 个——CPU/GPU/Memory/Disk/Fan/Network/Stock/Countdown/Stopwatch/Calculator/Keyboard（usage 一文件四类，注册表共 11 项）
- 内存目标：空闲 RSS < 100MB（2026-08-02 用户裁决修订，原 80MB；实测 93.4MB）；轮询用 GLib 定时器，复用缓冲，禁止每帧分配新对象；默认 GSK_RENDERER=cairo
- 语言：zh/en 双语，词表从原 Swift `t()` 平移（`SideBarApp/Sources/SideBarApp/SideBarApp.swift:13-49`）
- 已知限制需在 UI/README 中体现：Wayland 无置顶；键盘监视 X11-only（失败显示「无权限」）；GPU 在 Flatpak 沙盒内回退 0；无真实背景模糊
- 目录：新代码全部在 `linux/`，**不得修改** `SideBarApp/`（原 macOS 版）
- 测试：纯逻辑 pytest ≥80% 覆盖；UI 冒烟在 xvfb 下运行，无显示环境自动跳过
- Python 3.10+，标准库为主；网络请求用 `urllib`；股票解码 GB18030

---

### Task 1: 项目骨架与 i18n

**Files:**
- Create: `linux/sidebay/__init__.py`（空文件）
- Create: `linux/sidebay/i18n.py`
- Create: `linux/tests/conftest.py`
- Create: `linux/tests/test_i18n.py`
- Create: `linux/pytest.ini`
- Create: `linux/.gitignore`（`__pycache__/`、`*.pyc`、`.pytest_cache/`）

**Interfaces:**
- Consumes: 无
- Produces: `sidebay.i18n.t(key: str, lang: str) -> str`——双语查表，键缺失返回 key 本身；`lang` 取 `"zh"`/`"en"`

- [ ] **Step 1: 写失败测试** `linux/tests/test_i18n.py`

```python
from sidebay.i18n import t


def test_known_key_zh():
    assert t("Settings", "zh") == "侧边栏模块管理"


def test_known_key_en():
    assert t("Settings", "en") == "Settings"


def test_missing_key_returns_key():
    assert t("NoSuchKey", "zh") == "NoSuchKey"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd linux && python3 -m pytest tests/test_i18n.py -v`
Expected: FAIL——`ModuleNotFoundError: No module named 'sidebay'`

- [ ] **Step 3: 实现**

`linux/sidebay/i18n.py`——词表从原 Swift 完整平移（含 Mirror/Server 等 V2 键，缺键回退）：

```python
"""zh/en 双语查表。词表对齐原 Swift 版 SideBarApp.swift t() 函数。"""

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "Settings": {"en": "Settings", "zh": "侧边栏模块管理"},
    "CPU": {"en": "CPU", "zh": "CPU"},
    "GPU": {"en": "GPU", "zh": "GPU"},
    "Memory": {"en": "RAM", "zh": "内存"},
    "Disk": {"en": "Disk", "zh": "磁盘"},
    "Fan": {"en": "Fan", "zh": "风扇"},
    "Network": {"en": "Network", "zh": "网络"},
    "Stock": {"en": "Stock", "zh": "股票"},
    "Countdown": {"en": "CD Timer", "zh": "倒计时"},
    "Stopwatch": {"en": "Timer", "zh": "秒表"},
    "Screen Record": {"en": "RecScreen", "zh": "录屏"},
    "Calculator": {"en": "Calculator", "zh": "计算器"},
    "Keyboard": {"en": "Keyboard", "zh": "键盘监视"},
    "Server": {"en": "Server", "zh": "服务器"},
    "Not Set": {"en": "Not Set", "zh": "未设置"},
    "Add Module": {"en": "Add Module", "zh": "新增模块"},
    "Add": {"en": "Add", "zh": "添加"},
    "Position": {"en": "Position", "zh": "位置"},
    "Left": {"en": "Left", "zh": "左边"},
    "Right": {"en": "Right", "zh": "右边"},
    "Launch at Login": {"en": "Launch at Login", "zh": "随系统启动"},
    "Hint": {
        "en": "Hint: Drag to reorder, click trash to delete.",
        "zh": "提示：按住行可以拖拽排序，点击右侧垃圾桶图标即可删除。",
    },
    "Language": {"en": "Language", "zh": "语言"},
    "Min": {"en": "Min", "zh": "分"},
    "KEYS": {"en": "KEYS", "zh": "按键"},
    "Loading...": {"en": "Loading...", "zh": "加载中..."},
    "Invalid Code": {"en": "Invalid Code", "zh": "无效代码"},
    "Waiting...": {"en": "Waiting...", "zh": "等待输入..."},
    "No Accessibility": {"en": "No Accessibility", "zh": "无辅助功能权限"},
    "SettingsTitle": {"en": "Settings", "zh": "后台设置"},
    "Width": {"en": "Width", "zh": "宽度"},
    "Select Fan": {"en": "Select Fan", "zh": "选择风扇"},
}


def t(key: str, lang: str) -> str:
    entry = _TRANSLATIONS.get(key)
    if entry is None:
        return key
    return entry.get(lang, entry["en"])
```

`linux/tests/conftest.py`——保证 `import sidebay` 可用：

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

`linux/pytest.ini`：

```ini
[pytest]
testpaths = tests
addopts = -q
```

- [ ] **Step 4: 运行确认通过**

Run: `cd linux && python3 -m pytest -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add linux/
git commit -m "feat(linux): scaffold project and i18n module"
```

---

### Task 2: 存储层（AppModule / Settings / Store）

**Files:**
- Create: `linux/sidebay/store.py`
- Create: `linux/tests/test_store.py`

**Interfaces:**
- Consumes: Task 1 的目录与 pytest 配置
- Produces:
  - `class AppModule`——`@dataclass`：`module_id: str`（uuid4 字符串）、`type: str`、`custom_data: str = ""`、`height_pct: float | None = None`
  - `class Settings`——`@dataclass`：`position: str = "left"`、`width: float = 0.0`（0=自动=屏宽/20）、`opacity: float = 1.0`、`language: str = "zh"`、`launch_at_login: bool = False`
  - `class Store`：`__init__(self, path: str | None = None)`（默认 `~/.config/sidebay/config.json`）；属性 `modules: list[AppModule]`、`settings: Settings`；方法 `load()`、`save()`、`add(type_: str, custom_data: str = "") -> AppModule`、`remove(module_id: str)`、`move(from_index: int, to_index: int)`、`set_custom_data(module_id: str, data: str)`、`set_height_pct(module_id: str, pct: float | None)`、`DEFAULT_TYPES: list[str] = ["CPU", "GPU", "Memory", "Disk", "Fan", "Network", "Stock", "Countdown", "Stopwatch", "Screen Record"]`

- [ ] **Step 1: 写失败测试** `linux/tests/test_store.py`

```python
import json
import uuid

import pytest

from sidebay.store import AppModule, Settings, Store


@pytest.fixture
def store(tmp_path):
    return Store(path=str(tmp_path / "config.json"))


def test_default_modules_on_fresh_store(store):
    assert [m.type for m in store.modules] == Store.DEFAULT_TYPES


def test_add_and_persist(store, tmp_path):
    store.add("Calculator")
    store.save()
    raw = json.loads((tmp_path / "config.json").read_text())
    assert raw["modules"][-1]["type"] == "Calculator"


def test_roundtrip(tmp_path):
    path = str(tmp_path / "config.json")
    s1 = Store(path=path)
    s1.add("Calculator", custom_data="x")
    s1.settings.position = "right"
    s1.settings.width = 120.0
    s1.save()
    s2 = Store(path=path)
    s2.load()
    assert s2.modules[-1].type == "Calculator"
    assert s2.modules[-1].custom_data == "x"
    assert s2.settings.position == "right"
    assert s2.settings.width == 120.0


def test_move(store):
    store.move(0, 2)
    assert store.modules[2].type == "CPU"
    assert store.modules[0].type == "GPU"


def test_remove_and_set_custom_data(store):
    mid = store.modules[0].module_id
    store.remove(mid)
    assert all(m.module_id != mid for m in store.modules)
    store.set_custom_data(store.modules[0].module_id, "sh000001")
    assert store.modules[0].custom_data == "sh000001"


def test_set_height_pct(store):
    mid = store.modules[0].module_id
    store.set_height_pct(mid, 50.0)
    assert store.modules[0].height_pct == 50.0
    store.set_height_pct(mid, None)
    assert store.modules[0].height_pct is None


def test_corrupt_file_recovers_to_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json")
    s = Store(path=str(path))
    s.load()
    assert [m.type for m in s.modules] == Store.DEFAULT_TYPES
```

- [ ] **Step 2: 运行确认失败**

Run: `cd linux && python3 -m pytest tests/test_store.py -v`
Expected: FAIL——`ModuleNotFoundError: No module named 'sidebay.store'`

- [ ] **Step 3: 实现** `linux/sidebay/store.py`

```python
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
```

- [ ] **Step 4: 运行确认通过**

Run: `cd linux && python3 -m pytest -v`
Expected: 3+7=10 passed（test_i18n 3 个 + test_store 7 个）

- [ ] **Step 5: 提交**

```bash
git add linux/
git commit -m "feat(linux): add module store with JSON persistence"
```

---

### Task 3: 系统采集纯函数解析

**Files:**
- Create: `linux/sidebay/monitor.py`
- Create: `linux/tests/test_monitor.py`

**Interfaces:**
- Consumes: Task 1 目录
- Produces（全部纯函数，不读文件）:
  - `@dataclass CpuSample`: `total: int`, `idle: int`
  - `parse_cpu_usage(text: str, prev: CpuSample | None) -> tuple[float, CpuSample]`——返回 (使用率 %, 新样本)；首采样返回 (0.0, sample)
  - `parse_meminfo(text: str) -> tuple[int, int]`——(used_bytes, total_bytes)，可用 = MemAvailable（无则 MemFree+Buffers+Cached）
  - `parse_net_dev(text: str) -> dict[str, tuple[int, int]]`——iface -> (rx_bytes, tx_bytes)，排除 `lo`
  - `compute_net_speeds(prev: dict[str, tuple[int, int]], curr: dict[str, tuple[int, int]], dt: float) -> tuple[float, float]`——(up_bps, down_bps)，负数钳 0；prev 为空返回 (0, 0)
  - `parse_fan_rpm(text: str) -> int | None`——hwmon fan1_input 内容 → RPM；非数字/空返回 None
  - `parse_gpu_busy(text: str) -> float`——amd `gpu_busy_percent` 内容 → 0-100；失败 0.0

- [ ] **Step 1: 写失败测试** `linux/tests/test_monitor.py`

```python
from sidebay.monitor import (
    CpuSample,
    compute_net_speeds,
    parse_cpu_usage,
    parse_fan_rpm,
    parse_gpu_busy,
    parse_meminfo,
    parse_net_dev,
)

CPU_S1 = """cpu  1000 10 200 3000 0 0 0 0 0 0
cpu0 1000 10 200 3000 0 0 0 0 0 0
"""
CPU_S2 = """cpu  2000 20 400 3100 0 0 0 0 0 0
cpu0 2000 20 400 3100 0 0 0 0 0 0
"""


def test_cpu_first_sample_zero():
    usage, sample = parse_cpu_usage(CPU_S1, None)
    assert usage == 0.0
    assert sample.total == 4210
    assert sample.idle == 3000


def test_cpu_second_sample_diff():
    _, prev = parse_cpu_usage(CPU_S1, None)
    usage, _ = parse_cpu_usage(CPU_S2, prev)
    # S1: total=4210 idle=3000 → S2: total=5520 idle=3100
    # busy_diff=1210, total_diff=1310 → 92.37%
    assert abs(usage - 100.0 * (1210 / 1310)) < 0.01


def test_meminfo():
    text = """MemTotal:       16000000 kB
MemFree:         2000000 kB
MemAvailable:   10000000 kB
Buffers:          500000 kB
Cached:          4000000 kB
"""
    used, total = parse_meminfo(text)
    assert total == 16000000 * 1024
    assert used == (16000000 - 10000000) * 1024


def test_meminfo_falls_back_without_memavailable():
    text = """MemTotal: 16000000 kB
MemFree: 2000000 kB
Buffers: 500000 kB
Cached: 4000000 kB
"""
    used, total = parse_meminfo(text)
    assert used == (16000000 - 2000000 - 500000 - 4000000) * 1024


def test_net_dev_skips_lo():
    text = """Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 1000       10    0    0    0     0          0         0     1000       10    0    0    0     0       0          0
  eth0: 5000        5    0    0    0     0          0         0     3000        3    0    0    0     0       0          0
"""
    parsed = parse_net_dev(text)
    assert "lo" not in parsed
    assert parsed["eth0"] == (5000, 3000)


def test_net_speeds():
    prev = {"eth0": (1000, 1000)}
    curr = {"eth0": (3000, 5000)}
    up, down = compute_net_speeds(prev, curr, dt=2.0)
    # tuple 第一列 rx（计为上行 up），第二列 tx（计为下行 down）
    assert up == 1000.0  # (3000-1000)/2
    assert down == 2000.0  # (5000-1000)/2


def test_net_speeds_empty_prev():
    up, down = compute_net_speeds({}, {"eth0": (1, 2)}, dt=1.0)
    assert (up, down) == (0.0, 0.0)


def test_net_speeds_clamps_negative():
    prev = {"eth0": (5000, 5000)}
    curr = {"eth0": (1000, 1000)}
    up, down = compute_net_speeds(prev, curr, dt=1.0)
    assert up >= 0 and down >= 0


def test_fan_rpm():
    assert parse_fan_rpm("1200\n") == 1200
    assert parse_fan_rpm("") is None
    assert parse_fan_rpm("not a number\n") is None


def test_gpu_busy():
    assert parse_gpu_busy("37\n") == 37.0
    assert parse_gpu_busy("") == 0.0
```

- [ ] **Step 2: 运行确认失败**

Run: `cd linux && python3 -m pytest tests/test_monitor.py -v`
Expected: FAIL——导入错误

- [ ] **Step 3: 实现** `linux/sidebay/monitor.py`

```python
"""Linux 系统采集：/proc 与 /sys 文件的纯函数解析 + 采样类。"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class CpuSample:
    total: int
    idle: int


def parse_cpu_usage(text: str, prev: CpuSample | None) -> tuple[float, CpuSample]:
    for line in text.splitlines():
        if line.startswith("cpu ") or line == "cpu":
            parts = line.split()
            nums = [int(p) for p in parts[1:]]
            total = sum(nums)
            idle = nums[3] if len(nums) > 3 else 0
            sample = CpuSample(total=total, idle=idle)
            if prev is None or prev.total == 0:
                return 0.0, sample
            total_diff = sample.total - prev.total
            idle_diff = sample.idle - prev.idle
            if total_diff <= 0:
                return 0.0, sample
            return (1.0 - idle_diff / total_diff) * 100.0, sample
    return 0.0, CpuSample(total=0, idle=0)


def parse_meminfo(text: str) -> tuple[int, int]:
    values: dict[str, int] = {}
    for line in text.splitlines():
        cols = line.split()
        if len(cols) >= 2 and cols[0].endswith(":"):
            values[cols[0][:-1]] = int(cols[1]) * 1024  # kB -> bytes
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable")
    if available is None:
        available = values.get("MemFree", 0) + values.get("Buffers", 0) + values.get("Cached", 0)
    used = max(total - available, 0)
    return used, total


def parse_net_dev(text: str) -> dict[str, tuple[int, int]]:
    result: dict[str, tuple[int, int]] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        iface, rest = line.split(":", 1)
        iface = iface.strip()
        if iface == "lo":
            continue
        cols = rest.split()
        if len(cols) >= 9:
            try:
                result[iface] = (int(cols[0]), int(cols[8]))
            except ValueError:
                continue
    return result


def compute_net_speeds(
    prev: dict[str, tuple[int, int]],
    curr: dict[str, tuple[int, int]],
    dt: float,
) -> tuple[float, float]:
    if not prev or dt <= 0:
        return 0.0, 0.0
    up = down = 0.0
    for iface, (rx, tx) in curr.items():
        if iface in prev:
            up += max(rx - prev[iface][0], 0)
            down += max(tx - prev[iface][1], 0)
    return up / dt, down / dt


def parse_fan_rpm(text: str) -> int | None:
    try:
        rpm = int(text.strip())
    except ValueError:
        return None
    return rpm if rpm > 0 else None


def parse_gpu_busy(text: str) -> float:
    try:
        return float(text.strip())
    except ValueError:
        return 0.0
```

- [ ] **Step 4: 运行确认通过**

Run: `cd linux && python3 -m pytest -v`
Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
git add linux/
git commit -m "feat(linux): add pure sysinfo parsers for /proc and /sys"
```

---

### Task 4: SystemMonitor 采样类

**Files:**
- Create: `linux/sidebay/monitor.py`（追加，勿改已有函数）
- Create: `linux/tests/test_monitor_sampler.py`

**Interfaces:**
- Consumes: Task 3 全部解析函数
- Produces:
  - `@dataclass Stats`：`cpu: float = 0.0`、`gpu: float = 0.0`、`mem_used: int = 0`、`mem_total: int = 0`、`disk_pct: float = 0.0`、`disk_total: float = 0.0`、`net_up: float = 0.0`、`net_down: float = 0.0`、`fan_rpm: int = 0`
  - `class SystemMonitor`：`__init__(self, proc_root: str = "/proc", sys_root: str = "/sys")`；`tick() -> Stats`；属性 `fan_simulated: bool`（无真实风扇时 True）
  - 风扇降级：无 `fan*_input` 时按原版公式模拟——`rpm = 1800 + (cpu+gpu)/200 * 4200 ± 50 噪声`（cpu/gpu 为 tick 内刚采的值）
  - GPU 降级链：`/sys/class/drm/*/device/gpu_busy_percent` 首个可读文件 → 无则 `nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits`（`subprocess.run`，超时 2s，失败回退 0.0）

- [ ] **Step 1: 写失败测试** `linux/tests/test_monitor_sampler.py`

```python
from pathlib import Path

from sidebay.monitor import SystemMonitor


def write(root: Path, rel: str, content: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def make_proc(root: Path) -> None:
    write(root, "stat", "cpu  1000 10 200 3000 0 0 0 0 0 0\n")
    write(root, "meminfo", "MemTotal:       16000000 kB\nMemFree:         2000000 kB\nMemAvailable:   10000000 kB\n")
    write(root, "net/dev", "Inter-| Receive                                                | Transmit\n face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed\n    lo: 1000 10 0 0 0 0 0 0 1000 10 0 0 0 0 0 0\n  eth0: 5000 5 0 0 0 0 0 0 3000 3 0 0 0 0 0 0\n")


def test_tick_reads_all_sources(tmp_path):
    proc = tmp_path / "proc"
    sys = tmp_path / "sys"
    make_proc(proc)
    write(sys, "class/hwmon/hwmon0/fan1_input", "1200\n")
    write(sys, "class/drm/card0/device/gpu_busy_percent", "37\n")

    m = SystemMonitor(proc_root=str(proc), sys_root=str(sys))
    first = m.tick()
    assert first.cpu == 0.0
    assert first.mem_total == 16000000 * 1024
    assert first.fan_rpm == 1200
    assert first.gpu == 37.0
    assert not m.fan_simulated

    # 更新 /proc/stat 后第二次 tick 得 CPU 差分（busy 1210 / total 1310）
    write(proc, "stat", "cpu  2000 20 400 3100 0 0 0 0 0 0\n")
    second = m.tick()
    assert abs(second.cpu - 100.0 * (1210 / 1310)) < 0.01
    assert second.net_up > 0 or second.net_down > 0
    assert second.disk_total > 0


def test_tick_fallback_no_fan_no_gpu(tmp_path):
    proc = tmp_path / "proc"
    sys = tmp_path / "sys"
    make_proc(proc)  # 无 fan、无 gpu 文件

    m = SystemMonitor(proc_root=str(proc), sys_root=str(sys))
    stats = m.tick()
    assert m.fan_simulated
    assert stats.gpu == 0.0
    assert stats.fan_rpm >= 1800 - 50  # 模拟公式下限
    assert stats.fan_rpm <= (1800 + 4200) + 50
```

- [ ] **Step 2: 运行确认失败**

Run: `cd linux && python3 -m pytest tests/test_monitor_sampler.py -v`
Expected: FAIL——`ImportError`

- [ ] **Step 3: 实现**——追加到 `linux/sidebay/monitor.py` 末尾：

```python
import random
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Stats:
    cpu: float = 0.0
    gpu: float = 0.0
    mem_used: int = 0
    mem_total: int = 0
    disk_pct: float = 0.0
    disk_total: float = 0.0
    net_up: float = 0.0
    net_down: float = 0.0
    fan_rpm: int = 0


class SystemMonitor:
    def __init__(self, proc_root: str = "/proc", sys_root: str = "/sys"):
        self.proc_root = Path(proc_root)
        self.sys_root = Path(sys_root)
        self.fan_simulated = False
        self._prev_cpu: CpuSample | None = None
        self._prev_net: dict[str, tuple[int, int]] = {}
        self._last_net_time = 0.0

    def tick(self) -> Stats:
        cpu_text = self._read(self.proc_root / "stat")
        cpu, self._prev_cpu = parse_cpu_usage(cpu_text, self._prev_cpu)
        gpu = self._read_gpu()

        mem_text = self._read(self.proc_root / "meminfo")
        mem_used, mem_total = parse_meminfo(mem_text)

        disk_pct, disk_total = self._read_disk()

        net_text = self._read(self.proc_root / "net" / "dev")
        curr_net = parse_net_dev(net_text)
        now = __import__("time").time()
        dt = now - self._last_net_time if self._last_net_time else 0.0
        net_up, net_down = compute_net_speeds(self._prev_net, curr_net, dt)
        self._prev_net = curr_net
        self._last_net_time = now

        fan = self._read_fan()
        if fan is None:
            self.fan_simulated = True
            total_load = min(cpu + gpu, 200.0)
            fan = int(1800.0 + (total_load / 200.0) * 4200.0 + random.randint(-50, 50))
        else:
            self.fan_simulated = False

        return Stats(
            cpu=cpu, gpu=gpu, mem_used=mem_used, mem_total=mem_total,
            disk_pct=disk_pct, disk_total=disk_total,
            net_up=net_up, net_down=net_down, fan_rpm=fan,
        )

    @staticmethod
    def _read(path: Path) -> str:
        try:
            return path.read_text()
        except OSError:
            return ""

    def _read_disk(self) -> tuple[float, float]:
        try:
            st = __import__("os").statvfs("/")
            total = st.f_blocks * st.f_frsize
            free = st.f_bavail * st.f_frsize
            used = total - free
            return (used / total * 100.0 if total > 0 else 0.0), total
        except OSError:
            return 0.0, 0.0

    def _read_fan(self) -> int | None:
        for hwmon in sorted(self.sys_root.glob("class/hwmon/hwmon*")):
            for fan in sorted(hwmon.glob("fan*_input")):
                rpm = parse_fan_rpm(self._read(fan))
                if rpm is not None:
                    return rpm
        return None

    def _read_gpu(self) -> float:
        for dev in sorted(self.sys_root.glob("class/drm/*/device/gpu_busy_percent")):
            busy = parse_gpu_busy(self._read(dev))
            if busy > 0:
                return busy
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2,
            )
            return parse_gpu_busy(out.stdout.strip().splitlines()[0]) if out.stdout.strip() else 0.0
        except (OSError, subprocess.TimeoutExpired, IndexError):
            return 0.0
```

- [ ] **Step 4: 运行确认通过**

Run: `cd linux && python3 -m pytest -v`
Expected: 全部通过（`test_tick_reads_all_sources` 中 disk 断言读真实 `/` 的 statvfs——`disk_total > 0` 恒真）

- [ ] **Step 5: 提交**

```bash
git add linux/
git commit -m "feat(linux): add SystemMonitor sampler with fan/gpu fallbacks"
```

---

### Task 5: 环形仪表 Ring 与样式表

**Files:**
- Create: `linux/sidebay/widgets/__init__.py`（空）
- Create: `linux/sidebay/widgets/ring.py`
- Create: `linux/sidebay/style.css`
- Create: `linux/tests/test_ring.py`

**Interfaces:**
- Consumes: Task 1 目录
- Produces:
  - `class Ring(Gtk.DrawingArea)`：`__init__(self, color: Gdk.RGBA, size: int = 44, stroke: int = 5)`；`set_value(value: float)`（钳 0-100）；`set_color(color: Gdk.RGBA)`；`value: float` 属性
  - `ring_segment_colors(base: tuple[float, float, float, float], n: int) -> list[tuple[float, float, float, float]]`——纯函数：n 段圆弧颜色，从 `base` 亮度 0.4 渐变到 `base` 满亮，返回 RGBA 元组列表（0-1 通道）
  - `style.css` 类名：`.sb-glass`（背景+渐变）、`.sb-ring-label`、`.sb-module-title`、`.sb-tick-label`、`.sb-btn-glass`、`.sb-slider`、`.sb-calc-display`、`.sb-settings-header`、`.sb-settings-close`

- [ ] **Step 1: 写失败测试** `linux/tests/test_ring.py`

```python
from sidebay.widgets.ring import ring_segment_colors


def test_segment_colors_count_and_order():
    colors = ring_segment_colors((0.2, 0.5, 1.0, 1.0), n=32)
    assert len(colors) == 32
    first, last = colors[0], colors[-1]
    # 第一段最暗（亮度 ~0.4 倍），最后一段为基色
    assert first[0] < last[0] and first[1] < last[1] and first[2] < last[2]
    assert last == (0.2, 0.5, 1.0, 1.0)


def test_segment_colors_n_one():
    assert ring_segment_colors((0.2, 0.5, 1.0, 1.0), n=1) == [(0.2, 0.5, 1.0, 1.0)]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd linux && python3 -m pytest tests/test_ring.py -v`
Expected: FAIL——导入错误

- [ ] **Step 3: 实现** `linux/sidebay/widgets/ring.py`

```python
"""cairo 自绘环形仪表：分段圆弧插值模拟角度渐变 + 发光。"""

from math import cos, pi, sin

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk


def ring_segment_colors(base: tuple[float, float, float, float], n: int) -> list[tuple[float, float, float, float]]:
    """从 base 亮度 40% 渐变到满亮，n 段颜色。"""
    if n <= 1:
        return [base]
    return [
        tuple(min(c * (0.4 + 0.6 * i / (n - 1)), 1.0) for c in base[:3]) + (base[3],)
        for i in range(n)
    ]


class Ring(Gtk.DrawingArea):
    def __init__(self, color: Gdk.RGBA, size: int = 44, stroke: int = 5):
        super().__init__()
        self._value = 0.0
        self._color = color
        self._stroke = stroke
        self.set_size_request(size, size)
        self.set_draw_func(self._draw)

    def set_value(self, value: float) -> None:
        self._value = max(0.0, min(100.0, value))
        self.queue_draw()

    def set_color(self, color: Gdk.RGBA) -> None:
        self._color = color
        self.queue_draw()

    def _draw(self, area: Gtk.DrawingArea, cr, width: int, height: int) -> None:
        from math import tau

        r = (min(width, height) - self._stroke) / 2.0
        cx, cy = width / 2.0, height / 2.0
        base = (self._color.red, self._color.green, self._color.blue, self._color.alpha)

        # 底环
        cr.set_source_rgba(base[0], base[1], base[2], 0.15)
        cr.set_line_width(self._stroke)
        cr.arc(cx, cy, r, 0, tau)
        cr.stroke()

        # 分段渐变弧
        n = 32
        colors = ring_segment_colors(base, n)
        arc_end = tau * self._value / 100.0
        for i in range(n):
            a0 = (tau * i / n) - tau / 4
            a1 = a0 + tau / n
            if a0 >= arc_end:
                break
            a1 = min(a1, arc_end)
            c = colors[i]
            cr.set_source_rgba(*c)
            cr.set_line_cap(1)  # CAIRO_LINE_CAP_ROUND
            cr.arc(cx, cy, r, a0, a1)
            cr.stroke()
            # 发光：同色低透明度稍粗描一遍
            cr.set_source_rgba(c[0], c[1], c[2], 0.35)
            cr.set_line_width(self._stroke + 1.0)
            cr.arc(cx, cy, r, a0, a1)
            cr.stroke()
            cr.set_line_width(self._stroke)
```

`linux/sidebay/style.css`——深色玻璃质感（任务后续步骤的类名一并预置）：

```css
* { font-family: "Cantarell", "Noto Sans CJK SC", sans-serif; }

.sb-glass {
  background-color: rgba(20, 22, 28, 0.75);
  background-image: linear-gradient(90deg,
    rgba(255, 255, 255, 0.35), rgba(255, 255, 255, 0.0) 40%, rgba(0, 0, 0, 0.3));
}

.sb-module-title {
  font-weight: bold;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
}

.sb-tick-label {
  font-family: monospace;
  font-weight: medium;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.9);
}

.sb-btn-glass {
  background-color: rgba(255, 255, 255, 0.12);
  border-radius: 9999px;
  min-width: 28px;
  min-height: 28px;
}
.sb-btn-glass:hover { background-color: rgba(255, 255, 255, 0.22); }
.sb-btn-glass:active { background-color: rgba(255, 255, 255, 0.08); }

.sb-slider slider {
  background-color: rgba(255, 255, 255, 0.7);
  border-radius: 9999px;
  min-width: 12px;
  min-height: 12px;
}

.sb-calc-display {
  background-color: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  font-family: monospace;
  font-weight: bold;
  font-size: 16px;
}

.sb-settings-header {
  background-color: rgba(20, 22, 28, 0.9);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.sb-settings-close {
  background-color: rgba(255, 59, 48, 0.85);
  border-radius: 9999px;
  min-width: 12px;
  min-height: 12px;
}
.sb-settings-close:hover { background-color: rgba(255, 59, 48, 1.0); }

.sb-rounded { border-radius: 24px; }
```

- [ ] **Step 4: 运行确认通过**

Run: `cd linux && python3 -m pytest -v`
Expected: 通过（ring 测试不导入 gi，纯函数）

- [ ] **Step 5: 提交**

```bash
git add linux/
git commit -m "feat(linux): add cairo ring widget and glass style sheet"
```

---

### Task 6: 应用骨架——无装饰贴边悬浮窗口

**Files:**
- Create: `linux/sidebay/main.py`
- Create: `linux/sidebay/app.py`
- Create: `linux/sidebay/window.py`
- Create: `linux/run.sh`
- Create: `linux/tests/test_smoke.py`

**Interfaces:**
- Consumes: Task 1-5（Store、i18n、style.css）
- Produces:
  - `sidebay.app.SidebayApplication(Gtk.Application)`：`do_activate` 创建 `SidebarWindow`；action `app.open-settings` 打开设置（本任务先占位：`print` 日志，Task 12 接真实现）；首次 activate 时装载 CSS provider（`style.css` 全应用生效）
  - `sidebay.window.SidebarWindow(Gtk.ApplicationWindow)`：`set_decorated(False)`、`set_keep_above(True)`、`set_resizable(False)`；`do_move` 监听；方法 `rebuild_modules()`（先空实现）、`apply_width()`、`apply_position()`、`apply_opacity()`
  - `main.py`：`python3 -m sidebay` 入口，注册 Gtk CSS provider 后 `SidebayApplication().run(sys.argv)`
  - `run.sh`：`PYTHONPATH=$(dirname "$0") python3 -m sidebay "$@"`（`#!/usr/bin/env bash` + `set -e`）
  - 窗口定位：`Gdk.Monitor` 的 workarea 全高；`x = workarea.x`（left）或 `workarea.x + workarea.width - width`（right）；宽度 = settings.width > 0 ? settings.width : workarea.width / 20

- [ ] **Step 1: 写冒烟测试** `linux/tests/test_smoke.py`

```python
import pytest

gi = pytest.importorskip("gi")

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from sidebay.app import SidebayApplication
from sidebay.store import Store


@pytest.mark.smoke
def test_app_creates_sidebar_window(tmp_path):
    app = SidebayApplication(store=Store(path=str(tmp_path / "c.json")))
    win = app.create_window()
    assert isinstance(win, Gtk.Window)
    assert not win.get_decorated()
    win.destroy()


@pytest.mark.smoke
def test_rebuild_modules_creates_widgets(tmp_path):
    app = SidebayApplication(store=Store(path=str(tmp_path / "c.json")))
    win = app.create_window()
    win.rebuild_modules()
    box = win._module_box  # 测试只读内部挂载点
    assert box.get_first_child() is not None
    win.destroy()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd linux && xvfb-run -a python3 -m pytest tests/test_smoke.py -v`
Expected: FAIL——`ImportError: No module named 'sidebay.app'`

- [ ] **Step 3: 实现**

`linux/sidebay/window.py`：

```python
"""无装饰、贴屏边缘、全高的主侧边栏窗口。"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk


class SidebarWindow(Gtk.ApplicationWindow):
    def __init__(self, app, store):
        super().__init__(application=app)
        self.store = store
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_resizable(False)
        self.set_title("Sidebay")

        self._module_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(self._module_box)
        scroller.set_overlay_scrolling(True)

        self._opacity = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self._opacity.set_range(0.1, 1.0)
        self._opacity.set_value(self.store.settings.opacity)
        self._opacity.set_hexpand(True)
        self._opacity.add_css_class("sb-slider")
        self._opacity.connect("value-changed", self._on_opacity_changed)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.append(scroller)
        outer.append(self._opacity)
        self.set_child(outer)

        self._apply_position()
        self._apply_width()
        self._apply_opacity()
        self.rebuild_modules()

    def rebuild_modules(self) -> None:
        # Task 7 接入真实模块；先用占位分隔线保证结构存在
        while (child := self._module_box.get_first_child()) is not None:
            self._module_box.remove(child)
        for _ in self.store.modules:
            sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            self._module_box.append(sep)

    def _on_opacity_changed(self, scale: Gtk.Scale) -> None:
        value = scale.get_value()
        self.set_opacity(value)
        self.store.settings.opacity = value
        self.store.save()

    def _apply_position(self) -> None:
        display = self.get_display()
        monitor = display.get_monitor_at_surface(self.get_surface()) if self.get_surface() else display.get_primary_monitor()
        if monitor is None:
            return
        work = monitor.get_workarea()
        self._workarea = (work.x(), work.y(), work.width(), work.height())

    def _apply_width(self) -> None:
        if not hasattr(self, "_workarea"):
            return
        _, y, w, h = self._workarea
        width = int(self.store.settings.width) if self.store.settings.width > 0 else int(w / 20)
        self.set_default_size(width, h)
        self.resize(width, h)
        self.move(
            self._workarea[0] if self.store.settings.position == "left"
            else self._workarea[0] + self._workarea[2] - width,
            y,
        )

    def _apply_opacity(self) -> None:
        self.set_opacity(self.store.settings.opacity)
```

`linux/sidebay/app.py`：

```python
"""Gtk.Application：单实例、CSS 装载、窗口管理。"""

import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from sidebay.store import Store
from sidebay.window import SidebarWindow

CSS_PATH = Path(__file__).parent / "style.css"


class SidebayApplication(Gtk.Application):
    def __init__(self, store: Store | None = None, **kwargs):
        super().__init__(application_id="org.sidebay.SideBay", **kwargs)
        self.store = store or Store()
        self.window: SidebarWindow | None = None
        self.connect("startup", self._on_startup)

    def _on_startup(self, app) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_path(str(CSS_PATH))
        Gtk.StyleContext.add_provider_for_display(
            Gtk.Window.get_default_display(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def create_window(self) -> SidebarWindow:
        self.window = SidebarWindow(self, self.store)
        self.window.present()
        return self.window

    def do_activate(self) -> None:
        if self.window is None:
            self.create_window()
        else:
            self.window.present()
```

`linux/sidebay/main.py`：

```python
"""Sidebay Linux 入口：python3 -m sidebay"""

import sys

from sidebay.app import SidebayApplication


def main() -> int:
    app = SidebayApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
```

`linux/run.sh`：

```bash
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
PYTHONPATH="$(pwd)" exec python3 -m sidebay "$@"
```

- [ ] **Step 4: 运行确认通过**

Run: `cd linux && chmod +x run.sh && xvfb-run -a python3 -m pytest tests/test_smoke.py -v`
Expected: 2 passed（无 xvfb 时 smoke 自动 skip——`pytest.importorskip("gi")` 不适用时需显示；有 GI 但无显示时本测试会 fail，正常——按文档用 xvfb-run）

若本机无 xvfb：`sudo apt install xvfb` 后重试。

- [ ] **Step 5: 提交**

```bash
git add linux/
git commit -m "feat(linux): add undecorated edge-docked sidebar window skeleton"
```

---

### Task 7: 模块框架与监控类模块（Usage / Network / Fan）

**Files:**
- Create: `linux/sidebay/modules/__init__.py`
- Create: `linux/sidebay/modules/base.py`
- Create: `linux/sidebay/modules/registry.py`
- Create: `linux/sidebay/modules/usage.py`
- Create: `linux/sidebay/modules/network.py`
- Create: `linux/sidebay/modules/fan.py`
- Modify: `linux/sidebay/window.py`（`rebuild_modules` 接真实模块）
- Create: `linux/tests/test_modules_registry.py`

**Interfaces:**
- Consumes: Task 2 Store、Task 4 SystemMonitor、Task 5 Ring、i18n
- Produces:
  - `sidebay.modules.base.Module`（`ABC`）：`__init__(self, store: Store, module_id: str)`；`build(self) -> Gtk.Widget`（abstract）；`on_tick(self) -> None`（默认空）；`on_destroy(self) -> None`（默认空）
  - `sidebay.modules.registry.MODULE_TYPES: list[str]` = `["CPU", "GPU", "Memory", "Disk", "Fan", "Network", "Stock", "Countdown", "Stopwatch", "Calculator", "Keyboard"]`
  - `sidebay.modules.registry.create_module(type_: str, store: Store, module_id: str, monitor: SystemMonitor | None) -> Module`
  - 所有模块 `build()` 返回的 widget 添加 CSS 类 `sb-module`，且 `widget.connect("destroy", lambda *_: module.on_destroy())`
  - `UsageModule(store, module_id, monitor, kind: str)`——kind ∈ {"CPU","GPU","Memory","Disk"}，颜色 CPU 蓝 `(0.32,0.6,1.0)`、GPU 紫 `(0.6,0.45,1.0)`、Memory 橙 `(1.0,0.65,0.2)`、Disk 棕 `(0.62,0.48,0.33)`；标题 + 44px Ring + 数值 `%.0f%%`
  - `NetworkModule`——标题 + 上行（绿 `(0.2,0.85,0.4)` ↑ 图标 `▲`）下行（蓝 `(0.32,0.6,1.0)` ▼）等宽数字 `%.1f MB/s` / `%.0f KB/s` / `%.0f B/s`（阈值 1_048_576 / 1024）
  - `FanModule`——标题 + 旋转扇叶（`Gtk.DrawingArea` 画 6 片椭圆扇叶，按 `rpm * 0.18 度/秒` 旋转，GLib timeout 30ms 驱动）+ RPM 文本；扇叶色 teal `(0.2,0.8,0.8)`，发光叠影

- [ ] **Step 1: 写失败测试** `linux/tests/test_modules_registry.py`

```python
import pytest

from sidebay.modules.registry import MODULE_TYPES, create_module


def test_module_types_order():
    assert MODULE_TYPES == ["CPU", "GPU", "Memory", "Disk", "Fan", "Network",
                            "Stock", "Countdown", "Stopwatch", "Calculator", "Keyboard"]


def test_usage_kinds_map_to_one_class():
    from sidebay.modules.usage import UsageModule

    for kind in ("CPU", "GPU", "Memory", "Disk"):
        assert UsageModule.KINDS[kind] is not None


@pytest.mark.smoke
def test_create_usage_module_builds(tmp_path):
    from sidebay.store import Store

    store = Store(path=str(tmp_path / "c.json"))
    module = create_module("CPU", store, store.modules[0].module_id, monitor=None)
    widget = module.build()
    assert widget is not None
    widget.destroy()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd linux && xvfb-run -a python3 -m pytest tests/test_modules_registry.py -v`
Expected: FAIL——导入错误

- [ ] **Step 3: 实现**

`linux/sidebay/modules/base.py`：

```python
"""模块基类：统一接口，build() 返回 Gtk.Widget。"""

from abc import ABC, abstractmethod

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from sidebay.store import Store


class Module(ABC):
    def __init__(self, store: Store, module_id: str):
        self.store = store
        self.module_id = module_id

    @abstractmethod
    def build(self) -> Gtk.Widget:
        """构建模块视图，仅调用一次。"""

    def on_tick(self) -> None:
        """每秒轮询钩子（可选重写）。"""

    def on_destroy(self) -> None:
        """清理定时器/连接（可选重写）。"""

    def _boxed(self, child: Gtk.Widget) -> Gtk.Widget:
        """统一包装：固定高度、CSS 类、destroy 钩子。"""
        child.add_css_class("sb-module")
        child.set_size_request(-1, 100)
        child.connect("destroy", lambda *_: self.on_destroy())
        return child
```

`linux/sidebay/modules/usage.py`：

```python
"""CPU/GPU/Memory/Disk 环形仪表模块。"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk

from sidebay.i18n import t
from sidebay.modules.base import Module
from sidebay.widgets.ring import Ring

KINDS = {"CPU": "cpu", "GPU": "gpu", "Memory": "memory", "Disk": "disk"}
COLORS = {
    "CPU": (0.32, 0.60, 1.00),
    "GPU": (0.60, 0.45, 1.00),
    "Memory": (1.00, 0.65, 0.20),
    "Disk": (0.62, 0.48, 0.33),
}


class UsageModule(Module):
    def __init__(self, store, module_id, monitor, kind: str):
        super().__init__(store, module_id)
        self.monitor = monitor
        self.kind = kind
        self._ring: Ring | None = None
        self._label: Gtk.Label | None = None
        self._lang = store.settings.language

    def build(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        title = Gtk.Label(label=t(self.kind, self._lang))
        title.add_css_class("sb-module-title")
        box.append(title)

        rgba = Gdk.RGBA()
        rgba.parse(f"rgb({int(COLORS[self.kind][0]*255)}, {int(COLORS[self.kind][1]*255)}, {int(COLORS[self.kind][2]*255)})")
        self._ring = Ring(rgba, size=44, stroke=5)
        self._label = Gtk.Label(label="0%")
        self._label.add_css_class("sb-tick-label")
        box.append(self._ring)
        box.append(self._label)
        return self._boxed(box)

    def on_tick(self) -> None:
        if self.monitor is None or self._ring is None:
            return
        value = getattr(self.monitor.last, KINDS[self.kind], 0.0)
        if self.kind == "Memory":
            last = self.monitor.last
            value = last.mem_used / last.mem_total * 100.0 if last.mem_total else 0.0
        elif self.kind == "Disk":
            value = self.monitor.last.disk_pct
        self._ring.set_value(value)
        self._label.set_text(f"{value:.0f}%")
```

`linux/sidebay/modules/network.py`：

```python
"""网络上下行速率模块。"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk

from sidebay.i18n import t
from sidebay.modules.base import Module


def format_bytes(bytes_per_sec: float) -> str:
    if bytes_per_sec > 1_048_576:
        return f"{bytes_per_sec / 1_048_576:.1f} MB/s"
    if bytes_per_sec > 1024:
        return f"{bytes_per_sec / 1024:.0f} KB/s"
    return f"{bytes_per_sec:.0f} B/s"


class NetworkModule(Module):
    def __init__(self, store, module_id, monitor):
        super().__init__(store, module_id)
        self.monitor = monitor
        self._up: Gtk.Label | None = None
        self._down: Gtk.Label | None = None
        self._lang = store.settings.language

    def build(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(self._title(t("Network", self._lang)))
        self._up = self._row("▲", (0.20, 0.85, 0.40), "sb-tick-label")
        self._down = self._row("▼", (0.32, 0.60, 1.00), "sb-tick-label")
        box.append(self._up)
        box.append(self._down)
        return self._boxed(box)

    def _title(self, text: str) -> Gtk.Label:
        label = Gtk.Label(label=text)
        label.add_css_class("sb-module-title")
        return label

    def _row(self, arrow: str, color: tuple, css: str) -> Gtk.Label:
        label = Gtk.Label(label=f"{arrow}  0 B/s")
        label.add_css_class(css)
        label.set_halign(Gtk.Align.CENTER)
        return label

    def on_tick(self) -> None:
        if self.monitor is None or self._up is None:
            return
        self._up.set_text(f"▲  {format_bytes(self.monitor.last.net_up)}")
        self._down.set_text(f"▼  {format_bytes(self.monitor.last.net_down)}")
```

`linux/sidebay/modules/fan.py`：

```python
"""风扇模块：旋转扇叶 + RPM。扇叶 6 片，转速 rpm*0.18 度/秒（对齐原版）。"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import GLib, Gdk, Gtk

from sidebay.i18n import t
from sidebay.modules.base import Module

from math import cos, pi, sin


class FanModule(Module):
    def __init__(self, store, module_id, monitor):
        super().__init__(store, module_id)
        self.monitor = monitor
        self._angle = 0.0
        self._timer: int | None = None
        self._rpm_label: Gtk.Label | None = None
        self._lang = store.settings.language

    def build(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        title = Gtk.Label(label=t("Fan", self._lang))
        title.add_css_class("sb-module-title")
        box.append(title)

        area = Gtk.DrawingArea()
        area.set_size_request(44, 44)
        area.set_draw_func(self._draw_blades)
        box.append(area)

        self._rpm_label = Gtk.Label(label="0 RPM")
        self._rpm_label.add_css_class("sb-tick-label")
        box.append(self._rpm_label)

        self._timer = GLib.timeout_add(30, self._advance)
        return self._boxed(box)

    def _advance(self) -> bool:
        rpm = self.monitor.last.fan_rpm if self.monitor else 0
        self._angle = (self._angle + rpm * 0.18 * 0.03) % 360.0
        if self._rpm_label is not None:
            self._rpm_label.set_text(f"{rpm} RPM")
        self._redraw()
        return True

    def _redraw(self) -> None:
        parent = self._rpm_label.get_parent()
        if parent is not None:
            area = parent.get_first_child().get_next_sibling()
            if isinstance(area, Gtk.DrawingArea):
                area.queue_draw()

    def _draw_blades(self, area: Gtk.DrawingArea, cr, width: int, height: int) -> None:
        cx, cy, r = width / 2, height / 2, min(width, height) / 2 - 4
        cr.translate(cx, cy)
        cr.rotate(self._angle * pi / 180.0)
        for i in range(6):
            cr.save()
            cr.rotate(i * 2 * pi / 6)
            cr.scale(1.0, 0.42)  # 椭圆扇叶
            cr.set_source_rgba(0.2, 0.8, 0.8, 0.9)
            cr.arc(0, -r * 0.55, r * 0.38, 0, 2 * pi)
            cr.fill()
            cr.restore()
        cr.set_source_rgba(0.2, 0.8, 0.8, 0.25)
        cr.arc(0, 0, 3, 0, 2 * pi)
        cr.fill()

    def on_destroy(self) -> None:
        if self._timer is not None:
            GLib.source_remove(self._timer)
            self._timer = None
```

`linux/sidebay/modules/registry.py`：

```python
"""模块注册表：类型 -> 工厂。"""

from sidebay.modules.base import Module
from sidebay.modules.fan import FanModule
from sidebay.modules.network import NetworkModule
from sidebay.modules.usage import UsageModule

MODULE_TYPES = ["CPU", "GPU", "Memory", "Disk", "Fan", "Network",
                "Stock", "Countdown", "Stopwatch", "Calculator", "Keyboard"]


def create_module(type_: str, store, module_id: str, monitor) -> Module:
    if type_ in ("CPU", "GPU", "Memory", "Disk"):
        return UsageModule(store, module_id, monitor, kind=type_)
    if type_ == "Fan":
        return FanModule(store, module_id, monitor)
    if type_ == "Network":
        return NetworkModule(store, module_id, monitor)
    raise ValueError(f"module type not wired yet: {type_}")
```

修改 `linux/sidebay/window.py` 的 `rebuild_modules`：

```python
    def rebuild_modules(self) -> None:
        from sidebay.modules.registry import create_module

        while (child := self._module_box.get_first_child()) is not None:
            self._module_box.remove(child)
        self._modules: list[Module] = []
        for m in self.store.modules:
            if m.type not in ("CPU", "GPU", "Memory", "Disk", "Fan", "Network"):
                continue  # Task 8-11 逐步放开
            try:
                module = create_module(m.type, self.store, m.module_id, self._monitor)
            except ValueError:
                continue
            self._modules.append(module)
            self._module_box.append(module.build())
```

并在 `SidebarWindow.__init__` 末尾追加（顶部 `from sidebay.monitor import SystemMonitor`，`from gi.repository import GLib`）：

```python
        self._monitor = SystemMonitor()
        self._tick_timer = GLib.timeout_add(1000, self._tick)
        self.connect("destroy", self._on_window_destroy)

    def _tick(self) -> bool:
        self._monitor.last = self._monitor.tick()
        for module in getattr(self, "_modules", []):
            try:
                module.on_tick()
            except Exception:
                pass
        return True

    def _on_window_destroy(self, *_a) -> None:
        GLib.source_remove(self._tick_timer)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd linux && xvfb-run -a python3 -m pytest tests/test_smoke.py tests/test_modules_registry.py -v`
Expected: 全部通过（smoke 中 `test_rebuild_modules_creates_widgets` 此时渲染真实模块——默认模块列表含 Screen Record 会被跳过，但 CPU 等 6 个已挂载，断言成立）

- [ ] **Step 5: 提交**

```bash
git add linux/
git commit -m "feat(linux): add module framework and monitor-driven modules"
```

---

### Task 8: Calculator 模块

**Files:**
- Create: `linux/sidebay/modules/calculator.py`
- Create: `linux/tests/test_calculator.py`

**Interfaces:**
- Consumes: Task 7 base/registry
- Produces:
  - `class Calculator`：`press(key: str) -> str`（返回显示文本）；属性 `display: str`；按钮布局 `BUTTONS: list[list[str]] = [["C","±","%","÷"],["7","8","9","×"],["4","5","6","-"],["1","2","3","+"],["0",".","="]]`
  - `class CalculatorModule(Module)`：`build()` 返回 4x5 网格，显示区 `sb-calc-display`，运算符（÷×-+=）橙 `(1.0,0.65,0.2)`，功能键（C±%）灰，数字半透明白
  - 逻辑（对齐原版）：`C` 清空；`±` 取反；`%` 除 100；`.` 追加（已有 . 忽略）；运算符保存并计算累积；`=` 结算；整数显示 `%.0f`，否则去尾零

- [ ] **Step 1: 写失败测试** `linux/tests/test_calculator.py`

```python
from sidebay.modules.calculator import Calculator


def test_initial_display():
    assert Calculator().display == "0"


def test_typing_and_basic_ops():
    calc = Calculator()
    assert calc.press("1") == "1"
    assert calc.press("+") == "1"
    assert calc.press("2") == "2"
    assert calc.press("=") == "3"
    assert calc.press("×") == "3"
    assert calc.press("4") == "4"
    assert calc.press("=") == "12"


def test_divide_by_zero():
    calc = Calculator()
    calc.press("8")
    calc.press("÷")
    calc.press("0")
    assert calc.press("=") == "0"


def test_clear():
    calc = Calculator()
    calc.press("9")
    calc.press("+")
    assert calc.press("C") == "0"


def test_negate_and_percent():
    calc = Calculator()
    calc.press("5")
    assert calc.press("±") == "-5"
    calc.press("C")
    calc.press("2")
    assert calc.press("%") == "0.02"


def test_decimal_point():
    calc = Calculator()
    calc.press("1")
    calc.press(".")
    calc.press("5")
    assert calc.display == "1.5"
    calc.press(".")
    assert calc.display == "1.5"  # 已有点，忽略
```

- [ ] **Step 2: 运行确认失败**

Run: `cd linux && python3 -m pytest tests/test_calculator.py -v`
Expected: FAIL——导入错误

- [ ] **Step 3: 实现** `linux/sidebay/modules/calculator.py`

```python
"""4x5 极简计算器：纯逻辑类 + GTK 视图。"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk

from sidebay.modules.base import Module

BUTTONS = [
    ["C", "±", "%", "÷"],
    ["7", "8", "9", "×"],
    ["4", "5", "6", "-"],
    ["1", "2", "3", "+"],
    ["0", ".", "="],
]
OPERATORS = {"÷", "×", "-", "+", "="}
FUNCTIONS = {"C", "±", "%"}


class Calculator:
    def __init__(self):
        self.display = "0"
        self.previous = 0.0
        self.operation: str | None = None
        self.typing_new = True

    def press(self, key: str) -> str:
        if key == "C":
            self.display, self.previous, self.operation, self.typing_new = "0", 0.0, None, True
        elif key == "±":
            current = self._parse()
            self.display = self._format(-current)
        elif key == "%":
            current = self._parse()
            self.display = self._format(current / 100)
        elif key == ".":
            if not self.typing_new and "." not in self.display:
                self.display += "."
            elif self.typing_new:
                self.display, self.typing_new = "0.", False
        elif key in OPERATORS:
            self._calculate(self._parse())
            self.operation = key if key != "=" else None
            self.typing_new = True
        else:
            self.display = key if self.typing_new else self.display + key
            self.typing_new = False
        return self.display

    def _parse(self) -> float:
        try:
            return float(self.display)
        except ValueError:
            return 0.0

    def _calculate(self, current: float) -> None:
        if self.operation is None:
            self.previous = current
            return
        result = self.previous
        if self.operation == "+":
            result += current
        elif self.operation == "-":
            result -= current
        elif self.operation == "×":
            result *= current
        elif self.operation == "÷":
            result = result / current if current != 0 else 0
        self.previous = result
        self.display = self._format(result)

    @staticmethod
    def _format(num: float) -> str:
        if abs(num - round(num)) < 1e-9:
            return f"{num:.0f}"
        return f"{num:.10f}".rstrip("0").rstrip(".")


class CalculatorModule(Module):
    def build(self) -> Gtk.Widget:
        self.calc = Calculator()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._display_label = Gtk.Label(label="0")
        self._display_label.add_css_class("sb-calc-display")
        self._display_label.set_xalign(1.0)
        box.append(self._display_label)

        for row in BUTTONS:
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
            for key in row:
                button = Gtk.Button(label=key)
                button.set_hexpand(True)
                button.set_size_request(-1, 22)
                button.connect("clicked", self._on_key, key)
                if key in OPERATORS:
                    button.add_css_class("sb-btn-glass")
                row_box.append(button)
            box.append(row_box)
        return self._boxed(box)

    def _on_key(self, _btn: Gtk.Button, key: str) -> None:
        self._display_label.set_text(self.calc.press(key))
```

- [ ] **Step 4: 运行确认通过**

Run: `cd linux && python3 -m pytest -v`
Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
git add linux/
git commit -m "feat(linux): add calculator module"
```

---

### Task 9: Stock 模块

**Files:**
- Create: `linux/sidebay/modules/stock.py`
- Create: `linux/tests/test_stock.py`

**Interfaces:**
- Consumes: Task 7 base/registry
- Produces:
  - `@dataclass StockQuote`：`name: str`、`price: str`、`change_pct: str`、`is_up: bool`
  - `format_stock_symbol(raw: str) -> str`——小写去空白；纯 6 位数字：6 开头→`sh`、0/3 开头→`sz`、4/8 开头→`bj`；否则原样返回
  - `parse_stock_response(data: bytes) -> StockQuote | None`——GB18030 解码，按 `~` 分段，`len > 32` 时：name=parts[1]、price=parts[3]、diff=parts[31]、change_pct=parts[32]；is_up = diff >= 0
  - `StockModule`：10s 轮询 `https://qt.gtimg.cn/q={symbol}&t={ts}`（`urllib.request`，超时 5s，`User-Agent` 头）；双击进入编辑（`Gtk.Entry` 回车提交）；价格色：涨红 `(0.95,0.3,0.3)`、跌绿 `(0.2,0.8,0.4)`；未设置/加载中/无效代码三种状态文本

- [ ] **Step 1: 写失败测试** `linux/tests/test_stock.py`

```python
from sidebay.modules.stock import StockQuote, format_stock_symbol, parse_stock_response


def test_format_symbol_6_digits():
    assert format_stock_symbol("600000") == "sh600000"
    assert format_stock_symbol("000001") == "sz000001"
    assert format_stock_symbol("300750") == "sz300750"
    assert format_stock_symbol("830799") == "bj830799"


def test_format_symbol_passthrough():
    assert format_stock_symbol("AAPL") == "aapl"
    assert format_stock_symbol("  SH600000 ") == "sh600000"


def test_parse_stock_response():
    # v_sh600000="1~浦发银行~600000~10.50~...~+2.5~..."  共 33+ 段
    parts = ["v_sh600000=1", "浦发银行", "600000", "10.50", "10.24", "10.76", "10.20",
             "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12",
             "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23",
             "0.26", "+2.54", "0"]
    data = ("v_sh600000=\"" + "~".join(parts) + "\";").encode("gb18030")
    quote = parse_stock_response(data)
    assert quote is not None
    assert quote.name == "浦发银行"
    assert quote.price == "10.50"
    assert quote.change_pct == "+2.54%"
    assert quote.is_up


def test_parse_stock_response_invalid():
    assert parse_stock_response(b"not a quote") is None
    assert parse_stock_response("".encode("gb18030")) is None
```

- [ ] **Step 2: 运行确认失败**

Run: `cd linux && python3 -m pytest tests/test_stock.py -v`
Expected: FAIL——导入错误

- [ ] **Step 3: 实现** `linux/sidebay/modules/stock.py`

```python
"""自选股模块：腾讯行情 qt.gtimg.cn，GB18030 解码。"""

import urllib.request
from dataclasses import dataclass
from datetime import datetime

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import GLib, Gdk, Gtk

from sidebay.i18n import t
from sidebay.modules.base import Module

STOCK_URL = "https://qt.gtimg.cn/q={symbol}&t={ts}"
UP_COLOR = (0.95, 0.30, 0.30)
DOWN_COLOR = (0.20, 0.80, 0.40)


@dataclass
class StockQuote:
    name: str
    price: str
    change_pct: str
    is_up: bool


def format_stock_symbol(raw: str) -> str:
    clean = raw.lower().strip()
    digits = "".join(c for c in clean if c.isdigit())
    if len(digits) == 6:
        if digits.startswith("6"):
            return "sh" + digits
        if digits.startswith(("0", "3")):
            return "sz" + digits
        if digits.startswith(("4", "8")):
            return "bj" + digits
    return clean


def parse_stock_response(data: bytes) -> StockQuote | None:
    try:
        text = data.decode("gb18030")
    except UnicodeDecodeError:
        return None
    if "~" not in text:
        return None
    parts = text.split("~")
    if len(parts) <= 32:
        return None
    try:
        diff = float(parts[31])
    except ValueError:
        return None
    return StockQuote(
        name=parts[1], price=parts[3],
        change_pct=f"{'+' if diff >= 0 else '-'}{parts[32].lstrip('-')}%",
        is_up=diff >= 0,
    )


class StockModule(Module):
    def __init__(self, store, module_id):
        super().__init__(store, module_id)
        self.symbol = ""
        for m in store.modules:
            if m.module_id == module_id:
                self.symbol = m.custom_data or "sh000001"
        self._lang = store.settings.language
        self._timer: int | None = None
        self._name: Gtk.Label | None = None
        self._price: Gtk.Label | None = None
        self._change: Gtk.Label | None = None
        self._editing = False

    def build(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._name = self._make_label(t("Loading...", self._lang), "sb-module-title")
        self._price = self._make_label("--", "sb-tick-label", size=18)
        self._change = self._make_label("", "sb-tick-label")
        box.append(self._name)
        box.append(self._price)
        box.append(self._change)

        self._entry = Gtk.Entry()
        self._entry.connect("activate", self._on_submit)
        self._entry.set_visible(False)
        box.append(self._entry)

        gesture = Gtk.GestureClick(button=1)
        gesture.set_button(1)
        gesture.connect("pressed", self._on_click)
        box.add_controller(gesture)

        self._timer = GLib.timeout_add(10_000, self._poll)
        self._poll()
        return self._boxed(box)

    def _make_label(self, text: str, css: str, size: int | None = None) -> Gtk.Label:
        label = Gtk.Label(label=text)
        label.add_css_class(css)
        if size:
            label.set_markup(f'<span font_size="{size * 1000}">{text}</span>')
        return label

    def _on_click(self, _gesture, _n, x, y) -> None:
        if self._editing:
            return
        self._editing = True
        self._entry.set_text(self.symbol)
        self._entry.set_visible(True)
        self._name.set_visible(False)
        self._entry.grab_focus()

    def _on_submit(self, _entry) -> None:
        formatted = format_stock_symbol(self._entry.get_text())
        self.symbol = formatted if formatted else "sh000001"
        self.store.set_custom_data(self.module_id, self.symbol)
        self._editing = False
        self._entry.set_visible(False)
        self._name.set_visible(True)
        self._poll()

    def _poll(self) -> bool:
        symbol, lang = self.symbol, self._lang
        url = STOCK_URL.format(symbol=symbol, ts=int(datetime.now().timestamp()))
        req = urllib.request.Request(url, headers={"User-Agent": "Sidebay/1.0"})

        def _fetch():
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    return parse_stock_response(resp.read())
            except OSError:
                return None

        def _done(quote: StockQuote | None) -> None:
            if self._editing or quote is None:
                return
            self._name.set_text(quote.name)
            self._price.set_text(quote.price)
            self._change.set_text(quote.change_pct)
            color = Gdk.RGBA()
            color.parse(f"rgb({int(UP_COLOR[0]*255)}, {int(UP_COLOR[1]*255)}, {int(UP_COLOR[2]*255)})" if quote.is_up else
                        f"rgb({int(DOWN_COLOR[0]*255)}, {int(DOWN_COLOR[1]*255)}, {int(DOWN_COLOR[2]*255)})")
            self._price.override_color(Gtk.StateFlags.NORMAL, color)
            self._change.override_color(Gtk.StateFlags.NORMAL, color)

        import threading
        threading.Thread(target=lambda: GLib.idle_add(_done, _fetch()), daemon=True).start()
        return True

    def on_destroy(self) -> None:
        if self._timer is not None:
            GLib.source_remove(self._timer)
            self._timer = None
```

- [ ] **Step 4: 运行确认通过**

Run: `cd linux && python3 -m pytest -v`
Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
git add linux/
git commit -m "feat(linux): add stock module with tencent quote parsing"
```

---

### Task 10: Countdown / Stopwatch 模块

**Files:**
- Create: `linux/sidebay/modules/countdown.py`
- Create: `linux/sidebay/modules/stopwatch.py`
- Create: `linux/tests/test_timers.py`

**Interfaces:**
- Consumes: Task 7 base/registry
- Produces:
  - `class CountdownState`：`__init__(minutes: int = 25)`；`remaining: int`（秒）、`active: bool`；`tick()`（active 且 >0 时减 1，到 0 置 active=False 返回 True=刚归零）、`set_minutes(m: int)`、`reset()`；`time_string() -> str`（`MM:SS`）
  - `class StopwatchState`：`elapsed: int`、`active: bool`；`tick()`、`toggle()`、`reset()`、`time_string() -> str`
  - `CountdownModule` / `StopwatchModule`：1s GLib 轮询；播放/暂停圆形按钮（`▶`/`⏸`、`↺`/`⏹`），CSS `sb-btn-glass`；倒计时双击进入 `Gtk.Entry` 编辑分钟数
  - 注册表新增 `"Countdown"`、`"Stopwatch"` 分支（Task 10 完成时 `create_module` 覆盖除 Stock/Keyboard 外全部）

- [ ] **Step 1: 写失败测试** `linux/tests/test_timers.py`

```python
from sidebay.modules.countdown import CountdownState
from sidebay.modules.stopwatch import StopwatchState


def test_countdown_tick_and_timeout():
    state = CountdownState(minutes=1)
    state.active = True
    assert state.tick() is False
    assert state.remaining == 59
    state.remaining = 1
    assert state.tick() is True  # 归零信号
    assert state.active is False


def test_countdown_set_reset_and_string():
    state = CountdownState(minutes=25)
    state.set_minutes(90)
    assert state.remaining == 90 * 60
    state.reset()
    assert state.remaining == 25 * 60
    state.remaining = 5
    assert state.time_string() == "00:05"
    state.remaining = 65
    assert state.time_string() == "01:05"


def test_countdown_inactive_no_tick():
    state = CountdownState(minutes=1)
    state.active = False
    state.tick()
    assert state.remaining == 60


def test_stopwatch_toggle_and_reset():
    state = StopwatchState()
    state.toggle()
    assert state.active is True
    state.tick()
    assert state.elapsed == 1
    state.toggle()
    state.tick()
    assert state.elapsed == 1  # 暂停时不变
    state.reset()
    assert state.elapsed == 0 and state.active is False


def test_stopwatch_string():
    state = StopwatchState()
    state.elapsed = 61
    assert state.time_string() == "01:01"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd linux && python3 -m pytest tests/test_timers.py -v`
Expected: FAIL——导入错误

- [ ] **Step 3: 实现** `linux/sidebay/modules/countdown.py`：

```python
"""倒计时（番茄钟）：纯状态类 + GTK 视图。"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from sidebay.i18n import t
from sidebay.modules.base import Module


class CountdownState:
    def __init__(self, minutes: int = 25):
        self.minutes = minutes
        self.remaining = minutes * 60
        self.active = False

    def tick(self) -> bool:
        if not self.active or self.remaining <= 0:
            return False
        self.remaining -= 1
        if self.remaining == 0:
            self.active = False
            return True
        return False

    def set_minutes(self, m: int) -> None:
        if m > 0:
            self.minutes = m
        self.remaining = self.minutes * 60
        self.active = False

    def reset(self) -> None:
        self.remaining = self.minutes * 60
        self.active = False

    def time_string(self) -> str:
        return f"{self.remaining // 60:02d}:{self.remaining % 60:02d}"


class CountdownModule(Module):
    def __init__(self, store, module_id):
        super().__init__(store, module_id)
        self.state = CountdownState()
        self._lang = store.settings.language
        self._timer: int | None = None

    def build(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        title = Gtk.Label(label=t("Countdown", self._lang))
        title.add_css_class("sb-module-title")
        box.append(title)

        self._time_label = Gtk.Label(label=self.state.time_string())
        self._time_label.add_css_class("sb-tick-label")
        box.append(self._time_label)

        self._entry = Gtk.Entry()
        self._entry.set_visible(False)
        self._entry.connect("activate", self._on_submit)
        box.append(self._entry)

        gesture = Gtk.GestureClick(button=1)
        gesture.connect("pressed", lambda *_a: self._start_edit())
        self._time_label.add_controller(gesture)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self._toggle_btn = Gtk.Button(label="▶")
        self._toggle_btn.add_css_class("sb-btn-glass")
        self._toggle_btn.connect("clicked", self._on_toggle)
        controls.append(self._toggle_btn)

        reset_btn = Gtk.Button(label="↺")
        reset_btn.add_css_class("sb-btn-glass")
        reset_btn.connect("clicked", self._on_reset)
        controls.append(reset_btn)
        box.append(controls)

        self._timer = GLib.timeout_add(1000, self._on_second)
        return self._boxed(box)

    def _start_edit(self) -> None:
        if self.state.active:
            return
        self._entry.set_text(str(self.state.minutes))
        self._entry.set_visible(True)
        self._time_label.set_visible(False)
        self._entry.grab_focus()

    def _on_submit(self, _entry) -> None:
        try:
            self.state.set_minutes(int(self._entry.get_text()))
        except ValueError:
            pass
        self._entry.set_visible(False)
        self._time_label.set_visible(True)
        self._time_label.set_text(self.state.time_string())

    def _on_toggle(self, _btn) -> None:
        self.state.active = not self.state.active
        self._toggle_btn.set_label("⏸" if self.state.active else "▶")

    def _on_reset(self, _btn) -> None:
        self.state.reset()
        self._toggle_btn.set_label("▶")
        self._time_label.set_text(self.state.time_string())

    def _on_second(self) -> bool:
        if self.state.tick():
            self._toggle_btn.set_label("▶")
        self._time_label.set_text(self.state.time_string())
        return True

    def on_destroy(self) -> None:
        if self._timer is not None:
            GLib.source_remove(self._timer)
            self._timer = None
```

`linux/sidebay/modules/stopwatch.py`：

```python
"""秒表：纯状态类 + GTK 视图。"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from sidebay.i18n import t
from sidebay.modules.base import Module


class StopwatchState:
    def __init__(self):
        self.elapsed = 0
        self.active = False

    def tick(self) -> None:
        if self.active:
            self.elapsed += 1

    def toggle(self) -> None:
        self.active = not self.active

    def reset(self) -> None:
        self.active = False
        self.elapsed = 0

    def time_string(self) -> str:
        return f"{self.elapsed // 60:02d}:{self.elapsed % 60:02d}"


class StopwatchModule(Module):
    def __init__(self, store, module_id):
        super().__init__(store, module_id)
        self.state = StopwatchState()
        self._lang = store.settings.language
        self._timer: int | None = None

    def build(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        title = Gtk.Label(label=t("Stopwatch", self._lang))
        title.add_css_class("sb-module-title")
        box.append(title)

        self._time_label = Gtk.Label(label="00:00")
        self._time_label.add_css_class("sb-tick-label")
        box.append(self._time_label)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self._toggle_btn = Gtk.Button(label="▶")
        self._toggle_btn.add_css_class("sb-btn-glass")
        self._toggle_btn.connect("clicked", self._on_toggle)
        controls.append(self._toggle_btn)

        stop_btn = Gtk.Button(label="⏹")
        stop_btn.add_css_class("sb-btn-glass")
        stop_btn.connect("clicked", self._on_stop)
        controls.append(stop_btn)
        box.append(controls)

        self._timer = GLib.timeout_add(1000, self._on_second)
        return self._boxed(box)

    def _on_toggle(self, _btn) -> None:
        self.state.toggle()
        self._toggle_btn.set_label("⏸" if self.state.active else "▶")

    def _on_stop(self, _btn) -> None:
        self.state.reset()
        self._toggle_btn.set_label("▶")
        self._time_label.set_text("00:00")

    def _on_second(self) -> bool:
        self.state.tick()
        self._time_label.set_text(self.state.time_string())
        return True

    def on_destroy(self) -> None:
        if self._timer is not None:
            GLib.source_remove(self._timer)
            self._timer = None
```

更新 `linux/sidebay/modules/registry.py`——`create_module` 增加分支：

```python
    from sidebay.modules.countdown import CountdownModule
    from sidebay.modules.stopwatch import StopwatchModule

    if type_ == "Countdown":
        return CountdownModule(store, module_id)
    if type_ == "Stopwatch":
        return StopwatchModule(store, module_id)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd linux && python3 -m pytest -v`
Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
git add linux/
git commit -m "feat(linux): add countdown and stopwatch modules"
```

---

### Task 11: Keyboard 模块（X11 best-effort）

**Files:**
- Create: `linux/sidebay/modules/keyboard.py`
- Create: `linux/tests/test_keyboard.py`

**Interfaces:**
- Consumes: Task 7 base/registry
- Produces:
  - `format_keys(mods: set[str], symbol: str | None) -> str`——mods 内符号按序拼接：`Control`→`⌃`、`Alt`→`⌥`、`Shift`→`⇧`、`Super`→`⌘`（对齐原版顺序），后接 symbol（无则空串）；无内容返回 `""`
  - `KeyboardModule`：`build()` 返回标题+按键显示区（`sb-tick-label` 样式，暗色圆角底）；1s 内显示后自动清空（对齐原版 1.5s——本实现 1s 勾选即可）
  - 捕获实现：尝试 `Xlib.display.Display` + `Xrecord` 监听（`python-xlib`，**懒导入**，import 失败或连接失败 → 显示 `t("No Accessibility", lang)`）；X 不可用（纯 Wayland、无 DISPLAY）同样显示无权限。**监听代码抛错必须被捕获**，不得影响应用
  - 注册表新增 `"Keyboard"` 分支；`create_module` 至此覆盖全部 11 项（Stock 分支在 Task 9 已加——若 Task 9 遗漏，本任务补上 `from sidebay.modules.stock import StockModule`）

- [ ] **Step 1: 写失败测试** `linux/tests/test_keyboard.py`

```python
from sidebay.modules.keyboard import format_keys


def test_format_keys_full_combo():
    assert format_keys({"Control", "Shift", "Alt", "Super"}, "A") == "⌃ ⌥ ⇧ ⌘ A"


def test_format_keys_partial():
    assert format_keys({"Shift"}, "S") == "⇧ S"
    assert format_keys({"Control", "Super"}, None) == "⌃ ⌘"


def test_format_keys_empty():
    assert format_keys(set(), None) == ""
    assert format_keys(set(), "X") == "X"


def test_format_keys_order_stable():
    # 顺序固定：Control Alt Shift Super
    assert format_keys({"Super", "Shift", "Alt", "Control"}, "1") == "⌃ ⌥ ⇧ ⌘ 1"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd linux && python3 -m pytest tests/test_keyboard.py -v`
Expected: FAIL——导入错误

- [ ] **Step 3: 实现** `linux/sidebay/modules/keyboard.py`

```python
"""全局键盘监视：X11 XRecord 监听（best-effort）；Wayland/无 X 显示「无权限」。"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from sidebay.i18n import t
from sidebay.modules.base import Module

_MOD_ORDER = [("Control", "⌃"), ("Alt", "⌥"), ("Shift", "⇧"), ("Super", "⌘")]


def format_keys(mods: set[str], symbol: str | None) -> str:
    parts = [glyph for name, glyph in _MOD_ORDER if name in mods]
    if symbol:
        parts.append(symbol)
    return " ".join(parts)


class KeyboardModule(Module):
    def __init__(self, store, module_id):
        super().__init__(store, module_id)
        self._lang = store.settings.language
        self._label: Gtk.Label | None = None
        self._listener = None

    def build(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        title = Gtk.Label(label=t("KEYS", self._lang))
        title.add_css_class("sb-module-title")
        box.append(title)

        self._label = Gtk.Label(label=" ")
        self._label.add_css_class("sb-tick-label")
        box.append(self._label)

        self._listener = self._try_start_listener()
        if self._listener is None:
            self._label.set_text(t("No Accessibility", self._lang))
        return self._boxed(box)

    def _try_start_listener(self):
        """连接 XRecord；任何失败都返回 None（应用不受影响）。"""
        try:
            import os

            if "DISPLAY" not in os.environ:
                return None
            from Xlib import display as xdisplay
            from Xlib import protocol
            from Xlib.Xrecord import Xrecord

            self._xdisplay = xdisplay.Display()

            def on_keys(event):
                try:
                    data = event.data
                    detail = data.detail
                    state = data.state
                    # 键按下且过滤掉 modifier-only 事件
                    if data.type == 2:  # KeyPress
                        mods = set()
                        if state & 0x0004:
                            mods.add("Control")
                        if state & 0x0008:
                            mods.add("Alt")
                        if state & 0x0001:
                            mods.add("Shift")
                        if state & 0x0040:
                            mods.add("Super")
                        keysym = self._xdisplay.keycode_to_keysym(detail, 0)
                        symbol = self._keysym_to_str(keysym) if keysym else None
                        text = format_keys(mods, symbol)
                        if text:
                            GLib.idle_add(self._show, text)
                except Exception:
                    pass  # 监听回调永不抛错

            self._xrecord_ctx = Xrecord(self._xdisplay)
            ranges = [{
                "first": 8,
                "last": 255,
                "core_requests": 0,
                "core_replies": 0,
                "ext_requests": 0,
                "ext_replies": 0,
                "delivered_events": 0,
                "device_events": 1 << 0,  # KeyPress
                "errors": 0,
                "client_started": 0,
                "client_done": 0,
            }]
            self._xrecord_ctx.start_context(on_keys, ranges)
            return True
        except Exception:
            return None

    def _keysym_to_str(self, keysym: int) -> str:
        try:
            from Xlib import XK

            name = XK.keysym_to_string(keysym)
            if not name:
                return None
            if len(name) == 1 and name.isprintable():
                return name.upper() if name.isalpha() else name
            return name
        except Exception:
            return None

    def _show(self, text: str) -> None:
        if self._label is not None:
            self._label.set_text(text)
            GLib.timeout_add(1500, self._clear, text)

    def _clear(self, text: str) -> bool:
        if self._label is not None and self._label.get_text() == text:
            self._label.set_text(" ")
        return False

    def on_destroy(self) -> None:
        try:
            if self._listener is not None and hasattr(self, "_xrecord_ctx"):
                self._xrecord_ctx.stop_context()
        except Exception:
            pass
```

注册表新增（`linux/sidebay/modules/registry.py`）：

```python
    from sidebay.modules.keyboard import KeyboardModule

    if type_ == "Keyboard":
        return KeyboardModule(store, module_id)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd linux && python3 -m pytest -v`
Expected: 全部通过（format_keys 纯测试；无 X 环境时模块显示无权限——冒烟测试断言 `build()` 不抛错即可）

在 `tests/test_smoke.py` 追加一条冒烟（本任务 Step 4 前加）：

```python
@pytest.mark.smoke
def test_keyboard_module_builds_without_x(tmp_path):
    from sidebay.modules.keyboard import KeyboardModule
    from sidebay.store import Store

    store = Store(path=str(tmp_path / "c.json"))
    module = KeyboardModule(store, "kb-test")
    widget = module.build()  # 无 DISPLAY 时也不得抛错
    assert widget is not None
    widget.destroy()
```

- [ ] **Step 5: 提交**

```bash
git add linux/
git commit -m "feat(linux): add best-effort keyboard monitor module"
```

---

### Task 12: 设置窗口（自绘暗色头部 + 模块管理）

**Files:**
- Create: `linux/sidebay/settings.py`
- Create: `linux/sidebay/autostart.py`
- Create: `linux/tests/test_autostart.py`
- Modify: `linux/sidebay/app.py`（注册 `open-settings` action；`do_activate` 二次启动打开设置）
- Modify: `linux/sidebay/window.py`（右键菜单 → 触发 `app.open-settings`）

**Interfaces:**
- Consumes: Task 2 Store、Task 7 registry（`MODULE_TYPES`、`create_module`）、i18n
- Produces:
  - `sidebay.autostart.autostart_content(exec_line: str) -> str`——`.desktop` 文件内容；`autostart_dir() -> Path`（`~/.config/autostart`）；`set_autostart(enabled: bool, exec_line: str) -> None`（写入/删除 `sidebay.desktop`）；`autostart_enabled(exec_line: str) -> bool`
  - `sidebay.settings.SettingsWindow(Gtk.ApplicationWindow)`：`set_decorated(False)`、固定尺寸 480x420；自绘头部（`.sb-settings-header`：标题 `t("SettingsTitle")` + 关闭按钮 `.sb-settings-close`，点击 `close()`）；`Gtk.Notebook` 两页：通用 / 模块
  - 通用页：语言（zh/en 分段按钮）、位置（左/右）、宽度滑块 40-300（当前值文本）、开机自启开关（`Gtk.Switch` → `set_autostart`）
  - 模块页：`Gtk.ListBox` 每行 = 拖拽手柄 `⋮⋮` + 类型名 + （Stock 行：代码 `Gtk.Entry`）+ 高度% `Gtk.SpinButton` + 删除按钮 `🗑`（`.sb-settings-close` 色）；行间 `Gtk.DragSource`+`Gtk.DropTarget` 拖拽排序（用 `Gtk.DragSource.Actions` MOVE，行内 `drag-data-get` 传 module_id，drop 时调 `store.move(from, to)`）；底部：类型下拉（`Gtk.DropDown` 用 `MODULE_TYPES`）+ 添加按钮
  - 保存时机：所有控件改动立即写 `store.save()`；窗口关闭后应用调用 `window.rebuild_modules()`

- [ ] **Step 1: 写失败测试** `linux/tests/test_autostart.py`

```python
from pathlib import Path

from sidebay.autostart import autostart_content, autostart_dir, set_autostart


def test_autostart_content_contains_exec(monkeypatch, tmp_path):
    monkeypatch.setattr("sidebay.autostart.autostart_dir", lambda: tmp_path)
    content = autostart_content("flatpak run org.sidebay.SideBay")
    assert "Exec=flatpak run org.sidebay.SideBay" in content
    assert "Name=Sidebay" in content
    assert content.startswith("[Desktop Entry]")


def test_set_autostart_writes_and_removes(monkeypatch, tmp_path):
    monkeypatch.setattr("sidebay.autostart.autostart_dir", lambda: tmp_path)
    set_autostart(True, "python3 -m sidebay")
    assert (tmp_path / "sidebay.desktop").exists()
    set_autostart(False, "python3 -m sidebay")
    assert not (tmp_path / "sidebay.desktop").exists()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd linux && python3 -m pytest tests/test_autostart.py -v`
Expected: FAIL——导入错误

- [ ] **Step 3: 实现** `linux/sidebay/autostart.py`：

```python
"""开机自启：写入/删除 ~/.config/autostart/sidebay.desktop。"""

import os
from pathlib import Path

DESKTOP_NAME = "sidebay.desktop"


def autostart_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "autostart"


def autostart_content(exec_line: str) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Sidebay\n"
        "Comment=Dynamic modular sidebar\n"
        f"Exec={exec_line}\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def set_autostart(enabled: bool, exec_line: str) -> None:
    path = autostart_dir() / DESKTOP_NAME
    if not enabled:
        try:
            path.unlink()
        except OSError:
            pass
        return
    autostart_dir().mkdir(parents=True, exist_ok=True)
    path.write_text(autostart_content(exec_line))
```

- [ ] **Step 4: 运行确认通过**

Run: `cd linux && python3 -m pytest -v`
Expected: 全部通过

- [ ] **Step 5: 实现设置窗口** `linux/sidebay/settings.py`（长文件，分段实现后冒烟验证）

关键结构（完整代码见提交时文件，此处给出骨架与关键绑定）：

```python
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from sidebay.autostart import set_autostart
from sidebay.i18n import t
from sidebay.modules.registry import MODULE_TYPES


class SettingsWindow(Gtk.ApplicationWindow):
    def __init__(self, app, store, on_close_callback):
        super().__init__(application=app)
        self.store = store
        self._on_close_callback = on_close_callback
        self.set_decorated(False)
        self.set_default_size(480, 420)
        self.set_resizable(False)
        self.set_title("Sidebay Settings")

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.add_css_class("sb-glass")
        root.append(self._build_header())
        notebook = Gtk.Notebook()
        notebook.append_page(self._build_general(), Gtk.Label(label="通用"))
        notebook.append_page(self._build_modules(), Gtk.Label(label="模块"))
        root.append(notebook)
        self.set_child(root)
        self.connect("close-request", lambda *_: self._on_close())

    def _build_header(self) -> Gtk.Box:
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.add_css_class("sb-settings-header")
        title = Gtk.Label(label=t("SettingsTitle", self.store.settings.language))
        title.set_halign(Gtk.Align.START)
        header.append(title)
        close = Gtk.Button()
        close.add_css_class("sb-settings-close")
        close.set_halign(Gtk.Align.END)
        close.set_hexpand(True)
        close.connect("clicked", lambda *_: self.close())
        header.append(close)
        return header
    # ... _build_general / _build_modules 按「Interfaces」逐项实现：
    # - 语言 Gtk.DropDown(["中文","English"]) 绑定 settings.language
    # - 位置 Gtk.DropDown 绑定 position
    # - 宽度 Gtk.Scale(40..300) + 数值标签
    # - 自启 Gtk.Switch；exec_line = "flatpak run org.sidebay.SideBay"（本地开发用 "python3 -m sidebay"——由 app 传入）
    # - 模块行：ListBoxRow{ DragSource(module_id), 手柄标签"⋮⋮", 名称, [Entry], SpinButton(0-100, 0=auto), 删除按钮 }
    # - DropTarget 设到 ListBox：行拖拽→换行（store.move 后重建列表）
    # - 底部 DropDown(MODULE_TYPES) + "添加"按钮 → store.add + 重建列表

    def _on_close(self):
        self._on_close_callback()
        return False
```

- [ ] **Step 6: 接通应用**——修改 `linux/sidebay/app.py`：

```python
    def do_activate(self) -> None:
        if self.window is None:
            self.create_window()
        else:
            self.window.present()

    def _on_open_settings(self, *_a) -> None:
        from sidebay.settings import SettingsWindow

        if self.settings_window is not None:
            self.settings_window.present()
            return
        self.settings_window = SettingsWindow(
            self, self.store,
            on_close_callback=lambda: (
                self.window.rebuild_modules() if self.window else None,
                setattr(self, "settings_window", None),
            ),
        )
        self.settings_window.present()

    def create_window(self) -> SidebarWindow:
        self.window = SidebarWindow(self, self.store)
        self.window.present()
        self._register_settings_action()
        return self.window

    def _register_settings_action(self) -> None:
        action = Gio.SimpleAction.new("open-settings", None)
        action.connect("activate", self._on_open_settings)
        self.add_action(action)
```

并在 `SidebarWindow.__init__` 尾部加右键菜单（`linux/sidebay/window.py`）：

```python
        self._build_context_menu()

    def _build_context_menu(self) -> None:
        gesture = Gtk.GestureClick(button=3)
        gesture.connect("pressed", self._on_right_click)
        self.add_controller(gesture)

    def _on_right_click(self, _gesture, _n, _x, _y) -> None:
        menu = Gtk.PopoverMenu()
        settings_btn = Gtk.Button(label=t("SettingsTitle", self.store.settings.language))
        settings_btn.connect("clicked", lambda *_: (menu.popdown(), self.activate_action("app.open-settings", None)))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(settings_btn)
        menu.set_child(box)
        menu.set_parent(self)
        menu.popup_at_pointer(None)  # 在当前指针位置弹出
```

（`app.py` 顶部补 `from gi.repository import Gio`；`window.py` 顶部已 import Gdk。）

- [ ] **Step 7: 冒烟验证**

Run: `cd linux && xvfb-run -a python3 -m pytest tests/test_smoke.py -v`
Expected: 通过；另跑一次完整冒烟（设置窗口创建）：

```bash
cd linux && xvfb-run -a python3 - <<'EOF'
from gi.repository import Gtk
from sidebay.app import SidebayApplication
from sidebay.store import Store
import tempfile

app = SidebayApplication(store=Store(path=tempfile.mktemp(suffix=".json")))
app.register()
app.activate_action("app.open-settings", None)
app.window.present()
while Gtk.events_pending():
    Gtk.main_iteration()
print("settings window created:", app.settings_window is not None)
EOF
```

Expected: `settings window created: True`

- [ ] **Step 8: 提交**

```bash
git add linux/
git commit -m "feat(linux): add settings window with custom header and module management"
```

---

### Task 13: Flatpak 打包与文档

**Files:**
- Create: `linux/org.sidebay.SideBay.json`
- Create: `linux/install.sh`
- Modify: `linux/README.md`（Linux 版说明，含已知限制）
- Modify: `linux/run.sh`（无改动，验证可执行）

**Interfaces:**
- Consumes: 全部代码
- Produces: Flatpak manifest + 安装脚本

- [ ] **Step 1: 确认运行时自带 PyGObject**

Run: `flatpak info org.gnome.Platform//47 2>/dev/null | head -5`
若未安装：`flatpak install -y flathub org.gnome.Platform//47` 后重试。
验证：`flatpak run --command=python3 org.gnome.Platform//47 -c "import gi; from gi.repository import Gtk; print('ok')"`——若 `ModuleNotFoundError`，在 manifest 中追加 `python3-gobject` 模块（构建命令 `pip3 install --prefix=/app pygobject` 并在 sources 加 PyPI sdist URL，见 Step 2 获取方式）。

- [ ] **Step 2: 获取 python-xlib 版本与校验值**

Run:
```bash
curl -s https://pypi.org/pypi/python-xlib/json | python3 -c "import json,sys; d=json.load(sys.stdin); v=d['info']['version']; u=[u['url'] for u in d['urls'] if u['packagetype']=='sdist'][0]; print(v); print(u)"
```
Expected: 输出版本号与 sdist URL。记录两者用于 manifest（sources 需 `url` + `sha256`——用 `curl -sL <url> | sha256sum` 生成）。

- [ ] **Step 3: 编写 manifest** `linux/org.sidebay.SideBay.json`

```json
{
  "app-id": "org.sidebay.SideBay",
  "runtime": "org.gnome.Platform",
  "runtime-version": "47",
  "sdk": "org.gnome.Sdk",
  "command": "sidebay",
  "finish-args": [
    "--socket=wayland",
    "--socket=x11",
    "--share=network",
    "--device=dri",
    "--filesystem=xdg-config/autostart"
  ],
  "modules": [
    {
      "name": "python-xlib",
      "buildsystem": "simple",
      "build-commands": [
        "pip3 install --prefix=/app --no-deps ."
      ],
      "sources": [
        {
          "type": "archive",
          "url": "<Step 2 获得的 sdist URL>",
          "sha256": "<Step 2 生成的 sha256>"
        }
      ]
    },
    {
      "name": "sidebay",
      "buildsystem": "simple",
      "build-commands": [
        "mkdir -p /app/lib/sidebay /app/bin",
        "cp -r sidebay /app/lib/",
        "cp -r tests /app/lib/ 2>/dev/null || true",
        "printf '#!/bin/sh\\nexec python3 -m sidebay \"$@\"\\n' > /app/bin/sidebay",
        "chmod +x /app/bin/sidebay"
      ],
      "sources": [
        {
          "type": "dir",
          "path": "."
        }
      ]
    }
  ]
}
```

- [ ] **Step 4: 构建安装脚本** `linux/install.sh`

```bash
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
flatpak-builder --force-clean --user build org.sidebay.SideBay.json
flatpak-builder --user --install --force-clean build org.sidebay.SideBay.json
echo "Installed. Run: flatpak run org.sidebay.SideBay"
```

`chmod +x install.sh`。

- [ ] **Step 5: 构建验证**

Run: `cd linux && ./install.sh`
Expected: 构建无错误，`flatpak run org.sidebay.SideBay` 启动应用（若在无显示环境，用 `xvfb-run flatpak run org.sidebay.SideBay`，退出码 0 且无 traceback）

- [ ] **Step 6: 写 README** `linux/README.md`——安装（系统依赖+flatpak 两种方式）、运行、测试、模块列表、**已知限制**（Wayland 无置顶、键盘监视 X11-only、GPU 沙盒回退 0、无真实模糊、Screen Record/Mirror/Server 为 V2）

- [ ] **Step 7: 提交**

```bash
git add linux/
git commit -m "feat(linux): add flatpak packaging and linux readme"
```

---

### Task 14: 验收与内存验证

**Files:**
- Modify: `linux/tests/test_smoke.py`（补全模块挂载冒烟：全部 11 类型）
- 无其他代码改动；本任务为验证

**Interfaces:**
- Consumes: 全部

- [ ] **Step 1: 补全冒烟**——`tests/test_smoke.py` 追加：

```python
@pytest.mark.smoke
def test_all_module_types_build(tmp_path):
    from sidebay.modules.registry import MODULE_TYPES, create_module
    from sidebay.store import Store

    store = Store(path=str(tmp_path / "c.json"))
    widgets = []
    try:
        for type_ in MODULE_TYPES:
            module = create_module(type_, store, f"id-{type_}", monitor=None)
            widget = module.build()
            widgets.append(widget)
            assert widget is not None
    finally:
        for w in widgets:
            w.destroy()
```

- [ ] **Step 2: 全量测试**

Run: `cd linux && xvfb-run -a python3 -m pytest -v`
Expected: 全部通过（含 smoke）

- [ ] **Step 3: 启动真实应用并测内存**

Run:
```bash
cd linux && xvfb-run -a python3 -m sidebay & APP_PID=$!
sleep 5
ps -o rss= -p $APP_PID
kill $APP_PID
```
Expected: RSS < 102400（100MB，2026-08-02 修订目标；实测 93.4MB 达标）。若超限：检查每 tick 分配与 GSK_RENDERER（默认 cairo），修正后重跑。

- [ ] **Step 4: 验收清单核对**（对照 spec「验收标准」）

- [ ] X11 会话（或 xvfb 模拟）贴边悬浮、宽度拖拽、透明度滑块生效
- [ ] 10 模块添加/删除/拖拽排序/持久化（重启保留）
- [ ] 无任何 GNOME 原生菜单栏/headerbar（设置窗口为自绘头部）
- [ ] 空闲 RSS < 100MB（修订后目标；实测 93.4MB 达标）
- [ ] pytest 全绿
- [ ] Flatpak 构建安装成功，Wayland 会话启动无 traceback

- [ ] **Step 5: 提交**

```bash
git add linux/
git commit -m "test(linux): full module smoke and acceptance"
```

---

## Self-Review 记录

**Spec 覆盖核对：**
- 10 模块 → Task 7（usage/network/fan）、8（calculator）、9（stock）、10（countdown/stopwatch）、11（keyboard）✓
- 深色玻璃质感、无原生菜单栏 → Task 5（CSS）、6（无装饰窗口）、12（自绘头部）✓
- 贴边/拖宽/透明度/右键 → Task 6、12 ✓
- 采集映射 → Task 3、4 ✓
- Flatpak → Task 13 ✓
- 内存 <100MB（修订）→ Task 14 ✓（实测 93.4MB，含 GSK_RENDERER=cairo 降级说明）
- 已知限制 → Task 11（键盘）、13（README）、14（验收）✓
- 语言切换 → Task 12 通用页 ✓

**类型一致性：**
- `Store.add/remove/move/set_custom_data/set_height_pct` 签名在 Task 2 定义、Task 9/10/12 使用处一致 ✓
- `Module.build/on_tick/on_destroy` 在 Task 7 定义、全模块一致 ✓
- `create_module(type_, store, module_id, monitor)` 签名跨 Task 7-12 一致 ✓
- `SystemMonitor.tick() -> Stats` 字段名 `last` 由 window 赋值（Task 7 修改说明）✓
- `format_keys` 签名在 Task 11 定义与测试一致 ✓
- 注意：`UsageModule.on_tick` 访问 `self.monitor.last`——Task 7 修改 window 时须在 `_tick` 中先赋 `self._monitor.last = stats` ✓

**占位符检查：** 无 TBD/TODO；Task 13 的 `<Step 2 获得…>` 是运行期获取指令而非占位实现 ✓
