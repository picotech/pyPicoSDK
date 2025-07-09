import ctypes
import os
import warnings
import platform
import typing
import numpy as np

from .error_list import ERROR_STRING
from .constants import *
from .version import VERSION

# Exceptions
class PicoSDKNotFoundException(Exception):
    pass

class PicoSDKException(Exception):
    pass

class OverrangeWarning(UserWarning):
    pass

class PowerSupplyWarning(UserWarning):
    pass


# General Functions
def _check_path(location, folders):
    """Return the first existing path from ``folders`` joined to ``location``.

    Args:
        location (str): Base directory to search within.
        folders (Iterable[str]): Candidate folder names relative to ``location``.

    Returns:
        str: The full path to the first folder found.

    Raises:
        PicoSDKException: If none of the provided paths exist.
    """
    for folder in folders:
        path = os.path.join(location, folder)
        if os.path.exists(path):
            return path
    raise PicoSDKException(
        "No PicoSDK or PicoScope 7 drivers installed, get them from http://picotech.com/downloads"
    )

def _get_lib_path() -> str:
    """Determine the platform-specific directory containing PicoSDK libraries.

    Returns:
        str: Absolute path to the PicoSDK library directory.

    Raises:
        PicoSDKException: If the platform is unsupported or required drivers are
            missing.
    """
    system = platform.system()
    if system == "Windows":
        program_files = os.environ.get("PROGRAMFILES")
        checklist = [
            "Pico Technology\\SDK\\lib",
            "Pico Technology\\PicoScope 7 T&M Stable",
            "Pico Technology\\PicoScope 7 T&M Early Access",
        ]
        return _check_path(program_files, checklist)
    elif system == "Linux":
        return _check_path("opt", "picoscope")
    elif system == "Darwin":
        raise PicoSDKException("macOS is not yet tested and supported")
    else:
        raise PicoSDKException("Unsupported OS")



