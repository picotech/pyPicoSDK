"""Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.

Mock tests for pypicosdk.MultiScope - no hardware needed.

A FakeBench models what the bench probes showed on real 6000E units: the
master triggers on a shared edge, each follower triggers on the master's AUX
pulse after a latency that jitters by tens of samples, and every scope keeps
a trigger time-stamp counter that only restarts when the timebase changes.

Covers: open/close bookkeeping (AUX modes, follower AUX trigger, callbacks),
index order, choosing the master, per-device timebases and the interval-mismatch error, the
uncalibrated warning path, calibrate() maths, sample-accurate block and rapid
block alignment from time stamps, arming order, missed-trigger and
counter-reset handling in strict and non-strict modes, stimulus routing when
the master AWG is the reference, buffer pinning and JSON round trips.

Runs under pytest, or standalone: python tests/multiscope_mock_test.py
"""
import ctypes
import json
import os
import tempfile
import warnings
from types import SimpleNamespace

import numpy as np

import pypicosdk as psdk
from pypicosdk.common import PicoSDKException
from pypicosdk.multiscope import (
    MultiScope, MultiScopeError, MultiScopeWarning, Calibration, TIME_STAMP_RESET_FLAG,
    _rising_edge_time,
)

MASTER, FOLLOWER = 'AA000/0001', 'BB000/0002'
CH = psdk.CHANNEL.A
RANGE_MV = 500
MAX_ADC = 32767
DT = 3.2                      # ns, the interval both fakes reach at "500 MS/s"


class FakeBench:
    """Shared physics for a master + followers group.

    Absolute time is in ns. Capture i puts the shared edge at E_i; the master
    trigger sample sits exactly on it, follower k triggers L_k samples later
    plus a fixed phase offset PHASE (its sample grid is not aligned to the
    master's, the reference only locks the frequency).
    """
    PHASE = 0.4 * DT          # follower sample-grid phase offset, ns
    COUNTER_C = 12345         # follower counter origin, in samples

    def __init__(self):
        self.timebases = {MASTER: {500e6: 4, 250e6: 8}, FOLLOWER: {500e6: 5, 250e6: 9}}
        self.intervals = {MASTER: {4: DT, 8: 2 * DT}, FOLLOWER: {5: DT, 9: 2 * DT}}
        self.reference = {MASTER: psdk.CLOCK_REFERENCE.EXTERNAL_REF,
                          FOLLOWER: psdk.CLOCK_REFERENCE.EXTERNAL_REF}
        self.fail_open = set()
        self.mean_lag_samples = 1030
        # deterministic jitter, roughly uniform over +/- 70 samples like the real AUX path
        self.jitter = [(-70 + (37 * n) % 141) for n in range(400)]
        self.missed_segments = {}         # segment index -> extra lag in samples
        self.capture_counter = 0
        self.arm_order = []
        self.scopes = {}
        self.last_timebase = {}
        self.reset_pending = {}

    # -- timebase bookkeeping
    def timebase_for(self, serial, rate):
        return self.timebases[serial][rate]

    def interval_ns(self, serial, tb):
        return self.intervals[serial][tb]

    def note_timebase(self, serial, tb):
        if self.last_timebase.get(serial) not in (None, tb):
            self.reset_pending[serial] = True
        self.last_timebase[serial] = tb

    # -- the acquisition itself: fill every armed scope consistently
    def acquire(self):
        """Called once per capture set (by the master's arm) to compute a consistent set."""
        master = self.scopes[MASTER]
        captures = master.captures if master.buffers[CH].ndim == 2 else 1
        dt = self.interval_ns(MASTER, master.armed['timebase'])
        base = self.capture_counter
        self.capture_counter += captures
        events = []
        for i in range(captures):
            edge = 1_000_000.0 * (base + i + 1)          # ns, one edge per ms
            events.append(edge)
        for serial, scope in self.scopes.items():
            is_master = serial == MASTER
            infos = []
            for i, edge in enumerate(events):
                if is_master:
                    trig = edge                                       # trigger sample on the edge
                    ts = round(trig / dt)
                else:
                    lag = self.mean_lag_samples + self.jitter[(base + i) % len(self.jitter)]
                    lag += self.missed_segments.get(i, 0)
                    trig = edge + lag * dt + self.PHASE
                    ts = round((trig - self.PHASE) / dt) - self.COUNTER_C
                pre = scope.armed['pre']
                n = scope.armed['samples']
                t = trig + (np.arange(n) - pre) * dt
                ramp = np.clip((t - edge) / 8.0, -0.5, 0.5)        # 8 ns rise, -300..+300 mV
                mv = 600.0 * ramp
                adc = np.round(mv / RANGE_MV * MAX_ADC).astype(np.int16)
                for ch in scope.buffers:
                    if captures == 1:
                        scope.buffers[ch][:] = adc
                    else:
                        scope.buffers[ch][i, :] = adc
                status = TIME_STAMP_RESET_FLAG if self.reset_pending.pop(serial, False) else 0
                infos.append({'status': status, 'segmentIndex': i, 'triggerIndex': 0,
                              'triggerTime': 0.0, 'timeUnits': 0, 'missedTriggers': 1,
                              'timeStampCounter': int(ts)})
            scope.infos = infos


