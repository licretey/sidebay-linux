import pytest

from sidebay.modules.registry import MODULE_TYPES, create_module


def test_module_types_order():
    assert MODULE_TYPES == ["CPU", "GPU", "Memory", "Disk", "Fan", "Network",
                            "Stock", "Countdown", "Stopwatch", "Calculator", "Keyboard"]


def test_usage_kinds_map_to_one_class():
    from sidebay.modules.usage import UsageModule

    for kind in ("CPU", "GPU", "Memory", "Disk"):
        assert UsageModule.KINDS[kind] is not None


@pytest.mark.smoke
def test_create_usage_module_builds(tmp_path):
    from sidebay.store import Store

    store = Store(path=str(tmp_path / "c.json"))
    module = create_module("CPU", store, store.modules[0].module_id, monitor=None)
    widget = module.build()
    assert widget is not None
    widget.run_dispose()  # GTK 4.22 已移除 gtk_widget_destroy，用 run_dispose 触发 destroy 信号
