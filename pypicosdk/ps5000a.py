from .base import PicoScopeBase
from .constants import CHANNEL, RANGE, COUPLING, TRIGGER_DIR, RESOLUTION, RATIO_MODE

class ps5000a(PicoScopeBase):
    def __init__(self, *args, **kwargs):
        super().__init__("ps5000a", *args, **kwargs)

    def open_unit(self, serial_number=None, resolution=RESOLUTION):
        status = super()._open_unit(serial_number, resolution)
        self.max_adc_value = super()._get_maximum_adc_value()
        return status

    def set_channel(self, channel, range, enabled=True, coupling=COUPLING.DC, offset=0):
        return super()._set_channel(channel, range, enabled, coupling, offset)
    
    def get_timebase(self, timebase, samples, segment=0):
        return super()._get_timebase_2(timebase, samples, segment)
    
    def set_simple_trigger(self, channel, threshold_mv, enable=True, direction=TRIGGER_DIR.RISING, delay=0, auto_trigger_ms=5000):
        """
        Sets up a simple trigger from a specified channel and threshold in mV

        Args:
            channel (int): The input channel to apply the trigger to.
            threshold_mv (float): Trigger threshold level in millivolts.
            enable (bool, optional): Enables or disables the trigger. 
            direction (TRIGGER_DIR, optional): Trigger direction (e.g., TRIGGER_DIR.RISING, TRIGGER_DIR.FALLING). 
            delay (int, optional): Delay in samples after the trigger condition is met before starting capture. 
            auto_trigger_ms (int, optional): Timeout in milliseconds after which data capture proceeds even if no trigger occurs. 
        """
        return super().set_simple_trigger(channel, threshold_mv, enable, direction, delay, auto_trigger_ms)
    
    def set_data_buffer(self, channel, samples, segment=0, ratio_mode=0):
        return super()._set_data_buffer_ps5000a(channel, samples, segment, ratio_mode)
    
    def set_data_buffer_for_enabled_channels(self, samples, segment=0, ratio_mode=0):
        channels_buffer = {}
        for channel in self.range:
            channels_buffer[channel] = super()._set_data_buffer_ps5000a(channel, samples, segment, ratio_mode)
        return channels_buffer
    
    def change_power_source(self, state):
        return super()._change_power_source(state)

