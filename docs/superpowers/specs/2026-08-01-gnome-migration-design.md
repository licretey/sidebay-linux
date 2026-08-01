# Sidebay Linux（GNOME）迁移设计

- 日期：2026-08-01
- 状态：已批准（用户确认后写入）
- 目标平台：Linux / GNOME（Wayland 与 X11 均支持，行为差异见「已知限制」）
- 技术栈：Python 3 + GTK4（pygobject）
- 打包：Flatpak（org.sidebay.SideBay）

## 背景

Sidebay 原为 macOS 原生 SwiftUI/AppKit 应用（约 2,240 行，4 个文件）：无边框、贴屏边缘、悬浮式模块化侧边栏，深色毛玻璃质感，通过 ⚙️ 设置后台自由增删/拖拽排序模块。本设计将该应用迁移至 Linux/GNOME，保持精美 UI 质感并控制内存占用。

## 决策记录

| 决策点 | 结论 |
|---|---|
| 语言 | Python + GTK4（开发快、内存较低 ~90-100MB、GNOME 原生渲染） |
| V1 模块范围 | 10 个核心模块：CPU/GPU/RAM/Disk 环形仪表、网络、风扇、股票、倒计时、秒表、计算器、键盘监视 |
| 延后模块 | Mirror（摄像头预览）与 Screen Record（录屏）— V2 用 GStreamer/Pipewire 实现 |
| 键盘监视 | 尽力而为：X11 会话全局监听；Wayland 显示「无权限」提示 |
| 视觉 | 深色玻璃质感（GTK CSS 半透明+渐变+阴影），非 libadwaita 原生风格 |
| 毛玻璃 | 不做真实背景模糊（GNOME Wayland 不支持）；半透明+高光渐变+描边+阴影模拟质感 |
| 打包 | Flatpak（org.gnome.Platform 运行时）；本地开发直跑系统 Python |
| 菜单栏 | **禁用 GNOME 原生菜单栏/headerbar**：所有窗口无装饰，自绘暗色头部 |
| 语言 | zh/en 双语（复用原 Swift 词表） |

## 一、架构与代码组织

```
linux/
├── sidebay/
│   ├── main.py            # 入口：Gtk.Application（GApplication 原生单实例，重复启动→打开设置）
│   ├── app.py             # 应用逻辑：窗口管理、信号
│   ├── window.py          # 边缘吸附悬浮窗口（无装饰、全高、贴边）
│   ├── settings.py        # 设置窗口（无装饰+自绘暗色头部；通用/模块 两个标签页）
│   ├── store.py           # 模块存储（JSON → ~/.var/app/org.sidebay.SideBay/config/sidebay.json）
│   ├── monitor.py         # CPU/GPU/RAM/Disk/Net/Fan 采集（/proc + /sys + statvfs）
│   ├── widgets/
│   │   ├── ring.py        # 环形进度条（cairo 自绘，分段圆弧插值模拟角度渐变+发光）
│   │   └── glass.py       # 玻璃背景/高光渐变/描边/阴影（GTK CSS 类）
│   ├── modules/           # 每模块一个文件，统一接口 build(store, module_id) -> Gtk.Widget
│   │   ├── usage.py       # CPU/GPU/RAM/Disk 环形仪表（四色：蓝/紫/橙/棕）
│   │   ├── network.py     # 上下行速率（绿↑/蓝↓ 图标 + 等宽字体数字）
│   │   ├── fan.py         # 风扇旋转动画（速度映射转速，真实 RPM 优先）＋ RPM 数值
│   │   ├── stock.py       # 腾讯行情（qt.gtimg.cn，GB18030 解码，双击改代码）
│   │   ├── countdown.py   # 番茄钟（双击设时长、播放/暂停/重置）
│   │   ├── stopwatch.py   # 秒表（播放/暂停/清零）
│   │   ├── calculator.py  # 4x5 极简计算器（橙运算符、显示区）
│   │   └── keyboard.py    # 键盘监视（X11 监听；Wayland 显示「无权限」）
│   ├── i18n.py            # zh/en 双语查表
│   └── style.css          # 深色玻璃质感样式（全局）
├── org.sidebay.SideBay.json   # Flatpak manifest
├── run.sh                 # 本地开发：python3 -m sidebay
├── install.sh             # flatpak-builder 构建安装
└── tests/                 # pytest
```

