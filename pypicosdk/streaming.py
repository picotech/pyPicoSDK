from .constants import *
from .ps6000a import ps6000a
import numpy as np
from warnings import warn

"""
Todo:
 - Multichannel
    - get_streaming_latest_values() PICO_STREAMIN_DATA_INFO needs to be a list of structs
    """

class StreamingScope:
    def __init__(self, scope:ps6000a):
        self.scope = scope
        self.stop_bool = False  # Bool to stop streaming while loop
        self.channel_config = []

    def config_streaming(
            self, 
            channel:CHANNEL, 
            samples:int, 
            interval:int, 
            time_units:PICO_TIME_UNIT,
            max_buffer_size:int | None,
            pre_trig_samples:int=0,
            post_trig_samples:int=250,
            ratio:int=0,
            ratio_mode:RATIO_MODE=RATIO_MODE.RAW,
            data_type:DATA_TYPE=DATA_TYPE.INT16_T,
        ) -> None:
        """
        Configures the streaming settings for data acquisition. This method sets up the channel, 
        sample counts, timing intervals, and buffer management for streaming data from the device. 

        Args:
            channel (CHANNEL): The channel to stream data from.
            samples (int): The number of samples to acquire in each streaming segment.
            interval (int): The time interval between samples.
            time_units (PICO_TIME_UNIT): Units for the sample interval (e.g., microseconds).
            max_buffer_size (int | None): Maximum number of samples the python buffer can hold.
                If None, the buffer will not constrain.
            pre_trig_samples (int, optional): Number of samples to capture before a trigger event.
                Defaults to 0.
            post_trig_samples (int, optional): Number of samples to capture after a trigger event.
                Defaults to 250.
            ratio (int, optional): Downsampling ratio to apply to the captured data.
                Defaults to 0 (no downsampling).
            ratio_mode (RATIO_MODE, optional): Mode used for applying the downsampling ratio.
                Defaults to RATIO_MODE.RAW.
            data_type (DATA_TYPE, optional): Data type for the samples in the buffer.
                Defaults to DATA_TYPE.INT16_T.

        Returns:
            None
        """
        # Streaming settings 
        self.channel = channel
        self.samples = samples
        self.pre_trig_samples = pre_trig_samples
        self.post_trig_samples = post_trig_samples
        self.interval = interval
        self.time_units = time_units
        self.ratio = ratio
        self.ratio_mode = ratio_mode
        self.data_type = data_type

        # python buffer setup
        self.info_list = [] # List of info retrieved from each buffer
        if max_buffer_size is None:
            self.buffer_array = np.empty(0)
        else:
            self.buffer_array = np.zeros(shape=max_buffer_size)  # Main sample buffer
        self.max_buffer_size = max_buffer_size # Maximum size of buffer before overwriting

    def add_channel(
            self,
            channel:CHANNEL,
            ratio_mode:RATIO_MODE=RATIO_MODE.RAW,
            data_type:DATA_TYPE=DATA_TYPE.INT16_T,
        ) -> None:
        """
        !NOT YET IMPLEMETED!
        Adds a channel configuration for data acquisition.

        This method appends a new channel configuration to the internal list,
        specifying the channel, ratio mode, and data type to be used for streaming.

        Args:
            channel (CHANNEL): The channel to add for streaming.
            ratio_mode (RATIO_MODE, optional): The downsampling ratio mode for this channel.
                Defaults to RATIO_MODE.RAW.
            data_type (DATA_TYPE, optional): The data type to use for samples from this channel.
                Defaults to DATA_TYPE.INT16_T.

        Returns:
            None
        """
        self.channel_config.append([channel, ratio_mode, data_type])
        

    def run_streaming(self) -> None:
        """
        Initiates the data streaming process.

        This method prepares the device for streaming by clearing existing data buffers, 
        setting up a new data buffer for the selected channel, and starting the streaming process 
        with the configured parameters such as sample interval, trigger settings, and downsampling options.

        The method resets internal buffer indices and flags to prepare for incoming data.
        """
        self.buffer_index = 0
        self.stop_bool = False
        # Setup empty variables for streaming
        # Setup initial buffer for streaming
        self.scope.set_data_buffer(0, 0, action=ACTION.CLEAR_ALL) # Clear all buffers
        self.buffer = self.scope.set_data_buffer(self.channel, self.samples, segment=0)
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
    
    def main_streaming_loop(self) -> None:
        """
        Main loop for handling streaming data acquisition.

        This method retrieves the latest streaming data from the device, appends new 
        samples to the internal buffer array, and manages buffer rollover when the 
        hardware buffer becomes full.

        The method ensures that the internal buffer (`self.buffer_array`) always 
        contains the most recent samples up to `max_buffer_size`. It also handles 
        alternating between buffer segments when a buffer overflow condition is detected.
        """

        info = self.scope.get_streaming_latest_values(
            channel=self.channel,
            ratio_mode=self.ratio_mode,
            data_type=self.data_type
        )
        n_samples = info['no of samples']
        start_index = info['start index']
        # If buffer isn't empty, add data to array
        if n_samples > 0:
            # Add the new buffer to the buffer array and take end chunk
            self.buffer_array = np.concatenate([self.buffer_array] + [self.buffer[start_index:start_index+n_samples]])
            if self.max_buffer_size is not None:
                self.buffer_array = self.buffer_array[-self.max_buffer_size:]
        # If buffer full, create new buffer
        if info['status'] == 407:
            self.buffer_index = (self.buffer_index + 1) % 2 # Switch between buffer segment index 0*samples and 1*samples
            self.buffer = self.scope.set_data_buffer(self.channel, self.samples, segment=self.buffer_index*self.samples, action=ACTION.ADD)

    def run_streaming_while(self) -> None:
        """
        Starts and continuously runs the streaming acquisition loop until
        StreamingScope.stop() is called.
        """
        self.run_streaming()
        while not self.stop_bool:
            self.main_streaming_loop()

    def run_streaming_for(self, n_times) -> None:
        """
        Runs the streaming acquisition loop for a fixed number of iterations.

        Args:
            n_times (int): Number of iterations to run the streaming loop.
        """

        if self.max_buffer_size is not None:
            warn('max_buffer_data needs to be None to retrieve the full streaming data.')
        self.run_streaming()
        for i in range(n_times):
            self.main_streaming_loop()

    def run_streaming_for_samples(self, no_of_samples) -> np.ndarray:
        """
        Runs streaming acquisition until a specified number of samples are collected.
        The loop will terminate early if `StreamingScope.stop()` is called.

        Args:
            no_of_samples (int): The total number of samples to acquire before stopping.

        Returns:
            numpy.ndarray: The buffer array containing the collected samples.
        """
        self.run_streaming()
        while not self.stop_bool:
            self.main_streaming_loop()
            if len(self.buffer_array) >= no_of_samples:
                return self.buffer_array


    def stop(self):
        """Signals the streaming loop to stop."""
        self.stop_bool = True

