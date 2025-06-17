from pypicosdk import ps6000a, PICO_TRIGGER_INFO


def test_get_trigger_info_invocation():
    scope = ps6000a('pytest')
    called = {}

    def fake_call(name, *args):
        called['name'] = name
        called['args'] = args
        return 0

    scope._call_attr_function = fake_call
    info = (PICO_TRIGGER_INFO * 1)()
    scope.get_trigger_info(info, 0, 1)
    assert called['name'] == 'GetTriggerInfo'