class FakeScope:
    """ps6000a stand-in that records calls and serves FakeBench data."""
    _unit_prefix_n = 'ps6000a'

    def __init__(self, bench):
        self.bench = bench
        self.serial = None
        self.handle = ctypes.c_short(1)
        self.resolution = 0
        self.max_adc_value = MAX_ADC
        self.channel_db = {}
        self.calls = []
        self.aux_mode = None
        self.trigger = None
        self.ref_cb = 'unset'
        self.siggen = None
        self.armed = None
        self.buffers = None
        self.infos = []
        self.segments = 1
        self.captures = 1
        self.stopped = False
        self.closed = False

    def open_unit(self, serial_number=None, resolution=0):
        if serial_number in self.bench.fail_open:
            raise PicoSDKException(f'Pico Not Found: {serial_number}')
        self.serial = serial_number
        self.resolution = resolution
        self.bench.scopes[serial_number] = self
        self.calls.append(('open', serial_number, resolution))

    def close_unit(self):
        self.closed = True
        self.calls.append(('close',))

    def set_external_reference_interaction_callback(self, callback):
        self.ref_cb = callback
        self.calls.append(('ref_cb', callback is not None))
        if callback is not None and self.bench.reference.get(self.serial) is not None:
            callback(self.handle.value, 0, int(self.bench.reference[self.serial]))

    def set_aux_io_mode(self, mode):
        self.aux_mode = mode
        self.calls.append(('aux', mode))

    def set_simple_trigger(self, channel, threshold=0, threshold_unit='mv', enable=True,
                           direction=psdk.TRIGGER_DIR.RISING, delay=0, auto_trigger=0):
        self.trigger = dict(channel=channel, threshold=threshold, threshold_unit=threshold_unit,
                            direction=direction, auto_trigger=auto_trigger)
        self.calls.append(('simple_trigger', channel))

    def set_advanced_trigger(self, channel, *args, **kwargs):
        self.trigger = dict(channel=channel, advanced=True)
        self.calls.append(('advanced_trigger', channel))

    def set_channel(self, channel, range=psdk.RANGE.V1, enabled=True, **kwargs):  # pylint: disable=W0622
        if enabled:
            self.channel_db[channel] = SimpleNamespace(range_mv=RANGE_MV, probe_scale=1.0)
        else:
            self.channel_db.pop(channel, None)
        self.calls.append(('channel', channel, range, enabled))

    def set_siggen(self, frequency, pk2pk, wave_type, **kwargs):
        self.siggen = (frequency, pk2pk, wave_type)
        return {}

    def sample_rate_to_timebase(self, sample_rate, unit=psdk.SAMPLE_RATE.MSPS):
        return self.bench.timebase_for(self.serial, sample_rate * unit)

    def interval_to_timebase(self, interval, unit=psdk.TIME_UNIT.S):
        interval_ns = interval / unit * 1e9
        for tb, iv in self.bench.intervals[self.serial].items():
            if abs(iv - interval_ns) < 1e-9:
                return tb
        raise PicoSDKException(f'no timebase for {interval_ns} ns')

    def get_timebase(self, timebase, samples, segment=0):
        return {'Interval(ns)': self.bench.interval_ns(self.serial, timebase), 'Samples': 10 ** 9}

    def memory_segments(self, n_segments):
        self.segments = n_segments
        self.calls.append(('segments', n_segments))
        return 10 ** 6

    def set_no_of_captures(self, n_captures):
        self.captures = n_captures

    def set_data_buffer_for_enabled_channels(self, samples, segment=0,
                                             datatype=psdk.DATA_TYPE.INT16_T,
                                             ratio_mode=psdk.RATIO_MODE.RAW, clear_buffer=True,
                                             captures=0):
        shape = (captures, samples) if captures else (samples,)
        self.buffers = {ch: np.zeros(shape, dtype=np.int16) for ch in self.channel_db}
        self.calls.append(('buffers', samples, captures))
        return self.buffers

    def run_block_capture(self, timebase, samples, pre_trig_percent=None, segment=0,
                          pre_trig_samples=None):
        pre = pre_trig_samples if pre_trig_samples is not None else int(
            samples * (50 if pre_trig_percent is None else pre_trig_percent) / 100)
        self.armed = dict(timebase=timebase, samples=samples, pre=pre)
        self.bench.note_timebase(self.serial, timebase)
        self.bench.arm_order.append(self.serial)
        self.calls.append(('arm', timebase, samples, pre))
        if self.serial == MASTER:
            self.bench.acquire()
        return 1

    def _call_attr_function(self, name, *args):
        if name == 'IsReady':
            args[1]._obj.value = 1  # pylint: disable=protected-access
        return 0

    def stop(self):
        self.stopped = True

    def get_values(self, samples, start_index=0, segment=0, ratio=0,
                   ratio_mode=psdk.RATIO_MODE.RAW, data_type=psdk.DATA_TYPE.INT16_T,
                   wait_for_ready=True):
        self.calls.append(('get_values', samples, wait_for_ready))
        return samples

    def get_values_bulk(self, samples, from_segment_index, to_segment_index, start_index=0,
                        ratio=0, ratio_mode=psdk.RATIO_MODE.RAW, wait_for_ready=True):
        self.calls.append(('get_values_bulk', samples, from_segment_index, to_segment_index))
        return samples, []

    def get_trigger_info(self, first_segment_index, to_segment_index):
        return self.infos[first_segment_index:first_segment_index + to_segment_index]

    def _adc_to_(self, buffer, channel=None, unit='mv'):
        scale = RANGE_MV / MAX_ADC / (1000.0 if unit == 'v' else 1.0)
        return {ch: arr * scale for ch, arr in buffer.items()}


