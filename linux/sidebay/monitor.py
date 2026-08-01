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
