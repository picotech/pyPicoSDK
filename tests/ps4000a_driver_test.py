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


def test_open_unit_async_default_matches_sync_12bit():
    """The shared default of 0 (8-bit) is invalid on 4000A hardware."""
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.open_unit_async()
    (name, args), = calls
    assert args[2] == RESOLUTION.BIT_12


def test_change_power_source_string_literals():
    """The documented 'USB'/'AC PSU' literals must resolve (case-insensitive)."""
    from pypicosdk.constants import POWER_SOURCE
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.change_power_source('USB')
    scope.change_power_source('AC PSU')
    assert [args[1] for _, args in calls] == \
        [POWER_SOURCE.SUPPLY_NOT_CONNECTED, POWER_SOURCE.SUPPLY_CONNECTED]
    assert scope.ac_adaptor is True


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


# --- trigger layer ---------------------------------------------------------------

def test_trigger_struct_sizes_match_header():
    """PS4000A trigger structs are pack(1): 16-byte properties, 8-byte direction."""
    from pypicosdk.constants import PS4000A_TRIGGER_CHANNEL_PROPERTIES, PS4000A_DIRECTION
    assert ctypes.sizeof(PS4000A_TRIGGER_CHANNEL_PROPERTIES) == 16
    assert ctypes.sizeof(PS4000A_DIRECTION) == 8


def test_simple_trigger_converts_us_to_ms():
    """ps4000aSetSimpleTrigger's timeout is milliseconds (int16), not us."""
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.set_simple_trigger(CHANNEL.A, threshold=100, threshold_unit='adc',
                             auto_trigger=5000)
    (name, args), = calls
    assert name == 'SetSimpleTrigger'
    assert args[6] == 5  # 5000 us -> 5 ms


def test_simple_trigger_us_overflow_raises():
    from pypicosdk import PicoSDKException
    scope, _ = _scope_with_recorded_calls(ps4000a)
    with pytest.raises(PicoSDKException):
        scope.set_simple_trigger(CHANNEL.A, threshold=0, threshold_unit='adc',
                                 auto_trigger=40_000_000)  # 40000 ms > int16


def test_simple_trigger_sub_ms_rounds_up_not_infinite():
    """500 us must not round to 0 ms (which would mean wait-forever)."""
    from pypicosdk.common import ParameterNotSupported
    scope, calls = _scope_with_recorded_calls(ps4000a)
    with pytest.warns(ParameterNotSupported):
        scope.set_simple_trigger(CHANNEL.A, threshold=0, threshold_unit='adc',
                                 auto_trigger=500)
    assert calls[0][1][6] == 1


def test_simple_trigger_external_remap():
    """CHANNEL.EXTERNAL (virtual 1000) -> PS4000A_EXTERNAL = 8; mV threshold
    converted against the fixed +/-5 V EXT range."""
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.set_simple_trigger(CHANNEL.EXTERNAL, threshold=2500, threshold_unit='mv')
    (name, args), = calls
    assert args[2] == 8
    assert args[3] == int((2500 / 5000) * 32767)


def test_trigger_properties_struct_and_ms():
    from pypicosdk.constants import PS4000A_TRIGGER_CHANNEL_PROPERTIES, THRESHOLD_MODE
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.set_trigger_channel_properties(1000, 10, -1000, 10, CHANNEL.B,
                                         auto_trigger_us=2_000_000)
    (name, args), = calls
    assert name == 'SetTriggerChannelProperties'
    prop = args[1]._obj
    assert isinstance(prop, PS4000A_TRIGGER_CHANNEL_PROPERTIES)
    assert prop.channel_ == CHANNEL.B
    assert prop.thresholdMode_ == THRESHOLD_MODE.LEVEL
    assert args[4].value == 2000  # int32 milliseconds


def test_trigger_directions_two_field_struct():
    from pypicosdk.constants import PS4000A_DIRECTION, THRESHOLD_DIRECTION
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.set_trigger_channel_directions(
        [CHANNEL.A, CHANNEL.EXTERNAL],
        [THRESHOLD_DIRECTION.RISING, THRESHOLD_DIRECTION.FALLING])
    (name, args), = calls
    assert name == 'SetTriggerChannelDirections'
    dir_array = args[1]._obj
    assert ctypes.sizeof(dir_array) == 2 * 8  # 8-byte stride
    assert dir_array[1].channel_ == 8  # EXTERNAL remapped
    assert dir_array[1].direction_ == THRESHOLD_DIRECTION.FALLING