def make_group(bench=None, serials=(MASTER, FOLLOWER), open_it=True, master=None):
    bench = bench or FakeBench()
    group = MultiScope(list(serials), master=master, arm_settle_s=0.0,
                       _scope_factory=lambda: FakeScope(bench))
    if open_it:
        group.open_unit()
    return group, bench


def configured_group(bench=None, **kwargs):
    group, bench = make_group(bench, **kwargs)
    group.set_channel(CH, range=psdk.RANGE.mV500, coupling=psdk.COUPLING.DC_50OHM)
    group.set_simple_trigger(CH, threshold=0)
    tb = group.sample_rate_to_timebase(500, psdk.SAMPLE_RATE.MSPS)
    return group, bench, tb


def edge_skew_ns(data, t):
    em = _rising_edge_time(data[0][CH], t)
    ef = _rising_edge_time(data[1][CH], t, em)
    return em - ef


# ----------------------------------------------------------------- lifecycle
def test_open_configures_master_and_followers():
    group, _ = make_group()
    master, follower = group[0], group[1]
    assert master.aux_mode == psdk.AUXIO_MODE.TRIGGER_OUT
    assert follower.aux_mode == psdk.AUXIO_MODE.INPUT
    assert follower.trigger['channel'] == psdk.CHANNEL.TRIGGER_AUX
    assert follower.trigger['auto_trigger'] == 0
    assert follower.trigger['threshold_unit'] == 'adc'
    assert master.trigger is None
    assert callable(master.ref_cb) and callable(follower.ref_cb)
    assert group.reference_status == [psdk.CLOCK_REFERENCE.EXTERNAL_REF] * 2
    assert group.wait_for_lock(0.1) is True


