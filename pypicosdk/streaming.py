"""
This is a streaming scope class. Due to how streaming works, it needs its own
class and config independant to the main PicoScope drivers.
To use this class do the following:
 - Initialise the class: `stream = StreamingScope()`
 - Configure the class: `stream.config(...)`
 - Run streaming (in a thread): `stream.start_streaming_while()`
 - To stop use `stream.stop()

Todo:
 - Multichannel
    - get_streaming_latest_values() PICO_STREAMIN_DATA_INFO needs to be a list
      of structs
"""
from warnings import warn
import numpy as np
from .constants import (
    CHANNEL,
    TIME_UNIT,
    RATIO_MODE,
    DATA_TYPE,
    ACTION,
    TimeUnit_L,
    TimeUnitStd_M,
    _TimeUnitText,
)
from .common import _get_literal, PicoSDKException, BufferTooSmall
from .pypicosdk import psospa, ps6000a


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
