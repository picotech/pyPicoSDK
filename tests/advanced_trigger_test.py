import ctypes
from pypicosdk import (
    ps6000a,
    CHANNEL,
    RANGE,
    TRIGGER_STATE,
    THRESHOLD_DIRECTION,
    THRESHOLD_MODE,
    TRIGGER_CHANNEL_PROPERTIES,
    DIRECTION,
    CONDITION,
)


def test_set_trigger_channel_properties(monkeypatch):
    scope = ps6000a("pytest")
    scope.range = {CHANNEL.A: RANGE.V1}
    scope.max_adc_value = 32000

    captured = {}

    def fake_call(name, handle, props, n_props, aux, auto_us):
        captured["name"] = name
        arr = ctypes.cast(props, ctypes.POINTER(TRIGGER_CHANNEL_PROPERTIES))
        captured["upper"] = arr.contents.thresholdUpper_
        captured["channel"] = arr.contents.channel_
        captured["auto"] = auto_us
        return 0

    monkeypatch.setattr(scope, "_call_attr_function", fake_call)
    scope.set_trigger_channel_properties([
        {
            "channel": CHANNEL.A,
            "threshold_upper": 500.0,
            "threshold_lower": -500.0,
            "threshold_upper_hysteresis": 0.0,
            "threshold_lower_hysteresis": 0.0,
        }
    ], auto_trigger_ms=1)

    assert captured["name"] == "SetTriggerChannelProperties"
    assert captured["channel"] == CHANNEL.A
    assert captured["auto"] == 1000
    assert captured["upper"] == scope.mv_to_adc(500.0, RANGE.V1)


def test_set_trigger_channel_directions(monkeypatch):
    scope = ps6000a("pytest")
    captured = {}

    def fake_call(name, handle, dirs, n_dirs):
        captured["name"] = name
        arr = ctypes.cast(dirs, ctypes.POINTER(DIRECTION))
        captured["direction"] = arr.contents.direction_
        captured["mode"] = arr.contents.thresholdMode_
        return 0

    monkeypatch.setattr(scope, "_call_attr_function", fake_call)
    scope.set_trigger_channel_directions({CHANNEL.A: (THRESHOLD_DIRECTION.RISING, THRESHOLD_MODE.LEVEL)})

    assert captured["name"] == "SetTriggerChannelDirections"
    assert captured["direction"] == THRESHOLD_DIRECTION.RISING
    assert captured["mode"] == THRESHOLD_MODE.LEVEL


def test_set_trigger_channel_conditions(monkeypatch):
    scope = ps6000a("pytest")
    captured = {}

    def fake_call(name, handle, conds, n_conds, action):
        captured["name"] = name
        arr = ctypes.cast(conds, ctypes.POINTER(CONDITION))
        captured["state"] = arr.contents.condition_
        return 0

    monkeypatch.setattr(scope, "_call_attr_function", fake_call)
    scope.set_trigger_channel_conditions({CHANNEL.A: TRIGGER_STATE.TRUE})

    assert captured["name"] == "SetTriggerChannelConditions"
    assert captured["state"] == TRIGGER_STATE.TRUE


def test_set_advanced_trigger(monkeypatch):
    scope = ps6000a("pytest")
    called = {"prop": False, "dir": False, "cond": False}

    monkeypatch.setattr(scope, "set_trigger_channel_properties", lambda *a, **k: called.__setitem__("prop", True))
    monkeypatch.setattr(scope, "set_trigger_channel_directions", lambda *a, **k: called.__setitem__("dir", True))
    monkeypatch.setattr(scope, "set_trigger_channel_conditions", lambda *a, **k: called.__setitem__("cond", True))

    scope.set_advanced_trigger([], {}, {})
    assert all(called.values())
