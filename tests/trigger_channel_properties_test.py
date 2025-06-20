import sys
import os

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, repo_root)
if 'pypicosdk' in sys.modules:
    del sys.modules['pypicosdk']
if 'pypicosdk.constants' in sys.modules:
    del sys.modules['pypicosdk.constants']
if 'pypicosdk.pypicosdk' in sys.modules:
    del sys.modules['pypicosdk.pypicosdk']

from pypicosdk import ps6000a, PICO_TRIGGER_CHANNEL_PROPERTIES


def test_set_trigger_channel_properties_invocation():
    scope = ps6000a('pytest')
    called = {}

    def fake_call(name, *args):
        called['name'] = name
        called['args'] = args
        return 0

    scope._call_attr_function = fake_call
    props = PICO_TRIGGER_CHANNEL_PROPERTIES(100, 10, -100, 10, 0)
    scope.set_trigger_channel_properties([props])
    assert called['name'] == 'SetTriggerChannelProperties'
