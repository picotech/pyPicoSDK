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
import threading
import numpy as np
from . import constants as cst
from .common import _get_literal, PicoSDKException
from .pypicosdk import psospa, ps6000a


class StreamingScope:
    """Streaming Scope class"""
    def __init__(
        self,
        scope: ps6000a | psospa,
        channel: str | cst.channel_literal | cst.CHANNEL,
        samples: int,
        interval: int,
        time_units: str | cst.TimeUnit_L | cst.TIME_UNIT,
        pre_trig_samples: int = 0,
        post_trig_samples: int = 250,
        ratio: int = 0,
        ratio_mode: str | cst.RatioMode_L | cst.RATIO_MODE = cst.RATIO_MODE.RAW,
        data_type: str | cst.DataType_L | cst.DATA_TYPE = cst.DATA_TYPE.INT16_T,
    ) -> None:
        """
        Creates a class with streaming settings for data acquisition. By intialising
        this class it sets up the channel, sample counts, timing intervals, and buffer
        management for streaming data from the device.

        Args:
            channel (str | CHANNEL): The channel to stream data from.
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
            ratio_mode (str | RATIO_MODE, optional): Mode used for applying the
                downsampling ratio. Defaults to RATIO_MODE.RAW.
            data_type (str | DATA_TYPE, optional): Data type for the samples in the
                buffer. Defaults to DATA_TYPE.INT16_T.
        """

        # Get typing literals
        channel = _get_literal(channel, cst.channel_map)
        time_units = _get_literal(time_units, cst.TimeUnitStd_M)
        ratio_mode = _get_literal(ratio_mode, cst.RatioMode_M)
        data_type = _get_literal(data_type, cst.DataType_M)

        if interval/time_units >= 0.001:
            raise PicoSDKException(
                f'An interval of {interval} {cst.TimeUnitText[time_units]} is too long. '
                f'Please specify an interval less than 1 ms.')

        # Threading
        self._streaming_thread: threading.Thread
        self._stop = False  # Bool to stop streaming while loop

        # Scope Setup
        self.scope = scope
        self._channel_config: list
        self.info: cst.StreamInfo

        # Streaming settings
        self._channel = channel
        self._pre_trig_samples = pre_trig_samples
        self._post_trig_samples = post_trig_samples
        self._interval = interval
        self._time_units = time_units
        self._ratio = ratio
        self._ratio_mode = ratio_mode
        self._data_type = data_type

        # python buffer setup
        self._buffer_index = 0
        self._last_index = 0
        self._samples = samples
        self._np_samples = int(samples/2)
        if self._ratio_mode == cst.RATIO_MODE.AGGREGATE:
            self._buffer = np.zeros((2, samples))
            self._np_buffer = np.zeros((2, 2, self._np_samples), dtype=np.int16)
        else:
            self._buffer = np.zeros(samples)
            self._np_buffer = np.zeros((2, self._np_samples), dtype=np.int16)

    def get_data(self) -> np.ndarray:
        """
        Returns the data from the buffer

        Returns:
            np.ndarray: Numpy array of the streaming buffer.
        """
        if self._ratio_mode == cst.RATIO_MODE.AGGREGATE:
            return self._buffer[0], self._buffer[1]
        return self._buffer

    def get_last_sample_index(self) -> int:
        """
        Returns the index of the last sample captured.
        Ideal for adding a sweep line on the graph.

        Returns:
            int: Integer of the last sample added.
        """
        return self._last_index

    def _add_channel(
        self,
        channel: cst.CHANNEL,
        ratio_mode: cst.RATIO_MODE = cst.RATIO_MODE.RAW,
        data_type: cst.DATA_TYPE = cst.DATA_TYPE.INT16_T,
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
        self._channel_config.append([channel, ratio_mode, data_type])

    def _stream_set_data_buffer(self, buffer_index: int):
        """Set data buffer function for consistency when creating a new buffer
        Args:
            buffer_index (int): Index of buffer to set to PicoScope"""
        if self._ratio_mode == cst.RATIO_MODE.AGGREGATE:
            self.scope.set_data_buffers(
                self._channel,
                self._np_samples,
                buffers=self._np_buffer[buffer_index],
                action=cst.ACTION.ADD,
                ratio_mode=self._ratio_mode
            )
        else:
            self.scope.set_data_buffer(
                    self._channel,
                    self._np_samples,
                    buffer=self._np_buffer[buffer_index],
                    action=cst.ACTION.ADD,
                    ratio_mode=self._ratio_mode,
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
        self._stop = False

        # Setup initial buffer for streaming
        self.scope.set_data_buffer(0, 0, action=cst.ACTION.CLEAR_ALL)
        for buffer_index in range(self._np_buffer.shape[0]):
            self._stream_set_data_buffer(buffer_index)

        # start streaming
        self.scope.run_streaming(
            sample_interval=self._interval,
            time_units=self._time_units,
            max_pre_trigger_samples=self._pre_trig_samples,
            max_post_trigger_samples=self._post_trig_samples,
            auto_stop=0,
            ratio=self._ratio,
            ratio_mode=self._ratio_mode
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
            channel=self._channel,
            ratio_mode=self._ratio_mode,
            data_type=self._data_type
        )
        n_samples = self.info.no_of_samples
        start_index = self.info.start_index
        scope_buffer_index = self.info.buffer_index

        # Buffer indexes
        buffer_index = scope_buffer_index % 2
        new_buf_index = 1 - buffer_index

        # Once a buffer is finished with, add it again as a new buffer
        if buffer_index != self._buffer_index:
            self._buffer_index = buffer_index
            self._stream_set_data_buffer(new_buf_index)

        # If buffer isn't empty, add data to array
        if n_samples > 0:
            # Update _last_index with the location of the last gathered sample location
            self._last_index = (n_samples + start_index) + (buffer_index * self._np_samples)
            # Add the numpy buffers together
            if self._ratio_mode == cst.RATIO_MODE.AGGREGATE:
                for i in range(2):
                    self._buffer[i] = np.concatenate([self._np_buffer[0][i], self._np_buffer[1][i]])
            else:
                self._buffer = np.concatenate([self._np_buffer[0], self._np_buffer[1]])

    def _streaming_loop(self) -> None:
        """
        Starts and continuously runs the streaming acquisition loop until
        StreamingScope.stop() is called.
        """
        self.run_streaming()
        while not self._stop:
            self.get_streaming_values()
        self.scope.stop()

    def start(self):
        "Starts streaming as a thread"
        self._streaming_thread = threading.Thread(target=self._streaming_loop)
        self._streaming_thread.start()

    def stop(self):
        """Signals the streaming loop to stop."""
        self._stop = True
        self._streaming_thread.join()
