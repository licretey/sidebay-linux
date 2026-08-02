# Sidebay Linux uv 工程管理转换 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `linux/` 的环境/依赖/测试/运行入口统一转为 uv 管理（pyproject.toml + uv sync + uv run），消除手工 .pth 桥接，应用源码零改动。

**Architecture:** `pyproject.toml` 声明项目与 dev 依赖组；`[tool.uv] python-preference = "system"` + `python-system-site-packages = true` 让 venv 基于系统 Python 3.14 并继承系统 gi 包；`[project.scripts]` 提供 `sidebay` 命令；`run.sh` 委托 `uv run --no-sync sidebay`。

**Tech Stack:** uv 0.11.7、Python 3.14（系统）、PyGObject（系统）、pytest 9、python-xlib 0.33

**Spec:** `docs/superpowers/specs/2026-08-02-uv-project-management-design.md`

## Global Constraints

- 全部变更在 `linux/`；**`sidebay/` 源码零改动**；`SideBarApp/`（macOS 原版）不动
- `pyproject.toml` 内容以 spec 为准（含 `python-preference = "system"`、`python-system-site-packages = true`、dev 依赖组、console script）
- `uv.lock` 提交；`.venv/` 继续 gitignore
- `org.sidebay.SideBay.json`（flatpak manifest）不改
- 测试必须保持 72 passed；xvfb 冒烟命令 `GDK_BACKEND=x11 xvfb-run -a` 前缀不变
- venv 内必须能 `import gi`、`from gi.repository import Gtk`、`import gi._gi_cairo`（无 .pth hack）

---

### Task 1: pyproject.toml 与 uv sync 环境重建

**Files:**
- Create: `linux/pyproject.toml`
- Create: `linux/uv.lock`（由 `uv sync` 生成）
- Modify: `linux/.gitignore`（确认 `.venv/` 与 `build/` 已忽略，无需改动——仅验证）

**Interfaces:**
- Consumes: 现有 `linux/` 目录结构（sidebay/ 包、tests/、pytest.ini）
- Produces: uv 管理的 venv（基于系统 Python 3.14，含系统 site-packages + pytest + python-xlib）；`uv sync` 可复现的环境

- [ ] **Step 1: 编写 pyproject.toml**

`linux/pyproject.toml`（逐字使用 spec 中的内容）：

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
python-system-site-packages = true
```

- [ ] **Step 2: 删除旧 venv 并 uv sync**

Run:
```bash
cd /home/de/d/code/my-make/sidebay/linux && rm -rf .venv && uv sync
```
Expected: uv 解析依赖、创建基于系统 Python 3.14 的 `.venv`、安装 pytest + python-xlib、生成 `uv.lock`。**必须无报错**；若 uv 提示找不到系统 Python 或要求下载 Python，检查 `python-preference` 配置是否生效（`uv sync --verbose` 可诊断）。

- [ ] **Step 3: 验证桥接（无 .pth hack）**

Run:
```bash
cd /home/de/d/code/my-make/sidebay/linux && ls .venv/lib/python3.14/site-packages/*.pth
```
Expected: **没有** `system_dist.pth`（手工桥接已消除——系统 site-packages 由 uv 的 `python-system-site-packages` 原生提供）。

Run:
```bash
cd /home/de/d/code/my-make/sidebay/linux && .venv/bin/python -c "import gi; gi.require_version('Gtk','4.0'); from gi.repository import Gtk; import gi._gi_cairo; print('gi bridge OK', Gtk.get_major_version())"
```
Expected: `gi bridge OK 4`（gi 与 gi._gi_cairo 均可用）。

- [ ] **Step 4: 验证测试基础设施**

Run:
```bash
cd /home/de/d/code/my-make/sidebay/linux && uv run pytest tests/test_i18n.py tests/test_store.py -q
```
Expected: 通过（uv run 正确解析 dev 组依赖与项目本身）。

- [ ] **Step 5: 提交**

```bash
cd /home/de/d/code/my-make/sidebay && git add linux/pyproject.toml linux/uv.lock && git commit -m "build(linux): manage project with uv (pyproject + lockfile)"
```
（确认 `.venv/` 与 `build/` 未被暂存：`git status --short` 应只显示这两个文件。）

---

### Task 2: run.sh 与 README 更新 + 全量验证

**Files:**
- Modify: `linux/run.sh`
- Modify: `linux/README.md`（安装/运行/测试段落）

**Interfaces:**
- Consumes: Task 1 的 venv（`uv run sidebay` 可用）
- Produces: `./run.sh` = `uv run --no-sync sidebay`；README 反映 uv 工作流

- [ ] **Step 1: 更新 run.sh**

`linux/run.sh` 全文替换为：

```bash
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
exec uv run --no-sync sidebay "$@"
```

保留可执行位（提交时确认 `git ls-files -s linux/run.sh` 为 100755；必要时 `git update-index --chmod=+x`）。

- [ ] **Step 2: 更新 README 的运行/测试段落**

`linux/README.md` 中：
- 「环境准备」改为 uv 流程：`sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 xvfb` + `cd linux && uv sync`
- 「运行」改为 `./run.sh`（说明 = `uv run --no-sync sidebay`）；flatpak 段落保留不变
- 「测试」改为 `uv run pytest` / `GDK_BACKEND=x11 xvfb-run -a uv run pytest`
- 保留已知限制、模块列表、GSK_RENDERER 说明等既有内容

- [ ] **Step 3: 全量测试**

Run:
```bash
cd /home/de/d/code/my-make/sidebay/linux && GDK_BACKEND=x11 xvfb-run -a uv run pytest
```
Expected: **72 passed**（与转换前一致；键盘 XRecord 集成测试包含在内）。

- [ ] **Step 4: 启动验证**

Run:
```bash
cd /home/de/d/code/my-make/sidebay/linux && timeout 8 bash -c 'GDK_BACKEND=x11 xvfb-run -a ./run.sh 2>&1 | head -5'; echo "rc=$?"
```
Expected: 无 traceback（`rc=124` 表示被 timeout 终止 = 应用正常运行）；`uv run sidebay` 与 `./run.sh` 一致（可再跑一次 `uv run --no-sync sidebay` 对照）。

- [ ] **Step 5: 提交**

```bash
cd /home/de/d/code/my-make/sidebay && git add linux/run.sh linux/README.md && git commit -m "build(linux): run and document via uv"
```

---

## Self-Review 记录

**Spec 覆盖核对：**
- pyproject.toml 内容逐字 → Task 1 Step 1 ✓
- uv.lock 提交 → Task 1 Step 5 ✓
- run.sh = uv run --no-sync sidebay → Task 2 Step 1 ✓
- README uv 命令 → Task 2 Step 2 ✓
- 验证标准 1-5（venv 重建/gi 桥接/72 测试/启动无 traceback/命令一致）→ Task 1 Step 2-4 + Task 2 Step 3-4 ✓
- flatpak 不变、源码零改动 → Global Constraints ✓

**类型/接口一致性：** `sidebay.main:main` 存在（返回 int，console script 兼容）✓；`uv run` 在 0.11.7 支持 `--no-sync` ✓；`python-system-site-packages` 与 `python-preference` 为 0.11.7 有效键 ✓。

**占位符检查：** 无 TBD/TODO；所有命令含预期输出 ✓
