"""
Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.

High-level streaming helpers.

`StreamingSession` is the supported, hardware-agnostic streaming loop: it owns
buffer registration, rotation and polling for every driver, so the same user
code streams on a 6000E (ps6000a), 3000E/5000E (psospa) or 5000D (ps5000a):

 - Configure the scope (open_unit, set_channel) as normal
 - `with StreamingSession(scope, sample_interval=..., time_units=...) as stream:`
 - `for chunk in stream:` - each chunk carries per-channel numpy copies

`StreamingScope` is the older 6000a-generation-only helper, kept for
reference; prefer `StreamingSession`.
"""
import time
from warnings import warn
import numpy as np
from .constants import (
    CHANNEL,
    TIME_UNIT,
    RATIO_MODE,
    DATA_TYPE,
    ACTION,
    RESOLUTION,
    TimeUnit_L,
    TimeUnitStd_M,
    _TimeUnitText,
    DataTypeNPMap,
)
from .common import (
    _get_literal,
    PicoSDKException,
    BufferTooSmall,
    OverrangeWarning,
)
from .ps6000a import ps6000a
from .psospa import psospa


class StreamingScope:
    """Streaming Scope class"""
    def __init__(self, scope: ps6000a | psospa):
        self.scope = scope
        self.stop_bool = False  # Bool to stop streaming while loop
        self.msps_current = 0
        self.channel_config: list
        self.info: dict

        # Streaming settings
        self.channel: CHANNEL
        self.pre_trig_samples: int
        self.post_trig_samples: int
        self.interval: int
        self.time_units: TIME_UNIT
        self.ratio: int
        self.ratio_mode: RATIO_MODE
        self.data_type: DATA_TYPE

        # Buffers
        self.np_buffer = np.empty(0)
        self.buffer_index = 0
        self.buffer = np.empty(0)
        self.samples: int
        self.np_samples: int
        self.max_buffer_size: int

        # Stats
        self._debug = False
        self._msps_avg_array = np.empty(0, dtype=np.int32)
        self._msps_avg_len = 100
        self.msps_avg = 0.0
        self.msps_min = 9999.9
        self.msps_max = 0.0

    def config_streaming(
        self,
        channel: CHANNEL,
        samples: int,
        interval: int,
        time_units: TIME_UNIT | TimeUnit_L,
        pre_trig_samples: int = 0,
        post_trig_samples: int = 250,
        ratio: int = 0,
        ratio_mode: RATIO_MODE = RATIO_MODE.RAW,
        data_type: DATA_TYPE = DATA_TYPE.INT16_T,
    ) -> None:
        """
        Configures the streaming settings for data acquisition. This method
        sets up the channel, sample counts, timing intervals, and buffer
        management for streaming data from the device.

        Args:
            channel (CHANNEL): The channel to stream data from.
            samples (int):
                The number of samples to acquire in each streaming segment.
            interval (int): The time interval between samples.
            time_units (str | TIME_UNIT): Units for the sample interval
                (e.g., 'ms' or TIME_UNIT.MS).
            pre_trig_samples (int, optional): Number of samples to capture
                before a trigger event. Defaults to 0.
            post_trig_samples (int, optional): Number of samples to capture
                after a trigger event. Defaults to 250.
            ratio (int, optional): Downsampling ratio to apply to the captured
                data. Defaults to 0 (no downsampling).
            ratio_mode (RATIO_MODE, optional): Mode used for applying the
                downsampling ratio. Defaults to RATIO_MODE.RAW.
            data_type (DATA_TYPE, optional): Data type for the samples in the
                buffer. Defaults to DATA_TYPE.INT16_T.

        Returns:
            None
        """
        # Get typing literals
        time_units = _get_literal(time_units, TimeUnitStd_M)

        if interval/time_units >= 0.001:
            raise PicoSDKException(
                f'An interval of {interval} {_TimeUnitText[time_units]} is too long. '
                f'Please specify an interval less than 1 ms.')

        # Streaming settings
        self.channel = channel
        self.pre_trig_samples = pre_trig_samples
        self.post_trig_samples = post_trig_samples
        self.interval = interval
        self.time_units = time_units
        self.ratio = ratio
        self.ratio_mode = ratio_mode
        self.data_type = data_type

        # python buffer setup
        self.samples = samples
        self.np_samples = int(samples/2)
        if self.ratio_mode == RATIO_MODE.AGGREGATE:
            self.buffer = np.zeros((2, samples))
            self.np_buffer = np.zeros((2, 2, self.np_samples), dtype=np.int16)
        else:
            self.buffer = np.zeros(samples)
            self.np_buffer = np.zeros((2, self.np_samples), dtype=np.int16)
        # max_buffer_size (int | None): Maximum number of samples the python
        # buffer can hold. If None, the buffer will not constrain.
        self.max_buffer_size = samples

    def _add_channel(
        self,
        channel: CHANNEL,
        ratio_mode: RATIO_MODE = RATIO_MODE.RAW,
        data_type: DATA_TYPE = DATA_TYPE.INT16_T,
    ) -> None:
        """
        !NOT YET IMPLEMETED!
        Adds a channel configuration for data acquisition.

        This method appends a new channel configuration to the internal list,
        specifying the channel, ratio mode, and data type to be used for
        streaming.

        Args:
            channel (CHANNEL): The channel to add for streaming.
            ratio_mode (RATIO_MODE, optional): The downsampling ratio mode for
                this channel. Defaults to RATIO_MODE.RAW.
            data_type (DATA_TYPE, optional): The data type to use for samples
                from this channel. Defaults to DATA_TYPE.INT16_T.

        Returns:
            None
        """
        self.channel_config.append([channel, ratio_mode, data_type])

    def _stream_set_data_buffer(self, buffer_index: int):
        """Set data buffer function for consistency when creating a new buffer
        Args:
            buffer_index (int): Index of buffer to set to PicoScope"""
        if self.ratio_mode == RATIO_MODE.AGGREGATE:
            self.scope.set_data_buffers(
                self.channel,
                self.np_samples,
                buffers=self.np_buffer[buffer_index],
                action=ACTION.ADD,
                ratio_mode=self.ratio_mode
            )
        else:
            self.scope.set_data_buffer(
                    self.channel,
                    self.np_samples,
                    buffer=self.np_buffer[buffer_index],
                    action=ACTION.ADD,
                    ratio_mode=self.ratio_mode,
                )

    def run_streaming(self) -> None:
        """
        Initiates the data streaming process.

        This method prepares the device for streaming by clearing existing
        data buffers, setting up a new data buffer for the selected channel,
        and starting the streaming process with the configured parameters such
        as sample interval, trigger settings, and downsampling options.

        The method resets internal buffer indices and flags to prepare for
        incoming data.
        """
        # Setup empty variables for streaming
        self.stop_bool = False

        # Setup initial buffer for streaming
        self.scope.set_data_buffer(0, 0, action=ACTION.CLEAR_ALL)
        for buffer_index in range(self.np_buffer.shape[0]):
            self._stream_set_data_buffer(buffer_index)

        # start streaming
        self.scope.run_streaming(
            sample_interval=self.interval,
            time_units=self.time_units,
            max_pre_trigger_samples=self.pre_trig_samples,
            max_post_trigger_samples=self.post_trig_samples,
            auto_stop=0,
            ratio=self.ratio,
            ratio_mode=self.ratio_mode
        )

    def get_streaming_values(self) -> None:
        """
        Main loop for handling streaming data acquisition.

        This method retrieves the latest streaming data from the device,
        appends new samples to the internal buffer array, and manages buffer
        rollover when the hardware buffer becomes full.

        The method ensures that the internal buffer (`self.buffer_array`)
        always contains the most recent samples up to `max_buffer_size`. It
        also handles alternating between buffer segments when a buffer
        overflow condition is detected.
        """
        self.info = self.scope.get_streaming_latest_values(
            channel=self.channel,
            ratio_mode=self.ratio_mode,
            data_type=self.data_type
        )
        status = self.info['status']
        n_samples = self.info['no of samples']
        start_index = self.info['start index']
        scope_buffer_index = self.info['Buffer index']

        # Buffer indexes
        buffer_index = scope_buffer_index % 2
        new_buf_index = 1 - buffer_index

        # Once a buffer is finished with, add it again as a new buffer
        if buffer_index != self.buffer_index:
            self.buffer_index = buffer_index
            self._stream_set_data_buffer(new_buf_index)

        # If buffer isn't empty, add data to array
        if n_samples > 0:
            # If buffer is overflowing to device
            if status == 407:
                if self.ratio_mode == RATIO_MODE.AGGREGATE:
                    warn(f'Max buffer size {self.max_buffer_size} too small to capture samples at '
                         f'{self.interval} {_TimeUnitText[self.time_units]} interval, increase to '
                         f'sample size or ratio to not miss data.',
                         BufferTooSmall)
                else:
                    warn(f'Max buffer size {self.max_buffer_size} too small to capture samples at '
                         f'{self.interval} {_TimeUnitText[self.time_units]} interval, increase to '
                         f'not miss data.',
                         BufferTooSmall)

            # Add the new buffer to the buffer array and take end chunk
            if self.ratio_mode == RATIO_MODE.AGGREGATE:
                new_data = self.np_buffer[buffer_index][:, start_index:start_index + n_samples]
                pad_len = max(self.samples - (self.buffer.shape[1] + new_data.shape[1]), 0)
                temp_pad_array = np.zeros((2, pad_len))
                self.buffer = (np.concatenate([temp_pad_array, self.buffer, new_data], axis=1)
                               [:, -self.max_buffer_size:])
            else:
                new_data = (self.np_buffer[buffer_index][start_index:start_index + n_samples])
                pad_len = max(self.samples - (len(self.buffer) + len(new_data)), 0)
                temp_pad_array = np.zeros(pad_len)
                self.buffer = (np.concatenate([temp_pad_array, self.buffer, new_data])
                               [-self.max_buffer_size:])

    def start_streaming_while(self) -> None:
        """
        Starts and continuously runs the streaming acquisition loop until
        StreamingScope.stop() is called.
        """
        self.run_streaming()
        while not self.stop_bool:
            self.get_streaming_values()
        self.scope.stop()

    def _run_streaming_for(self, n_times) -> None:
        """
        Runs the streaming acquisition loop for a fixed number of iterations.

        Args:
            n_times (int): Number of iterations to run the streaming loop.
        """

        if self.max_buffer_size is not None:
            warn('max_buffer_data needs to be None to retrieve the full '
                 'streaming data.')
        self.run_streaming()
        for _ in range(n_times):
            self.get_streaming_values()
        self.scope.stop()

    def _run_streaming_for_samples(self, no_of_samples) -> np.ndarray:
        """
        Runs streaming acquisition until a specified number of samples are
        collected. The loop will terminate early if `StreamingScope.stop()` is
        called.

        Args:
            no_of_samples (int):
                The total number of samples to acquire before stopping.

        Returns:
            numpy.ndarray: The buffer array containing the collected samples.
        """
        self.run_streaming()
        while not self.stop_bool:
            self.get_streaming_values()
            if len(self.buffer) >= no_of_samples:
                return self.buffer

    def stop(self):
        """Signals the streaming loop to stop."""
        self.stop_bool = True


