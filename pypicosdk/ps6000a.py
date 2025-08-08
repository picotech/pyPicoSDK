import ctypes

from .constants import *
from .common import PicoSDKException
from .base import PicoScopeBase
from .shared.ps6000a_psospa import shared_ps6000a_psospa
from .shared.ps6000a_ps4000a import shared_4000a_6000a

class ps6000a(PicoScopeBase, shared_ps6000a_psospa, shared_4000a_6000a):
    """PicoScope 6000 (A) API specific functions"""
    def __init__(self, *args, **kwargs):
        super().__init__("ps6000a", *args, **kwargs)

    def open_unit(self, serial_number:str=None, resolution:RESOLUTION | resolution_literal=0) -> None:
        # If using Literals, convert to int
        if resolution in resolution_map:
            resolution = resolution_map[resolution]

        super().open_unit(serial_number, resolution)
        self.min_adc_value, self.max_adc_value =super().get_adc_limits()
    
    def get_channel_combinations(self, timebase: int) -> list[int]:
        """Return valid channel flag combinations for a proposed timebase.
        This wraps ``ps6000aChannelCombinationsStateless`` and requires the
        device to be opened first.
        Args:
            timebase: Proposed timebase value to test.
        Returns:
            list[int]: Sequence of bit masks using :class:`PICO_CHANNEL_FLAGS`.
        Raises:
            PicoSDKException: If the device has not been opened.
        """

        if self.resolution is None:
            raise PicoSDKException("Device has not been initialized, use open_unit()")

        n_combos = ctypes.c_uint32()
        # First call obtains the required array size
        self._call_attr_function(
            "ChannelCombinationsStateless",
            self.handle,
            None,
            ctypes.byref(n_combos),
            self.resolution,
            ctypes.c_uint32(timebase),
        )

        combo_array = (ctypes.c_uint32 * n_combos.value)()
        self._call_attr_function(
            "ChannelCombinationsStateless",
            self.handle,
            combo_array,
            ctypes.byref(n_combos),
            self.resolution,
            ctypes.c_uint32(timebase),
        )

        return list(combo_array)

    def get_accessory_info(self, channel: CHANNEL, info: UNIT_INFO) -> str:
        """Return accessory details for the given channel.
        This wraps the driver ``GetAccessoryInfo`` call which retrieves
        information about any accessory attached to ``channel``.
        Args:
            channel: Channel the accessory is connected to.
            info: Information field requested from :class:`UNIT_INFO`.
        Returns:
            str: Information string provided by the driver.
        """

        string = ctypes.create_string_buffer(16)
        string_length = ctypes.c_int16(32)
        required_size = ctypes.c_int16(32)

        self._call_attr_function(
            "GetAccessoryInfo",
            self.handle,
            channel,
            string,
            string_length,
            ctypes.byref(required_size),
            ctypes.c_uint32(info),
        )

        return string.value.decode()

    def set_simple_trigger(
            self, 
            channel:CHANNEL | channel_literal, 
            threshold_mv=0, 
            enable=True, 
            direction:TRIGGER_DIR=TRIGGER_DIR.RISING, 
            delay=0, 
            auto_trigger_ms=5_000):
        
        # Check if typing Literals
        if channel in channel_map:
            channel = channel_map[channel]

        auto_trigger_us = auto_trigger_ms * 1000
        return super().set_simple_trigger(channel, threshold_mv, enable, direction, delay, auto_trigger_us)
    
    def siggen_clock_manual(self, dac_clock_frequency: float, prescale_ratio: int) -> None:
        """Manually control the signal generator clock.
        Args:
            dac_clock_frequency: Frequency of the DAC clock in Hz.
            prescale_ratio: Prescale divisor for the DAC clock.
        """

        self._call_attr_function(
            "SigGenClockManual",
            self.handle,
            ctypes.c_double(dac_clock_frequency),
            ctypes.c_uint64(prescale_ratio),
        )

    def siggen_filter(self, filter_state: SIGGEN_FILTER_STATE) -> None:
        """Enable or disable the signal generator output filter.
        Args:
            filter_state: can be set on or off, or put in automatic mode.
        """

        self._call_attr_function(
            "SigGenFilter",
            self.handle,
            filter_state,
        )
    
__all__ = ['ps6000a']