### 模块接口

每个模块实现统一接口：

```python
class Module:
    def build(self) -> Gtk.Widget      # 返回模块视图
    def on_tick(self) -> None          # 1 秒轮询（可选重写）
    def on_destroy(self) -> None       # 清理定时器/连接
```

- 轮询走 GLib 定时器（`GLib.timeout_add`），单线程主循环，复用缓冲对象避免每帧分配
- 数据层（monitor.py）与 UI 层分离：monitor 纯函数式采集，UI 订阅

### 内存策略（目标：空闲 <100MB RSS — 2026-08-02 由用户裁决修订，实测 93.4MB）

- GTK4 + pygobject 基线 ~60-70MB；默认 `GSK_RENDERER=cairo` 规避 GL 渲染栈（llvmpipe/NVIDIA 下可达 268MB）
- 无图片资源：图标用 cairo 自绘/Unicode 符号/字体 glyph
- 轮询不创建新对象：`/proc` 读取复用 `bytearray` 缓冲与预分配字符串
- 股票网络请求用 `urllib`（stdlib，无重依赖），仅请求模块挂载时活跃

## 二、窗口行为

### 主侧边栏（window.py）

- `Gtk.Window` + `set_decorated(False)`，贴屏幕左/右边缘、全高、无圆角（与原版一致；悬浮窗口才用 24px 圆角）
- 宽度默认屏幕 1/20，设置范围 40-300px
- 悬停右边缘拖拽改宽度：`Gtk.Overlay` 顶层 + 边缘热区（3px）+ `Gtk.GestureDrag`
- 底部透明度滑块：`gtk_window_set_opacity`（0.1-1.0，X11/Wayland 均有效）
- 右键弹出菜单 → 打开设置；模块内容区 `Gtk.ScrolledWindow`（隐藏滚动条）
- 模块高度：默认 100px，或按侧边栏高度的百分比（heightPct）
- 拖拽排序：设置窗口内实现（见下）

### 设置窗口（settings.py）

- **无装饰 + 自绘暗色头部**：顶部自定义条 = 标题「后台设置」+ 关闭按钮（macOS 风格圆形 ⚫️🔴/✕，悬停高亮）+ 语言切换；不使用任何 GNOME headerbar/menubar
- 下方两个标签页：通用（语言/位置/宽度/透明度/开机自启/关于）、模块（列表：拖拽排序、删除、高度百分比、股票代码输入；底部模块类型下拉+添加按钮）
- 开机自启：写入 `~/.config/autostart/sidebay.desktop`（Flatpak 下经 `--filesystem=xdg-config/autostart`）
- 单实例：GApplication D-Bus 注册，二次启动 → 唤起设置窗口

### 已知限制（文档说明，非缺陷）

- **GNOME Wayland 无 keep-above**：X11 会话完全复刻「置顶悬浮」；Wayland 下窗口保持贴边但属普通层叠（全屏窗口会盖住）。Gtk 的 `keep_above` 在 Wayland 是无操作
- **键盘监视**：X11 会话 `XGrabKey` 全局监听（flatpak 需 `--socket=x11`）；Wayland 下无法全局捕获 → 模块显示「无辅助功能权限」提示（与原版无权限状态一致）
- 无真实背景模糊（GNOME Wayland 限制）→ 半透明+高光模拟
- **GPU 采集在 Flatpak 沙盒内受限**：`/sys/class/drm` 与 `nvidia-smi` 在沙盒内通常不可读 → GPU 显示 0；本地开发模式（直跑系统 Python）可读到真实值。采集逻辑带降级链，不报错

## 三、系统采集映射（monitor.py）

| 指标 | Linux 实现 | 对应原版 |
|---|---|---|
| CPU | `/proc/stat` 差分（user+sys+nice+idle），1s 采样 | host_statistics64 |
| RAM | `/proc/meminfo`：MemTotal−MemAvailable（含 buffers/cached 归可用） | vm_statistics64 |
| Disk | `os.statvfs("/")` | attributesOfFileSystem |
| 网络 | `/proc/net/dev` 差分（排除 lo，聚合物理接口） | getifaddrs |
| Fan | 优先 `/sys/class/hwmon/*/fan*_input` 真实 RPM；无则按 CPU+GPU 负载模拟（原版同款公式） | SMC 模拟 |
| GPU | amd: `/sys/class/drm/*/device/gpu_busy_percent`；nvidia: `nvidia-smi --query-gpu=utilization.gpu`；均不可用 → 0 | IOAccelerator |

