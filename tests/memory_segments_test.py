import ctypes
from pypicosdk import ps6000a, RESOLUTION


def test_memory_segments(monkeypatch):
    scope = ps6000a("pytest")
    scope.resolution = RESOLUTION._8BIT

    def fake_call(name, *args):
        ptr = ctypes.cast(args[2], ctypes.POINTER(ctypes.c_uint64))
        ptr.contents.value = 123
        return 0

    monkeypatch.setattr(scope, "_call_attr_function", fake_call)
    assert scope.memory_segments(10) == 123


def test_memory_segments_by_samples(monkeypatch):
    scope = ps6000a("pytest")
    scope.resolution = RESOLUTION._8BIT

    def fake_call(name, *args):
        ptr = ctypes.cast(args[2], ctypes.POINTER(ctypes.c_uint64))
        ptr.contents.value = 5
        return 0

    monkeypatch.setattr(scope, "_call_attr_function", fake_call)
    assert scope.memory_segments_by_samples(1000) == 5


def test_query_max_segments_by_samples(monkeypatch):
    scope = ps6000a("pytest")
    scope.resolution = RESOLUTION._8BIT

    def fake_call(name, *args):
        ptr = ctypes.cast(args[3], ctypes.POINTER(ctypes.c_uint64))
        ptr.contents.value = 8
        return 0

    monkeypatch.setattr(scope, "_call_attr_function", fake_call)
    assert scope.query_max_segments_by_samples(1000, 2) == 8
