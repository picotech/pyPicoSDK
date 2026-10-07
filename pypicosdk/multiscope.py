"""
Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.

Multi-scope synchronisation for PicoScope 6000E devices.

`MultiScope` drives two or more 6000E units as one instrument:

 - every unit runs from the same 10 MHz reference on its rear REF IN, so the
   sample clocks never drift apart (the lock state is reported, not enforced)
 - the master triggers on whatever you configure; its AUX I/O is switched to
   TRIGGER_OUT and every follower triggers on the rising edge at its AUX input
 - `calibrate()` measures each follower's AUX trigger latency from a shared
   edge and records the constant offset between the units' hardware trigger
   time-stamp counters
 - every later capture arms the followers with extra pre-trigger samples, then
   cuts each follower's record to the master's window using the two trigger
   time stamps, so the returned arrays line up sample for sample even though
   the AUX trigger path itself jitters by tens of samples

Block and rapid block modes are supported, RAW data only.
"""
import ctypes
import json
import operator
import time
import warnings
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

import numpy as np

from . import constants as cst
from .constants import (
    CHANNEL,
    AUXIO_MODE,
    CLOCK_REFERENCE,
    DATA_TYPE,
    RATIO_MODE,
    SAMPLE_RATE,
    TIME_UNIT,
    TRIGGER_DIR,
    WAVEFORM,
)
from .common import PicoSDKException, _get_literal
from .ps6000a import ps6000a

#: PICO_DEVICE_TIME_STAMP_RESET bit in PICO_TRIGGER_INFO.status: the trigger
#: time-stamp counter restarted since the previous capture (settings changed).
TIME_STAMP_RESET_FLAG = 0x01000000


class MultiScopeError(PicoSDKException):
    """Raised when the scopes in a :class:`MultiScope` group cannot be kept in step."""


class MultiScopeWarning(UserWarning):
    """Warning for captures that ran without de-skew or with a stale calibration."""


@dataclass
class FollowerCalibration:
    """Measured AUX trigger path of one follower relative to the master.

    Attributes:
        serial: Follower serial number.
        latency_ns: Mean time the follower triggers after the master.
        jitter_ns: Standard deviation of that latency (the AUX path jitter).
        latency_min_ns: Smallest latency seen during calibration.
        latency_max_ns: Largest latency seen during calibration.
        timestamp_offset: Constant ``(ts_follower - ts_master) - latency_samples``
            in sample periods. It is what turns two trigger time stamps into the
            exact per-capture lag.
        timestamp_offset_std: Spread of that constant over the calibration
            captures, in samples. Well under one sample when the units are
            locked and the calibration edge was clean.
        margin_samples: Extra samples captured either side of the expected
            follower window to absorb the AUX jitter.
        lag_ns: Raw AUX lag of every calibration capture (histogram material).
        residual_samples: Per-capture ``timestamp_offset`` residual, in samples.
    """
    serial: str
    latency_ns: float
    jitter_ns: float
    latency_min_ns: float
    latency_max_ns: float
    timestamp_offset: float
    timestamp_offset_std: float
    margin_samples: int
    lag_ns: list[float] = field(default_factory=list)
    residual_samples: list[float] = field(default_factory=list)


@dataclass
class Calibration:
    """Result of :meth:`MultiScope.calibrate`, valid for one timebase.

    Attributes:
        serials: Serial numbers in group order (index 0 is the master).
        interval_ns: Sample interval the calibration was measured at.
        timebases: Per-device timebases used.
        channel: Channel that carried the shared calibration edge.
        captures: Number of captures averaged.
        created: ISO-8601 UTC time of the calibration.
        followers: One :class:`FollowerCalibration` per follower, in group
            order (``followers[0]`` is scope index 1).
    """
    serials: list[str]
    interval_ns: float
    timebases: list[int]
    channel: int
    captures: int
    created: str
    followers: list[FollowerCalibration]

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Calibration":
        """Rebuild a calibration from :meth:`to_dict` output."""
        followers = [FollowerCalibration(**f) for f in data["followers"]]
        return cls(**{**data, "followers": followers})

    def save(self, path: str) -> None:
        """Write the calibration to a JSON file."""
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    @classmethod
    def load(cls, path: str) -> "Calibration":
        """Read a calibration written by :meth:`save`."""
        with open(path, "r", encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))


@dataclass
class AlignmentInfo:
    """What the last capture did to line the followers up with the master.

    Every list has one entry per scope in group order; the master's entries
    are zeros. For rapid block captures the entries are numpy arrays with one
    value per segment.

    Attributes:
        mode: ``'timestamp'`` (exact, from the trigger time stamps),
            ``'latency'`` (mean latency only, jitter not removed) or
            ``'none'`` (uncalibrated, nothing shifted).
        lag_ns: Actual time each follower triggered after the master.
        shift_samples: Integer shift applied to each follower record.
        residual_samples: Sub-sample part of the shift that was not applied.
        timestamps: Trigger time-stamp counter of each scope.
        timestamp_reset: True where a scope reported its counter restarted.
        missed_triggers: Driver ``missedTriggers`` per scope.
    """
    mode: str
    lag_ns: list
    shift_samples: list
    residual_samples: list
    timestamps: list
    timestamp_reset: list
    missed_triggers: list


