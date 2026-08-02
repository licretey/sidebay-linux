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
    # 网卡计数器递增，第二次 tick 才能算出非零速率
    write(proc, "net/dev", "Inter-| Receive                                                | Transmit\n face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed\n    lo: 1000 10 0 0 0 0 0 0 1000 10 0 0 0 0 0 0\n  eth0: 8000 8 0 0 0 0 0 0 5000 5 0 0 0 0 0 0\n")
    second = m.tick()
    assert abs(second.cpu - 100.0 * (1210 / 1310)) < 0.01
    assert second.net_up > 0 or second.net_down > 0
    assert second.disk_total > 0


def test_tick_fallback_no_fan_no_gpu(tmp_path, monkeypatch):
    proc = tmp_path / "proc"
    sys = tmp_path / "sys"
    make_proc(proc)  # 无 fan、无 gpu 文件

    # 本机装有 nvidia-smi 会读到真实占用；打桩使其失败，验证降级链回退 0.0
    def _fake_run(*args, **kwargs):
        raise OSError("nvidia-smi unavailable")
    monkeypatch.setattr("sidebay.monitor.subprocess.run", _fake_run)

    m = SystemMonitor(proc_root=str(proc), sys_root=str(sys))
    stats = m.tick()
    assert m.fan_simulated
    assert stats.gpu == 0.0
    assert stats.fan_rpm >= 1800 - 50  # 模拟公式下限
    assert stats.fan_rpm <= (1800 + 4200) + 50
