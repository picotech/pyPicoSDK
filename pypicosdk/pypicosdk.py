import ctypes
import os
import warnings
import platform
import time
import typing

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
    for folder in folders:
        path = os.path.join(location, folder)
        if os.path.exists(path):
            return path
    raise PicoSDKException("No PicoSDK or PicoScope 7 drivers installed, get them from http://picotech.com/downloads")

def _get_lib_path() -> str:
    system = platform.system()
    if system == "Windows":
        program_files = os.environ.get("PROGRAMFILES")
        checklist = [
            'Pico Technology\\SDK\\lib', 
            'Pico Technology\\PicoScope 7 T&M Stable',
            'Pico Technology\\PicoScope 7 T&M Early Access']
        return _check_path(program_files, checklist)
    elif system == "Linux":
        return _check_path('opt', 'picoscope')
    elif system == "Darwin":
        raise PicoSDKException("macOS is not yet tested and supported")
    else:
        raise PicoSDKException("Unsupported OS")

def get_all_enumerated_units() -> tuple[int, list[str]]:
    """
    Enumerates all PicoScope units supported by this wrapper
    returns the number of units and serial of each unit

    Returns:
        tuple[int, list[str]]: int of units and list of unit serials
    """
    n_units = 0
    unit_serial = []
    for scope in [ps6000a()]:
        units = scope.get_enumerated_units()
        n_units += units[0]
        unit_serial += units[1].split(',')
    return n_units, unit_serial


