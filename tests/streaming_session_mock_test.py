"""Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.

Mock-driver tests for StreamingSession - no hardware needed.

Covers: 6000a-generation double-buffer rotation and hot-swap, transient
starvation handling (status 407), auto-stop draining, poll pacing state,
ps5000a single-buffer + int8 unscaled routing + overflow bitmask decode,
RATIO_MODE.NONE normalisation, and the construction-time capability walls.

Runs under pytest, or standalone: python tests/streaming_session_mock_test.py
"""
import warnings

import numpy as np

import pypicosdk as psdk
from pypicosdk.streaming import StreamingSession
from pypicosdk.common import PicoSDKException


class Fake6000a:
    """6000a-generation mock: FIFO buffer registration + scripted polls."""
    _unit_prefix_n = 'ps6000a'
    resolution = 0

    def __init__(self, script, channels=(0,)):
        self.channel_db = {ch: object() for ch in channels}
        self.script = script
        self.poll_n = 0
        self.registrations = []   # (channel, samples, action, id(buffer))
        self.buffers = []         # registered arrays in ADD order
        self.stopped = False
        self.run_kwargs = None

    def set_data_buffer(self, channel, samples, segment=0, datatype=1,
                        ratio_mode=None, action=None, buffer=None):
        self.registrations.append((channel, samples, action,
                                   None if buffer is None else id(buffer)))
        if samples == 0:
            return None
        if buffer is None:
            buffer = np.zeros(samples, dtype=np.int16)
        self.buffers.append(buffer)
        return buffer

    def run_streaming(self, **kwargs):
        self.run_kwargs = kwargs
        return kwargs['sample_interval']

    def get_streaming_latest_values_multi(self, requests):
        i = min(self.poll_n, len(self.script) - 1)
        self.poll_n += 1
        entry = self.script[i]
        if entry['n'] > 0:
            buf = self.buffers[entry['Buffer index'] % 2]
            buf[entry['start']:entry['start'] + entry['n']] = entry['fill']
        return {
            'status': entry.get('status', 0),
            'channels': [{
                'channel': ch,
                'no of samples': entry.get(f'n{ch}', entry['n']),
                'Buffer index': entry['Buffer index'],
                'start index': entry['start'],
                'overflowed?': entry.get('overflow', 0),
            } for ch, _, _ in requests],
            'triggered at': 0,
            'triggered?': 0,
            'auto stopped?': entry.get('auto_stop', 0),
        }

    def stop(self):
        self.stopped = True


class Fake5000a:
    """ps5000a mock: single overview buffer, callback-style poll dict."""
    _unit_prefix_n = 'ps5000a'
    resolution = 0  # RESOLUTION.BIT_8

    def __init__(self, script, channels=(0, 1)):
        self.channel_db = {ch: object() for ch in channels}
        self.script = script
        self.poll_n = 0
        self.unscaled_calls = []
        self.std_calls = []
        self.buffers = {}
        self.stopped = False
        self.run_kwargs = None

    def set_unscaled_data_buffer(self, channel, samples, segment=0,
                                 ratio_mode=None, buffer=None):
        self.unscaled_calls.append((channel, samples))
        buf = np.zeros(samples, dtype=np.int8)
        self.buffers[channel] = buf
        return buf

    def set_data_buffer(self, channel, samples, segment=0, datatype=None,
                        ratio_mode=None, action=None, buffer=None):
        self.std_calls.append((channel, samples))
        buf = np.zeros(samples, dtype=np.int16)
        self.buffers[channel] = buf
        return buf

    def run_streaming(self, **kwargs):
        self.run_kwargs = kwargs
        return kwargs['sample_interval']

    def get_streaming_latest_values(self):
        i = min(self.poll_n, len(self.script) - 1)
        self.poll_n += 1
        e = self.script[i]
        if e['n'] > 0:
            for ch, buf in self.buffers.items():
                buf[e['start']:e['start'] + e['n']] = e['fill'] + ch
        return {
            'status': e.get('status', 0),
            'no of samples': e['n'],
            'Buffer index': 0,
            'start index': e['start'],
            'overflowed?': e.get('overflow', 0),
            'triggered at': 0,
            'triggered?': 0,
            'auto stopped?': e.get('auto_stop', 0),
        }

    def stop(self):
        self.stopped = True