def test_pwq_properties_leading_direction():
    from pypicosdk.constants import THRESHOLD_DIRECTION, PULSE_WIDTH_TYPE
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.set_pulse_width_qualifier_properties(
        10, 100, PULSE_WIDTH_TYPE.GREATER_THAN,
        direction=THRESHOLD_DIRECTION.FALLING)
    (name, args), = calls
    assert name == 'SetPulseWidthQualifierProperties'
    assert args[1] == THRESHOLD_DIRECTION.FALLING  # leading direction
    assert (args[2].value, args[3].value) == (10, 100)


def test_pwq_directions_raises():
    from pypicosdk import PicoSDKException
    scope, _ = _scope_with_recorded_calls(ps4000a)
    with pytest.raises(PicoSDKException):
        scope.set_pulse_width_qualifier_directions(CHANNEL.A, 0, 0)


def test_trigger_time_offset_uses_64_variant():
    scope, calls = _scope_with_recorded_calls(ps4000a)
    from pypicosdk.constants import TIME_UNIT
    scope.get_trigger_time_offset(TIME_UNIT.NS)
    assert calls[0][0] == 'GetTriggerTimeOffset64'


def test_get_trigger_info_raises():
    from pypicosdk import PicoSDKException
    scope, _ = _scope_with_recorded_calls(ps4000a)
    with pytest.raises(PicoSDKException):
        scope.get_trigger_info(0, 1)


def test_advanced_trigger_end_to_end_remap_and_ms():
    """set_advanced_trigger drives conditions/directions/properties with the
    remapped channel and a millisecond auto-trigger."""
    from pypicosdk.constants import (
        THRESHOLD_DIRECTION, THRESHOLD_MODE, TRIGGER_STATE)
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.set_advanced_trigger(
        CHANNEL.EXTERNAL, TRIGGER_STATE.TRUE, THRESHOLD_DIRECTION.RISING,
        THRESHOLD_MODE.LEVEL, threshold_upper_mv=2500, threshold_lower_mv=-2500,
        auto_trigger_ms=100)
    names = [name for name, _ in calls]
    assert names == ['SetTriggerChannelConditions', 'SetTriggerChannelDirections',
                     'SetTriggerChannelProperties']
    # Conditions: PICO_CONDITION array with remapped source
    cond = calls[0][1][1]._obj
    assert cond[0].source_ == 8
    # Properties: remapped channel, EXT-range-scaled threshold, 100 ms
    prop = calls[2][1][1]._obj
    assert prop.channel_ == 8
    assert prop.thresholdUpper_ == int((2500 / 5000) * 32767)
    assert calls[2][1][4].value == 100


def test_advanced_trigger_window_mode_reaches_struct():
    """WINDOW must land in the properties struct's thresholdMode - the only
    carrier of level/window on ps4000a (PS4000A_DIRECTION has no field and
    the INSIDE/OUTSIDE aliases are numerically identical to ABOVE/BELOW)."""
    from pypicosdk.constants import (
        THRESHOLD_DIRECTION, THRESHOLD_MODE, TRIGGER_STATE)
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.set_advanced_trigger(
        CHANNEL.A, TRIGGER_STATE.TRUE, THRESHOLD_DIRECTION.INSIDE,
        THRESHOLD_MODE.WINDOW, threshold_upper_mv=100, threshold_lower_mv=-100)
    prop = [args for name, args in calls
            if name == 'SetTriggerChannelProperties'][0][1]._obj
    assert prop.thresholdMode_ == THRESHOLD_MODE.WINDOW


def test_pulse_width_trigger_external_scales_threshold():
    """PWT on EXTERNAL must apply the same +/-5 V scaling as the simple and
    advanced trigger paths."""
    from pypicosdk.constants import THRESHOLD_DIRECTION, PULSE_WIDTH_TYPE
    scope, calls = _scope_with_recorded_calls(ps4000a)
    # get_timebase feeds the sample-interval maths; give it a real interval
    scope.get_timebase = lambda timebase, samples, segment=0: {'Interval(ns)': 8.0}
    scope.set_pulse_width_trigger(
        CHANNEL.EXTERNAL, timebase=8, samples=1000,
        direction=THRESHOLD_DIRECTION.RISING,
        pulse_width_type=PULSE_WIDTH_TYPE.GREATER_THAN,
        time_lower=1, threshold_upper_mv=2500)
    prop = [args for name, args in calls
            if name == 'SetTriggerChannelProperties'][0][1]._obj
    assert prop.thresholdUpper_ == int((2500 / 5000) * 32767)
    assert prop.channel_ == 8