# PicoScope Classes
class PicoScopeBase:
    """PicoScope base class including common SDK and python modules and functions"""
    # Class Functions
    def __init__(self, dll_name, *args, **kwargs):
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
        self.close_unit()

    def __del__(self):
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
            # Certain status codes indicate that the driver is busy or waiting
            # for more data rather than an actual failure. These should not
            # raise an exception as callers may poll until data is ready.
            if status == 407:  # PICO_WAITING_FOR_DATA_BUFFERS
                return
            # Streaming related status codes indicate no new data is ready.
            # These should not be treated as fatal errors and simply signal
            # the caller to try again later.
            if status in [28672, 28673, 28674]:
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
    def _open_unit(self, serial_number:int=None, resolution:RESOLUTION=0) -> None:
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
        raise NotImplementedError("Method not yet available for this oscilloscope")
    
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

        Currently tested on: 5000a.

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
    
    def get_time_axis(self, timebase:int, samples:int) -> list:
        """
        Return an array of time values based on the timebase and number
        of samples

        Args:
            timebase (int): PicoScope timebase 
            samples (int): Number of samples captured

        Returns:
            list: List of time values in nano-seconds
        """
        interval = self.get_timebase(timebase, samples)['Interval(ns)']
        return [round(x*interval, 4) for x in range(samples)]
    
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

        This method wraps the ``ps6000aGetTriggerInfo`` API call and returns
        one or more :class:`~pypicosdk.constants.PICO_TRIGGER_INFO` structures.
        Each structure exposes attributes such as ``status_``, ``triggerTime_``
        and ``timeUnits_`` (refer to :mod:`pypicosdk.constants` for the full
        list of fields).  The ``status_`` field is a
        :class:`~pypicosdk.constants.PICO_STATUS` bit field that may include
        flags like ``PICO_DEVICE_TIME_STAMP_RESET`` or
        ``PICO_TRIGGER_TIME_NOT_REQUESTED``. ``timeUnits_`` values are defined
        by :class:`~pypicosdk.constants.PICO_TIME_UNIT`.

        Args:
            first_segment_index: Index of the first memory segment to query.
            segment_count: Number of consecutive segments starting at
                ``first_segment_index``.

        Returns:
            If ``segment_count`` is ``1``, a single ``PICO_TRIGGER_INFO``
            instance is returned. Otherwise a list of ``PICO_TRIGGER_INFO``
            objects is provided.

        Raises:
            PicoSDKException: If the function call fails or preconditions are
                not met.
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
    
    def _set_channel(self, channel, range, enabled=True, coupling=COUPLING.DC, offset=0.0):
        """Set a channel ON with a specified range (5000D)"""
        self.range[channel] = range
        status = self.dll.ps5000aSetChannel(
            self.handle,
            channel,
            enabled,
            coupling,
            range,
            ctypes.c_float(offset)
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
        if channel in self.range:
            threshold_adc = self.mv_to_adc(threshold_mv, self.range[channel])
        else:
            threshold_adc = int(threshold_mv)
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

    def set_trigger_channel_conditions(
        self,
        conditions: typing.Sequence[PICO_CONDITION],
        action: int = ACTION.CLEAR_ALL | ACTION.ADD,
    ) -> None:
        """Configure complex triggering logic using ``SetTriggerChannelConditions``.

        Args:
            conditions: Sequence of :class:`~pypicosdk.constants.PICO_CONDITION`
                structures defining the trigger logic. An empty sequence
                disables triggering.
            action: How to apply the provided conditions relative to any
                existing conditions. Defaults to ``ACTION.CLEAR_ALL | ACTION.ADD``.
        """

        n_conditions = len(conditions)
        if n_conditions:
            cond_array = (PICO_CONDITION * n_conditions)(*conditions)
            cond_ptr = cond_array
        else:
            cond_ptr = None

        self._call_attr_function(
            "SetTriggerChannelConditions",
            self.handle,
            cond_ptr,
            ctypes.c_int16(n_conditions),
            action,
        )
    
    def set_data_buffer_for_enabled_channels():
        raise NotImplementedError("Method not yet available for this oscilloscope")
    
    def _set_data_buffer_ps5000a(self, channel, samples, segment=0, ratio_mode=0):
        """Set data buffer (5000D)"""
        buffer = (ctypes.c_int16 * samples)
        buffer = buffer()
        self._call_attr_function(
            'SetDataBuffer',
            self.handle,
            channel,
            ctypes.byref(buffer),
            samples,
            segment,
            ratio_mode
        )
        return buffer
    
    def _set_data_buffer_ps6000a(self, channel, samples, segment=0, 
                                 datatype=DATA_TYPE.INT16_T, ratio_mode=RATIO_MODE.RAW, 
                                 action=ACTION.CLEAR_ALL | ACTION.ADD) -> ctypes.Array:
        """
        Allocates and assigns a data buffer for a specified channel on the 6000A series.

        Args:
            channel (int): The channel to associate the buffer with (e.g., CHANNEL.A).
            samples (int): Number of samples to allocate in the buffer.
            segment (int, optional): Memory segment to use. 
            datatype (DATA_TYPE, optional): C data type for the buffer (e.g., INT16_T). 
            ratio_mode (RATIO_MODE, optional): Downsampling mode. 
            action (ACTION, optional): Action to apply to the data buffer (e.g., CLEAR_ALL | ADD).

        Returns:
            ctypes.Array: A ctypes array that will be populated with data during capture.

        Raises:
            PicoSDKException: If an unsupported data type is provided.
        """
        if datatype == DATA_TYPE.INT8_T:     buffer = (ctypes.c_int8 * samples)
        elif datatype == DATA_TYPE.INT16_T:  buffer = (ctypes.c_int16 * samples)
        elif datatype == DATA_TYPE.INT32_T:  buffer = (ctypes.c_int32 * samples)
        elif datatype == DATA_TYPE.INT64_T:  buffer = (ctypes.c_int64 * samples)
        elif datatype == DATA_TYPE.UINT32_T: buffer = (ctypes.c_uint32 * samples)
        else: raise PicoSDKException("Invalid datatype selected for buffer")

        buffer = buffer()
        
        self._call_attr_function(
            'SetDataBuffer',
            self.handle,
            channel,
            ctypes.byref(buffer),
            samples,
            datatype,
            segment,
            ratio_mode,
            action
        )
        return buffer
    
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

    def run_streaming(
        self,
        sample_interval: float,
        sample_interval_time_units: PICO_TIME_UNIT,
        max_pre_trigger_samples: int,
        max_post_trigger_samples: int,
        auto_stop: int = 1,
        down_sample_ratio: int = 1,
        down_sample_ratio_mode: int = RATIO_MODE.RAW,
    ) -> float:
        """
        Start streaming acquisition using ``RunStreaming``.

        Args:
            sample_interval (float): Requested time between samples.
            sample_interval_time_units (PICO_TIME_UNIT): Time units for
                ``sample_interval``. See :mod:`pypicosdk.constants`.
            max_pre_trigger_samples (int): Maximum number of pre-trigger
                samples to collect.
            max_post_trigger_samples (int): Maximum number of post-trigger
                samples to collect.
            auto_stop (int, optional): ``1`` to automatically stop once
                ``max_post_trigger_samples`` have been captured.
            down_sample_ratio (int, optional): Down-sampling ratio to apply.
            down_sample_ratio_mode (RATIO_MODE, optional): Down-sampling mode
                (for example, ``RATIO_MODE.RAW`` or ``RATIO_MODE.AVERAGE``).

        Returns:
            float: The actual sampling interval in the units specified by
            ``sample_interval_time_units``.
        """

        c_sample_interval = ctypes.c_double(sample_interval)
        self._call_attr_function(
            "RunStreaming",
            self.handle,
            ctypes.byref(c_sample_interval),
            sample_interval_time_units,
            ctypes.c_uint64(max_pre_trigger_samples),
            ctypes.c_uint64(max_post_trigger_samples),
            ctypes.c_int16(auto_stop),
            ctypes.c_uint64(down_sample_ratio),
            down_sample_ratio_mode,
        )
        return c_sample_interval.value

    def get_streaming_latest_values(
        self,
        streaming_data_info,
        trigger_info: PICO_STREAMING_DATA_TRIGGER_INFO,
    ) -> None:
        """Retrieve latest streaming values into provided buffers."""

        self._call_attr_function(
            "GetStreamingLatestValues",
            self.handle,
            streaming_data_info,
            ctypes.c_uint64(len(streaming_data_info)),
            ctypes.byref(trigger_info),
        )

    def no_of_streaming_values(self) -> int:
        """Return the number of samples currently available for streaming.

        Wraps the PicoSDK ``NoOfStreamingValues`` function to query how many
        values are ready to be retrieved from the driver's internal buffer.  See
        :mod:`pypicosdk.constants` for related streaming constants.

        Returns:
            int: Number of samples that can be read using
            :py:meth:`get_streaming_latest_values`.
        """

        values = ctypes.c_uint64()
        self._call_attr_function(
            "NoOfStreamingValues",
            self.handle,
            ctypes.byref(values),
        )
        return values.value
    
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
        
    
    def run_simple_block_capture(self) -> dict:
        raise NotImplementedError("This method is not yet implemented in this PicoScope")
    
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



class ps6000a(PicoScopeBase):
    """PicoScope 6000 (A) API specific functions"""
    def __init__(self, *args, **kwargs):
        super().__init__("ps6000a", *args, **kwargs)


    def open_unit(self, serial_number:str=None, resolution:RESOLUTION = 0) -> None:
        """
        Open PicoScope unit.

        Args:
                serial_number (str, optional): Serial number of device.
                resolution (RESOLUTION, optional): Resolution of device.
        """
        super()._open_unit(serial_number, resolution)
        self.min_adc_value, self.max_adc_value =super()._get_adc_limits()
    
    def get_timebase(self, timebase:int, samples:int, segment:int=0) -> None:
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

        return super()._get_timebase(timebase, samples, segment)
    
    def set_channel(self, channel:CHANNEL, range:RANGE, enabled=True, coupling:COUPLING=COUPLING.DC, 
                    offset:float=0.0, bandwidth=BANDWIDTH_CH.FULL) -> None:
        """
        Enable/disable a channel and specify certain variables i.e. range, coupling, offset, etc.
        
        For the ps6000a drivers, this combines _set_channel_on/off to a single function. 
        Set channel on/off by adding enabled=True/False

        Args:
                channel (CHANNEL): Channel to setup.
                range (RANGE): Voltage range of channel.
                enabled (bool, optional): Enable or disable channel.
                coupling (COUPLING, optional): AC/DC/DC 50 Ohm coupling of selected channel.
                offset (int, optional): Analog offset in volts (V) of selected channel.
                bandwidth (BANDWIDTH_CH, optional): Bandwidth of channel (selected models).
        """

        if enabled:
            super()._set_channel_on(channel, range, coupling, offset, bandwidth)
        else:
            super()._set_channel_off(channel)

    def set_digital_port_on(
        self,
        port: DIGITAL_PORT,
        logic_threshold_level: list[int],
        hysteresis: DIGITAL_PORT_HYSTERESIS,
    ) -> None:
        """Enable a digital port using ``ps6000aSetDigitalPortOn``.

        Args:
            port: Digital port to enable.
            logic_threshold_level: Threshold level for each pin in millivolts.
            hysteresis: Hysteresis level applied to all pins.
        """

        level_array = (ctypes.c_int16 * len(logic_threshold_level))(
            *logic_threshold_level
        )

        self._call_attr_function(
            "SetDigitalPortOn",
            self.handle,
            port,
            level_array,
            len(logic_threshold_level),
            hysteresis,
        )

    def set_digital_port_off(self, port: DIGITAL_PORT) -> None:
        """Disable a digital port using ``ps6000aSetDigitalPortOff``."""

        self._call_attr_function(
            "SetDigitalPortOff",
            self.handle,
            port,
        )

    def set_aux_io_mode(self, mode: AUXIO_MODE) -> None:

        """Configure the AUX IO connector using ``ps6000aSetAuxIoMode``.

        Args:
            mode: Requested AUXIO mode from :class:`~pypicosdk.constants.AUXIO_MODE`.
        """

        self._call_attr_function(
            "SetAuxIoMode",
            self.handle,
            mode,
        )

    def set_simple_trigger(self, channel, threshold_mv, enable=True, direction=TRIGGER_DIR.RISING, delay=0, auto_trigger_ms=5_000):
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
        auto_trigger_us = auto_trigger_ms * 1000
        return super().set_simple_trigger(channel, threshold_mv, enable, direction, delay, auto_trigger_us)

    def set_trigger_channel_conditions(
        self,
        conditions: typing.Sequence[PICO_CONDITION],
        action: int = ACTION.CLEAR_ALL | ACTION.ADD,
    ) -> None:
        """Configure complex triggering logic using ``ps6000aSetTriggerChannelConditions``.

        This method mirrors :meth:`PicoScopeBase.set_trigger_channel_conditions` but
        documents the underlying API call specific to the 6000A series.

        Args:
            conditions: Sequence of :class:`~pypicosdk.constants.PICO_CONDITION`
                structures defining the trigger logic. An empty sequence disables
                triggering.
            action: How to combine ``conditions`` with any existing configuration.
                Defaults to ``ACTION.CLEAR_ALL | ACTION.ADD``.
        """

        super().set_trigger_channel_conditions(conditions, action)
    
    def set_data_buffer(self, channel:CHANNEL, samples:int, segment:int=0, datatype:DATA_TYPE=DATA_TYPE.INT16_T, 
                        ratio_mode:RATIO_MODE=RATIO_MODE.RAW, action:ACTION=ACTION.CLEAR_ALL | ACTION.ADD) -> ctypes.Array:
        """
        Tells the driver where to store the data that will be populated when get_values() is called.
        This function works on a single buffer. For aggregation mode, call set_data_buffers instead.

        Args:
                channel (CHANNEL): Channel you want to use with the buffer.
                samples (int): Number of samples/length of the buffer.
                segment (int, optional): Location of the buffer.
                datatype (DATATYPE, optional): C datatype of the data.
                ratio_mode (RATIO_MODE, optional): Down-sampling mode.
                action (ACTION, optional): Method to use when creating a buffer.

        Returns:
                ctypes.Array: Array that will be populated when get_values() is called.
        """
        return super()._set_data_buffer_ps6000a(channel, samples, segment, datatype, ratio_mode, action)
    
    def set_data_buffer_for_enabled_channels(self, samples:int, segment:int=0, datatype=DATA_TYPE.INT16_T, 
                                             ratio_mode=RATIO_MODE.RAW) -> dict:
        """
        Sets data buffers for enabled channels set by picosdk.set_channel()

        Args:
            samples (int): The sample buffer or size to allocate.
            segment (int): The memory segment index.
            datatype (DATA_TYPE): The data type used for the buffer.
            ratio_mode (RATIO_MODE): The ratio mode (e.g., RAW, AVERAGE).

        Returns:
            dict: A dictionary mapping each channel to its associated data buffer.
        """
        # Clear the buffer
        super()._set_data_buffer_ps6000a(0, 0, 0, 0, 0, ACTION.CLEAR_ALL)
        channels_buffer = {}
        for channel in self.range:
            channels_buffer[channel] = super()._set_data_buffer_ps6000a(channel, samples, segment, datatype, ratio_mode, action=ACTION.ADD)
        return channels_buffer
    
    def set_siggen(self, frequency:float, pk2pk:float, wave_type:WAVEFORM, offset:float=0.0, duty:float=50) -> dict:
        """Configures and applies the signal generator settings.

        Sets up the signal generator with the specified waveform type, frequency,
        amplitude (peak-to-peak), offset, and duty cycle.

        Args:
            frequency (float): Signal frequency in hertz (Hz).
            pk2pk (float): Peak-to-peak voltage in volts (V).
            wave_type (WAVEFORM): Waveform type (e.g., WAVEFORM.SINE, WAVEFORM.SQUARE).
            offset (float, optional): Voltage offset in volts (V).
            duty (int or float, optional): Duty cycle as a percentage (0–100).

        Returns:
            dict: Returns dictionary of the actual achieved values.
        """
        self._siggen_set_waveform(wave_type)
        self._siggen_set_range(pk2pk, offset)
        self._siggen_set_frequency(frequency)
        self._siggen_set_duty_cycle(duty)
        return self._siggen_apply()
    
    def run_simple_block_capture(self, timebase:int, samples:int, segment=0, start_index=0, datatype=DATA_TYPE.INT16_T, ratio=0,
                         ratio_mode=RATIO_MODE.RAW, pre_trig_percent=50) -> tuple[dict, list]:
        """
        Performs a complete single block capture using current channel and trigger configuration.

        This function sets up data buffers for all enabled channels, starts a block capture,
        and retrieves the values once the device is ready. It is a simplified interface 
        for common block capture use cases.

        Args:
            timebase (int): Timebase value determining the sample interval (refer to PicoSDK guide).
            samples (int): Total number of samples to capture.
            segment (int, optional): Memory segment index to use.
            start_index (int, optional): Starting index in the buffer.
            datatype (DATA_TYPE, optional): Data type to use for the capture buffer.
            ratio (int, optional): Downsampling ratio.
            ratio_mode (RATIO_MODE, optional): Downsampling mode.
            pre_trig_percent (int, optional): Percentage of samples to capture before the trigger.

        Returns:
            dict: A dictionary mapping each enabled channel to its corresponding data buffer.
            list: Time axis (x-axis) list of timestamps for the sample data

        Examples:
            >>> scope.set_channel(CHANNEL.A, RANGE.V1)
            >>> scope.set_simple_trigger(CHANNEL.A, threshold_mv=500)
            >>> buffers = scope.run_simple_block_capture(timebase=3, samples=1000)
        """
        # Setup data buffer for enabled channels
        channels_buffer = self.set_data_buffer_for_enabled_channels(samples, segment, datatype, ratio_mode)

        # Start block capture
        self.run_block_capture(timebase, samples, pre_trig_percent, segment)

        # Get values from PicoScope (returning actual samples for time_axis)
        actual_samples = self.get_values(samples, start_index, segment, ratio, ratio_mode)

        # Convert from ADC to mV values
        channels_buffer = self.channels_buffer_adc_to_mv(channels_buffer)

        # Generate the time axis based on actual samples and timebase
        time_axis = self.get_time_axis(timebase, actual_samples)

        return channels_buffer, time_axis

    def run_simple_streaming_capture(
        self,
        sample_interval: float,
        sample_interval_time_units: PICO_TIME_UNIT,
        samples: int,
        auto_stop: bool = True,
        datatype: DATA_TYPE = DATA_TYPE.INT16_T,
        ratio_mode: int = RATIO_MODE.RAW,
    ) -> tuple[dict, list]:
        """Perform a simple streaming capture and return buffers and time axis.

        Args:
            sample_interval (float): Desired sample interval.
            sample_interval_time_units (PICO_TIME_UNIT): Units for ``sample_interval``.
            samples (int): Number of samples to capture.
            auto_stop (bool, optional): Stop automatically once ``samples`` have been collected.
            datatype (DATA_TYPE, optional): Data type used for the capture buffer.
            ratio_mode (RATIO_MODE, optional): Downsampling mode.

        Returns:
            tuple[dict, list]: Dictionary of channel buffers (in mV) and the time axis in seconds.
        """
        channels_buffer = self.set_data_buffer_for_enabled_channels(samples, 0, datatype, ratio_mode)

        actual_interval = self.run_streaming(
            sample_interval,
            sample_interval_time_units,
            0,
            samples,
            int(auto_stop),
            1,
            ratio_mode,
        )

        collected = 0
        trigger_info = PICO_STREAMING_DATA_TRIGGER_INFO()

        while collected < samples:
            to_read = samples - collected
            data_array = (PICO_STREAMING_DATA_INFO * len(channels_buffer))()
            for idx, ch in enumerate(channels_buffer):
                data_array[idx].channel_ = ch
                data_array[idx].mode_ = ratio_mode
                data_array[idx].type_ = datatype
                data_array[idx].noOfSamples_ = to_read
                data_array[idx].bufferIndex_ = collected
                data_array[idx].startIndex_ = collected
                data_array[idx].overflow_ = 0

            self.get_streaming_latest_values(data_array, trigger_info)
            collected += data_array[0].noOfSamples_

            if collected == 0:
                time.sleep(0.01)

            if auto_stop and trigger_info.autoStop_:
                break

        channels_buffer = self.channels_buffer_adc_to_mv(channels_buffer)

        seconds_per_sample = {
            PICO_TIME_UNIT.FS: 1e-15,
            PICO_TIME_UNIT.PS: 1e-12,
            PICO_TIME_UNIT.NS: 1e-9,
            PICO_TIME_UNIT.US: 1e-6,
            PICO_TIME_UNIT.MS: 1e-3,
            PICO_TIME_UNIT.S: 1,
        }[sample_interval_time_units] * actual_interval

        time_axis = [n * seconds_per_sample for n in range(collected)]

        return channels_buffer, time_axis
    
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
