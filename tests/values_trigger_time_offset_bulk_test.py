from pypicosdk import ps6000a, PICO_TIME_UNIT


def test_get_values_trigger_time_offset_bulk_invocation():
    scope = ps6000a('pytest')
    called = {}

    def fake_call(name, *args):
        called['name'] = name
        called['args'] = args
        return 0

    scope._call_attr_function = fake_call
    scope.get_values_trigger_time_offset_bulk(0, 3)
    assert called['name'] == 'GetValuesTriggerTimeOffsetBulk'
