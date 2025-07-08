import ctypes
import os
import sys
import importlib
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.modules.pop("pypicosdk", None)
from pypicosdk import ps6000a, PICO_TRIGGER_INFO, PICO_TIME_UNIT


def test_get_trigger_info_single(monkeypatch):
    scope = ps6000a("pytest")

    def fake_call(name, handle, info_ptr, first_index, count):
        arr = ctypes.cast(info_ptr, ctypes.POINTER(PICO_TRIGGER_INFO))
        arr[0].status_ = 0
        arr[0].segmentIndex_ = first_index
        arr[0].triggerIndex_ = 5
        arr[0].triggerTime_ = 1.0
        arr[0].timeUnits_ = PICO_TIME_UNIT.NS
        arr[0].missedTriggers_ = 0
        arr[0].timeStampCounter_ = 10
        return 0

    monkeypatch.setattr(scope, "_call_attr_function", fake_call)
    info = scope.get_trigger_info()
    assert isinstance(info, PICO_TRIGGER_INFO)
    assert info.segmentIndex_ == 0


def test_get_trigger_info_multiple(monkeypatch):
    scope = ps6000a("pytest")

    def fake_call(name, handle, info_ptr, first_index, count):
        n = count if isinstance(count, int) else count.value
        start = first_index if isinstance(first_index, int) else first_index.value
        arr_type = PICO_TRIGGER_INFO * n
        arr = ctypes.cast(info_ptr, ctypes.POINTER(arr_type)).contents
        for i in range(n):
            arr[i].segmentIndex_ = start + i
            arr[i].timeUnits_ = PICO_TIME_UNIT.NS
        return 0

    monkeypatch.setattr(scope, "_call_attr_function", fake_call)
    infos = scope.get_trigger_info(1, 3)
    assert [i.segmentIndex_ for i in infos] == [1, 2, 3]


def test_get_values_trigger_time_offset_bulk(monkeypatch):
    scope = ps6000a("pytest")

    def fake_call(name, handle, times_ptr, units_ptr, from_idx, to_idx):
        start = from_idx if isinstance(from_idx, int) else from_idx.value
        end = to_idx if isinstance(to_idx, int) else to_idx.value
        n = end - start + 1
        times = ctypes.cast(times_ptr, ctypes.POINTER(ctypes.c_int64))
        units = ctypes.cast(units_ptr, ctypes.POINTER(ctypes.c_int32))
        for i in range(n):
            times[i] = i
            units[i] = PICO_TIME_UNIT.NS
        return 0

    monkeypatch.setattr(scope, "_call_attr_function", fake_call)
    offsets = scope.get_values_trigger_time_offset_bulk(0, 2)
    assert offsets == [
        (0, PICO_TIME_UNIT.NS),
        (1, PICO_TIME_UNIT.NS),
        (2, PICO_TIME_UNIT.NS),
    ]