def test_index_order_follows_the_serial_list():
    group, _ = make_group(serials=(FOLLOWER, MASTER))
    assert group[0].serial == FOLLOWER and group[1].serial == MASTER
    assert group.master is group[0]
    assert group.followers == [group[1]]
    assert len(group) == 2


def test_master_can_be_chosen_by_serial_or_index():
    third = 'CC000/0003'
    for choice in (third, f' {third} ', 2):
        group, _ = make_group(serials=(MASTER, FOLLOWER, third), master=choice)
        assert group.serials == [third, MASTER, FOLLOWER]      # followers keep their order
        assert [scope.serial for scope in group] == group.serials
        assert group.master.aux_mode == psdk.AUXIO_MODE.TRIGGER_OUT
        for follower in group.followers:
            assert follower.aux_mode == psdk.AUXIO_MODE.INPUT
            assert follower.trigger['channel'] == psdk.CHANNEL.TRIGGER_AUX


def test_master_must_name_one_of_the_scopes():
    for bad in ('CC000/0003', 2, -1, 1.5):
        try:
            MultiScope([MASTER, FOLLOWER], master=bad)
        except MultiScopeError:
            pass
        else:
            raise AssertionError(f'master={bad!r} should be rejected')


def test_choosing_the_master_fixes_a_list_in_the_wrong_order():
    # the bench's physical master is listed second, as discover() may return it
    group, _, tb = configured_group(serials=(FOLLOWER, MASTER), master=MASTER)
    cal = group.calibrate(tb, captures=16, samples=10_000)
    assert cal.serials == [MASTER, FOLLOWER] and cal.followers[0].serial == FOLLOWER
    data, t = group.run_simple_block_capture(tb, 10_000)
    assert group.last_alignment.mode == 'timestamp'
    assert abs(edge_skew_ns(data, t)) <= 0.6 * DT


def test_constructor_validation():
    for bad in ([MASTER], [MASTER, MASTER]):
        try:
            MultiScope(bad)
        except MultiScopeError:
            pass
        else:
            raise AssertionError(f'{bad} should be rejected')


def test_open_failure_closes_units_already_opened():
    bench = FakeBench()
    bench.fail_open.add(FOLLOWER)
    group, _ = make_group(bench, open_it=False)
    try:
        group.open_unit()
    except MultiScopeError as exc:
        assert FOLLOWER in str(exc)
    else:
        raise AssertionError('expected MultiScopeError')
    assert bench.scopes[MASTER].closed is True
    assert group.scopes == []


def test_close_unregisters_callbacks_and_restores_aux():
    group, _ = make_group()
    master, follower = group[0], group[1]
    group.close_unit()
    for scope in (master, follower):
        assert scope.closed is True
        assert scope.aux_mode == psdk.AUXIO_MODE.INPUT
        assert ('ref_cb', False) in scope.calls
    try:
        _ = group.master
    except MultiScopeError:
        pass
    else:
        raise AssertionError('closed group should refuse access')


def test_reference_lock_wait_times_out_when_a_scope_is_internal():
    bench = FakeBench()
    bench.reference[FOLLOWER] = psdk.CLOCK_REFERENCE.INTERNAL_REF
    group, _ = make_group(bench)
    assert group.reference_status[1] == psdk.CLOCK_REFERENCE.INTERNAL_REF
    assert group.wait_for_lock(0.05) is False


# -------------------------------------------------------------- configuration
def test_timebases_are_per_device_and_intervals_verified():
    group, _, tb = configured_group()
    assert tb == (4, 5)
    assert group.interval_to_timebase(DT, psdk.TIME_UNIT.NS) == (4, 5)


def test_interval_mismatch_raises_with_both_serials():
    bench = FakeBench()
    bench.intervals[FOLLOWER][5] = 3.3
    group, _, = make_group(bench)
    group.set_channel(CH, range=psdk.RANGE.mV500)
    try:
        group.sample_rate_to_timebase(500, psdk.SAMPLE_RATE.MSPS)
    except MultiScopeError as exc:
        assert MASTER in str(exc) and FOLLOWER in str(exc)
    else:
        raise AssertionError('expected MultiScopeError')