def _rising_edge_time(y: np.ndarray, t: np.ndarray, near: float = 0.0,
                      min_swing: float = 50.0) -> float | None:
    """Time of the mid-level rising crossing nearest ``near``, linearly interpolated.

    Args:
        y: Samples (any unit).
        t: Time axis, same length as ``y``.
        near: Pick the rising crossing closest to this time.
        min_swing: Minimum 5th to 95th percentile swing for ``y`` to count as
            carrying an edge, in the units of ``y``.

    Returns:
        Interpolated crossing time, or ``None`` when no edge is present.
    """
    lo, hi = np.percentile(y, 5), np.percentile(y, 95)
    if hi - lo < min_swing:
        return None
    mid = (lo + hi) / 2
    above = y > mid
    idx = np.flatnonzero(~above[:-1] & above[1:])
    if idx.size == 0:
        return None
    i = idx[np.argmin(np.abs(t[idx] - near))]
    y0, y1 = float(y[i]), float(y[i + 1])
    frac = (mid - y0) / (y1 - y0) if y1 != y0 else 0.0
    return float(t[i] + frac * (t[i + 1] - t[i]))


class MultiScope:
    """Two or more PicoScope 6000E units captured as one synchronised instrument.

    Wire every unit's rear REF IN to the same 10 MHz reference, the master's
    AUX I/O to each follower's AUX I/O, then:

        >>> import pypicosdk as psdk
        >>> group = psdk.MultiScope(["JR001/001", "JR001/002"])   # index 0 = master
        >>> group.open_unit()
        >>> group.set_channel(psdk.CHANNEL.A, range=psdk.RANGE.V1)  # broadcast
        >>> group.set_simple_trigger(psdk.CHANNEL.A, threshold=0)  # master only
        >>> TIMEBASES = group.sample_rate_to_timebase(500, psdk.SAMPLE_RATE.MSPS)
        >>> group.calibrate(TIMEBASES)      # shared edge on Ch A of every scope
        >>> data, time_axis = group.run_simple_block_capture(TIMEBASES, 10_000)
        >>> data[1][psdk.CHANNEL.A]          # follower, aligned to the master grid
        >>> group.close_unit()

    Anything the group does not broadcast is still available per device:
    ``group[1].set_channel(...)`` is the plain :class:`~pypicosdk.ps6000a`
    API. Do not change a follower's trigger yourself; the group owns it.

    Args:
        serials: Serial numbers in the order you want to index them. The first
            is the master, unless ``master`` names another; the rest follow it
            over AUX.
        master: Serial number of the master, or its position in ``serials``.
            That scope moves to index 0 and the followers keep their order, so
            :attr:`serials` shows the resulting index order.
        arm_settle_s: Pause between arming the followers and arming the
            master, so a follower cannot miss the first trigger.
    """

    def __init__(self, serials: list[str], master: str | int | None = None,
                 arm_settle_s: float = 0.005, _scope_factory=None):
        serials = [str(s) for s in serials]
        if len(serials) < 2:
            raise MultiScopeError("MultiScope needs at least two serial numbers")
        if len(set(serials)) != len(serials):
            raise MultiScopeError(f"Duplicate serial numbers in {serials}")
        if master is not None:
            serials.insert(0, serials.pop(self._master_index(serials, master)))
        self.serials: list[str] = serials
        self.arm_settle_s = float(arm_settle_s)
        self._scope_factory = _scope_factory or ps6000a
        self.scopes: list[ps6000a] = []
        self.calibration: Calibration | None = None
        self.last_alignment: AlignmentInfo | None = None
        self._reference: list[CLOCK_REFERENCE | None] = [None] * len(serials)
        self._master_awg_is_reference = False
        self._calibration_stale = False
        self._segments = 1
        self._buffers: list[dict] = []
        self._open = False

    @staticmethod
    def _master_index(serials: list[str], master) -> int:
        """Position of ``master`` (a serial number or an index) in ``serials``."""
        if isinstance(master, str):
            if master.strip() not in serials:
                raise MultiScopeError(
                    f"Master {master!r} is not one of the serial numbers {serials}")
            return serials.index(master.strip())
        try:
            index = operator.index(master)
        except TypeError:
            raise MultiScopeError(
                f"master must be a serial number or an index into serials, not {master!r}") from None
        if not 0 <= index < len(serials):
            raise MultiScopeError(
                f"Master index {index} is out of range for {len(serials)} serial numbers")
        return index

    @staticmethod
    def discover() -> list[str]:
        """Serial numbers of every 6000E the ps6000a driver can see, sorted.

        The driver's own enumeration order changes from run to run, so the
        list is sorted to be stable. Sorted order still says nothing about the
        wiring: name the unit whose AUX drives the others (and whose AWG is
        the test signal) with ``MultiScope(serials, master=...)``.
        """
        try:
            count, serials, _ = ps6000a().get_enumerated_units()
        except PicoSDKException:
            return []
        if not count:
            return []
        return sorted(serial.strip() for serial in serials.split(',') if serial.strip())

    # ------------------------------------------------------------------ basics
    def __getitem__(self, index: int) -> ps6000a:
        return self.scopes[index]

    def __len__(self) -> int:
        return len(self.serials)

    def __iter__(self):
        return iter(self.scopes)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close_unit()

    @property
    def master(self) -> ps6000a:
        """The scope at index 0: it owns the trigger and drives AUX out."""
        self._require_open()
        return self.scopes[0]

    @property
    def followers(self) -> list[ps6000a]:
        """Scopes at index 1 onwards: they trigger from the master's AUX pulse."""
        self._require_open()
        return self.scopes[1:]

    @property
    def stimulus_scope(self) -> ps6000a:
        """The scope whose signal generator is free to drive a test signal.

        The master, unless :meth:`use_master_awg_as_reference` turned the
        master's AWG into the 10 MHz reference; then it is the first follower.
        """
        self._require_open()
        return self.scopes[1] if self._master_awg_is_reference else self.scopes[0]

    def _require_open(self) -> None:
        if not self._open:
            raise MultiScopeError("MultiScope is not open: call open_unit() first")

    # ---------------------------------------------------------------- lifecycle
    def open_unit(self, resolution=0) -> None:
        """Open every scope, register the reference-lock callback and set up AUX.

        Args:
            resolution: Resolution for every device, as accepted by
                :meth:`pypicosdk.ps6000a.open_unit` (enum or ``'8bit'`` style
                literal).
        """
        if self._open:
            raise MultiScopeError("MultiScope is already open")
        scopes = []
        try:
            for serial in self.serials:
                scope = self._scope_factory()
                scope.open_unit(serial_number=serial, resolution=resolution)
                scopes.append(scope)
        except PicoSDKException as exc:
            for scope in scopes:
                try:
                    scope.close_unit()
                except PicoSDKException:
                    pass
            raise MultiScopeError(
                f"Could not open scope {self.serials[len(scopes)]!r}: {exc}") from exc
        self.scopes = scopes
        self._open = True

        for index, scope in enumerate(self.scopes):
            scope.set_external_reference_interaction_callback(self._make_reference_callback(index))

        # Master drives AUX; followers listen on it and wait indefinitely.
        self.scopes[0].set_aux_io_mode(AUXIO_MODE.TRIGGER_OUT)
        for scope in self.scopes[1:]:
            scope.set_aux_io_mode(AUXIO_MODE.INPUT)
            scope.set_simple_trigger(CHANNEL.TRIGGER_AUX, threshold=0, threshold_unit='adc',
                                     direction=TRIGGER_DIR.RISING, auto_trigger=0)

    def _make_reference_callback(self, index: int):
        def _on_reference(handle, status, reference):  # pylint: disable=unused-argument
            self._reference[index] = CLOCK_REFERENCE(reference)
        return _on_reference

    def close_unit(self) -> None:
        """Unregister callbacks, return AUX to input and close every scope."""
        for scope in self.scopes:
            for step in (lambda s=scope: s.set_external_reference_interaction_callback(None),
                         lambda s=scope: s.set_aux_io_mode(AUXIO_MODE.INPUT),
                         lambda s=scope: s.close_unit()):
                try:
                    step()
                except (PicoSDKException, OSError):
                    pass
        self.scopes = []
        self._buffers = []
        self._open = False

    # -------------------------------------------------------------- reference
    @property
    def reference_status(self) -> list[CLOCK_REFERENCE | None]:
        """Clock each scope reports running from, in group order.

        ``EXTERNAL_REF`` means locked to the 10 MHz on REF IN. ``None`` means
        the driver has not reported yet (it takes a few hundred milliseconds
        after :meth:`open_unit`); use :meth:`wait_for_lock`.
        """
        return list(self._reference)

    def wait_for_lock(self, timeout_s: float = 5.0) -> bool:
        """Wait until every scope reports the external reference.

        Args:
            timeout_s: Give up after this many seconds.

        Returns:
            True when every scope is on ``EXTERNAL_REF``, else False.
        """
        deadline = time.perf_counter() + timeout_s
        while True:
            if all(ref == CLOCK_REFERENCE.EXTERNAL_REF for ref in self._reference):
                return True
            if time.perf_counter() >= deadline:
                return False
            time.sleep(0.02)

    def use_master_awg_as_reference(self, frequency: float = 10e6, pk2pk: float = 1.0) -> None:
        """Turn the master's signal generator into the 10 MHz reference.

        Connect the master AWG output to every follower's REF IN. The AWG is
        clocked from the master's own timebase, so the followers lock to the
        master. The master AWG is then no longer free as a test signal:
        :meth:`set_siggen` and :attr:`stimulus_scope` switch to the first
        follower's generator.

        Args:
            frequency: Reference frequency in Hz. The 6000E expects 10 MHz.
            pk2pk: Open-circuit amplitude in volts. REF IN is high impedance,
                AC coupled and accepts 200 mV to 3.3 V pk-pk.
        """
        self._require_open()
        self.scopes[0].set_siggen(frequency=frequency, pk2pk=pk2pk, wave_type=WAVEFORM.SINE)
        self._master_awg_is_reference = True

    # ----------------------------------------------------------- configuration
    def set_channel(self, channel, range=cst.RANGE.V1, enabled=True,  # pylint: disable=W0622
                    coupling=cst.COUPLING.DC, offset=0.0,
                    bandwidth=cst.BANDWIDTH_CH.BW_FULL, probe_scale=1.0) -> None:
        """Configure the same channel on every scope (see ``ps6000a.set_channel``).

        Use ``group[i].set_channel(...)`` instead when the models differ, for
        example a 6428E-D that only accepts 50 ohm coupling.
        """
        self._require_open()
        for scope in self.scopes:
            scope.set_channel(channel, range=range, enabled=enabled, coupling=coupling,
                              offset=offset, bandwidth=bandwidth, probe_scale=probe_scale)

    def set_simple_trigger(self, channel, threshold=0, threshold_unit='mv', enable=True,
                           direction=TRIGGER_DIR.RISING, delay=0, auto_trigger=0) -> None:
        """Set the master's simple trigger (see ``ps6000a.set_simple_trigger``).

        The followers keep their AUX trigger. ``auto_trigger`` on the master
        still fires the followers, because a forced trigger is also emitted on
        AUX out.
        """
        self._require_open()
        self._reject_aux_source(channel)
        self.scopes[0].set_simple_trigger(channel, threshold=threshold, threshold_unit=threshold_unit,
                                          enable=enable, direction=direction, delay=delay,
                                          auto_trigger=auto_trigger)

    def set_advanced_trigger(self, channel, *args, **kwargs) -> None:
        """Set an advanced trigger on the master (see ``ps6000a.set_advanced_trigger``)."""
        self._require_open()
        self._reject_aux_source(channel)
        self.scopes[0].set_advanced_trigger(channel, *args, **kwargs)

    @staticmethod
    def _reject_aux_source(channel) -> None:
        if _get_literal(channel, cst.channel_map) == CHANNEL.TRIGGER_AUX:
            raise MultiScopeError(
                "The master's AUX connector is the trigger OUTPUT for the followers, "
                "so the master cannot trigger from TRIGGER_AUX")

    def set_siggen(self, frequency: float, pk2pk: float, wave_type, **kwargs) -> dict:
        """Drive the free signal generator (see ``ps6000a.set_siggen``).

        Goes to the master's AWG, or to the first follower's when the master
        AWG is the 10 MHz reference.
        """
        return self.stimulus_scope.set_siggen(frequency, pk2pk, wave_type, **kwargs)

    # ---------------------------------------------------------------- timebase
    def sample_rate_to_timebase(self, sample_rate: float,
                                unit=SAMPLE_RATE.MSPS) -> tuple[int, ...]:
        """One timebase per scope for the requested rate, intervals verified equal.

        Different 6000E models number their timebases differently (a 6428E-D
        reaches 10 GS/s where a 6426E stops at 5 GS/s), so the same rate can
        be a different integer on each unit. Call it after enabling channels.

        Raises:
            MultiScopeError: If the devices cannot all reach the same interval.
        """
        return self._timebases(lambda s: s.sample_rate_to_timebase(sample_rate, unit))

    def interval_to_timebase(self, interval: float, unit=TIME_UNIT.S) -> tuple[int, ...]:
        """One timebase per scope for the requested sample interval, verified equal."""
        return self._timebases(lambda s: s.interval_to_timebase(interval, unit))

    def _timebases(self, convert) -> tuple[int, ...]:
        self._require_open()
        for serial, scope in zip(self.serials, self.scopes):
            if not scope.channel_db:
                raise MultiScopeError(
                    f"Scope {serial} has no channel enabled; enable channels before "
                    "choosing a timebase")
        timebases = tuple(int(convert(scope)) for scope in self.scopes)
        intervals = [scope.get_timebase(tb, 1)['Interval(ns)']
                     for scope, tb in zip(self.scopes, timebases)]
        if max(intervals) - min(intervals) > 1e-6:
            listing = ", ".join(f"{serial}: timebase {tb} = {iv:.4g} ns"
                                for serial, tb, iv in zip(self.serials, timebases, intervals))
            raise MultiScopeError(
                "The scopes cannot all sample at the same interval with these settings "
                f"({listing}); choose a rate every model can reach")
        return timebases

    def _check_timebases(self, timebases) -> tuple[int, ...]:
        if isinstance(timebases, (int, np.integer)):
            raise MultiScopeError(
                "Pass the per-device timebases from group.sample_rate_to_timebase(...), "
                "not a single integer")
        timebases = tuple(int(tb) for tb in timebases)
        if len(timebases) != len(self.scopes):
            raise MultiScopeError(
                f"Expected {len(self.scopes)} timebases (one per scope), got {len(timebases)}")
        return timebases

    def _interval_ns(self, timebases, samples: int) -> float:
        intervals = [scope.get_timebase(tb, samples)['Interval(ns)']
                     for scope, tb in zip(self.scopes, timebases)]
        if max(intervals) - min(intervals) > 1e-6:
            listing = ", ".join(f"{serial}: {iv:.4g} ns"
                                for serial, iv in zip(self.serials, intervals))
            raise MultiScopeError(f"Sample intervals differ between scopes ({listing})")
        return float(intervals[0])

    # ------------------------------------------------------------ acquisition
    def _set_segments(self, captures: int) -> None:
        if captures == self._segments:
            return
        for scope in self.scopes:
            scope.memory_segments(captures)
            scope.set_no_of_captures(captures)
        self._segments = captures

    @staticmethod
    def _poll_ready(scope) -> bool:
        ready = ctypes.c_int16()
        scope._call_attr_function('IsReady', scope.handle, ctypes.byref(ready))  # pylint: disable=protected-access
        return bool(ready.value)

    def _stop_all(self) -> None:
        for scope in self.scopes:
            try:
                scope.stop()
            except PicoSDKException:
                pass

    def _wait_ready_all(self, timeout_s: float | None) -> None:
        pending = list(range(len(self.scopes)))
        start = time.perf_counter()
        try:
            while pending:
                for index in list(pending):
                    if self._poll_ready(self.scopes[index]):
                        pending.remove(index)
                if not pending:
                    return
                if timeout_s is not None and time.perf_counter() - start > timeout_s:
                    self._stop_all()
                    waiting = ", ".join(self.serials[i] for i in pending)
                    raise MultiScopeError(
                        f"Timed out after {timeout_s} s waiting for a trigger on {waiting}")
                time.sleep(0.0005)
        except KeyboardInterrupt:
            self._stop_all()
            raise

    def _acquire(self, timebases, samples_per_scope: list[int], pre_per_scope: list[int],
                 captures: int, timeout_s: float | None, datatype) -> tuple[list[dict], list[list[dict]]]:
        """Arm followers, then the master; wait; fetch data and trigger info from all.

        Returns:
            ``(buffers, infos)``: per-scope channel->array dicts (pinned on the
            instance for the driver's sake) and per-scope lists of trigger-info
            dicts, one per segment.
        """
        self._set_segments(captures)
        rapid = captures > 1
        # Register the new buffers before dropping the old ones: the driver
        # keeps the previous pointers until CLEAR_ALL runs inside this call.
        new_buffers = []
        for scope, n in zip(self.scopes, samples_per_scope):
            new_buffers.append(scope.set_data_buffer_for_enabled_channels(
                n, datatype=datatype, captures=captures if rapid else 0))
        self._buffers = new_buffers

        order = list(range(1, len(self.scopes))) + [0]
        for index in order:
            if index == 0 and len(self.scopes) > 1:
                time.sleep(self.arm_settle_s)
            self.scopes[index].run_block_capture(
                timebases[index], samples_per_scope[index], pre_trig_samples=pre_per_scope[index])
        self._wait_ready_all(timeout_s)

        infos = []
        for scope, n in zip(self.scopes, samples_per_scope):
            if rapid:
                scope.get_values_bulk(n, 0, captures - 1, ratio_mode=RATIO_MODE.RAW,
                                      wait_for_ready=False)
            else:
                scope.get_values(n, wait_for_ready=False)
            infos.append(scope.get_trigger_info(0, captures))
        return self._buffers, infos

    def _time_axis(self, samples: int, pre: int, interval_ns: float, time_unit) -> np.ndarray:
        scalar = cst.TimeUnitStd_M['ns'] / cst.TimeUnitStd_M[time_unit]
        return (np.arange(samples) - pre) * (interval_ns / scalar)

    # ------------------------------------------------------------- calibration
    def calibrate(self, timebases, channel=CHANNEL.A, captures: int = 64, samples: int = 10_000,
                  pre_trig_percent: float = 50, timeout_s: float | None = 10.0,
                  min_swing_mv: float = 50.0, margin_factor: float = 1.5) -> Calibration:
        """Measure each follower's AUX trigger latency and time-stamp offset.

        Feed the same edge into ``channel`` of every scope (a BNC tee from a
        signal generator with equal-length leads) and make the master trigger
        on it. The group takes ``captures`` rapid-block segments at the given
        timebases with identical windows on every scope, finds the edge in each
        record, and derives per follower: the mean latency, its jitter, the
        constant offset between the follower's and the master's trigger
        time-stamp counters, and a margin that covers the jitter.

        The signal's period must be longer than the capture window so exactly
        one rising edge is in view. The result is valid for this timebase only
        and until any setting that restarts the time-stamp counters changes
        (the timebase does; channel settings and re-applying the same trigger
        do not). Captures detect a restart and refuse to mis-align.

        Args:
            timebases: Per-device timebases from :meth:`sample_rate_to_timebase`.
            channel: Channel carrying the shared edge on every scope.
            captures: Rapid-block segments to average.
            samples: Samples per segment.
            pre_trig_percent: Pre-trigger percentage for the calibration windows.
            timeout_s: Trigger wait limit per capture set.
            min_swing_mv: Minimum edge amplitude to accept, in mV.
            margin_factor: Margin = this times the largest latency excursion
                seen, plus eight samples.

        Returns:
            The :class:`Calibration`, also stored in :attr:`calibration`.
        """
        self._require_open()
        timebases = self._check_timebases(timebases)
        channel = _get_literal(channel, cst.channel_map)
        for serial, scope in zip(self.serials, self.scopes):
            if channel not in scope.channel_db:
                raise MultiScopeError(
                    f"Calibration channel {CHANNEL(channel).name} is not enabled on scope {serial}")
        if captures < 2:
            raise MultiScopeError("calibrate() needs at least two captures")
        interval_ns = self._interval_ns(timebases, samples)
        pre = int(samples * pre_trig_percent / 100)
        t_axis = (np.arange(samples) - pre) * interval_ns

        buffers, infos = self._acquire(timebases, [samples] * len(self.scopes),
                                       [pre] * len(self.scopes), captures, timeout_s,
                                       DATA_TYPE.INT16_T)
        # (captures, samples) arrays in mV, one per scope
        records = [scope._adc_to_({channel: buf[channel]}, unit='mv')[channel]  # pylint: disable=protected-access
                   for scope, buf in zip(self.scopes, buffers)]
        master_edges = [_rising_edge_time(records[0][i], t_axis, 0.0, min_swing_mv)
                        for i in range(captures)]
        if any(edge is None for edge in master_edges):
            raise MultiScopeError(
                f"No calibration edge found on the master's channel {CHANNEL(channel).name}: "
                "connect the shared edge to that channel and trigger the master on it")
        master_ts = np.array([info['timeStampCounter'] for info in infos[0]], dtype=np.float64)

        followers = []
        for k in range(1, len(self.scopes)):
            edges = [_rising_edge_time(records[k][i], t_axis, master_edges[i], min_swing_mv)
                     for i in range(captures)]
            if any(edge is None for edge in edges):
                raise MultiScopeError(
                    f"No calibration edge found on scope {self.serials[k]} channel "
                    f"{CHANNEL(channel).name}: is the shared edge connected, and is the window "
                    "long enough to contain the follower's delayed copy of it?")
            lag_ns = np.array(master_edges) - np.array(edges)
            lag_samples = lag_ns / interval_ns
            ts = np.array([info['timeStampCounter'] for info in infos[k]], dtype=np.float64)
            offsets = (ts - master_ts) - lag_samples
            offset = float(np.mean(offsets))
            offset_std = float(np.std(offsets))
            if offset_std > 0.5:
                raise MultiScopeError(
                    f"Trigger time stamps of scope {self.serials[k]} do not track the master "
                    f"(spread {offset_std:.2f} samples): check the 10 MHz reference on both "
                    "units and that the same edge reaches both calibration channels")
            excursion = float(np.max(np.abs(lag_samples - lag_samples.mean())))
            margin = int(np.ceil(excursion * margin_factor)) + 8
            followers.append(FollowerCalibration(
                serial=self.serials[k],
                latency_ns=float(lag_ns.mean()),
                jitter_ns=float(lag_ns.std()),
                latency_min_ns=float(lag_ns.min()),
                latency_max_ns=float(lag_ns.max()),
                timestamp_offset=offset,
                timestamp_offset_std=offset_std,
                margin_samples=margin,
                lag_ns=[float(x) for x in lag_ns],
                residual_samples=[float(x) for x in offsets - offset],
            ))

        self._set_segments(1)
        self._calibration_stale = False
        self.calibration = Calibration(
            serials=list(self.serials),
            interval_ns=interval_ns,
            timebases=list(timebases),
            channel=int(channel),
            captures=captures,
            created=datetime.now(timezone.utc).isoformat(timespec='seconds'),
            followers=followers,
        )
        return self.calibration

    def load_calibration(self, path: str) -> Calibration:
        """Load a saved :class:`Calibration` and check it belongs to this group."""
        cal = Calibration.load(path)
        if cal.serials != list(self.serials):
            raise MultiScopeError(
                f"Calibration in {path} is for {cal.serials}, this group is {self.serials}")
        self.calibration = cal
        self._calibration_stale = False
        return cal

    # ---------------------------------------------------------------- captures
    STALE_MESSAGE = ("The trigger time-stamp counters restarted since calibrate() (a setting "
                     "such as the timebase changed, or the reference lock changed); call "
                     "calibrate() again")

    def _plan(self, timebases, samples: int, pre: int, interval_ns: float, align: bool,
              strict: bool = True):
        """Per-scope (samples, pre-trigger samples) and whether time stamps will be used."""
        cal = self.calibration if align else None
        if cal is not None and abs(cal.interval_ns - interval_ns) > 1e-6:
            raise MultiScopeError(
                f"Calibration was measured at {cal.interval_ns:.4g} ns per sample but this "
                f"capture runs at {interval_ns:.4g} ns; call calibrate() at this timebase")
        if cal is not None and self._calibration_stale and strict:
            raise MultiScopeError(self.STALE_MESSAGE)
        n_per, pre_per, base_shift = [samples], [pre], [0]
        if cal is None:
            if align:
                warnings.warn("MultiScope has no calibration: follower data is returned "
                              "un-shifted. Call calibrate() first to de-skew.", MultiScopeWarning)
            n_per += [samples] * (len(self.scopes) - 1)
            pre_per += [pre] * (len(self.scopes) - 1)
            base_shift += [0] * (len(self.scopes) - 1)
            return n_per, pre_per, base_shift, False
        for fc in cal.followers:
            shift = int(round(fc.latency_ns / interval_ns)) + fc.margin_samples
            n_f = samples + 2 * fc.margin_samples
            pre_f = pre + shift
            if pre_f > n_f:
                raise MultiScopeError(
                    f"Follower {fc.serial} needs {pre_f} pre-trigger samples to cover the master's "
                    f"window but only {n_f} are captured: increase samples or reduce "
                    "pre_trig_percent")
            n_per.append(n_f)
            pre_per.append(pre_f)
            base_shift.append(shift)
        return n_per, pre_per, base_shift, True

    def _align(self, buffers, infos, samples, base_shift, interval_ns, use_timestamps, strict,
               captures):
        """Cut follower records to the master window; build the AlignmentInfo."""
        n_scopes = len(self.scopes)
        cal = self.calibration
        seg = np.arange(captures)
        zeros = np.zeros(captures)
        lag_ns = [zeros.copy()]
        shifts = [np.zeros(captures, dtype=int)]
        residuals = [zeros.copy()]
        timestamps = [np.array([i['timeStampCounter'] for i in infos[0]], dtype=np.int64)]
        resets = [np.array([bool(i['status'] & TIME_STAMP_RESET_FLAG) for i in infos[0]])]
        missed = [np.array([i['missedTriggers'] for i in infos[0]], dtype=np.int64)]
        out = [buffers[0]]
        mode = 'timestamp' if use_timestamps else 'none'

        for k in range(1, n_scopes):
            ts = np.array([i['timeStampCounter'] for i in infos[k]], dtype=np.int64)
            reset = np.array([bool(i['status'] & TIME_STAMP_RESET_FLAG) for i in infos[k]])
            timestamps.append(ts)
            resets.append(reset)
            missed.append(np.array([i['missedTriggers'] for i in infos[k]], dtype=np.int64))
            if not use_timestamps:
                lag_ns.append(np.full(captures, np.nan))
                shifts.append(np.zeros(captures, dtype=int))
                residuals.append(zeros.copy())
                out.append(buffers[k])
                continue

            fc = cal.followers[k - 1]
            if reset.any() or resets[0].any() or self._calibration_stale:
                self._calibration_stale = True
                if strict:
                    raise MultiScopeError(self.STALE_MESSAGE)
                warnings.warn(self.STALE_MESSAGE + ". Followers were aligned by mean latency "
                              "only.", MultiScopeWarning)
                mode = 'latency'
                lag_seg = np.full(captures, fc.latency_ns / interval_ns)
            else:
                lag_seg = (ts - timestamps[0]).astype(np.float64) - fc.timestamp_offset
            shift = base_shift[k] - lag_seg
            s_int = np.rint(shift).astype(int)
            bad = (s_int < 0) | (s_int > 2 * fc.margin_samples)
            if bad.any():
                which = ", ".join(str(int(i)) for i in seg[bad][:8])
                worst_ns = float(lag_seg[bad][0] * interval_ns)
                msg = (f"Scope {self.serials[k]} triggered {worst_ns:.0f} ns after the master "
                       f"in segment(s) {which}, outside the calibrated "
                       f"{fc.latency_min_ns:.0f} to {fc.latency_max_ns:.0f} ns window: either "
                       "it missed a trigger or its time stamps no longer fit the calibration "
                       "(check the reference lock, then call calibrate() again)")
                if strict:
                    raise MultiScopeError(msg)
                warnings.warn(msg + ". Those segments were aligned by mean latency only.",
                              MultiScopeWarning)
                s_int = np.where(bad, fc.margin_samples, s_int)
                shift = np.where(bad, float(fc.margin_samples), shift)
            lag_ns.append(lag_seg * interval_ns)
            shifts.append(s_int)
            residuals.append(shift - s_int)
            aligned = {}
            for ch, arr in buffers[k].items():
                if captures == 1:
                    aligned[ch] = np.ascontiguousarray(arr[s_int[0]:s_int[0] + samples])
                else:
                    aligned[ch] = np.stack([arr[i, s_int[i]:s_int[i] + samples]
                                            for i in range(captures)])
            out.append(aligned)

        squeeze = (lambda x: x[0]) if captures == 1 else (lambda x: x)
        self.last_alignment = AlignmentInfo(
            mode=mode,
            lag_ns=[squeeze(x) for x in lag_ns],
            shift_samples=[squeeze(x) for x in shifts],
            residual_samples=[squeeze(x) for x in residuals],
            timestamps=[squeeze(x) for x in timestamps],
            timestamp_reset=[squeeze(x) for x in resets],
            missed_triggers=[squeeze(x) for x in missed],
        )
        return out

    def _finish(self, out, output_unit):
        if output_unit == 'adc':
            return [dict(d) for d in out]
        return [scope._adc_to_(dict(d), unit=output_unit)  # pylint: disable=protected-access
                for scope, d in zip(self.scopes, out)]

    def run_simple_block_capture(self, timebases, samples: int, pre_trig_percent: float = 50,
                                 datatype=DATA_TYPE.INT16_T, output_unit: str = 'mv',
                                 time_unit: str = 'ns', timeout_s: float | None = None,
                                 align: bool = True, strict: bool = True):
        """One synchronised block capture on every scope.

        Followers are armed first, the master last. With a calibration in
        place each follower captures a slightly longer record and the part
        matching the master's window is returned, located from the two trigger
        time stamps. Details of what was shifted are in :attr:`last_alignment`.

        Args:
            timebases: Per-device timebases from :meth:`sample_rate_to_timebase`.
            samples: Samples per scope (all scopes return this many).
            pre_trig_percent: Pre-trigger percentage, applied to the master's window.
            datatype: Buffer data type (``INT16_T`` or ``INT8_T``).
            output_unit: ``'mv'``, ``'v'`` or ``'adc'``.
            time_unit: Unit of the returned time axis.
            timeout_s: Seconds to wait for the trigger; ``None`` waits forever
                (Ctrl+C stops every scope cleanly).
            align: Set False to return every record un-shifted.
            strict: Raise on a restarted time-stamp counter or an out-of-margin
                follower; False warns and falls back to mean-latency alignment.

        Returns:
            ``(data, time_axis)`` where ``data[index][channel]`` is a numpy array
            and ``time_axis`` is shared by every scope.
        """
        self._require_open()
        timebases = self._check_timebases(timebases)
        interval_ns = self._interval_ns(timebases, samples)
        pre = int(samples * pre_trig_percent / 100)
        n_per, pre_per, base_shift, use_ts = self._plan(timebases, samples, pre, interval_ns,
                                                        align, strict)
        buffers, infos = self._acquire(timebases, n_per, pre_per, 1, timeout_s, datatype)
        out = self._align(buffers, infos, samples, base_shift, interval_ns, use_ts, strict, 1)
        return self._finish(out, output_unit), self._time_axis(samples, pre, interval_ns, time_unit)

    def run_simple_rapid_block_capture(self, timebases, samples: int, captures: int,
                                       pre_trig_percent: float = 50, datatype=DATA_TYPE.INT16_T,
                                       output_unit: str = 'mv', time_unit: str = 'ns',
                                       timeout_s: float | None = None, align: bool = True,
                                       strict: bool = True):
        """A synchronised rapid block capture: ``captures`` segments on every scope.

        Every segment is aligned to the master's segment from its own pair of
        trigger time stamps, so a follower that misses a trigger is detected
        rather than silently shifting all later segments.

        Args:
            timebases: Per-device timebases from :meth:`sample_rate_to_timebase`.
            samples: Samples per segment per scope.
            captures: Number of segments.
            pre_trig_percent: Pre-trigger percentage of the master's window.
            datatype: Buffer data type.
            output_unit: ``'mv'``, ``'v'`` or ``'adc'``.
            time_unit: Unit of the returned time axis.
            timeout_s: Seconds to wait for all segments; ``None`` waits forever.
            align: Set False to return every record un-shifted.
            strict: Raise on a missed trigger or restarted time-stamp counter;
                False warns and aligns the affected segments by mean latency.

        Returns:
            ``(data, time_axis)`` where ``data[index][channel]`` has shape
            ``(captures, samples)``.
        """
        self._require_open()
        if captures < 1:
            raise MultiScopeError("captures must be at least 1")
        timebases = self._check_timebases(timebases)
        interval_ns = self._interval_ns(timebases, samples)
        pre = int(samples * pre_trig_percent / 100)
        n_per, pre_per, base_shift, use_ts = self._plan(timebases, samples, pre, interval_ns,
                                                        align, strict)
        buffers, infos = self._acquire(timebases, n_per, pre_per, captures, timeout_s, datatype)
        out = self._align(buffers, infos, samples, base_shift, interval_ns, use_ts, strict,
                          captures)
        return self._finish(out, output_unit), self._time_axis(samples, pre, interval_ns, time_unit)


__all__ = [
    'MultiScope',
    'MultiScopeError',
    'MultiScopeWarning',
    'Calibration',
    'FollowerCalibration',
    'AlignmentInfo',
]
