import ctypes
from pypicosdk import (
    ps6000a,
    DIGITAL_PORT,
    DIGITAL_PORT_HYSTERESIS,
    AUX_IO_MODE,
)


def test_set_digital_port_on(monkeypatch):
    scope = ps6000a("pytest")
    captured = {}

    def fake_call(name, handle, port, level_array, length, hysteresis):
        captured["name"] = name
        captured["port"] = port
        captured["levels"] = [level_array[i] for i in range(length)]
        captured["hysteresis"] = hysteresis
        return 0

    monkeypatch.setattr(scope, "_call_attr_function", fake_call)
    scope.set_digital_port_on(DIGITAL_PORT.PORT0, [100] * 2, DIGITAL_PORT_HYSTERESIS.NORMAL_100MV)

    assert captured["name"] == "SetDigitalPortOn"
    assert captured["port"] == DIGITAL_PORT.PORT0
    assert captured["levels"] == [100, 100]
    assert captured["hysteresis"] == DIGITAL_PORT_HYSTERESIS.NORMAL_100MV


def test_set_digital_port_off(monkeypatch):
    scope = ps6000a("pytest")
    captured = {}

    def fake_call(name, handle, port):
        captured["name"] = name
        captured["port"] = port
        return 0

    monkeypatch.setattr(scope, "_call_attr_function", fake_call)
    scope.set_digital_port_off(DIGITAL_PORT.PORT1)

    assert captured["name"] == "SetDigitalPortOff"
    assert captured["port"] == DIGITAL_PORT.PORT1


def test_set_aux_io_mode(monkeypatch):
    scope = ps6000a("pytest")
    captured = {}

    def fake_call(name, handle, mode):
        captured["name"] = name
        captured["mode"] = mode
        return 0

    monkeypatch.setattr(scope, "_call_attr_function", fake_call)
    scope.set_aux_io_mode(AUX_IO_MODE.INPUT)

    assert captured["name"] == "SetAuxIoMode"
    assert captured["mode"] == AUX_IO_MODE.INPUT