def test_timebase_needs_channels_enabled_first():
    group, _ = make_group()
    try:
        group.sample_rate_to_timebase(500, psdk.SAMPLE_RATE.MSPS)
    except MultiScopeError as exc:
        assert 'enable channels' in str(exc)
    else:
        raise AssertionError('expected MultiScopeError')


def test_single_integer_timebase_is_rejected():
    group, _, _ = configured_group()
    try:
        group.run_simple_block_capture(4, 1000)
    except MultiScopeError as exc:
        assert 'per-device' in str(exc)
    else:
        raise AssertionError('expected MultiScopeError')


def test_master_cannot_trigger_from_aux():
    group, _ = make_group()
    for call in (lambda: group.set_simple_trigger(psdk.CHANNEL.TRIGGER_AUX),
                 lambda: group.set_advanced_trigger(psdk.CHANNEL.TRIGGER_AUX, 1, 2, 3, 0, 0)):
        try:
            call()
        except MultiScopeError:
            pass
        else:
            raise AssertionError('TRIGGER_AUX must be refused on the master')


def test_trigger_calls_reach_only_the_master():
    group, _, _ = configured_group()
    assert group[0].trigger['channel'] == CH
    assert group[1].trigger['channel'] == psdk.CHANNEL.TRIGGER_AUX
    group.set_advanced_trigger(psdk.CHANNEL.B, 1, 2, 3, 0, 0)
    assert group[0].trigger['channel'] == psdk.CHANNEL.B
    assert group[1].trigger['channel'] == psdk.CHANNEL.TRIGGER_AUX


def test_stimulus_routing_when_master_awg_is_the_reference():
    group, _ = make_group()
    assert group.stimulus_scope is group[0]
    group.set_siggen(1000, 1.8, psdk.WAVEFORM.SQUARE)
    assert group[0].siggen == (1000, 1.8, psdk.WAVEFORM.SQUARE)
    group.use_master_awg_as_reference()
    assert group[0].siggen == (10e6, 1.0, psdk.WAVEFORM.SINE)
    assert group.stimulus_scope is group[1]
    group.set_siggen(2000, 0.5, psdk.WAVEFORM.SINE)
    assert group[1].siggen == (2000, 0.5, psdk.WAVEFORM.SINE)
    assert group[0].siggen == (10e6, 1.0, psdk.WAVEFORM.SINE)


# ------------------------------------------------------------------ captures
def test_uncalibrated_capture_warns_and_returns_raw_records():
    group, bench, tb = configured_group()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        data, t = group.run_simple_block_capture(tb, 10_000)
    assert any(issubclass(w.category, MultiScopeWarning) for w in caught)
    assert group.last_alignment.mode == 'none'
    assert data[0][CH].shape == data[1][CH].shape == (10_000,)
    assert t[5000] == 0 and abs(t[1] - t[0] - DT) < 1e-9
    # follower record still carries the AUX latency: its edge sits ~mean lag before t=0
    skew = edge_skew_ns(data, t)
    assert abs(skew - bench.mean_lag_samples * DT) < 100 * DT


def test_align_false_skips_the_warning():
    group, _, tb = configured_group()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        group.run_simple_block_capture(tb, 1000, align=False)
    assert not caught


def test_calibrate_measures_latency_offset_and_margin():
    group, bench, tb = configured_group()
    cal = group.calibrate(tb, channel=CH, captures=32, samples=10_000)
    assert cal is group.calibration
    fc = cal.followers[0]
    assert fc.serial == FOLLOWER
    # the first 32 captures use jitter[0:32], whose mean is not zero
    expected_ns = (bench.mean_lag_samples + np.mean(bench.jitter[:32])) * DT + bench.PHASE
    assert abs(fc.latency_ns - expected_ns) < 0.5 * DT
    assert abs(fc.jitter_ns - np.std(bench.jitter[:32]) * DT) < 0.5 * DT
    assert fc.latency_min_ns < fc.latency_ns < fc.latency_max_ns
    expected_offset = -bench.COUNTER_C - bench.PHASE / DT
    assert abs(fc.timestamp_offset - expected_offset) < 0.2
    assert fc.timestamp_offset_std < 0.2
    assert fc.margin_samples >= 70 + 8
    assert len(fc.lag_ns) == 32 and len(fc.residual_samples) == 32
    assert cal.interval_ns == DT and cal.timebases == [4, 5] and cal.channel == int(CH)
    # rapid-block calibration leaves the scopes back in single-segment mode
    assert group[0].segments == 1 and group[1].segments == 1


