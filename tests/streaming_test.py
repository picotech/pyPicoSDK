from pypicosdk import ps6000a, PICO_TIME_UNIT, RATIO_MODE, DATA_TYPE, PICO_STREAMING_DATA_INFO, PICO_STREAMING_DATA_TRIGGER_INFO

def test_run_streaming_invocation():
    scope = ps6000a('pytest')
    called = {}
    def fake_call(name, *args):
        called['name'] = name
        called['args'] = args
        return 0
    scope._call_attr_function = fake_call
    scope.run_streaming(1.0, PICO_TIME_UNIT.US, 0, 100, 1, 1, RATIO_MODE.RAW)
    assert called['name'] == 'RunStreaming'


def test_get_streaming_latest_values_invocation():
    scope = ps6000a('pytest')
    called = {}
    def fake_call(name, *args):
        called['name'] = name
        called['args'] = args
        return 0
    scope._call_attr_function = fake_call
    info = (PICO_STREAMING_DATA_INFO * 1)()
    trig = PICO_STREAMING_DATA_TRIGGER_INFO()
    scope.get_streaming_latest_values(info, trig)
    assert called['name'] == 'GetStreamingLatestValues'


def test_no_of_streaming_values_invocation():
    scope = ps6000a('pytest')
    called = {}
    def fake_call(name, *args):
        called['name'] = name
        return 0
    scope._call_attr_function = fake_call
    scope.no_of_streaming_values()
    assert called['name'] == 'NoOfStreamingValues'

