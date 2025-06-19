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
import pypicosdk
from pypicosdk import ps6000a, CHANNEL, ACTION
from pypicosdk.constants import PICO_CONDITION, PICO_TRIGGER_STATE


def test_set_trigger_channel_conditions_invocation():
    scope = ps6000a('pytest')
    called = {}

    def fake_call(name, *args):
        called['name'] = name
        called['args'] = args
        return 0

    scope._call_attr_function = fake_call

    condition = PICO_CONDITION(CHANNEL.A, PICO_TRIGGER_STATE.TRUE)
    scope.set_trigger_channel_conditions([condition], ACTION.CLEAR_ALL | ACTION.ADD)
    assert called['name'] == 'SetTriggerChannelConditions'




