import ctypes
from pypicosdk import ps6000a, CHANNEL, RANGE


def test_set_no_of_captures_invocation():
    scope = ps6000a('pytest')
    called = {}

    def fake_call(name, *args):
        called['name'] = name
        called['args'] = args
        return 0

    scope._call_attr_function = fake_call
    scope.set_no_of_captures(4)
    assert called['name'] == 'SetNoOfCaptures'


def test_get_no_of_captures_invocation():
    scope = ps6000a('pytest')
    called = {}

    def fake_call(name, *args):
        called['name'] = name
        called['args'] = args
        return 0

    scope._call_attr_function = fake_call
    scope.get_no_of_captures()
    assert called['name'] == 'GetNoOfCaptures'


def test_get_values_bulk_invocation():
    scope = ps6000a('pytest')
    called = {}

    def fake_call(name, *args):
        called['name'] = name
        called['args'] = args
        return 0

    scope._call_attr_function = fake_call
    scope.is_ready = lambda: None
    overflow = ctypes.c_int16()
    scope.get_values_bulk(0, 10, 0, 1, 1, 0, overflow)
    assert called['name'] == 'GetValuesBulk'


def test_get_values_bulk_async_invocation():
    scope = ps6000a('pytest')
    called = {}

    def fake_call(name, *args):
        called['name'] = name
        called['args'] = args
        return 0

    scope._call_attr_function = fake_call
    scope.get_values_bulk_async(0, 10, 0, 1, 1, 0, None, None)
    assert called['name'] == 'GetValuesBulkAsync'


def test_get_values_overlapped_invocation():
    scope = ps6000a('pytest')
    called = {}

    def fake_call(name, *args):
        called['name'] = name
        called['args'] = args
        return 0

    scope._call_attr_function = fake_call
    scope.is_ready = lambda: None
    overflow = ctypes.c_int16()
    scope.get_values_overlapped(0, 10, 1, 0, 0, 1, overflow)
    assert called['name'] == 'GetValuesOverlapped'


def test_stop_using_get_values_overlapped_invocation():
    scope = ps6000a('pytest')
    called = {}

    def fake_call(name, *args):
        called['name'] = name
        called['args'] = args
        return 0

    scope._call_attr_function = fake_call
    scope.stop_using_get_values_overlapped()
    assert called['name'] == 'StopUsingGetValuesOverlapped'


def test_run_simple_rapid_block_capture_invocation():
    scope = ps6000a('pytest')
    calls = []

    def fake_call(name, *args):
        calls.append(name)
        return 0

    scope._call_attr_function = fake_call
    scope.is_ready = lambda: None
    scope.range = {CHANNEL.A: RANGE.V1}
    scope.max_adc_value = 32767
    scope.get_time_axis = lambda *args, **kwargs: []
    scope.run_simple_rapid_block_capture(2, 10, 3)
    assert 'MemorySegments' in calls
    assert 'SetNoOfCaptures' in calls
    assert 'RunBlock' in calls
    assert 'GetValuesBulk' in calls
