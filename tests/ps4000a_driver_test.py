"""
Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.

pytest file for the ps4000a driver overrides (mock: no hardware, no dll).
Each test uses the driver_class('pytest') constructor and a recorded
_call_attr_function, following tests/bandwidth_filter_test.py.
"""
import ctypes

import pytest

from pypicosdk import ps4000a, ps5000a, CHANNEL, RANGE, RATIO_MODE, RESOLUTION
from pypicosdk._exceptions import PowerSourceWarning
from pypicosdk.shared._ps5000a_ps4000a import Sharedps5000aPs4000a


def _scope_with_recorded_calls(driver_class, returns=None):
    """Build a pytest-mode scope whose _call_attr_function records each
    (name, args) and returns returns.get(name, 0)."""
    scope = driver_class('pytest')
    calls = []
    returns = returns or {}

    def recorder(name, *args):
        calls.append((name, args))
        return returns.get(name, 0)

    scope._call_attr_function = recorder
    return scope, calls


# --- Shared mixin promotion -------------------------------------------------

def test_promoted_methods_shared_by_both_drivers():
    """Bodies promoted into Sharedps5000aPs4000a resolve from the mixin on
    both drivers instead of being duplicated."""
    for name in ('get_adc_limits', 'get_current_power_source',
                 'change_power_source', 'is_led_flashing',
                 'get_max_downsample_ratio', 'get_max_segments'):
        for driver_class in (ps4000a, ps5000a):
            assert getattr(driver_class, name) is getattr(Sharedps5000aPs4000a, name)


def test_get_adc_limits_calls_min_max_value():
    scope, calls = _scope_with_recorded_calls(ps4000a)
    limits = scope.get_adc_limits()
    assert [name for name, _ in calls] == ['MinimumValue', 'MaximumValue']
    assert limits == (0, 0)  # recorder leaves the c_int16 out-params at 0


def test_get_max_segments_uses_uint32():
    """Both C headers declare maxSegments as uint32*."""
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.get_max_segments()
    (_, args), = calls
    assert isinstance(args[1]._obj, ctypes.c_uint32)


# --- open_unit ---------------------------------------------------------------

def _openable_scope(returns=None):
    scope, calls = _scope_with_recorded_calls(ps4000a, returns)
    # set_all_channels_off needs GetUnitInfo string plumbing; not under test
    scope.set_all_channels_off = lambda: None
    return scope, calls


def test_open_unit_uses_openunitwithresolution_and_12bit_default():
    scope, calls = _openable_scope()
    scope.open_unit()
    assert calls[0][0] == 'OpenUnitWithResolution'
    assert calls[0][1][2] == RESOLUTION.BIT_12
    # ADC limits are fetched as part of opening
    assert [name for name, _ in calls[1:]] == ['MinimumValue', 'MaximumValue']
    assert scope.resolution == RESOLUTION.BIT_12


def test_open_unit_resolution_literal():
    scope, calls = _openable_scope()
    scope.open_unit(resolution='14bit')
    assert calls[0][1][2] == RESOLUTION.BIT_14


def test_open_unit_dc_power_handshake():
    """Status 282 (supply not connected) is acknowledged via ChangePowerSource."""
    scope, calls = _openable_scope(returns={'OpenUnitWithResolution': 282})
    with pytest.warns(PowerSourceWarning):
        scope.open_unit()
    assert scope.ac_adaptor is False
    assert ('ChangePowerSource', (scope.handle, 282)) in calls


def test_open_unit_full_power_no_handshake():
    scope, calls = _openable_scope()
    scope.open_unit()
    assert scope.ac_adaptor is True
    assert 'ChangePowerSource' not in [name for name, _ in calls]


# --- set_device_resolution ----------------------------------------------------

def test_set_device_resolution_refreshes_adc_limits():
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.set_device_resolution(RESOLUTION.BIT_14)
    assert [name for name, _ in calls] == \
        ['SetDeviceResolution', 'MinimumValue', 'MaximumValue']
    assert scope.resolution == RESOLUTION.BIT_14
    assert (scope.min_adc_value, scope.max_adc_value) == (0, 0)


# --- get_analogue_offset_limits dispatch --------------------------------------

def test_analogue_offset_limits_uses_float_getanalogueoffset():
    """ps4000a has GetAnalogueOffset (float*), not GetAnalogueOffsetLimits."""
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.get_analogue_offset_limits(RANGE.V1, 1)
    (name, args), = calls
    assert name == 'GetAnalogueOffset'
    assert isinstance(args[3]._obj, ctypes.c_float)


