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
