"""Linux 系统采集：/proc 与 /sys 文件的纯函数解析 + 采样类。"""

import os
import random
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CpuSample:
    total: int
    idle: int


def parse_cpu_usage(text: str, prev: CpuSample | None) -> tuple[float, CpuSample]:
    """标准 Linux CPU 语义（与 htop/gnome-system-monitor 一致）：

    - idle 含 iowait（iowait 是等磁盘的空闲时间，非忙碌）
    - guest/guest_nice 不参与求和（内核已将其计入 user/nice，重复求和会虚增 total）
    - busy = user + nice + system + irq + softirq + steal
    """
    for line in text.splitlines():
        if line.startswith("cpu ") or line == "cpu":
            nums = [int(p) for p in line.split()[1:]]
            user = nums[0] if len(nums) > 0 else 0
            nice = nums[1] if len(nums) > 1 else 0
            system = nums[2] if len(nums) > 2 else 0
            idle = nums[3] if len(nums) > 3 else 0
            iowait = nums[4] if len(nums) > 4 else 0
            irq = nums[5] if len(nums) > 5 else 0
            softirq = nums[6] if len(nums) > 6 else 0
            steal = nums[7] if len(nums) > 7 else 0
            total = user + nice + system + idle + iowait + irq + softirq + steal
            idle_total = idle + iowait
            sample = CpuSample(total=total, idle=idle_total)
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


# 虚拟/隧道接口不计入网速（VPN/容器/桥接会虚增流量）
SKIP_IFACE_PREFIXES = ("veth", "docker", "br-", "virbr", "tun", "tap", "wg", "zt", "bond", "dummy")


def parse_net_dev(text: str) -> dict[str, tuple[int, int]]:
    result: dict[str, tuple[int, int]] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        iface, rest = line.split(":", 1)
        iface = iface.strip()
        if iface == "lo" or iface.startswith(SKIP_IFACE_PREFIXES):
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
    """返回 (up, down) 字节/秒。up=上行=发送(tx)，down=下行=接收(rx)——与
    macOS 原版（obytes/ibytes）及通行语义一致。"""
    if not prev or dt <= 0:
        return 0.0, 0.0
    up = down = 0.0
    for iface, (rx, tx) in curr.items():
        if iface in prev:
            up += max(tx - prev[iface][1], 0)
            down += max(rx - prev[iface][0], 0)
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
        self.last = Stats()  # 复用实例：tick 就地更新，避免每秒新建对象
        self._prev_cpu: CpuSample | None = None
        self._prev_net: dict[str, tuple[int, int]] = {}
        self._last_net_time = 0.0
        # nvidia-smi 存在性只探测一次：无独显的机器不必每秒 fork+exec 一次
        self._has_nvidia_smi = shutil.which("nvidia-smi") is not None
        # nvidia-smi fork 成本高：结果缓存 3s，避免每秒起进程
        self._gpu_cache_value = 0.0
        self._gpu_cache_time = 0.0

    def tick(self) -> Stats:
        cpu_text = self._read(self.proc_root / "stat")
        cpu, self._prev_cpu = parse_cpu_usage(cpu_text, self._prev_cpu)
        gpu = self._read_gpu()

        mem_text = self._read(self.proc_root / "meminfo")
        mem_used, mem_total = parse_meminfo(mem_text)

        disk_pct, disk_total = self._read_disk()

        net_text = self._read(self.proc_root / "net" / "dev")
        curr_net = parse_net_dev(net_text)
        now = time.time()
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

        # 就地更新复用实例（减少每秒分配）
        self.last.cpu = cpu
        self.last.gpu = gpu
        self.last.mem_used = mem_used
        self.last.mem_total = mem_total
        self.last.disk_pct = disk_pct
        self.last.disk_total = disk_total
        self.last.net_up = net_up
        self.last.net_down = net_down
        self.last.fan_rpm = fan
        return self.last

    @staticmethod
    def _read(path: Path) -> str:
        try:
            return path.read_text()
        except OSError:
            return ""

    def _read_disk(self) -> tuple[float, float]:
        try:
            # Flatpak 沙盒内 "/" 是 tmpfs overlay；宿主磁盘经 --filesystem=host
            # 挂载于 HOME 路径，statvfs(HOME) 才能读到真实磁盘
            path = os.path.expanduser("~")
            st = os.statvfs(path)
            total = st.f_blocks * st.f_frsize
            # df 语义：pcent = used/(used+bavail)，used=blocks-bfree
            # （bavail 排除保留块；直接 total-bavail 会把保留块算进已用，虚高 ~1-2 点）
            used_for_pct = (st.f_blocks - st.f_bfree) * st.f_frsize
            avail = st.f_bavail * st.f_frsize
            denom = used_for_pct + avail
            return (used_for_pct / denom * 100.0 if denom > 0 else 0.0), total
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
        if not self._has_nvidia_smi:
            return 0.0
        # 节流：nvidia-smi fork 至少间隔 3s（sysfs 读取路径不受影响）
        now = time.time()
        if now - self._gpu_cache_time < 3.0:
            return self._gpu_cache_value
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2,
            )
            value = parse_gpu_busy(out.stdout.strip().splitlines()[0]) if out.stdout.strip() else 0.0
        except (OSError, subprocess.TimeoutExpired, IndexError):
            value = 0.0
        self._gpu_cache_value = value
        self._gpu_cache_time = now
        return value
