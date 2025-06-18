from pypicosdk import ps6000a, AUXIO_MODE


def test_set_aux_io_mode_invocation():
    scope = ps6000a('pytest')
    called = {}

    def fake_call(name, *args):
        called['name'] = name
        called['args'] = args
        return 0

    scope._call_attr_function = fake_call
    scope.set_aux_io_mode(AUXIO_MODE.INPUT)
    assert called['name'] == 'SetAuxIoMode'
