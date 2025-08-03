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
        self.result_array = 'append'    # Format to save data
        self.channel_config = []

    def config_streaming(
            self, 
            channel, 
            samples, 
            interval, 
            time_units,
            max_buffer_size:int | None,
            pre_trig_samples=0,
            post_trig_samples=250,
            ratio=0,
            ratio_mode=RATIO_MODE.RAW,
            data_type=DATA_TYPE.INT16_T,
        ):
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
        self.channel_config.append[channel, ratio_mode, data_type]
        

    def run_streaming(self):
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
    
    def main_streaming_loop(self):
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
            self.buffer = (self.buffer_index + 1) % 2 # Switch between buffer segment index 0*samples and 1*samples
            self.buffer = self.scope.set_data_buffer(self.channel, self.samples, segment=self.buffer_index*self.samples, action=ACTION.ADD)

    def run_streaming_while(self, stop=True):
        self.run_streaming()
        while not self.stop_bool:
            self.main_streaming_loop()

    def run_streaming_for(self, n_times):
        if self.max_buffer_size is not None:
            warn('max_buffer_data needs to be None to retrieve the full streaming data.')
        self.run_streaming()
        for i in range(n_times):
            self.main_streaming_loop()

    def run_streaming_for_samples(self, no_of_samples):
        self.run_streaming()
        while not self.stop_bool:
            self.main_streaming_loop()
            # print(len(self.buffer_array))
            if len(self.buffer_array) >= no_of_samples:
                return self.buffer_array


    def stop(self):
        self.stop_bool = True

