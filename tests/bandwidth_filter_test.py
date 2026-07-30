"""
Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.

pytest file for the shared ps5000a/ps4000a bandwidth-filter mapping
"""
import pytest

from pypicosdk import ps4000a, ps5000a, BANDWIDTH_CH, PicoSDKException
from pypicosdk.shared._ps5000a_ps4000a import Sharedps5000aPs4000a


def _scope_with_recorded_calls(driver_class):
    scope = driver_class('pytest')
    calls = []
    scope._call_attr_function = lambda name, *args: calls.append((name, args))
    return scope, calls


def test_shared_mixin_in_both_mros():
    """set_channel/set_bandwidth_filter resolve from the shared mixin on both drivers"""
    for driver_class in (ps4000a, ps5000a):
        assert driver_class.set_channel is Sharedps5000aPs4000a.set_channel
        assert driver_class.set_bandwidth_filter is Sharedps5000aPs4000a.set_bandwidth_filter


def test_ps5000a_bandwidth_mapping():
    """BANDWIDTH_CH Hz values map to PS5000A_BANDWIDTH_LIMITER ordinals"""
    scope, calls = _scope_with_recorded_calls(ps5000a)
    scope.set_bandwidth_filter('channel_a', BANDWIDTH_CH.BW_FULL)
    scope.set_bandwidth_filter('channel_a', BANDWIDTH_CH.BW_20MHZ)
    assert [args[2] for _, args in calls] == [0, 1]


def test_ps4000a_bandwidth_mapping():
    """BANDWIDTH_CH Hz values map to PS4000A_BANDWIDTH_LIMITER ordinals"""
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.set_bandwidth_filter('channel_a', BANDWIDTH_CH.BW_FULL)
    scope.set_bandwidth_filter('channel_a', BANDWIDTH_CH.BW_20KHZ)
    scope.set_bandwidth_filter('channel_a', BANDWIDTH_CH.BW_100KHZ)
    scope.set_bandwidth_filter('channel_a', BANDWIDTH_CH.BW_1MHZ)
    assert [args[2] for _, args in calls] == [0, 1, 2, 3]


def test_ps5000a_rejects_unsupported_bandwidth():
    """Unsupported bandwidths raise the public PicoSDKException, not silently pass"""
    scope, calls = _scope_with_recorded_calls(ps5000a)
    with pytest.raises(PicoSDKException):
        scope.set_bandwidth_filter('channel_a', BANDWIDTH_CH.BW_100KHZ)
    assert not calls


def test_ps4000a_rejects_unsupported_bandwidth():
    """ps4000a has no 20 MHz limiter; the old passthrough silently set 20 kHz"""
    scope, calls = _scope_with_recorded_calls(ps4000a)
    with pytest.raises(PicoSDKException):
        scope.set_bandwidth_filter('channel_a', BANDWIDTH_CH.BW_20MHZ)
    assert not calls
