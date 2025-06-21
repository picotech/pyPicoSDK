from pypicosdk import ps6000a, ps5000a, CHANNEL


def test_ps6000a_simple_trigger_converts_ms_to_us():
    scope = ps6000a('pytest')
    called = {}

    def fake_call(name, *args):
        called['name'] = name
        called['args'] = args
        return 0

    scope._call_attr_function = fake_call
    scope.set_simple_trigger(CHANNEL.A, 100, auto_trigger_ms=5)
    assert called['name'] == 'SetSimpleTrigger'
    assert called['args'][-1] == 5000


def test_ps5000a_simple_trigger_converts_ms_to_us():
    scope = ps5000a('pytest')
    called = {}

    def fake_call(name, *args):
        called['name'] = name
        called['args'] = args
        return 0

    scope._call_attr_function = fake_call
    scope.set_simple_trigger(CHANNEL.A, 100, auto_trigger_ms=7)
    assert called['name'] == 'SetSimpleTrigger'
    assert called['args'][-1] == 7000