def test_calibrate_requires_the_channel_on_every_scope():
    group, _ = make_group()
    group[0].set_channel(CH)
    tb = (4, 5)
    try:
        group.calibrate(tb, channel=CH)
    except MultiScopeError as exc:
        assert FOLLOWER in str(exc)
    else:
        raise AssertionError('expected MultiScopeError')


def test_block_capture_is_sample_aligned_from_time_stamps():
    group, bench, tb = configured_group()
    cal = group.calibrate(tb, captures=16, samples=10_000)
    margin = cal.followers[0].margin_samples
    lat = int(round(cal.followers[0].latency_ns / DT))
    for _ in range(6):
        data, t = group.run_simple_block_capture(tb, 10_000, pre_trig_percent=30)
        info = group.last_alignment
        assert info.mode == 'timestamp'
        assert data[0][CH].shape == data[1][CH].shape == (10_000,)
        assert 0 <= info.shift_samples[1] <= 2 * margin
        assert abs(info.residual_samples[1]) <= 0.5
        assert abs(edge_skew_ns(data, t)) <= 0.6 * DT
        # follower captured the widened, latency-compensated window
        assert group[1].armed['samples'] == 10_000 + 2 * margin
        assert group[1].armed['pre'] == 3000 + lat + margin
        assert group[0].armed['pre'] == 3000


def test_arming_order_is_followers_first_then_master():
    group, bench, tb = configured_group()
    bench.arm_order.clear()
    group.run_simple_block_capture(tb, 1000, align=False)
    assert bench.arm_order == [FOLLOWER, MASTER]


def test_data_and_time_units_are_honoured():
    group, _, tb = configured_group()
    data_mv, t_ns = group.run_simple_block_capture(tb, 1000, align=False)
    data_v, t_us = group.run_simple_block_capture(tb, 1000, align=False, output_unit='v',
                                                  time_unit='us')
    data_adc, _ = group.run_simple_block_capture(tb, 1000, align=False, output_unit='adc')
    assert abs(t_us[1] - t_us[0] - DT / 1000) < 1e-12
    assert np.allclose(data_v[1][CH] * 1000, data_mv[1][CH])
    assert data_adc[1][CH].dtype == np.int16


def test_rapid_block_aligns_every_segment():
    group, _, tb = configured_group()
    group.calibrate(tb, captures=16, samples=10_000)
    data, t = group.run_simple_rapid_block_capture(tb, 10_000, captures=8)
    info = group.last_alignment
    assert info.mode == 'timestamp'
    assert data[0][CH].shape == data[1][CH].shape == (8, 10_000)
    assert len(info.lag_ns[1]) == 8 and len(set(np.round(info.lag_ns[1], 1))) > 1
    for i in range(8):
        em = _rising_edge_time(data[0][CH][i], t)
        ef = _rising_edge_time(data[1][CH][i], t, em)
        assert abs(em - ef) <= 0.6 * DT
    assert group[0].segments == 8 and group[1].segments == 8


def test_missed_trigger_raises_in_strict_mode_and_warns_otherwise():
    group, bench, tb = configured_group()
    group.calibrate(tb, captures=16, samples=10_000)
    bench.missed_segments = {3: 312_500}       # follower slips a whole 1 ms period
    try:
        group.run_simple_rapid_block_capture(tb, 10_000, captures=6)
    except MultiScopeError as exc:
        assert 'segment(s) 3' in str(exc) and 'missed' in str(exc)
    else:
        raise AssertionError('expected MultiScopeError')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        data, t = group.run_simple_rapid_block_capture(tb, 10_000, captures=6, strict=False)
    assert any('missed' in str(w.message) for w in caught)
    info = group.last_alignment
    margin = group.calibration.followers[0].margin_samples
    assert info.shift_samples[1][3] == margin            # mean-latency fallback for that segment
    for i in (0, 1, 2, 4, 5):                             # the others are still exact
        em = _rising_edge_time(data[0][CH][i], t)
        ef = _rising_edge_time(data[1][CH][i], t, em)
        assert abs(em - ef) <= 0.6 * DT