# PicoScope Classes
class PicoScopeBase:
    """PicoScope base class including common SDK and python modules and functions"""
    # Class Functions
    def __init__(self, dll_name, *args, **kwargs):
        """Initialise a PicoScope wrapper and load the underlying SDK library.

        Args:
            dll_name (str): Prefix of the PicoSDK DLL for this scope model.
            *args: Optional positional arguments. Passing ``"pytest"`` skips DLL
                loading for unit tests.
            **kwargs: Additional keyword arguments (unused).
        """

        # Pytest override
        self._pytest = "pytest" in args

        # Setup DLL location per device
        if self._pytest:
            self.dll = None
        else:
            self.dll = ctypes.CDLL(os.path.join(_get_lib_path(), dll_name + ".dll"))
        self._unit_prefix_n = dll_name

        # Setup class variables
        self.handle = ctypes.c_short()
        self.range = {}
        self.resolution = None
        self.max_adc_value = None
        self.min_adc_value = None
        self.over_range = 0
    
    def __exit__(self):
        """Context manager cleanup that closes the PicoScope unit."""
        self.close_unit()

    def __del__(self):
        """Destructor ensuring the PicoScope unit is closed."""
        self.close_unit()

    # General Functions
    def _get_attr_function(self, function_name: str) -> ctypes.CDLL:
        """
        Returns ctypes function based on sub-class prefix name.

        For example, `_get_attr_function("OpenUnit")` will return `self.dll.ps####aOpenUnit()`.

        Args:
            function_name (str): PicoSDK function name, e.g., "OpenUnit".

        Returns:
            ctypes.CDLL: CDLL function for the specified name.
        """
        return getattr(self.dll, self._unit_prefix_n + function_name)
    
    def _error_handler(self, status: int) -> None:
        """
        Checks status code against error list; raises an exception if not 0.

        Errors such as `SUPPLY_NOT_CONNECTED` are returned as warnings.

        Args:
            status (int): Returned status value from PicoSDK.

        Raises:
            PicoSDKException: Pythonic exception based on status value.
        """
        error_code = ERROR_STRING[status]
        if status != 0:
            if status in [POWER_SOURCE.SUPPLY_NOT_CONNECTED]:
                warnings.warn('Power supply not connected.', 
                              PowerSupplyWarning)
                return
            self.close_unit()
            raise PicoSDKException(error_code)
        return
    
    def _call_attr_function(self, function_name:str, *args) -> int:
        """
        Calls a specific attribute function with the provided arguments.

        Args:
            function_name (str): PicoSDK function suffix.

        Returns:
            int: Returns status integer of PicoSDK dll.
        """
        attr_function = self._get_attr_function(function_name)
        status = attr_function(*args)
        self._error_handler(status)
        return status

    # General PicoSDK functions    
    def _open_unit(self, serial_number: int | None = None, resolution: RESOLUTION = RESOLUTION._8BIT) -> None:
        """
        Opens PicoScope unit.

        Args:
            serial_number (int, optional): Serial number of specific unit, e.g., JR628/0017.
            resolution (RESOLUTION, optional): Resolution of device. 
        """

        if serial_number is not None:
            serial_number = serial_number.encode()
        self._call_attr_function(
            'OpenUnit',
            ctypes.byref(self.handle),
            serial_number, 
            resolution
        )
        self.resolution = resolution
    
    def close_unit(self) -> None:
        """
        Closes the PicoScope device and releases the hardware handle.

        This calls the PicoSDK `CloseUnit` function to properly disconnect from the device.

        Returns:
                None
        """
        if self._pytest:
            return
        else:
            self._get_attr_function('CloseUnit')(self.handle)

    def stop(self) -> None: 
        """
        This function stops the scope device from sampling data
        """
        self._call_attr_function(
            'Stop',
            self.handle
        )

    def is_ready(self) -> None:
        """
        Blocks execution until the PicoScope device is ready.

        Continuously calls the PicoSDK `IsReady` function in a loop, checking if
        the device is prepared to proceed with data acquisition.

        Returns:
                None
        """

        ready = ctypes.c_int16()
        attr_function = getattr(self.dll, self._unit_prefix_n + "IsReady")
        while True:
            status = attr_function(
                self.handle, 
                ctypes.byref(ready)
            )
            self._error_handler(status)
            if ready.value != 0:
                break
    
    # Get information from PicoScope
    def get_unit_info(self, unit_info: UNIT_INFO) -> str:
        """
        Get specified information from unit. Use UNIT_INFO.XXXX or integer.

        Args:
            unit_info (UNIT_INFO): Specify information from PicoScope unit i.e. UNIT_INFO.PICO_BATCH_AND_SERIAL.

        Returns:
            str: Returns data from device.
        """
        string = ctypes.create_string_buffer(16)
        string_length = ctypes.c_int16(32)
        required_size = ctypes.c_int16(32)
        status = self._call_attr_function(
            'GetUnitInfo',
            self.handle,
            string,
            string_length,
            ctypes.byref(required_size),
            ctypes.c_uint32(unit_info)
        )
        return string.value.decode()
    
    def get_unit_serial(self) -> str:
        """
        Get and return batch and serial of unit.

        Returns:
                str: Returns serial, e.g., "JR628/0017".
        """
        return self.get_unit_info(UNIT_INFO.PICO_BATCH_AND_SERIAL)
    
    def _get_enabled_channel_flags(self) -> int:
        """
        Returns integer of enabled channels as a binary code.
        Where channel A is LSB.
        I.e. Channel A and channel C would be '0101' -> 5

        Returns:
            int: Decimal of enabled channels
        """
        enabled_channel_byte = 0
        for channel in self.range:
            enabled_channel_byte += 2**channel
        return enabled_channel_byte
    
    def get_nearest_sampling_interval(self, interval_s:float) -> dict:
        """
        This function returns the nearest possible sample interval to the requested 
        sample interval. It does not change the configuration of the oscilloscope.

        Channels need to be setup first before calculating as more channels may 
        increase sample interval.

        Args:
            interval_s (float): Time value in seconds (s) you would like to obtain.

        Returns:
            dict: Dictionary of suggested timebase and actual sample interval in seconds (s).
        """
        timebase = ctypes.c_uint32()
        time_interval = ctypes.c_double()
        self._call_attr_function(
            'NearestSampleIntervalStateless',
            self.handle,
            self._get_enabled_channel_flags(),
            ctypes.c_double(interval_s),
            self.resolution,
            ctypes.byref(timebase),
            ctypes.byref(time_interval),
        )
        return {"timebase": timebase.value, "actual_sample_interval": time_interval.value}
    
    def get_timebase(timebase, samples):
        # Override for PicoScopeBase
        raise NotImplemented("Method not yet available for this oscilloscope")
    
    def _get_timebase(self, timebase: int, samples: int, segment:int=0) -> dict:
        """
        This function calculates the sampling rate and maximum number of 
        samples for a given timebase under the specified conditions.

        Args:
                timebase (int): Selected timebase multiplier (refer to programmer's guide).
                samples (int): Number of samples.
                segment (int, optional): The index of the memory segment to use.

        Returns:
                dict: Returns interval (ns) and max samples as a dictionary.
        """
        time_interval_ns = ctypes.c_double()
        max_samples = ctypes.c_uint64()
        attr_function = getattr(self.dll, self._unit_prefix_n + 'GetTimebase')
        status = attr_function(
            self.handle,
            timebase,
            samples,
            ctypes.byref(time_interval_ns),
            ctypes.byref(max_samples),
            segment
        )
        self._error_handler(status)
        return {"Interval(ns)": time_interval_ns.value, 
                "Samples":          max_samples.value}
    
    def _get_timebase_2(self, timebase: int, samples: int, segment:int=0):
        """
        Calculates the sampling rate and maximum number of samples for a given
        timebase under the specified conditions.

        Args:
                timebase (int): Selected timebase multiplier (refer to programmer's guide).
                samples (int): Number of samples.
                segment (int, optional): Index of the memory segment to use.

        Returns:
                dict: Dictionary containing:
                        - 'interval' (ns): Time interval between samples.
                        - 'max_samples': Maximum number of samples.
        """
        time_interval_ns = ctypes.c_float()
        max_samples = ctypes.c_int32()
        attr_function = getattr(self.dll, self._unit_prefix_n + 'GetTimeBase2')
        status = attr_function(
            self.handle,
            timebase,
            samples,
            ctypes.byref(time_interval_ns),
            ctypes.byref(max_samples),
            segment
        )
        self._error_handler(status)
        return {"Interval(ns)": time_interval_ns.value, 
                "Samples":          max_samples.value}
    
    def sample_rate_to_timebase(self, sample_rate:float, unit=SAMPLE_RATE.MSPS):
        """
        Converts sample rate to a PicoScope timebase value based on the 
        attached PicoScope.

        This function will return the closest possible timebase.
        Use `get_nearest_sample_interval(interval_s)` to get the full timebase and 
        actual interval achieved.

        Args:
            sample_rate (int): Desired sample rate 
            unit (SAMPLE_RATE): unit of sample rate.
        """
        interval_s = 1 / (sample_rate * unit)
        
        return self.get_nearest_sampling_interval(interval_s)["timebase"]
    
    def interval_to_timebase(self, interval:float, unit=TIME_UNIT.S):
        """
        Converts a time interval (between samples) into a PicoScope timebase 
        value based on the attached PicoScope.

        This function will return the closest possible timebase.
        Use `get_nearest_sample_interval(interval_s)` to get the full timebase and 
        actual interval achieved.

        Args:
            interval (float): Desired time interval between samples
            unit (TIME_UNIT, optional): Time unit of interval.
        """
        interval_s = interval / unit
        return self.get_nearest_sampling_interval(interval_s)["timebase"]
    
    def _get_adc_limits(self) -> tuple:
        """
        Gets the ADC limits for specified devices.

        Currently tested on: 6000a.

        Returns:
                tuple: (minimum value, maximum value)

        Raises:
                PicoSDKException: If device hasn't been initialized.
        """
        if self.resolution is None:
            raise PicoSDKException("Device has not been initialized, use open_unit()")
        min_value = ctypes.c_int32()
        max_value = ctypes.c_int32()
        self._call_attr_function(
            'GetAdcLimits',
            self.handle,
            self.resolution,
            ctypes.byref(min_value),
            ctypes.byref(max_value)
        )
        return min_value.value, max_value.value
    
    def _get_maximum_adc_value(self) -> int:
        """
        Gets the ADC limits for specified devices.

        Currently tested on: 6000a.

        Returns:
                int: Maximum ADC value.
        """
        max_value = ctypes.c_int16()
        self._call_attr_function(
            'MaximumValue',
            self.handle,
            ctypes.byref(max_value)
        )
        return max_value.value

    def get_time_axis(self, timebase:int, samples:int, unit: TIME_UNIT | None = TIME_UNIT.NS):
        """Return a NumPy array of time values for a capture.

        The returned array is generated using the sampling interval provided by
        :meth:`get_timebase`.  Users can specify the units for these values; if
        ``unit`` is ``None`` the method will choose a sensible unit based on the
        capture's total duration.

        Args:
            timebase (int): PicoScope timebase
            samples (int): Number of samples captured
            unit (TIME_UNIT | None, optional): Desired time units.  If ``None``
                an appropriate unit is chosen automatically.

        Returns:
            numpy.ndarray: Array of time values in the specified units
        """
        interval_ns = self.get_timebase(timebase, samples)['Interval(ns)']

        # Autoselect a sensible unit when not explicitly provided
        if unit is None:
            total_s = (interval_ns * samples) / TIME_UNIT.NS
            if total_s < 1e-6:
                unit = TIME_UNIT.NS
            elif total_s < 1e-3:
                unit = TIME_UNIT.US
            elif total_s < 1:
                unit = TIME_UNIT.MS
            else:
                unit = TIME_UNIT.S

        scale = unit / TIME_UNIT.NS
        interval = interval_ns * scale

        return np.around(np.arange(samples, dtype=float) * interval, 4)
    
    def get_trigger_time_offset(self, time_unit: TIME_UNIT, segment_index: int = 0) -> int:
        """
        Get the trigger time offset for jitter correction in waveforms.

        Args:
            time_unit (TIME_UNITS): Unit in which the trigger time offset will be returned.
            segment_index (int, optional): The memory segment to query. Default is 0.

        Returns:
            int: Trigger time offset in specified units.

        Raises:
            PicoSDKException: If the function call fails or preconditions are not met.
        """
        time = ctypes.c_int64()
        self._call_attr_function(
            'GetTriggerTimeOffset',
            self.handle,
            ctypes.byref(time),
            PICO_TIME_UNIT[time_unit.name],
            segment_index
        )
        return time.value

    def get_trigger_info(
        self,
        first_segment_index: int = 0,
        segment_count: int = 1,
    ) -> typing.Union[PICO_TRIGGER_INFO, list[PICO_TRIGGER_INFO]]:
        """Retrieve trigger timing information for one or more segments.

        This wraps the ``ps6000aGetTriggerInfo`` API call and returns one or
        more :class:`~pypicosdk.constants.PICO_TRIGGER_INFO` structures.

        Args:
            first_segment_index: Index of the first memory segment to query.
            segment_count: Number of consecutive segments starting at
                ``first_segment_index``.

        Returns:
            ``PICO_TRIGGER_INFO`` if ``segment_count`` is ``1`` otherwise a
            list of ``PICO_TRIGGER_INFO`` objects.

        Raises:
            PicoSDKException: If the driver call fails.
        """

        info_array = (PICO_TRIGGER_INFO * segment_count)()

        self._call_attr_function(
            "GetTriggerInfo",
            self.handle,
            ctypes.byref(info_array[0]),
            ctypes.c_uint64(first_segment_index),
            ctypes.c_uint64(segment_count),
        )

        if segment_count == 1:
            return info_array[0]
        return list(info_array)

    def get_values_trigger_time_offset_bulk(
        self,
        from_segment_index: int,
        to_segment_index: int,
    ) -> list[tuple[int, PICO_TIME_UNIT]]:
        """Retrieve trigger time offsets for a range of segments.

        This method calls ``ps6000aGetValuesTriggerTimeOffsetBulk`` and returns
        the trigger time offset and associated time unit for each requested
        segment.

        Args:
            from_segment_index: First segment index in the range.
            to_segment_index: Last segment index in the range.

        Returns:
            list[tuple[int, PICO_TIME_UNIT]]: Trigger offsets and units per
                segment.

        Raises:
            PicoSDKException: If the driver call fails.
        """

        count = to_segment_index - from_segment_index + 1
        times = (ctypes.c_int64 * count)()
        units = (ctypes.c_int32 * count)()

        self._call_attr_function(
            "GetValuesTriggerTimeOffsetBulk",
            self.handle,
            ctypes.byref(times),
            ctypes.byref(units),
            ctypes.c_uint64(from_segment_index),
            ctypes.c_uint64(to_segment_index),
        )

        return [
            (times[i], PICO_TIME_UNIT(units[i]))
            for i in range(count)
        ]

    def memory_segments(self, n_segments: int) -> int:
        """Configure the number of memory segments on the device.

        Args:
            n_segments (int): Desired number of memory segments.

        Returns:
            int: Maximum number of samples available per segment.
        """
        max_samples = ctypes.c_uint64()
        self._call_attr_function(
            "MemorySegments",
            self.handle,
            ctypes.c_uint64(n_segments),
            ctypes.byref(max_samples),
        )
        return max_samples.value

    def memory_segments_by_samples(self, n_samples: int) -> int:
        """Divide memory so each segment holds ``n_samples`` samples.

        Args:
            n_samples (int): Number of samples required per segment.

        Returns:
            int: Number of segments created by the driver.
        """
        max_segments = ctypes.c_uint64()
        self._call_attr_function(
            "MemorySegmentsBySamples",
            self.handle,
            ctypes.c_uint64(n_samples),
            ctypes.byref(max_segments),
        )
        return max_segments.value

    def query_max_segments_by_samples(self, n_samples: int, n_channel_enabled: int) -> int:
        """Query the maximum segments available for a capture setup.

        Args:
            n_samples (int): Number of samples per segment.
            n_channel_enabled (int): Number of channels enabled.

        Returns:
            int: Maximum number of segments supported.
        """
        max_segments = ctypes.c_uint64()
        self._call_attr_function(
            "QueryMaxSegmentsBySamples",
            self.handle,
            ctypes.c_uint64(n_samples),
            ctypes.c_uint32(n_channel_enabled),
            ctypes.byref(max_segments),
            self.resolution,
        )
        return max_segments.value


    
    # Data conversion ADC/mV & ctypes/int 
    def mv_to_adc(self, mv:float, channel_range:int) -> int:
        """
        Converts a millivolt (mV) value to an ADC value based on the device's
        maximum ADC range.

        Args:
                mv (float): Voltage in millivolts to be converted.
                channel_range (int): Range of channel in millivolts i.e. 500 mV.

        Returns:
                int: ADC value corresponding to the input millivolt value.
        """
        channel_range_mv = RANGE_LIST[channel_range]
        return int((mv / channel_range_mv) * self.max_adc_value)
    
    def adc_to_mv(self, adc: int, channel_range: int):
        "Converts ADC value to mV - based on maximum ADC value"
        channel_range_mv = float(RANGE_LIST[channel_range])
        return (float(adc) / float(self.max_adc_value)) * channel_range_mv
    
    def buffer_adc_to_mv(self, buffer: list, channel: str) -> list:
        """Converts an ADC buffer list to mV list"""
        return [self.adc_to_mv(sample, self.range[channel]) for sample in buffer]
    
    def channels_buffer_adc_to_mv(self, channels_buffer: dict) -> dict:
        "Converts dict of multiple channels adc values to millivolts (mV)"
        for channel in channels_buffer:
            channels_buffer[channel] = self.buffer_adc_to_mv(channels_buffer[channel], channel)
        return channels_buffer
    
    def buffer_ctypes_to_list(self, ctypes_list):
        "Converts a ctype dataset into a python list of samples"
        return [sample for sample in ctypes_list]
    
    def channels_buffer_ctype_to_list(self, channels_buffer):
        "Takes a ctypes channel dictionary buffer and converts into a integer array."
        for channel in channels_buffer:
            channels_buffer[channel] = self.buffer_ctypes_to_list(channels_buffer[channel])
        return channels_buffer

    def get_plot_range(self) -> tuple:
        """Return plot limits based on the widest enabled channel range."""
        if not self.range:
            raise PicoSDKException("No channels have been configured using set_channel()")
        max_mv = max(RANGE_LIST[r] for r in self.range.values())
        return -max_mv, max_mv

    # Set methods for PicoScope configuration    
    def _change_power_source(self, state: POWER_SOURCE) -> 0:
        """
        Change the power source of a device to/from USB only or DC + USB.

        Args:
                state (POWER_SOURCE): Power source variable (i.e. POWER_SOURCE.SUPPLY_NOT_CONNECTED).
        """
        self._call_attr_function(
            'ChangePowerSource',
            self.handle,
            state
        )

    def _set_channel_on(self, channel, range, coupling=COUPLING.DC, offset=0.0, bandwidth=BANDWIDTH_CH.FULL):
        """Sets a channel to ON at a specified range (6000E)"""
        self.range[channel] = range
        attr_function = getattr(self.dll, self._unit_prefix_n + 'SetChannelOn')
        status = attr_function(
            self.handle,
            channel,
            coupling,
            range,
            ctypes.c_double(offset),
            bandwidth
        )
        return self._error_handler(status)
    
    def _set_channel_off(self, channel):
        """Sets a channel to OFF (6000E)"""
        attr_function = getattr(self.dll, self._unit_prefix_n + 'SetChannelOff')
        status = attr_function(
            self.handle, 
            channel
        )
        return self._error_handler(status)
    
    
    def set_simple_trigger(self, channel, threshold_mv, enable=True, direction=TRIGGER_DIR.RISING, delay=0, auto_trigger=0):
        """
        Sets up a simple trigger from a specified channel and threshold in mV

        Args:
            channel (int): The input channel to apply the trigger to.
            threshold_mv (float): Trigger threshold level in millivolts.
            enable (bool, optional): Enables or disables the trigger. 
            direction (TRIGGER_DIR, optional): Trigger direction (e.g., TRIGGER_DIR.RISING, TRIGGER_DIR.FALLING). 
            delay (int, optional): Delay in samples after the trigger condition is met before starting capture. 
            auto_trigger (int, optional): Timeout after which data capture proceeds even if no trigger occurs. 
        """
        threshold_adc = self.mv_to_adc(threshold_mv, self.range[channel])
        self._call_attr_function(
            'SetSimpleTrigger',
            self.handle,
            enable,
            channel,
            threshold_adc,
            direction,
            delay,
            auto_trigger
        )

    def set_trigger_channel_properties(
        self,
        properties: list[dict],
        aux_output_enable: int = 0,
        auto_trigger: int = 0,
    ) -> None:
        """Configure per-channel trigger thresholds."""

        prop_array_type = TRIGGER_CHANNEL_PROPERTIES * len(properties)
        prop_array = prop_array_type()
        for idx, prop in enumerate(properties):
            ch = prop["channel"]
            prop_array[idx].thresholdUpper_ = self.mv_to_adc(prop["threshold_upper"], self.range[ch])
            prop_array[idx].thresholdUpperHysteresis_ = self.mv_to_adc(prop.get("threshold_upper_hysteresis", 0), self.range[ch])
            prop_array[idx].thresholdLower_ = self.mv_to_adc(prop["threshold_lower"], self.range[ch])
            prop_array[idx].thresholdLowerHysteresis_ = self.mv_to_adc(prop.get("threshold_lower_hysteresis", 0), self.range[ch])
            prop_array[idx].channel_ = ch

        self._call_attr_function(
            "SetTriggerChannelProperties",
            self.handle,
            prop_array,
            len(properties),
            aux_output_enable,
            auto_trigger,
        )

    def set_trigger_channel_conditions(
        self,
        conditions: dict,
        action: CONDITIONS_INFO = CONDITIONS_INFO.CLEAR_CONDITIONS | CONDITIONS_INFO.ADD_CONDITION,
    ) -> None:
        """Set conditions combining multiple trigger sources."""

        cond_array_type = CONDITION * len(conditions)
        cond_array = cond_array_type()
        for idx, (ch, state) in enumerate(conditions.items()):
            cond_array[idx].source_ = ch
            cond_array[idx].condition_ = state

        self._call_attr_function(
            "SetTriggerChannelConditions",
            self.handle,
            cond_array,
            len(conditions),
            action,
        )

    def set_trigger_channel_directions(self, directions: dict) -> None:
        """Specify trigger directions for multiple channels."""

        dir_array_type = DIRECTION * len(directions)
        dir_array = dir_array_type()
        for idx, (ch, (direction, mode)) in enumerate(directions.items()):
            dir_array[idx].channel_ = ch
            dir_array[idx].direction_ = direction
            dir_array[idx].thresholdMode_ = mode

        self._call_attr_function(
            "SetTriggerChannelDirections",
            self.handle,
            dir_array,
            len(directions),
        )

    def set_advanced_trigger(
        self,
        properties: list[dict],
        directions: dict,
        conditions: dict,
        aux_output_enable: int = 0,
        auto_trigger: int = 0,
        action: CONDITIONS_INFO = CONDITIONS_INFO.CLEAR_CONDITIONS | CONDITIONS_INFO.ADD_CONDITION,
    ) -> None:
        """Configure advanced trigger properties, directions and conditions."""

        self.set_trigger_channel_properties(properties, aux_output_enable, auto_trigger)
        self.set_trigger_channel_directions(directions)
        self.set_trigger_channel_conditions(conditions, action)
    
    def set_data_buffer_for_enabled_channels():
        raise NotImplemented("Method not yet available for this oscilloscope")
    
    
    def _set_data_buffer_ps6000a(
        self,
        channel,
        samples,
        segment=0,
        datatype=DATA_TYPE.INT16_T,
        ratio_mode=RATIO_MODE.RAW,
        action=ACTION.CLEAR_ALL | ACTION.ADD,
    ) -> np.ndarray:
        """Allocate and assign a NumPy data buffer for a single channel (6000A).

        Args:
            channel (int): Channel identifier (e.g., ``CHANNEL.A``).
            samples (int): Number of samples to allocate in the buffer.
            segment (int, optional): Memory segment index to use.
            datatype (DATA_TYPE, optional): C data type of the buffer.
            ratio_mode (RATIO_MODE, optional): Downsampling mode.
            action (ACTION, optional): Buffer action flags.

        Returns:
            numpy.ndarray: The allocated buffer that will be filled with data.

        Raises:
            PicoSDKException: If ``datatype`` is not supported.
        """

        if datatype == DATA_TYPE.INT8_T:
            dtype = np.int8
        elif datatype == DATA_TYPE.INT16_T:
            dtype = np.int16
        elif datatype == DATA_TYPE.INT32_T:
            dtype = np.int32
        elif datatype == DATA_TYPE.INT64_T:
            dtype = np.int64
        elif datatype == DATA_TYPE.UINT32_T:
            dtype = np.uint32
        else:
            raise PicoSDKException("Invalid datatype selected for buffer")

        ctype = np.ctypeslib.as_ctypes_type(dtype)
        buffer = np.zeros(samples, dtype=dtype)
        buf_ptr = np.ctypeslib.as_ctypes(buffer) if samples else None

        self._call_attr_function(
            "SetDataBuffer",
            self.handle,
            channel,
            buf_ptr,
            samples,
            datatype,
            segment,
            ratio_mode,
            action,
        )

        return buffer

    def _set_data_buffers_ps6000a(
        self,
        channel,
        samples,
        segment=0,
        datatype=DATA_TYPE.INT16_T,
        ratio_mode=RATIO_MODE.AGGREGATE,
        action=ACTION.CLEAR_ALL | ACTION.ADD,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Allocate and assign maximum and minimum NumPy buffers (6000A)."""

        if datatype == DATA_TYPE.INT8_T:
            dtype = np.int8
        elif datatype == DATA_TYPE.INT16_T:
            dtype = np.int16
        elif datatype == DATA_TYPE.INT32_T:
            dtype = np.int32
        elif datatype == DATA_TYPE.INT64_T:
            dtype = np.int64
        elif datatype == DATA_TYPE.UINT32_T:
            dtype = np.uint32
        else:
            raise PicoSDKException("Invalid datatype selected for buffer")

        ctype = np.ctypeslib.as_ctypes_type(dtype)
        buffer_max = np.zeros(samples, dtype=dtype)
        buffer_min = np.zeros(samples, dtype=dtype)

        self._call_attr_function(
            "SetDataBuffers",
            self.handle,
            channel,
            np.ctypeslib.as_ctypes(buffer_max) if samples else None,
            np.ctypeslib.as_ctypes(buffer_min) if samples else None,
            samples,
            datatype,
            segment,
            ratio_mode,
            action,
        )

        return buffer_max, buffer_min
    
    # Run functions
    def run_block_capture(self, timebase, samples, pre_trig_percent=50, segment=0) -> int:
        """
        Runs a block capture using the specified timebase and number of samples.

        This sets up the PicoScope to begin collecting a block of data, divided into
        pre-trigger and post-trigger samples. It uses the PicoSDK `RunBlock` function.

        Args:
                timebase (int): Timebase value determining sample interval (refer to PicoSDK guide).
                samples (int): Total number of samples to capture.
                pre_trig_percent (int, optional): Percentage of samples to capture before the trigger. 
                segment (int, optional): Memory segment index to use.

        Returns:
                int: Estimated time (in milliseconds) the device will be busy capturing data.
        """

        pre_samples = int((samples * pre_trig_percent) / 100)
        post_samples = int(samples - pre_samples)
        time_indisposed_ms = ctypes.c_int32()
        self._call_attr_function(
            'RunBlock',
            self.handle,
            pre_samples,
            post_samples,
            timebase,
            ctypes.byref(time_indisposed_ms),
            segment,
            None,
            None
        )
        return time_indisposed_ms.value
    
    def get_enumerated_units(self) -> tuple[int, str, int]:
        """
        Returns count, serials and serial string length of a specific PicoScope unit.

        Returns:
            Number of devices of this type
            Comma separated string of all serials
            Length of string
        """
        string_buffer_length = 256
        count = ctypes.c_int16()
        serials = ctypes.create_string_buffer(string_buffer_length)
        serial_length = ctypes.c_int16(string_buffer_length)
        self._call_attr_function(
            'EnumerateUnits',
            ctypes.byref(count),
            ctypes.byref(serials),
            ctypes.byref(serial_length)
        )
        return count.value, serials.value.decode(), serial_length.value
    
    def get_values(self, samples, start_index=0, segment=0, ratio=0, ratio_mode=RATIO_MODE.RAW) -> int:
        """
        Retrieves a block of captured samples from the device once it's ready.
        If a channel goes over-range a warning will appear.

        This function should be called after confirming the device is ready using `is_ready()`.
        It invokes the underlying PicoSDK `GetValues` function to read the data into memory.

        Args:
                samples (int): Number of samples to retrieve.
                start_index (int, optional): Starting index in the buffer.
                segment (int, optional): Memory segment index to retrieve data from.
                ratio (int, optional): Downsampling ratio.
                ratio_mode (RATIO_MODE, optional): Ratio mode for downsampling. 

        Returns:
                int: Actual number of samples retrieved.
        """

        self.is_ready()
        total_samples = ctypes.c_uint32(samples)
        over_range = ctypes.c_int16()
        self._call_attr_function(
            'GetValues',
            self.handle, 
            start_index,
            ctypes.byref(total_samples),
            ratio,
            ratio_mode,
            segment,
            ctypes.byref(over_range)
        )
        self.over_range = over_range.value
        self.is_over_range()
        return total_samples.value
    
    def is_over_range(self) -> list:
        """
        Logs and prints a warning if any channel has been over range.

        Returns:
            list: List of channels that have been over range
        """

        over_range_channels = [CHANNEL_NAMES[i] for i in range(8) if self.over_range & (1 << i)]
    
        if over_range_channels:
            warnings.warn(
                f"Overrange detected on channels: {', '.join(over_range_channels)}.",
                OverrangeWarning
            )
        return over_range_channels

    def set_no_of_captures(self, n_captures: int) -> None:
        """Configure the number of captures in rapid block mode.

        Args:
            n_captures (int): Number of waveforms to capture in one run.
        """
        self._call_attr_function(
            "SetNoOfCaptures",
            self.handle,
            ctypes.c_uint64(n_captures),
        )

    def get_no_of_captures(self) -> int:
        """Return how many captures were collected in rapid block mode.

        Returns:
            int: Number of available captures.
        """
        n_captures = ctypes.c_uint64()
        self._call_attr_function(
            "GetNoOfCaptures",
            self.handle,
            ctypes.byref(n_captures),
        )
        return n_captures.value

    def get_values_bulk(
        self,
        start_index: int,
        no_of_samples: int,
        from_segment_index: int,
        to_segment_index: int,
        down_sample_ratio: int = 0,
        ratio_mode: RATIO_MODE = RATIO_MODE.RAW,
    ) -> int:
        """Retrieve multiple waveforms captured in rapid block mode.

        Args:
            start_index (int): Starting index within each buffer.
            no_of_samples (int): Number of samples requested.
            from_segment_index (int): First memory segment index.
            to_segment_index (int): Last memory segment index.
            down_sample_ratio (int, optional): Downsampling ratio.
            ratio_mode (RATIO_MODE, optional): Downsampling mode.

        Returns:
            int: Actual number of samples retrieved.
        """
        self.is_ready()
        total_samples = ctypes.c_uint64(no_of_samples)
        over_range = ctypes.c_int16()
        self._call_attr_function(
            "GetValuesBulk",
            self.handle,
            ctypes.c_uint64(start_index),
            ctypes.byref(total_samples),
            ctypes.c_uint64(from_segment_index),
            ctypes.c_uint64(to_segment_index),
            ctypes.c_uint64(down_sample_ratio),
            ratio_mode,
            ctypes.byref(over_range),
        )
        self.over_range = over_range.value
        self.is_over_range()
        return total_samples.value

    def get_values_bulk_async(
        self,
        start_index: int,
        no_of_samples: int,
        from_segment_index: int,
        to_segment_index: int,
        down_sample_ratio: int = 0,
        ratio_mode: RATIO_MODE = RATIO_MODE.RAW,
        data_ready: ctypes.c_void_p | None = None,
        parameter: ctypes.c_void_p | None = None,
    ) -> None:
        """Retrieve multiple rapid block waveforms using a callback.

        Args:
            start_index (int): Starting index within each buffer.
            no_of_samples (int): Number of samples to request.
            from_segment_index (int): First memory segment index.
            to_segment_index (int): Last memory segment index.
            down_sample_ratio (int, optional): Downsampling ratio.
            ratio_mode (RATIO_MODE, optional): Downsampling mode.
            data_ready (ctypes.c_void_p | None, optional): Callback for when data is ready.
            parameter (ctypes.c_void_p | None, optional): User parameter for callback.
        """
        self._call_attr_function(
            "GetValuesBulkAsync",
            self.handle,
            ctypes.c_uint64(start_index),
            ctypes.c_uint64(no_of_samples),
            ctypes.c_uint64(from_segment_index),
            ctypes.c_uint64(to_segment_index),
            ctypes.c_uint64(down_sample_ratio),
            ratio_mode,
            data_ready,
            parameter,
        )

    def get_values_overlapped(
        self,
        start_index: int,
        no_of_samples: int,
        down_sample_ratio: int,
        ratio_mode: RATIO_MODE,
        from_segment_index: int,
        to_segment_index: int,
    ) -> int:
        """Request data collection deferred until ``run_block_capture``.

        Args:
            start_index (int): Starting index within each buffer.
            no_of_samples (int): Number of samples requested.
            down_sample_ratio (int): Downsampling ratio.
            ratio_mode (RATIO_MODE): Downsampling mode.
            from_segment_index (int): First memory segment index.
            to_segment_index (int): Last memory segment index.

        Returns:
            int: Actual number of samples that will be captured.
        """
        total_samples = ctypes.c_uint64(no_of_samples)
        over_range = ctypes.c_int16()
        self._call_attr_function(
            "GetValuesOverlapped",
            self.handle,
            ctypes.c_uint64(start_index),
            ctypes.byref(total_samples),
            ctypes.c_uint64(down_sample_ratio),
            ratio_mode,
            ctypes.c_uint64(from_segment_index),
            ctypes.c_uint64(to_segment_index),
            ctypes.byref(over_range),
        )
        self.over_range = over_range.value
        self.is_over_range()
        return total_samples.value

    def stop_using_get_values_overlapped(self) -> None:
        """Stop deferred data collection initiated by ``get_values_overlapped``."""
        self._call_attr_function(
            "StopUsingGetValuesOverlapped",
            self.handle,
        )
        
    
    def run_simple_block_capture(self) -> dict:
        raise NotImplementedError("This method is not yet implimented in this PicoScope")
    
    # Siggen Functions
    def _siggen_apply(self, enabled=1, sweep_enabled=0, trigger_enabled=0, 
                     auto_clock_optimise_enabled=0, override_auto_clock_prescale=0) -> dict:
        """
        Sets the signal generator running using parameters previously configured.

        Args:
                enabled (int, optional): SigGen Enabled, 
                sweep_enabled (int, optional): Sweep Enabled,
                trigger_enabled (int, optional): SigGen trigger enabled,
                auto_clock_optimise_enabled (int, optional): Auto Clock Optimisation,
                override_auto_clock_prescale (int, optional): Override Clock Prescale,

        Returns:
                dict: Returns dictionary of the actual achieved values.
        """
        c_frequency = ctypes.c_double()
        c_stop_freq = ctypes.c_double()
        c_freq_incr = ctypes.c_double()
        c_dwell_time = ctypes.c_double()
        self._call_attr_function(
            'SigGenApply',
            self.handle,
            enabled,
            sweep_enabled,
            trigger_enabled,
            auto_clock_optimise_enabled,
            override_auto_clock_prescale,
            ctypes.byref(c_frequency),
            ctypes.byref(c_stop_freq),
            ctypes.byref(c_freq_incr),
            ctypes.byref(c_dwell_time)
        )
        return {'Freq': c_frequency.value,
                'StopFreq': c_stop_freq.value,
                'FreqInc': c_freq_incr.value,
                'dwelltime': c_dwell_time.value}
    
    def _siggen_set_frequency(self, frequency:float) -> None:
        """
        Set frequency of SigGen in Hz.

        Args:
                frequency (int): Frequency in Hz.
        """   
        self._call_attr_function(
            'SigGenFrequency',
            self.handle,
            ctypes.c_double(frequency)
        )

    def _siggen_set_duty_cycle(self, duty:float) -> None:
        """
        Set duty cycle of SigGen in percentage

        Args:
                Duty cycle (int): Duty cycle in %.
        """   
        self._call_attr_function(
            'SigGenWaveformDutyCycle',
            self.handle,
            ctypes.c_double(duty)
        )
    
    def _siggen_set_range(self, pk2pk:float, offset:float=0.0):
        """
        Set mV range of SigGen (6000A).

        Args:
                pk2pk (int): Peak to peak of signal in volts (V).
                offset (int, optional): Offset of signal in volts (V).
        """      
        self._call_attr_function(
            'SigGenRange',
            self.handle,
            ctypes.c_double(pk2pk),
            ctypes.c_double(offset)
        )
    
    def _siggen_set_waveform(self, wave_type: WAVEFORM):
        """
        Set waveform type for SigGen (6000A).

        Args:
                wave_type (WAVEFORM): Waveform type i.e. WAVEFORM.SINE.
        """
        self._call_attr_function(
            'SigGenWaveform',
            self.handle,
            wave_type,
            None,
            None
        )

    def set_siggen(self, *args):
        raise NotImplementedError("Method not yet available for this oscilloscope")


# Public API exports
__all__ = [
    "PicoSDKNotFoundException",
    "PicoSDKException",
    "OverrangeWarning",
    "PowerSupplyWarning",
    "PicoScopeBase",
    "UNIT_INFO",
    "RESOLUTION",
    "TRIGGER_DIR",
    "TRIGGER_STATE",
    "THRESHOLD_MODE",
    "THRESHOLD_DIRECTION",
    "CONDITIONS_INFO",
    "TRIGGER_CHANNEL_PROPERTIES",
    "CONDITION",
    "DIRECTION",
    "PICO_TRIGGER_INFO",
    "WAVEFORM",
    "CHANNEL",
    "CHANNEL_NAMES",
    "COUPLING",
    "RANGE",
    "RANGE_LIST",
    "BANDWIDTH_CH",
    "DATA_TYPE",
    "ACTION",
    "RATIO_MODE",
    "POWER_SOURCE",
    "SAMPLE_RATE",
    "TIME_UNIT",
    "PICO_TIME_UNIT",
    "VERSION",
]


