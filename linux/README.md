# Sidebay Linux 版

macOS 版 Sidebay（动态模块化侧边栏）的 Linux 迁移实现：Python 3 + GTK4（PyGObject），
X11 贴边停靠，11 个模块。界面默认中文。

## 系统依赖

| 方式 | 依赖 |
|------|------|
| Flatpak | flatpak ≥ 1.16、flatpak-builder（构建时需要）、GNOME Platform 47 运行时 |
| 直接运行 | Python ≥ 3.10、PyGObject（python3-gi + python3-gi-cairo）、GTK 4.14+（gir1.2-gtk-4.0）、python-xlib（键盘监视模块需要） |

Debian/Ubuntu 直接运行所需包：

```bash
sudo apt install python3 python3-gi python3-gi-cairo gir1.2-gtk-4.0 xvfb   # xvfb 仅用于无显示环境冒烟测试
```

uv 安装指引：https://docs.astral.sh/uv/ （或 `pipx install uv`）。

python-xlib（键盘监视模块需要）由 uv 的 dev 依赖组随 `uv sync` 自动安装。

## 安装

### 方式一：Flatpak（推荐）

```bash
# 1. 首次使用先安装 GNOME Platform 47 运行时（已验证自带 python3 + PyGObject，无需额外模块）
flatpak install -y flathub org.gnome.Platform//47

# 2. 构建并安装（--user 安装到当前用户）
./install.sh

# 3. 运行
flatpak run org.sidebay.SideBay
```

`install.sh` 等价命令：

```bash
flatpak-builder --force-clean --user build org.sidebay.SideBay.json
flatpak-builder --user --install --force-clean build org.sidebay.SideBay.json
```

打包内容：python-xlib 0.33（PyPI sdist，随应用装到 `/app`）与应用本体
（复制到 `/app/lib/sidebay`，启动器 `/app/bin/sidebay` 执行 `python3 -m sidebay`）。
沙盒权限：Wayland + X11 套接字、网络（Stock/Network 模块）、DRI（GPU 渲染）、
可写 `~/.config/autostart`（开机自启开关）。

### 方式二：直接运行（uv）

```bash
cd linux && uv venv --system-site-packages && uv sync
./run.sh          # 等价于 uv run --no-sync sidebay
```

两步创建 venv 的原因：gi 来自系统包，需要 system-site-packages venv；uv 无配置文件键，故两步创建。
（`./run.sh` 首次运行时若 `.venv` 不存在，也会自动执行上述两步。）

## 运行

```bash
flatpak run org.sidebay.SideBay     # Flatpak 方式
./run.sh                            # 直接运行，等价于 uv run --no-sync sidebay
```

无显示环境冒烟验证（X11 后端）：

```bash
GDK_BACKEND=x11 xvfb-run -a ./run.sh   # 退出码 0 且无 traceback
```

开机自启：设置窗口的"开机自启"开关写入 `~/.config/autostart/sidebay.desktop`。
Exec 行自动适配运行方式——Flatpak 下（检测到 `FLATPAK_ID`）写
`flatpak run org.sidebay.SideBay`，直接运行写仓库 `run.sh` 的绝对路径。
配置文件：`~/.config/sidebay/config.json`。

## 测试

```bash
cd linux
uv run pytest                            # 纯 Python 测试，无需显示环境
GDK_BACKEND=x11 xvfb-run -a uv run pytest   # 无显示环境全量测试（含键盘 XRecord 集成测试）
```

覆盖：解析器（CPU/GPU/内存/磁盘）、SystemMonitor 采样、环形仪表纯逻辑、
i18n、Store 持久化、计时器、计算器、股票、键盘格式、模块注册表、自启文件。

## 模块列表（11 个）

| 模块 | 说明 |
|------|------|
| CPU / GPU / Memory / Disk | 系统占用环形仪表（每秒采样） |
| Fan | 风扇转速仪表 |
| Network | 网络速率仪表 |
| Stock | 股票行情（需要网络） |
| Countdown | 倒计时 |
| Stopwatch | 秒表 |
| Calculator | 计算器 |
| Keyboard | 全局键盘监视（X11 XRecord） |

## 已知限制

- **Wayland 无置顶**：贴边停靠与置顶基于 X11（`XMoveResizeWindow` / 置顶窗口属性）。
  Wayland 会话下窗口停留在 GTK 默认放置的位置且不置顶；请在 X11 / XWayland 会话使用
  以获得完整贴边体验。manifest 已同时开放 `--socket=wayland` 与 `--socket=x11`。
- **键盘监视 X11-only**：Keyboard 模块通过 XRecord 捕获全局按键，仅在 X11 下工作，
  且依赖 python-xlib（Flatpak 内已随应用打包到 `/app`）。Wayland 会话或无 `DISPLAY`
  时模块显示"无辅助功能权限"，应用其余功能不受影响。
- **GPU 在 Flatpak 沙盒内回退 0**：沙盒内无法读取 sysfs
  `/sys/class/drm/*/device/gpu_busy_percent`，且没有 `nvidia-smi`，
  GPU 仪表恒为 0。直接运行不受影响。
- **无真实背景模糊**：Linux 版未实现 macOS 版的窗口背景模糊效果，窗口背景为不透明。
- **Screen Record / Mirror / Server 为 V2**：这三个 macOS 模块在 Linux 版尚未实现，
  注册表会静默跳过未接线的模块类型（默认配置中的 "Screen Record" 不会导致崩溃）。
- **GPU 传感器直读**：GPU 占用读取受硬件与驱动限制（amdgpu sysfs / nvidia-smi），
  非 NVIDIA 或旧驱动时同样回退 0。
- **渲染器默认 `cairo`**：应用默认以 `GSK_RENDERER=cairo` 运行（无 GPU 依赖、
  内存策略稳定，实测空闲 RSS ~93MB）。如需 GPU 加速可覆盖：
  `GSK_RENDERER=gl ./run.sh` 或 `flatpak run --env=GSK_RENDERER=gl org.sidebay.SideBay`。

## 位置控制（任意 X/Y 坐标）

默认运行路径（Wayland 会话自动走 XWayland，Xorg 会话原生 X11）下，设置页
「位置 X/Y」**完全生效**（实时移动窗口，含垂直 Y）。注意：Mutter 初始放置
窗口期间（启动后数秒）移动可能被覆盖，应用会在 500ms/2s/5s 自动重试落位。
