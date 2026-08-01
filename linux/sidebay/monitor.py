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
