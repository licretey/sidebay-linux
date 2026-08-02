# Sidebay Linux v0.2 重构计划

- 日期：2026-08-02
- 作者：架构师审视角
- 目标：**功能不变的前提下**——精简复用实现、降低内存（本地 ≤80MB、flatpak ≤130MB）、降低 CPU 占用

## 0. 现状基线（实测）

| 环境 | RSS | 说明 |
|---|---|---|
| 本地运行（./run.sh） | **91MB** | 已达标（<100MB）；Python+GTK4+GL 基线 |
| Flatpak 运行 | **144MB** | 沙盒固有开销 ~50MB（bwrap/运行时库独立映射）+ 应用 ~90MB |
| 渲染器 | GL/ngl 均 ~188MB 的误解已澄清（此前误测为 flatpak 实例） | cairo 渲染器在 GTK 4.16+ 已移除，无回退空间 |

CPU 热点：fan 模块 30ms 重绘（~33fps 全窗口重绘）；5 个独立 GLib timer；stock 每 10s 起线程。

## 1. 性能与内存优化（P0）

### P0-1 轮询架构统一：模块独立 timer → 窗口 tick 调度

现状：countdown(1s)、stopwatch(1s)、stock(10s)、fan(30ms 动画)、keyboard(1500ms 清理) 各持 GLib timer。
- `countdown/stopwatch`：UI 更新频率 1s 与窗口 tick 相同 → 删除自建 timer，改用 `on_tick()`（窗口 tick 已按 `refresh_interval` 节流，1s 默认）。
- `stock`：10s 轮询并入 `should_update` 节流（refresh_interval=10s）；**取数线程改为 GLib.timeout 单发**（请求完成后再排下一次，避免线程堆积）。
- `keyboard` 的 1500ms 清理保留（独立短时 timer 合理）。
- `fan` 动画：30ms → **100ms**（10fps 旋转视觉等效，CPU 降 70%）；动画 timer 保留（动画需独立于数据 tick）。

收益：进程内 timer 从 5 → 2（窗口 tick + fan 动画）；线程创建归零（stock）；CPU 显著下降。

### P0-2 每 tick 分配优化

- `SystemMonitor.tick()` 每 1s 新建 `Stats` 对象 → **复用单个 Stats 实例**（字段就地更新），消除 GC 压力。
- `ring_segment_colors`：颜色不变时每帧重算 32 色 → **按 (color, n) 缓存**（LRU 或简单 dict），重绘时直接取。
- 模块 `on_tick` 字符串格式化（`f"{value:.0f}%"` 等）：保持，仅当值变化才 `set_text`（当前每次调用都 set_text → 触发布局/重绘）——**值未变时跳过**。

### P0-3 渲染与显示

- 窗口内容已最小（88x716 单滚动区）。GL/ngl 无内存差（实测），维持默认。
- 确认 `GSK_RENDERER=cairo` 相关注释/文档更新（不再有效，避免误导）。

## 2. 代码精简与复用（P1）

### P1-1 模块公共 UI 提取（base.py）

重复模式：6+ 模块各自构建 `标题 Gtk.Label(sb-module-title)` 与数值标签。
- `base.py` 增加 `make_title(text)` / `make_value_label()` 静态方法，模块统一调用。
- 颜色表集中：usage 的 COLORS、network 的 UP/DOWN、fan teal、stock 红绿 → `sidebay/theme.py` 单一来源。

### P1-2 文件拆分（保持行为不变）

- `window.py`（384 行）→ 拆出：
  - `sidebay/positioning.py`：`_x11_dock`、`_set_x11_window_type`、`apply_position_xy`、`_apply_width/position/opacity`（定位与窗口类型逻辑）
  - `sidebay/gestures.py`：长按、右键菜单、边缘拖宽
  - `window.py` 保留：窗口组装、模块重建、tick 调度
- `settings.py`（420 行）→ 拆出 `settings_controls.py`（通用页控件构建 + 处理器）；模块页保留在 settings.py。
- `monitor.py`（228 行）→ 已较清晰；仅 P0-2 复用优化。

### P1-3 死代码与一致性清理

- `style.css` 未使用类（sb-rounded 等）清理。
- i18n 词表精简（保留全部键，删除未引用——谨慎，V2 模块键保留）。
- `tray.py` 的 debug 残留确认无。

## 3. 内存目标与验证（P2）

| 指标 | 当前 | 目标 |
|---|---|---|
| 本地 RSS | 91MB | **≤80MB** |
| Flatpak RSS | 144MB | **≤130MB** |
| 进程 timer 数 | 5+1 | 2+1 |
| tick 期间新对象 | Stats+颜色数组每帧 | 复用/缓存 |
| pytest | 81 | ≥81 全绿 |

验证方式：
- 新增 `scripts/measure-memory.sh`：启动 → 15s → 读 /proc/PID/status VmRSS（本地与 flatpak 分别测量，输出基线）。
- 新增性能冒烟：连续 60 次 `monitor.tick()` 计时（<10ms 总量）与 fan 重绘间隔断言。
- 每阶段跑全量 pytest + 手动托盘/定位/样式回归。

## 4. 分阶段执行

| 阶段 | 内容 | 验收 |
|---|---|---|
| S1 | P0-1（timer 统一）+ P0-3 | 81 测试绿；CPU 下降可测 |
| S2 | P0-2（复用 Stats/颜色缓存/值变跳过） | 内存 -5~10MB |
| S3 | P1-1 公共 helper + theme.py | 代码 -100 行左右 |
| S4 | P1-2 文件拆分 | 结构清晰，行为不变 |
| S5 | P2 测量脚本 + 回归 | 本地 ≤80MB、flatpak ≤130MB |
| S6 | v0.2 发布（tag + README） | 发布物完整 |

## 5. 风险

- timer 统一改动的模块行为回归 → 每阶段全量 pytest + 手动验证。
- flatpak 沙盒开销不可压缩部分（~50MB）为平台固有，目标 130MB 已含余量。
- cairo 渲染器不可用（GTK 4.16+）——渲染器层面无优化空间，接受 GL 基线。
