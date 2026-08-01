from sidebay.widgets.ring import ring_segment_colors


def test_segment_colors_count_and_order():
    colors = ring_segment_colors((0.2, 0.5, 1.0, 1.0), n=32)
    assert len(colors) == 32
    first, last = colors[0], colors[-1]
    # 第一段最暗（亮度 ~0.4 倍），最后一段为基色
    assert first[0] < last[0] and first[1] < last[1] and first[2] < last[2]
    assert last == (0.2, 0.5, 1.0, 1.0)


def test_segment_colors_n_one():
    assert ring_segment_colors((0.2, 0.5, 1.0, 1.0), n=1) == [(0.2, 0.5, 1.0, 1.0)]
