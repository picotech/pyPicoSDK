"""Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.

Hardware validation for pypicosdk.MultiScope: two PicoScope 6000E units on the bench.

Skipped unless PYPICOSDK_MULTISCOPE_SERIALS names the units, master first:

    set PYPICOSDK_MULTISCOPE_SERIALS=JR001/001,JR001/002      (Windows)
    export PYPICOSDK_MULTISCOPE_SERIALS=JR001/001,JR001/002   (Linux/macOS)

Wiring (see examples/multiscope/README.md): a 10 MHz reference into every
REF IN, master AUX I/O to follower AUX I/O, master AWG through a tee to
Channel A of both scopes with equal-length leads. Both channels run 50 ohm,
+/-500 mV so any 6000E model can be either unit.

Runs under pytest, or standalone: python tests/multiscope_hw_validation.py
"""
import os
import warnings

import numpy as np
import pytest

import pypicosdk as psdk
from pypicosdk.multiscope import _rising_edge_time

SERIALS = [s.strip() for s in os.environ.get('PYPICOSDK_MULTISCOPE_SERIALS', '').split(',')
           if s.strip()]
pytestmark = pytest.mark.skipif(
    len(SERIALS) < 2, reason='set PYPICOSDK_MULTISCOPE_SERIALS=master,follower to run')

CH = psdk.CHANNEL.A
SAMPLES = 10_000
RATE_MSPS = 500


def edge_skew_ns(data, t):
    em = _rising_edge_time(data[0][CH], t)
    ef = _rising_edge_time(data[1][CH], t, em)
    assert em is not None and ef is not None, 'no edge found: is the AWG on the tee?'
    return em - ef


@pytest.fixture(scope='module')
def bench():
    group = psdk.MultiScope(SERIALS)
    group.open_unit()
    group.set_channel(CH, range=psdk.RANGE.mV500, coupling=psdk.COUPLING.DC_50OHM)
    group.set_siggen(frequency=1_000, pk2pk=1.8, wave_type=psdk.WAVEFORM.SQUARE)
    group.set_simple_trigger(CH, threshold=0)
    timebases = group.sample_rate_to_timebase(RATE_MSPS, psdk.SAMPLE_RATE.MSPS)
    interval_ns = group[0].get_timebase(timebases[0], SAMPLES)['Interval(ns)']
    yield group, timebases, interval_ns
    group.close_unit()


def test_reference_lock_reported(bench):
    group, _, _ = bench
    assert group.wait_for_lock(5.0), f'not all locked: {group.reference_status}'


def test_uncalibrated_capture_shows_the_aux_latency(bench):
    group, tb, interval_ns = bench
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        data, t = group.run_simple_block_capture(tb, SAMPLES, timeout_s=5)
    assert any(isinstance(w.message, psdk.MultiScopeWarning) for w in caught)
    assert group.last_alignment.mode == 'none'
    skew = edge_skew_ns(data, t)
    assert skew > 10 * interval_ns, f'expected a visible AUX latency, got {skew:.1f} ns'


def test_calibration_quality(bench):
    group, tb, interval_ns = bench
    cal = group.calibrate(tb, channel=CH, captures=64, samples=SAMPLES, timeout_s=10)
    fc = cal.followers[0]
    assert fc.timestamp_offset_std < 0.5, f'time stamps do not track: {fc.timestamp_offset_std}'
    assert 0 < fc.latency_ns < 100_000
    assert fc.latency_min_ns <= fc.latency_ns <= fc.latency_max_ns
    assert fc.margin_samples >= 8
    assert len(fc.lag_ns) == 64
    assert cal.interval_ns == interval_ns


def test_block_captures_align_to_within_a_sample(bench):
    group, tb, interval_ns = bench
    if group.calibration is None:
        group.calibrate(tb, channel=CH, captures=64, samples=SAMPLES, timeout_s=10)
    skews = []
    for _ in range(10):
        data, t = group.run_simple_block_capture(tb, SAMPLES, timeout_s=5)
        assert group.last_alignment.mode == 'timestamp'
        assert data[0][CH].shape == data[1][CH].shape == (SAMPLES,)
        skews.append(edge_skew_ns(data, t))
    skews = np.array(skews)
    assert abs(skews.mean()) < interval_ns, f'mean skew {skews.mean():.2f} ns'
    assert skews.std() < 0.5 * interval_ns, f'skew std {skews.std():.2f} ns'


def test_rapid_block_segments_align(bench):
    group, tb, interval_ns = bench
    if group.calibration is None:
        group.calibrate(tb, channel=CH, captures=64, samples=SAMPLES, timeout_s=10)
    data, t = group.run_simple_rapid_block_capture(tb, SAMPLES, captures=20, timeout_s=5)
    assert group.last_alignment.mode == 'timestamp'
    assert data[0][CH].shape == data[1][CH].shape == (20, SAMPLES)
    skews = np.array([_rising_edge_time(data[0][CH][i], t)
                      - _rising_edge_time(data[1][CH][i], t, _rising_edge_time(data[0][CH][i], t))
                      for i in range(20)])
    assert abs(skews.mean()) < interval_ns and skews.std() < 0.5 * interval_ns


def test_timebase_change_is_detected_and_recalibration_recovers(bench):
    group, tb, interval_ns = bench
    if group.calibration is None:
        group.calibrate(tb, channel=CH, captures=64, samples=SAMPLES, timeout_s=10)
    tb2 = group.sample_rate_to_timebase(RATE_MSPS // 2, psdk.SAMPLE_RATE.MSPS)
    with pytest.raises(psdk.MultiScopeError):
        group.run_simple_block_capture(tb2, SAMPLES, timeout_s=5)          # wrong interval
    group.run_simple_block_capture(tb2, SAMPLES, timeout_s=5, align=False)  # restarts counters
    with pytest.raises(psdk.MultiScopeError):
        group.run_simple_block_capture(tb, SAMPLES, timeout_s=5)           # restart detected
    group.calibrate(tb, channel=CH, captures=32, samples=SAMPLES, timeout_s=10)
    data, t = group.run_simple_block_capture(tb, SAMPLES, timeout_s=5)
    assert group.last_alignment.mode == 'timestamp'
    assert abs(edge_skew_ns(data, t)) < interval_ns


if __name__ == '__main__':
    import sys
    sys.exit(pytest.main([__file__, '-v', '-s']))
