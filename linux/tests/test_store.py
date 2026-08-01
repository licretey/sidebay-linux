import json
import uuid

import pytest

from sidebay.store import AppModule, Settings, Store


@pytest.fixture
def store(tmp_path):
    return Store(path=str(tmp_path / "config.json"))


def test_default_modules_on_fresh_store(store):
    assert [m.type for m in store.modules] == Store.DEFAULT_TYPES


def test_add_and_persist(store, tmp_path):
    store.add("Calculator")
    store.save()
    raw = json.loads((tmp_path / "config.json").read_text())
    assert raw["modules"][-1]["type"] == "Calculator"


def test_roundtrip(tmp_path):
    path = str(tmp_path / "config.json")
    s1 = Store(path=path)
    s1.add("Calculator", custom_data="x")
    s1.settings.position = "right"
    s1.settings.width = 120.0
    s1.save()
    s2 = Store(path=path)
    s2.load()
    assert s2.modules[-1].type == "Calculator"
    assert s2.modules[-1].custom_data == "x"
    assert s2.settings.position == "right"
    assert s2.settings.width == 120.0


def test_move(store):
    store.move(0, 2)
    assert store.modules[2].type == "CPU"
    assert store.modules[0].type == "GPU"


def test_remove_and_set_custom_data(store):
    mid = store.modules[0].module_id
    store.remove(mid)
    assert all(m.module_id != mid for m in store.modules)
    store.set_custom_data(store.modules[0].module_id, "sh000001")
    assert store.modules[0].custom_data == "sh000001"


def test_set_height_pct(store):
    mid = store.modules[0].module_id
    store.set_height_pct(mid, 50.0)
    assert store.modules[0].height_pct == 50.0
    store.set_height_pct(mid, None)
    assert store.modules[0].height_pct is None


def test_corrupt_file_recovers_to_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json")
    s = Store(path=str(path))
    s.load()
    assert [m.type for m in s.modules] == Store.DEFAULT_TYPES
