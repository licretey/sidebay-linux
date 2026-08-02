"""配色单一来源：各模块颜色统一在此定义。"""

# 环形仪表（CPU/GPU/Memory/Disk）
CPU_COLOR = (0.32, 0.60, 1.00)
GPU_COLOR = (0.60, 0.45, 1.00)
MEMORY_COLOR = (1.00, 0.65, 0.20)
DISK_COLOR = (0.62, 0.48, 0.33)

# 网络上下行
NET_UP_COLOR = (0.20, 0.85, 0.40)
NET_DOWN_COLOR = (0.32, 0.60, 1.00)

# 风扇
FAN_COLOR = (0.20, 0.80, 0.80)

# 股票涨跌（中国市场习惯：涨红跌绿）
STOCK_UP_COLOR = (0.95, 0.30, 0.30)
STOCK_DOWN_COLOR = (0.20, 0.80, 0.40)

# 环形仪表类型 → 颜色
USAGE_COLORS = {
    "CPU": CPU_COLOR,
    "GPU": GPU_COLOR,
    "Memory": MEMORY_COLOR,
    "Disk": DISK_COLOR,
}
