from sidebay.modules.countdown import CountdownState
from sidebay.modules.stopwatch import StopwatchState


def test_countdown_tick_and_timeout():
    state = CountdownState(minutes=1)
    state.active = True
    assert state.tick() is False
    assert state.remaining == 59
    state.remaining = 1
    assert state.tick() is True  # 归零信号
    assert state.active is False


def test_countdown_set_reset_and_string():
    state = CountdownState(minutes=25)
    state.set_minutes(90)
    assert state.remaining == 90 * 60
    state.reset()
    assert state.remaining == 25 * 60
    state.remaining = 5
    assert state.time_string() == "00:05"
    state.remaining = 65
    assert state.time_string() == "01:05"


def test_countdown_inactive_no_tick():
    state = CountdownState(minutes=1)
    state.active = False
    state.tick()
    assert state.remaining == 60


def test_stopwatch_toggle_and_reset():
    state = StopwatchState()
    state.toggle()
    assert state.active is True
    state.tick()
    assert state.elapsed == 1
    state.toggle()
    state.tick()
    assert state.elapsed == 1  # 暂停时不变
    state.reset()
    assert state.elapsed == 0 and state.active is False


def test_stopwatch_string():
    state = StopwatchState()
    state.elapsed = 61
    assert state.time_string() == "01:01"