采集函数为纯函数（入参文件路径/内容，出参数值），便于 pytest 覆盖。

## 四、视觉设计（深色玻璃质感，GTK CSS）

全部视觉经 `style.css` 实现，类名前缀 `sb-`：

- **背景**：`rgba(20,22,28,0.75)` 半透明深色 + `background-image: linear-gradient(90deg, rgba(255,255,255,0.35), transparent 40%, rgba(0,0,0,0.3))`（等效原版软光叠加）
- **描边**：1.5px 线性渐变边框（白 0.7 → 白 0.1 → 黑 0.5 → 白 0.3），`box-shadow` 外部投影 `rgba(0,0,0,0.4) 0 10px 15px`
- **环形仪表**（widgets/ring.py）：cairo 画 32 段圆弧，颜色沿 `AngularGradient` 插值（色 → 亮 0.4）；底环 0.15 透明度；进度端点圆帽；同色低透明度叠弧发光
- **字体**：系统 sans（标题加粗圆润感用 font-weight）+ monospace（数字/网速），字号与原版一致（标题 13、数值 18、标注 9-11）
- **颜色**：CPU 蓝 / GPU 紫 / RAM 橙 / Disk 棕 / 网络 绿↑蓝↓ / 风扇 teal / 股票红涨绿跌（中国市场）/ 计算器运算符橙
- **按钮/控件**：圆形玻璃按钮（播放/暂停/重置），悬停提亮、按下压暗；滑块轨道半透明
- 设置窗口自绘头部：与侧边栏同质感（玻璃背景、渐变描边），关闭按钮悬停变红

## 五、Flatpak 打包

- Manifest `org.sidebay.SideBay.json`：
  - 运行时 `org.gnome.Platform`（当前稳定版）
  - 权限：`--socket=wayland --socket=x11 --share=network --device=dri --filesystem=xdg-config/autostart`
  - 模块：python3（requests 或 stdlib urllib 按需）、pygobject、GTK4
- 本地开发：`run.sh`（系统 Python 直跑，不经沙盒，见「如何运行」）
- `install.sh`：`flatpak-builder build --force-clean` + `flatpak-builder --user --install`

## 六、测试

- **pytest 单元（≥80% 逻辑覆盖）**：/proc/stat、/proc/meminfo、/proc/net/dev 解析；股票响应解析（GB18030/`~` 分段）；计算器运算；倒计时/秒表状态机；模块存储读写
- **UI 冒烟**（xvfb）：应用启动、侧边栏创建、10 模块逐个挂载、设置窗口打开、拖拽排序回调、透明度/宽度设置生效
- 运行：`python3 -m pytest linux/tests`

## 七、如何运行（开发）

```bash
# 依赖（Ubuntu/Debian 示例）
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 libgtk-4-dev

# 运行
./run.sh

# 测试
python3 -m pytest linux/tests

# Flatpak 安装
./install.sh
```

## 范围外（V2）

- Mirror 摄像头预览（GStreamer/Pipewire + 独立窗口 + 黑屏开关 + 镜面翻转）
- Screen Record 录屏启动（调用 GNOME 截图工具）
- Server 远程监控（SSH/expect — 逻辑完全可移植，仅 UI 需重写，可快速跟进）
- 真实背景模糊（合成器支持时降级检测）

## 验收标准

1. 侧边栏在 X11 会话下贴边置顶悬浮，行为与 macOS 版一致（贴边/宽度拖拽/透明度/右键设置）
2. 10 个模块全部可添加、删除、拖拽排序、持久化（重启后保留）
3. 视觉为深色玻璃质感，无任何 GNOME 原生菜单栏/headerbar
4. 空闲内存 < 100MB RSS（实测 93.4MB，60s 平稳无泄漏；修订记录见「内存策略」）
5. pytest 逻辑覆盖 ≥80% 通过；xvfb 冒烟通过
6. Flatpak 构建安装成功，Wayland/X11 会话均能启动