class StreamingChunk:
    """One poll's worth of streamed data, delivered by :class:`StreamingSession`.

    Attributes:
        data (dict): ``{channel: np.ndarray}`` — a private copy per channel,
            safe to keep, process or hand to another thread. Arrays keep the
            native capture dtype (no upcasting).
        overflowed (list): Channels whose input went over range during this
            chunk (ADC over-range, not a buffer overflow).
        triggered (bool): True if the driver reported the trigger fired in
            this poll.
        trigger_at (int): The driver's raw trigger sample index, only
            meaningful when ``triggered`` is True. NOTE: the reference frame
            of this value (cumulative stream index vs buffer-relative) is
            driver-dependent and not fully verified — treat as approximate
            unless confirmed for your device.
        auto_stopped (bool): True when the driver reported auto-stop; this is
            the final chunk of the session.
    """

    def __init__(self, data, overflowed, triggered, trigger_at, auto_stopped):
        self.data = data
        self.overflowed = overflowed
        self.triggered = triggered
        self.trigger_at = trigger_at
        self.auto_stopped = auto_stopped

    @property
    def n_samples(self) -> int:
        """Number of samples per channel in this chunk (max across channels)."""
        if not self.data:
            return 0
        return max(len(arr) for arr in self.data.values())


class StreamingSession:
    """
    Hardware-agnostic streaming loop. Owns buffer registration, rotation and
    polling for every supported driver, so identical user code streams on a
    6000E (ps6000a), 3000E/5000E (psospa) or 5000D (ps5000a).

    Usage::

        scope = psdk.ps6000a()          # or psospa() / ps5000a()
        scope.open_unit()
        scope.set_channel(psdk.CHANNEL.A, range=psdk.RANGE.V1)

        with psdk.StreamingSession(scope, sample_interval=100,
                                   time_units=psdk.TIME_UNIT.NS) as stream:
            for chunk in stream:
                process(chunk.data[psdk.CHANNEL.A])
                if done:
                    break

    Per-driver behaviour handled internally:
     - ps6000a/psospa: double-buffer registration (ACTION.ADD), coherent
       multi-channel draining via ``get_streaming_latest_values_multi``,
       buffer-index rotation with hot-swap re-registration, and a stall
       warning if the driver reports buffer starvation (status 407)
       persistently rather than transiently.
     - ps5000a: a single persistent overview buffer per channel; INT8_T
       requests are routed to the native unscaled 8-bit transfer path
       (``set_unscaled_data_buffer``).

    Analog channels only for now; digital/MSO ports are not yet supported.

    Capability walls are surfaced, not hidden: configurations a driver cannot
    express (e.g. SUM downsampling or >2^32 sample targets on ps5000a) raise
    PicoSDKException at construction or start, never silently degrade.

    The session is single-threaded: iterate it from one thread and hand the
    chunk copies to consumers. The one thread-safe entry point is
    :meth:`request_stop`, which only sets a flag - another thread (e.g. a
    GUI thread) may call it to end the loop while every driver call stays
    on the iterating thread. ``last_info`` always holds the most recent raw
    poll result for debugging.
    """

    # Downsampling modes the session supports. AGGREGATE/DISTRIBUTION need
    # paired min/max buffers and are not yet supported here; the TRIGGER
    # family is block-mode-only and illegal in streaming.
    _SUPPORTED_RATIO_MODES = (
        RATIO_MODE.RAW,
        RATIO_MODE.NONE,
        RATIO_MODE.DECIMATE,
        RATIO_MODE.AVERAGE,
        RATIO_MODE.SUM,
    )

    def __init__(
        self,
        scope,
        sample_interval: float,
        time_units: TIME_UNIT | TimeUnit_L,
        channels: list | None = None,
        datatype: DATA_TYPE = DATA_TYPE.INT16_T,
        ratio: int = 0,
        ratio_mode: RATIO_MODE = RATIO_MODE.RAW,
        samples_per_buffer: int | None = None,
        poll_interval: float | None = None,
        pre_trigger_samples: int = 0,
        post_trigger_samples: int | None = None,
        auto_stop: bool = False,
    ):
        """
        Args:
            scope: An opened PicoScope driver instance (ps6000a, psospa or
                ps5000a) with channels already enabled via ``set_channel``.
            sample_interval: Requested interval between samples.
            time_units (TIME_UNIT | str): Unit for ``sample_interval``.
            channels (list, optional): Channels to stream. Defaults to every
                channel currently enabled on the scope.
            datatype (DATA_TYPE, optional): Capture data type. Defaults to
                INT16_T (supported natively on all drivers). INT8_T maps to
                the native 8-bit path on every driver.
            ratio (int, optional): Downsampling ratio. Required >= 1 for
                DECIMATE/AVERAGE/SUM.
            ratio_mode (RATIO_MODE, optional): Downsampling mode. Defaults to
                RAW (no downsampling).
            samples_per_buffer (int, optional): Driver transfer buffer length
                per channel. Defaults to ~200 ms of data at the requested
                rate, clamped to [10_000, 10_000_000].
            poll_interval (float, optional): Minimum seconds between driver
                polls. Defaults to a tenth of the buffer duration, clamped
                to [0.005, 0.05].
            pre_trigger_samples (int, optional): Pre-trigger sample target
                passed to the driver. Defaults to 0.
            post_trigger_samples (int, optional): Post-trigger sample target.
                Defaults to ``samples_per_buffer`` (a sizing hint) when
                ``auto_stop`` is False.
            auto_stop (bool, optional): Stop after the pre+post targets have
                streamed. Requires ``post_trigger_samples``. NOTE: with
                auto_stop the driver validates the targets against device
                memory, so the same targets may be rejected on a smaller
                scope. Defaults to False (stream until ``stop()``).

        Raises:
            PicoSDKException: If the configuration is invalid or not
                expressible on the connected driver.
        """
        self.scope = scope
        self._is_ps5000a = scope._unit_prefix_n == 'ps5000a'

        # --- channels ---
        if channels is None:
            channels = sorted(scope.channel_db.keys())
        if not channels:
            raise PicoSDKException(
                "No channels to stream: enable channels with set_channel() "
                "or pass channels=[...]")
        unknown = [ch for ch in channels if ch not in scope.channel_db]
        if unknown:
            raise PicoSDKException(
                f"Channels {unknown} are not enabled analog channels - "
                "enable them with set_channel() first. Digital/MSO ports are "
                "not yet supported by StreamingSession.")
        self.channels = list(channels)

        # --- ratio mode validation (surface capability walls early) ---
        if ratio_mode not in self._SUPPORTED_RATIO_MODES:
            raise PicoSDKException(
                "StreamingSession supports RAW/NONE, DECIMATE, AVERAGE and "
                "SUM ratio modes; AGGREGATE/DISTRIBUTION (paired min/max "
                "buffers) are not yet supported and the TRIGGER family is "
                "block-mode only")
        if self._is_ps5000a and ratio_mode == RATIO_MODE.SUM:
            raise PicoSDKException(
                "The ps5000a driver has no SUM downsampling mode")
        if ratio_mode not in (RATIO_MODE.RAW, RATIO_MODE.NONE) and ratio < 1:
            raise PicoSDKException(
                f"ratio must be >= 1 for downsampled streaming (got {ratio})")
        # The 6000a generation spells no-downsampling RAW (0x80000000); NONE
        # (0) exists only in the ps5000a enum. Mirror of the ps5000a driver's
        # RAW->NONE conversion, in the opposite direction.
        if not self._is_ps5000a and ratio_mode == RATIO_MODE.NONE:
            ratio_mode = RATIO_MODE.RAW
        self.ratio = ratio
        self.ratio_mode = ratio_mode

        # --- datatype validation / per-driver routing ---
        np_dtype = DataTypeNPMap.get(datatype, None)
        if np_dtype is None:
            raise PicoSDKException("Invalid datatype selected for streaming")
        if self._is_ps5000a and datatype not in (DATA_TYPE.INT8_T,
                                                 DATA_TYPE.INT16_T):
            raise PicoSDKException(
                "The ps5000a driver only supports INT8_T (native unscaled "
                "path) or INT16_T streaming buffers")
        # INT8_T on ps5000a goes through SetUnscaledDataBuffers, which is
        # only lossless at 8-bit resolution.
        self._use_unscaled = self._is_ps5000a and datatype == DATA_TYPE.INT8_T
        if (self._use_unscaled
                and getattr(scope, 'resolution', None) not in
                (None, RESOLUTION.BIT_8)):
            warn("INT8_T streaming on ps5000a uses the unscaled 8-bit "
                 "transfer path, which discards resolution above 8 bits.",
                 UserWarning)
        self.datatype = datatype
        self._np_dtype = np_dtype

        # --- interval / buffer sizing ---
        time_units = _get_literal(time_units, TimeUnitStd_M)
        self.sample_interval = sample_interval
        self.time_units = time_units
        interval_s = sample_interval / time_units
        if interval_s <= 0:
            raise PicoSDKException("sample_interval must be positive")

        if samples_per_buffer is None:
            samples_per_buffer = int(min(max(0.2 / interval_s, 10_000),
                                         10_000_000))
        elif samples_per_buffer < 1:
            raise PicoSDKException("samples_per_buffer must be >= 1")
        self.samples_per_buffer = samples_per_buffer

        if poll_interval is None:
            buffer_seconds = samples_per_buffer * interval_s
            poll_interval = min(max(buffer_seconds / 10, 0.005), 0.05)
        elif poll_interval < 0:
            raise PicoSDKException("poll_interval must be >= 0")
        self.poll_interval = poll_interval

        # --- stop targets ---
        if auto_stop and post_trigger_samples is None:
            raise PicoSDKException(
                "auto_stop=True requires post_trigger_samples")
        self.auto_stop = auto_stop
        self.pre_trigger_samples = pre_trigger_samples
        # Without auto_stop the post target is only a driver sizing hint.
        self.post_trigger_samples = (post_trigger_samples
                                     if post_trigger_samples is not None
                                     else samples_per_buffer)

        # --- state ---
        self._buffers: dict = {}        # channel -> list of registered arrays
        self._current_index: dict = {}  # channel -> active buffer index (6000a-gen)
        self._started = False
        self._finished = False
        self._draining = False          # auto-stop seen; deliver the tail
        self._stop_requested = False
        self._starved_polls = 0
        self._starve_warned = False
        self._next_poll_time = 0.0
        self.actual_sample_interval: float | None = None
        self.last_info = None           # most recent raw poll result (debugging)
        self.total_samples: dict = {ch: 0 for ch in self.channels}

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        """Register the driver buffers and start streaming.

        Called automatically on first iteration / context entry. After this
        returns, :attr:`actual_sample_interval` holds the interval the driver
        actually configured, in the requested ``time_units``.
        """
        if self._started:
            return

        n = self.samples_per_buffer
        if self._is_ps5000a:
            # Single persistent overview buffer per channel; the driver
            # recycles it, there is no rotation.
            for ch in self.channels:
                if self._use_unscaled:
                    buf = self.scope.set_unscaled_data_buffer(
                        ch, n, ratio_mode=self.ratio_mode)
                else:
                    buf = self.scope.set_data_buffer(
                        ch, n, ratio_mode=self.ratio_mode)
                self._buffers[ch] = [buf]
        else:
            # 6000a generation: clear any stale registrations, then register
            # a rotating pair per channel with ACTION.ADD.
            self.scope.set_data_buffer(
                self.channels[0], 0, action=ACTION.CLEAR_ALL)
            for ch in self.channels:
                pair = []
                for _ in range(2):
                    pair.append(self.scope.set_data_buffer(
                        ch, n, datatype=self.datatype,
                        ratio_mode=self.ratio_mode, action=ACTION.ADD))
                self._buffers[ch] = pair
                self._current_index[ch] = 0

        self.actual_sample_interval = self.scope.run_streaming(
            sample_interval=self.sample_interval,
            time_units=self.time_units,
            max_pre_trigger_samples=self.pre_trigger_samples,
            max_post_trigger_samples=self.post_trigger_samples,
            auto_stop=int(self.auto_stop),
            ratio=self.ratio,
            ratio_mode=self.ratio_mode,
            overview_buffer_size=(n if self._is_ps5000a else None),
        )
        self._started = True

    def stop(self) -> None:
        """Stop the capture. Safe to call more than once.

        Makes a driver call, so it must run on the thread that iterates the
        session; from any other thread use :meth:`request_stop` instead.
        """
        self._stop_requested = True
        if self._started:
            self.scope.stop()
            self._started = False

    def request_stop(self) -> None:
        """Ask the streaming loop to finish, without touching the driver.

        Unlike :meth:`stop`, this only sets the stop flag, so it is safe to
        call from another thread (e.g. a GUI thread) while the session is
        being iterated. The iterating thread observes the flag within one
        poll interval, performs the driver stop itself and ends iteration.
        """
        self._stop_requested = True

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()
        return False

    # -- polling ------------------------------------------------------------

    def _poll(self):
        """One driver poll, normalised to (per-channel list, trigger dict, status)."""
        if self._is_ps5000a:
            info = self.scope.get_streaming_latest_values()
            self.last_info = info
            # The single callback covers every registered channel with one
            # sample count / start index; overflow is a channel bitmask.
            per_channel = [
                {
                    'channel': ch,
                    'no of samples': info['no of samples'],
                    'start index': info['start index'],
                    'Buffer index': 0,
                    'overflowed?': (int(info['overflowed?']) >> ch) & 1,
                }
                for ch in self.channels
            ]
            trigger = {
                'triggered?': info['triggered?'],
                'triggered at': info['triggered at'],
                'auto stopped?': info['auto stopped?'],
            }
            return per_channel, trigger, info['status']

        result = self.scope.get_streaming_latest_values_multi(
            [(ch, self.ratio_mode, self.datatype) for ch in self.channels])
        self.last_info = result
        trigger = {
            'triggered?': result['triggered?'],
            'triggered at': result['triggered at'],
            'auto stopped?': result['auto stopped?'],
        }
        return result['channels'], trigger, result['status']

    def _handle_rotation(self, entry) -> None:
        """Hot-swap the vacated buffer when the driver moves on (6000a-gen)."""
        ch = entry['channel']
        index = entry['Buffer index'] % 2
        if index != self._current_index[ch]:
            self._current_index[ch] = index
            self.scope.set_data_buffer(
                ch, self.samples_per_buffer, datatype=self.datatype,
                ratio_mode=self.ratio_mode, action=ACTION.ADD,
                buffer=self._buffers[ch][1 - index])

    def _check_starvation(self, status: int) -> None:
        """Track persistent buffer starvation (status 407 with no data).

        A transient 407 is normal on the 6000a generation and resolves by
        re-polling - the rotation hot-swap keeps returning buffers to the
        driver. Proactively re-ADDing a buffer here would double-register
        memory the driver already holds and desynchronise the buffer-index
        mapping, so the session only watches for a persistent stall and
        warns once instead of stalling silently.
        """
        if status != 407 or self._is_ps5000a:
            self._starved_polls = 0
            return
        self._starved_polls += 1
        starved_seconds = self._starved_polls * max(self.poll_interval, 1e-3)
        if not self._starve_warned and starved_seconds > 2.0:
            self._starve_warned = True
            warn("Streaming driver has reported WAITING_FOR_DATA_BUFFERS "
                 "with no data for over 2 seconds; the stream may be "
                 "stalled. Consider a larger samples_per_buffer.",
                 BufferTooSmall)

    # -- iteration ----------------------------------------------------------

    def __iter__(self):
        return self

    def __next__(self) -> StreamingChunk:
        if not self._started and not self._stop_requested:
            self.start()

        while True:
            if self._stop_requested or self._finished:
                self.stop()
                raise StopIteration

            # Pace driver polls to poll_interval regardless of data flow so
            # chunk size tracks the configured cadence, not user-loop speed.
            now = time.monotonic()
            if now < self._next_poll_time:
                time.sleep(self._next_poll_time - now)
            self._next_poll_time = time.monotonic() + self.poll_interval

            per_channel, trigger, status = self._poll()
            got_samples = any(e['no of samples'] > 0 for e in per_channel)

            if got_samples:
                self._starved_polls = 0
                data = {}
                overflowed = []
                for entry in per_channel:
                    ch = entry['channel']
                    n = entry['no of samples']
                    if n <= 0:
                        # An entry the driver did not fill carries zeroed
                        # index fields - never rotate or copy from it.
                        data[ch] = np.empty(0, dtype=self._np_dtype)
                        continue
                    start = entry['start index']
                    buffers = self._buffers[ch]
                    buf = buffers[entry['Buffer index'] % len(buffers)]
                    data[ch] = buf[start:start + n].copy()
                    self.total_samples[ch] += n
                    # Per-entry over-range flag on the 6000a generation; the
                    # ps5000a path decodes its channel bitmask in _poll().
                    if entry['overflowed?']:
                        overflowed.append(ch)
                    if not self._is_ps5000a:
                        self._handle_rotation(entry)

                if overflowed:
                    warn("One or more channels exceeded their input range "
                         "during streaming (ADC over-range); affected "
                         "channels are listed in chunk.overflowed.",
                         OverrangeWarning)

                # Auto-stop starts a drain: keep delivering buffered chunks
                # until a poll returns no data, so the tail the driver
                # reports alongside/after the flag is never lost.
                if trigger['auto stopped?']:
                    self._draining = True

                return StreamingChunk(
                    data=data,
                    overflowed=overflowed,
                    triggered=bool(trigger['triggered?']),
                    trigger_at=int(trigger['triggered at']),
                    auto_stopped=bool(trigger['auto stopped?']),
                )

            # No data in this poll.
            if self._draining or trigger['auto stopped?']:
                self._finished = True
                continue

            self._check_starvation(status)