def _session(scope, **kwargs):
    defaults = dict(sample_interval=100, time_units=psdk.TIME_UNIT.NS,
                    samples_per_buffer=1000, poll_interval=0.001)
    defaults.update(kwargs)
    return StreamingSession(scope, **defaults)


def test_rotation_data_integrity_and_auto_stop_drain():
    script = [
        {'n': 100, 'Buffer index': 0, 'start': 0, 'fill': 11},
        {'n': 50, 'Buffer index': 0, 'start': 100, 'fill': 22},
        {'n': 80, 'Buffer index': 1, 'start': 0, 'fill': 33},   # rotation
        {'n': 40, 'Buffer index': 1, 'start': 80, 'fill': 44, 'auto_stop': 1},
        {'n': 0, 'Buffer index': 0, 'start': 0, 'fill': 0, 'auto_stop': 1},
    ]
    scope = Fake6000a(script)
    sess = _session(scope)
    chunks = list(sess)

    assert len(chunks) == 4
    assert all(np.all(c.data[0] == v) for c, v in zip(chunks, (11, 22, 33, 44)))
    assert [len(c.data[0]) for c in chunks] == [100, 50, 80, 40]
    assert [c.auto_stopped for c in chunks] == [False, False, False, True]
    assert scope.stopped
    assert sess.total_samples[0] == 270
    # CLEAR_ALL + two initial ADDs, then exactly one hot-swap re-ADD of the
    # vacated buffer (index 0) after the rotation flip
    adds_after_start = [r for r in scope.registrations[3:] if r[1] > 0]
    assert len(adds_after_start) == 1
    assert adds_after_start[0][3] == id(scope.buffers[0])
    # chunks are copies, never views into driver buffers
    assert not np.shares_memory(chunks[0].data[0], scope.buffers[0])
    assert scope.run_kwargs['overview_buffer_size'] is None


def test_starvation_is_transient_no_re_add():
    # 407 with no data must NOT trigger any driver registration (a re-ADD
    # would double-register a held buffer and desync the index mapping).
    script = [
        {'n': 0, 'Buffer index': 0, 'start': 0, 'fill': 0, 'status': 407},
        {'n': 0, 'Buffer index': 0, 'start': 0, 'fill': 0, 'status': 407},
        {'n': 20, 'Buffer index': 0, 'start': 0, 'fill': 55},
    ]
    scope = Fake6000a(script)
    sess = _session(scope)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        chunk = next(iter(sess))
    assert np.all(chunk.data[0] == 55)
    assert not [r for r in scope.registrations[3:] if r[1] > 0]
    assert not any('starved' in str(w.message).lower()
                   or 'stalled' in str(w.message).lower() for w in caught)
    sess.stop()


def test_persistent_starvation_warns_once():
    scope = Fake6000a([{'n': 0, 'Buffer index': 0, 'start': 0, 'fill': 0}])
    sess = _session(scope, poll_interval=0.1)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for _ in range(25):   # 25 * 0.1 s simulated > 2 s threshold
            sess._check_starvation(407)
    stall_warnings = [w for w in caught if 'stalled' in str(w.message)]
    assert len(stall_warnings) == 1
    # data resets the counter
    sess._check_starvation(0)
    assert sess._starved_polls == 0


def test_no_rotation_on_zero_sample_entries():
    # Channel 1 delivers nothing (zeroed entry fields) while channel 0 has
    # data; channel 1 must not rotate or contribute stale data.
    script = [
        {'n': 60, 'n1': 0, 'Buffer index': 1, 'start': 0, 'fill': 77},
    ]
    scope = Fake6000a(script, channels=(0, 1))
    sess = _session(scope)
    # put channel 1's tracked index out of phase with the zeroed entry
    chunk = next(iter(sess))
    assert len(chunk.data[1]) == 0
    assert sess._current_index[1] == 0   # untouched by the empty entry
    sess.stop()