def test_capture_at_another_timebase_refuses_the_stale_calibration():
    group, bench, tb = configured_group()
    group.calibrate(tb, captures=8, samples=10_000)
    tb2 = group.sample_rate_to_timebase(250, psdk.SAMPLE_RATE.MSPS)
    bench.arm_order.clear()
    try:
        group.run_simple_block_capture(tb2, 1000)
    except MultiScopeError as exc:
        assert 'calibrate() at this timebase' in str(exc)
    else:
        raise AssertionError('expected MultiScopeError')
    assert bench.arm_order == []                          # refused before arming anything


def test_time_stamp_reset_is_detected_after_a_timebase_change():
    group, bench, tb = configured_group()
    group.calibrate(tb, captures=8, samples=10_000)
    tb2 = group.sample_rate_to_timebase(250, psdk.SAMPLE_RATE.MSPS)
    group.run_simple_block_capture(tb2, 1000, align=False)        # restarts the counters
    try:
        group.run_simple_block_capture(tb, 10_000)
    except MultiScopeError as exc:
        assert 'restarted' in str(exc) and 'calibrate() again' in str(exc)
    else:
        raise AssertionError('expected MultiScopeError')
    group.run_simple_block_capture(tb2, 1000, align=False)        # restart again
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        group.run_simple_block_capture(tb, 10_000, strict=False)
    assert any('restarted' in str(w.message) for w in caught)
    info = group.last_alignment
    assert info.mode == 'latency'
    assert info.shift_samples[1] == group.calibration.followers[0].margin_samples
    # a fresh calibration makes it exact again
    group.calibrate(tb, captures=8, samples=10_000)
    data, t = group.run_simple_block_capture(tb, 10_000)
    assert group.last_alignment.mode == 'timestamp'
    assert abs(edge_skew_ns(data, t)) <= 0.6 * DT


def test_post_trigger_window_too_short_for_the_latency_raises():
    group, _, tb = configured_group()
    group.calibrate(tb, captures=8, samples=10_000)
    try:
        group.run_simple_block_capture(tb, 1000, pre_trig_percent=90)
    except MultiScopeError as exc:
        assert 'pre-trigger' in str(exc)
    else:
        raise AssertionError('expected MultiScopeError')


def test_buffers_stay_pinned_on_the_group_until_the_next_capture():
    group, _, tb = configured_group()
    group.run_simple_block_capture(tb, 1000, align=False)
    first = group._buffers  # pylint: disable=protected-access
    assert first[0] is group[0].buffers and first[1] is group[1].buffers
    group.run_simple_block_capture(tb, 1000, align=False)
    assert group._buffers[0] is group[0].buffers and group._buffers[0] is not first[0]  # pylint: disable=protected-access


def test_calibration_json_round_trip_and_serial_check():
    group, _, tb = configured_group()
    cal = group.calibrate(tb, captures=8, samples=10_000)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'cal.json')
        cal.save(path)
        with open(path, encoding='utf-8') as fh:
            raw = json.load(fh)
        assert raw['serials'] == [MASTER, FOLLOWER]
        loaded = Calibration.load(path)
        assert loaded == cal
        assert group.load_calibration(path) == cal
        other, _, _ = configured_group(FakeBench())
        other.serials = [MASTER, 'CC000/0003']
        try:
            other.load_calibration(path)
        except MultiScopeError:
            pass
        else:
            raise AssertionError('serial mismatch must be refused')


if __name__ == '__main__':
    import sys
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn()
                print(f'PASS {name}')
            except Exception as exc:  # pylint: disable=broad-except
                failures += 1
                print(f'FAIL {name}: {exc!r}')
    print(f'{failures} failure(s)')
    sys.exit(1 if failures else 0)