# --- async open ----------------------------------------------------------------

def test_open_unit_async_uses_withresolution():
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.open_unit_async(resolution=RESOLUTION.BIT_12)
    (name, args), = calls
    assert name == 'OpenUnitAsyncWithResolution'
    assert args[2] == RESOLUTION.BIT_12


# --- block path -----------------------------------------------------------------

def test_get_timebase_uses_gettimebase2():
    """ps4000aGetTimebase reports int32; GetTimebase2 reports float."""
    scope, calls = _scope_with_recorded_calls(ps4000a)
    result = scope.get_timebase(8, 1000)
    (name, args), = calls
    assert name == 'GetTimebase2'
    assert isinstance(args[3]._obj, ctypes.c_float)
    assert isinstance(args[4]._obj, ctypes.c_int32)
    assert result['Interval(ns)'] == 0.0


def test_nearest_sampling_interval_inserts_useets():
    """ps4000a has a uint16 useEts argument between resolution and the
    out-pointers; it must be 0."""
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.resolution = RESOLUTION.BIT_12
    scope.get_nearest_sampling_interval(1e-6)
    (name, args), = calls
    assert name == 'NearestSampleIntervalStateless'
    assert len(args) == 7
    assert args[4] == 0  # useEts


def test_set_data_buffer_six_args_and_raw_remap():
    """ps4000aSetDataBuffer takes 6 args (no dataType/action); RAW maps to NONE."""
    scope, calls = _scope_with_recorded_calls(ps4000a)
    buffer = scope.set_data_buffer(CHANNEL.A, 100, ratio_mode=RATIO_MODE.RAW)
    (name, args), = calls
    assert name == 'SetDataBuffer'
    assert len(args) == 6  # handle, channel, ptr, samples, segment, mode
    assert args[5] == RATIO_MODE.NONE
    assert buffer.size == 100


def test_set_data_buffers_seven_args():
    scope, calls = _scope_with_recorded_calls(ps4000a)
    buf_min, buf_max = scope.set_data_buffers(CHANNEL.A, 100)
    (name, args), = calls
    assert name == 'SetDataBuffers'
    assert len(args) == 7  # handle, channel, max ptr, min ptr, samples, segment, mode
    assert args[6] == RATIO_MODE.AGGREGATE
    assert buf_min.size == buf_max.size == 100


def test_get_values_raw_remaps_to_none():
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.get_values(100, ratio_mode=RATIO_MODE.RAW, wait_for_ready=False)
    (name, args), = calls
    assert name == 'GetValues'
    assert args[4] == RATIO_MODE.NONE


def test_get_values_bulk_no_start_index_uint32():
    """ps4000aGetValuesBulk has no startIndex; sample/segment args are uint32."""
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.is_ready = lambda: None
    samples, overflow = scope.get_values_bulk(100, 0, 3)
    (name, args), = calls
    assert name == 'GetValuesBulk'
    assert len(args) == 7  # handle, samples*, from, to, ratio, mode, overflow*
    assert isinstance(args[1]._obj, ctypes.c_uint32)
    assert len(overflow) == 4  # one entry per segment


def test_get_values_overlapped_single_segment():
    """ps4000aGetValuesOverlapped is single-segment (7 C params)."""
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.is_ready = lambda: None
    scope.get_values_overlapped(0, 100, 1, RATIO_MODE.RAW, segment_index=2)
    (name, args), = calls
    assert name == 'GetValuesOverlapped'
    assert len(args) == 7
    assert args[4] == RATIO_MODE.NONE
    assert args[5].value == 2  # segmentIndex, not a to_segment/overflow shift


def test_rapid_block_counters_use_uint32():
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.get_no_of_captures()
    scope.get_no_of_processed_captures()
    scope.no_of_streaming_values()
    for _, args in calls:
        assert isinstance(args[1]._obj, ctypes.c_uint32)


def test_memory_segments_uses_narrow_width():
    """ps4000aMemorySegments writes int32; base's ps5000a-width branch applies."""
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.memory_segments(4)
    (name, args), = calls
    assert name == 'MemorySegments'
    assert isinstance(args[2]._obj, ctypes.c_uint32)


def test_v50_range_for_4824a():
    """RANGE.V50 (PS4000A_50V = 11) resolves to 50 V in the range machinery."""
    from pypicosdk._classes._channel_class import ChannelClass
    assert RANGE.V50 == 11
    assert ChannelClass(ch_range=RANGE.V50, probe_scale=1.0).range_mv == 50000