def test_ps5000a_int8_routing_overflow_and_walls():
    script = [{'n': 30, 'start': 5, 'fill': 7, 'overflow': 0b10,
               'auto_stop': 1},
              {'n': 0, 'start': 0, 'fill': 0, 'auto_stop': 1}]
    scope5 = Fake5000a(script)
    sess5 = StreamingSession(scope5, sample_interval=1,
                             time_units=psdk.TIME_UNIT.US,
                             datatype=psdk.DATA_TYPE.INT8_T,
                             samples_per_buffer=500, poll_interval=0.001)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        chunks = list(sess5)
    assert len(scope5.unscaled_calls) == 2 and not scope5.std_calls
    assert len(chunks) == 1 and set(chunks[0].data) == {0, 1}
    assert np.all(chunks[0].data[0] == 7) and np.all(chunks[0].data[1] == 8)
    assert chunks[0].data[0].dtype == np.int8
    assert chunks[0].overflowed == [1]          # bitmask decoded: B only
    assert scope5.run_kwargs['overview_buffer_size'] == 500
    assert any('over-range' in str(w.message) for w in caught)


def test_ratio_mode_none_normalised_per_driver():
    # NONE (0) exists only in the ps5000a enum; the 6000a generation spells
    # no-downsampling RAW. The session normalises so both drivers accept it.
    scope = Fake6000a([{'n': 0, 'Buffer index': 0, 'start': 0, 'fill': 0}])
    sess = _session(scope, ratio_mode=psdk.RATIO_MODE.NONE)
    assert sess.ratio_mode == psdk.RATIO_MODE.RAW
    scope5 = Fake5000a([{'n': 0, 'start': 0, 'fill': 0}])
    sess5 = StreamingSession(scope5, sample_interval=1,
                             time_units=psdk.TIME_UNIT.US,
                             ratio_mode=psdk.RATIO_MODE.NONE,
                             samples_per_buffer=100, poll_interval=0.001)
    assert sess5.ratio_mode == psdk.RATIO_MODE.NONE


def test_construction_walls():
    scope5 = Fake5000a([{'n': 0, 'start': 0, 'fill': 0}])

    def raises(fn):
        try:
            fn()
            return False
        except PicoSDKException:
            return True

    assert raises(lambda: StreamingSession(
        scope5, 1, psdk.TIME_UNIT.US, ratio_mode=psdk.RATIO_MODE.AGGREGATE))
    assert raises(lambda: StreamingSession(
        scope5, 1, psdk.TIME_UNIT.US, ratio=2, ratio_mode=psdk.RATIO_MODE.SUM))
    assert raises(lambda: StreamingSession(
        scope5, 1, psdk.TIME_UNIT.US, datatype=psdk.DATA_TYPE.INT32_T))
    assert raises(lambda: StreamingSession(
        scope5, 1, psdk.TIME_UNIT.US, ratio_mode=psdk.RATIO_MODE.DECIMATE))
    assert raises(lambda: StreamingSession(
        scope5, 1, psdk.TIME_UNIT.US, channels=[7]))       # not enabled
    assert raises(lambda: StreamingSession(
        scope5, 1, psdk.TIME_UNIT.US, samples_per_buffer=0))
    assert raises(lambda: StreamingSession(
        scope5, 1, psdk.TIME_UNIT.US, poll_interval=-1))
    assert raises(lambda: StreamingSession(
        scope5, 1, psdk.TIME_UNIT.US, auto_stop=True))     # no post target
    assert raises(lambda: StreamingSession(
        type('S', (), {'_unit_prefix_n': 'ps6000a', 'channel_db': {}})(),
        1, psdk.TIME_UNIT.US))


if __name__ == '__main__':
    for name, fn in sorted(globals().items()):
        if name.startswith('test_'):
            fn()
            print(f"PASS {name}")
    print("all tests passed")