def test_ext_threshold_beyond_range_raises():
    """> +/-5 V would wrap the driver's int16 threshold (sign flip)."""
    from pypicosdk import PicoSDKException
    scope, _ = _scope_with_recorded_calls(ps4000a)
    with pytest.raises(PicoSDKException):
        scope.set_simple_trigger(CHANNEL.EXTERNAL, threshold=6000,
                                 threshold_unit='mv')


def test_set_trigger_delay_uint32():
    """ps4000aSetTriggerDelay takes uint32, not base's uint64."""
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.set_trigger_delay(1000)
    (name, args), = calls
    assert name == 'SetTriggerDelay'
    assert isinstance(args[1], ctypes.c_uint32)


# --- streaming --------------------------------------------------------------------

def test_run_streaming_uint32_interval_and_raw_remap():
    """ps4000aRunStreaming takes a uint32* sampleInterval and an
    overviewBufferSize; RAW remaps to NONE."""
    from pypicosdk.constants import TIME_UNIT
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope.base_dataclass.last_buffer_size = 5000
    scope.run_streaming(8, TIME_UNIT.NS, 0, 10000, ratio_mode=RATIO_MODE.RAW)
    (name, args), = calls
    assert name == 'RunStreaming'
    assert len(args) == 9
    assert isinstance(args[1]._obj, ctypes.c_uint32)   # sampleInterval*
    assert args[7] == RATIO_MODE.NONE                  # ratio mode remapped
    assert args[8].value == 5000                       # overviewBufferSize
    assert scope._streaming_callback_pointer is not None


def test_streaming_callback_feeds_poll_dict():
    scope, calls = _scope_with_recorded_calls(ps4000a)
    scope._setup_streaming_callback()
    scope._streaming_callback(1, 512, 100, 0, 42, 1, 0, None)
    info = scope.get_streaming_latest_values()
    assert calls[0][0] == 'GetStreamingLatestValues'
    assert info['no of samples'] == 512
    assert info['start index'] == 100
    assert info['triggered at'] == 42
    assert info['triggered?'] == 1
    assert info['status'] == 0


def test_streaming_poll_without_callback_returns_status():
    """An empty queue must report the real driver status, not fake data."""
    scope, _ = _scope_with_recorded_calls(ps4000a, returns={'GetStreamingLatestValues': 39})
    scope._setup_streaming_callback()
    info = scope.get_streaming_latest_values()
    assert info['status'] == 39  # PICO_BUSY passthrough
    assert info['no of samples'] == 0


def test_streaming_multi_poll_raises():
    from pypicosdk import PicoSDKException
    scope, _ = _scope_with_recorded_calls(ps4000a)
    with pytest.raises(PicoSDKException):
        scope.get_streaming_latest_values_multi([(CHANNEL.A, RATIO_MODE.NONE, 1)])


def test_streaming_poll_before_run_raises_cleanly():
    """Polling before run_streaming() raises PicoSDKException, not AttributeError."""
    from pypicosdk import PicoSDKException
    scope, _ = _scope_with_recorded_calls(ps4000a)
    with pytest.raises(PicoSDKException):
        scope.get_streaming_latest_values()


def test_streaming_callback_prototype_via_c_pointer():
    """Drive the callback through the CFUNCTYPE pointer itself so a wrong
    prototype (arg count/width) fails the suite."""
    scope, _ = _scope_with_recorded_calls(ps4000a)
    scope._setup_streaming_callback()
    scope._streaming_callback_pointer(1, 256, 64, 0, 7, 1, 0, None)
    info = scope._streaming_queue.get_nowait()
    assert info['no of samples'] == 256
    assert info['triggered at'] == 7


def test_streaming_session_rejects_ps4000a():
    """StreamingSession would silently mis-drive the ps4000a callback path;
    it must refuse cleanly at construction."""
    from pypicosdk import StreamingSession, PicoSDKException, TIME_UNIT
    scope, _ = _scope_with_recorded_calls(ps4000a)
    with pytest.raises(PicoSDKException):
        StreamingSession(scope, sample_interval=1, time_units=TIME_UNIT.US,
                         samples_per_buffer=1000)
