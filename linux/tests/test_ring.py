from math import tau

from sidebay.widgets.ring import ring_arc_end, ring_segment_colors


def test_segment_colors_count_and_order():
    colors = ring_segment_colors((0.2, 0.5, 1.0, 1.0), n=32)
    assert len(colors) == 32
    first, last = colors[0], colors[-1]
    # 第一段最暗（亮度 ~0.4 倍），最后一段为基色
    assert first[0] < last[0] and first[1] < last[1] and first[2] < last[2]
    assert last == (0.2, 0.5, 1.0, 1.0)


def test_segment_colors_n_one():
    assert ring_segment_colors((0.2, 0.5, 1.0, 1.0), n=1) == [(0.2, 0.5, 1.0, 1.0)]


def test_ring_arc_end_zero():
    # 弧终点落在顶部起点（-tau/4）：value=0 时不绘制任何弧段
    assert ring_arc_end(0) == -tau / 4


def test_ring_arc_end_half():
    assert ring_arc_end(50) == tau / 4  # 从顶部起半圆


def test_ring_arc_end_full():
    assert ring_arc_end(100) == 3 * tau / 4  # 从顶部起整圆
