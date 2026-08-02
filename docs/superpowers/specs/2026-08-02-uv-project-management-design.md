# Sidebay Linux 工程管理迁移至 uv

- 日期：2026-08-02
- 状态：已批准（用户确认设计）
- 范围：`linux/` 目录（原 macOS 代码不动）

## 背景

Sidebay Linux 版（Python + GTK4，11 模块，72 测试）当前环境管理为手工方式：`uv venv --system-site-packages` 创建 venv 后，再手工写入 `system_dist.pth` 桥接系统 `/usr/lib/python3/dist-packages`（以获取 `gi`/`gi._gi_cairo`），pytest 与 python-xlib 用 `uv pip` 装入。目标：转为标准 uv 工程管理，`pyproject.toml` 成为唯一声明源，`uv sync` 一键重建。

## 决策记录

| 决策点 | 结论 |
|---|---|
| 运行时入口 | `run.sh` 改用 `uv run --no-sync sidebay`（用户选择；接受 ~100-300ms 启动开销） |
| gi 来源 | 系统包（`python3-gi`/`python3-gi-cairo`，apt 安装）——`[tool.uv] python-system-site-packages = true` 桥接，替代 .pth hack |
| venv 基 Python | 系统 Python 3.14——`python-preference = "system"`（uv 自带 Python 无系统 gi） |
| system-site-packages | **实现修订（2026-08-02）**：uv 0.11.7 无 `python-system-site-packages` 配置键（astral-sh/uv#5737 未落地），改为两步创建：`uv venv --system-site-packages && uv sync`（flag 存于 pyvenv.cfg，sync 保留）；`run.sh` 守卫校验该 flag，缺失自动重建 |
| 打包 | **实现修订**：`[tool.uv] package = true`——否则 uv 按 virtual 工程处理，`sidebay` console script 不安装，`uv run sidebay` 失败 |
| uv.lock | 提交（应用可复现性） |
| Flatpak | 不变（沙盒内 pip 构建，不依赖 uv） |

## 一、文件变更

```
linux/
├── pyproject.toml      # 新增：项目元数据 + dev 依赖组 + [tool.uv] 配置 + console script
├── uv.lock             # 新增：提交
├── run.sh              # 修改：exec uv run --no-sync sidebay "$@"
├── README.md           # 修改：安装/运行/测试段改为 uv 命令
└── .venv/              # 删除后由 uv sync 重建（gitignore 已有 .venv/）
```

`pyproject.toml` 内容：

```toml
[project]
name = "sidebay"
version = "1.0.0"
description = "Dynamic modular sidebar for Linux (GNOME)"
requires-python = ">=3.10"
dependencies = []

[project.scripts]
sidebay = "sidebay.main:main"

[dependency-groups]
dev = [
    "pytest>=9",
    "python-xlib>=0.33",
]

[tool.uv]
python-preference = "system"
package = true  # 实现修订：确保 console script 安装（否则 uv 按 virtual 处理）
```

（实现修订：`python-system-site-packages` 键在 uv 0.11.7 不存在，system-site-packages 由 `uv venv --system-site-packages` 两步创建提供。）

## 二、命令约定

| 操作 | 命令 |
|---|---|
| 重建环境 | `cd linux && uv venv --system-site-packages && uv sync`（两步；`./run.sh` 首次运行自动执行） |
| 运行应用 | `./run.sh`（= `uv run --no-sync sidebay`） |
| 纯测试 | `uv run pytest` |
| xvfb 冒烟 | `GDK_BACKEND=x11 xvfb-run -a uv run pytest` |

## 三、验证标准

1. 删除旧 `.venv` 后 `uv sync` 成功，venv 基于系统 Python 3.14
2. venv 内 `import gi; from gi.repository import Gtk` 与 `import gi._gi_cairo` 均可导入（无 .pth hack）
3. `uv run pytest` 72 测试全绿
4. `GDK_BACKEND=x11 xvfb-run -a ./run.sh` 启动无 traceback（含 `import sidebay` 经 console script 正常）
5. `uv run sidebay` 与 `./run.sh` 行为一致
6. flatpak manifest/构建不受影响（README 中 flatpak 段落保留）

## 范围外

- 不改为 pip 安装 pygobject（系统包方案已验证可行）
- 不改动任何应用源码（sidebay/ 内代码零改动）
- 不动 macOS 原版目录
