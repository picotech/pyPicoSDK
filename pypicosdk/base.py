"""
Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms.
"""

# flake8: noqa
# pylint: skip-file
import ctypes
import os
import platform
import warnings

import numpy as np
import numpy.ctypeslib as npc

from ._classes._channel_class import ChannelClass
from .error_list import ERROR_STRING
from .constants import *
from . import constants as cst
from .constants import (
    CHANNEL,
    RANGE,
    RANGE_LIST,
    range_literal,
    OutputUnitV_L,
    OutputUnitV_M,
    _StandardPicoConv,
)
from .common import *
from .common import (
    _get_literal,
    ProbeScaleWarning,
    PicoSDKException
)
from ._classes import _general


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
            # Determine file extension and naming convention based on OS
            system = platform.system()
            if system == "Windows":
                lib_name = dll_name + ".dll"
            elif system == "Linux":
                lib_name = "lib" + dll_name + ".so"
            elif system == "Darwin":
                lib_name = "lib" + dll_name + ".dylib"
            else:
                lib_name = "lib" + dll_name + ".so"  # Default to Unix-like naming

            self.dll = ctypes.CDLL(os.path.join(_get_lib_path(), lib_name))
        self._unit_prefix_n = dll_name

        # Setup class variables
        self.handle = ctypes.c_short()
        self.channel_db: dict[int, ChannelClass] = {}
        self.resolution = None
        self.max_adc_value = None
        self.min_adc_value = None
        self.over_range = 0
        self._actual_interval = 0
        self.last_used_volt_unit: str = 'mv'

        self.base_dataclass = _general.BaseDataClass()

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
            # Ignore codes as they are warnings or status updates.
            # 407 - Pico Waiting For Data Buffers
            # 282 - Pico Power Supply Not Connected
            # 290 - Pico Channel Disabled Due To Usb Powered
            if status in [407, 282, 290]:
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
    def open_unit(self, serial_number:int=None, resolution:RESOLUTION=0) -> None:
        """
        Opens PicoScope unit.

        Args:
            serial_number (int, optional): Serial number of specific unit, e.g., JR628/0017.
            resolution (RESOLUTION, optional): Resolution of device.
        """

        if serial_number is not None:
            serial_number = serial_number.encode()
        status = self._call_attr_function(
            'OpenUnit',
            ctypes.byref(self.handle),
            serial_number,
            resolution
        )
        self.resolution = resolution
        self.set_all_channels_off()
        return status

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
        """Stop data acquisition on the device.

        Returns:
            None
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
        while True:
            status = self._call_attr_function(
                "IsReady",
                self.handle,
                ctypes.byref(ready)
            )
            if ready.value != 0:
                break

    def ping_unit(self) -> bool:
        """Check that the device is still connected.
        This wraps ``ps6000aPingUnit`` which verifies communication with
        the PicoScope. If the call succeeds the method returns ``True``.
        Returns:
            bool: ``True`` if the unit responded.
        """

        status = self._call_attr_function("PingUnit", self.handle)
        return status == 0

    def check_for_update(self, n_infos: int = 8) -> tuple[list, bool]:
        """Query whether a firmware update is available for the device.
        Args:
            n_infos: Size of the firmware information buffer.
        Returns:
            tuple[list, bool]: ``(firmware_info, updates_required)`` where
                ``firmware_info`` is a list of :class:`PICO_FIRMWARE_INFO`
                structures and ``updates_required`` indicates whether any
                firmware components require updating.
        """

        info_array = (PICO_FIRMWARE_INFO * n_infos)()
        n_returned = ctypes.c_int16(n_infos)
        updates_required = ctypes.c_uint16()
        self._call_attr_function(
            "CheckForUpdate",
            self.handle,
            info_array,
            ctypes.byref(n_returned),
            ctypes.byref(updates_required),
        )

        return list(info_array)[: n_returned.value], bool(updates_required.value)

    def start_firmware_update(self, progress=None) -> None:
        """Begin installing any available firmware update.
        Args:
            progress: Optional callback ``(handle, percent)`` that receives
                progress updates as the firmware is written.
        """

        CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int16, ctypes.c_uint16)
        cb = CALLBACK(progress) if progress else None
        self._call_attr_function(
            "StartFirmwareUpdate",
            self.handle,
            cb,
        )

    def memory_segments(self, n_segments: int) -> int:
        """Configure the number of memory segments.

        This wraps the ``ps6000aMemorySegments`` API call.

        Args:
            n_segments: Desired number of memory segments.

        Returns:
            int: Number of samples available in each segment.
        """

        max_samples = ctypes.c_uint64()
        self._call_attr_function(
            "MemorySegments",
            self.handle,
            ctypes.c_uint64(n_segments),
            ctypes.byref(max_samples),
        )
        return max_samples.value


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
        for channel in self.channel_db:
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
            0,
            ctypes.byref(timebase),
            ctypes.byref(time_interval),
        )
        return {"timebase": timebase.value, "actual_sample_interval": time_interval.value}

    def get_timebase(self, timebase: int, samples: int, segment:int=0) -> dict:
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
        status = self._call_attr_function(
            'GetTimebase',
            self.handle,
            timebase,
            samples,
            ctypes.byref(time_interval_ns),
            ctypes.byref(max_samples),
            segment
        )
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
        status = self._call_attr_function(
            'GetTimeBase2',
            self.handle,
            timebase,
            samples,
            ctypes.byref(time_interval_ns),
            ctypes.byref(max_samples),
            segment
        )
        return {"Interval(ns)": time_interval_ns.value,
                "Samples":          max_samples.value}

    def get_actual_interval(self):
        """
        Returns the actual interval set by device in seconds (s).


        Returns:
            float: Actual interval of device in seconds (s)
        """
        return self._actual_interval

    def get_actual_sample_rate(self):
        """
        Returns the actual sample rate set by device in samples per second (S/s)


        Returns:
            float: Actual sample rate of device in samples per second (S/s)
        """
        return (1 / self._actual_interval)

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
        timebase_dict = self.get_nearest_sampling_interval(interval_s)
        self._actual_interval = timebase_dict['actual_sample_interval']

        return timebase_dict["timebase"]

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

    def get_time_axis(
            self,
            timebase: int,
            samples: int,
            pre_trig_percent: int = None,
            unit: cst.TimeUnit_L = 'ns',
            ratio: int = 0
            ) -> np.ndarray:
        """
        Return an array of time values based on the timebase and number
        of samples

        Args:
            timebase (int): PicoScope timebase
            samples (int): Number of samples captured
            pre_trig_percent (int): Percent to offset the 0 point by. If None, defaults to last
                used pre_trig_percent or 50.
            unit (str): Unit of seconds the time axis is returned in.
                Default is 'ns' (nanoseconds).
            ratio (int): If using a downsampling ratio, this will scale the time interval
                to reflect the reduced samples.

        Returns:
            np.ndarray: Array of time values in nano-seconds
        """
        # Check and save pre_trig to base dataclass
        if pre_trig_percent == None:
            pre_trig_percent = self.base_dataclass.last_pre_trig
        self.base_dataclass.last_pre_trig = pre_trig_percent

        # Default to 1 when using ratio
        ratio = max(1, ratio)

        # Get unit scalar value
        scalar = cst.TimeUnitStd_M['ns'] / cst.TimeUnitStd_M[unit]

        # Get the interval for the specified timebase/samples
        interval = self.get_timebase(timebase, samples)['Interval(ns)'] * ratio / scalar

        # Maths
        time_axis = np.arange(samples) * interval
        offset = time_axis.max() * (pre_trig_percent / 100)
        return time_axis - offset

    def realign_downsampled_data(
            self,
            downsampled_buffers: dict[int, np.ndarray],
            total_raw_samples: int,
            returned_samples: int,
            ratio: int,
            ratio_mode: cst.RATIO_MODE,
            fill_value: float = np.nan,
        ) -> dict[int, np.ndarray]:
        """
        Expand downsampled channel buffers onto the raw-sample time grid by inserting NaNs
        in positions where downsampled data has no corresponding raw sample.

        Supported modes:
            - DECIMATE: places each returned sample at the FIRST index of its ratio block.
            - AVERAGE:  places each returned sample at the MIDDLE index of its ratio block.

        Args:
            buffers: Mapping from CHANNEL to its 1D downsampled data array (ADC or converted).
            total_raw_samples: Length of the raw-sample grid to expand onto.
            returned_samples: Number of downsampled samples returned by the driver.
            ratio: Downsample ratio used for the request.
            ratio_mode: Downsample mode used for the request
            (``RATIO_MODE.DECIMATE`` or ``RATIO_MODE.AVERAGE``).
            fill_value: Value used for gaps. Defaults to ``np.nan``.

        Returns:
            dict[int, np.ndarray]: Mapping from CHANNEL to expanded array
            of length ``total_raw_samples``.

        Raises:
            ValueError: If ``ratio_mode`` is not DECIMATE or AVERAGE.
        """

        expanded: dict[int, np.ndarray] = {}

        if ratio_mode == cst.RATIO_MODE.DECIMATE:
            offset = 0
        elif ratio_mode == cst.RATIO_MODE.AVERAGE:
            offset = ratio // 2
        else:
            raise ValueError("realign_downsampled_data supports only DECIMATE and AVERAGE modes")

        indices = (np.arange(returned_samples) * max(1, ratio)) + offset
        indices = indices[indices < total_raw_samples]

        for ch, data in downsampled_buffers.items():
            out = np.full(total_raw_samples, fill_value, dtype=float)
            n = min(len(indices), len(data))
            out[indices[:n]] = data[:n]
            expanded[ch] = out
        return expanded


    def get_trigger_time_offset(self, time_unit: TIME_UNIT, segment_index: int = 0) -> int:
        """
        Get the trigger time offset for jitter correction in waveforms.

        The driver interpolates between adjacent samples to estimate when the
        trigger actually occurred.  This means the value returned can have a
        very fine granularity—down to femtoseconds—even though the effective
        resolution is usually limited to roughly one-tenth of the sampling
        interval in real-world use.

        Args:
            time_unit (TIME_UNIT): Desired unit for the returned offset.
            segment_index (int, optional): The memory segment to query. Default
                is 0.

        Returns:
            int: Trigger time offset converted to ``time_unit``.

        Raises:
            PicoSDKException: If the function call fails or preconditions are
                not met.
        """
        time = ctypes.c_int64()
        returned_unit = ctypes.c_int32()

        self._call_attr_function(
            'GetTriggerTimeOffset',
            self.handle,
            ctypes.byref(time),
            ctypes.byref(returned_unit),
            ctypes.c_uint64(segment_index)
        )

        # Convert the returned time to the requested ``time_unit``
        pico_unit = _PICO_TIME_UNIT(returned_unit.value)
        time_s = time.value / TIME_UNIT[pico_unit.name]
        return int(time_s * TIME_UNIT[time_unit.name])

    def get_values_trigger_time_offset_bulk(
        self,
        from_segment_index: int,
        to_segment_index: int,
    ) -> list[tuple[int, _PICO_TIME_UNIT]]:
        """Retrieve trigger time offsets for a range of segments.

        This method returns the trigger time offset and associated
        time unit for each requested segment.

        Args:
            from_segment_index: Index of the first memory segment to query.
            to_segment_index: Index of the last memory segment. If this value
                is less than ``from_segment_index`` the driver wraps around.

        Returns:
            list[tuple[int, PICO_TIME_UNIT]]: ``[(offset, unit), ...]`` for each
            segment beginning with ``from_segment_index``.
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

        results = []
        for i in range(count):
            results.append((times[i], _PICO_TIME_UNIT(units[i])))
        return results

    def set_no_of_captures(self, n_captures: int) -> None:
        """Configure the number of captures for rapid block mode."""

        self._call_attr_function(
            "SetNoOfCaptures",
            self.handle,
            ctypes.c_uint64(n_captures),
        )

    def get_no_of_captures(self) -> int:
        """Return the number of captures configured for rapid block."""

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
        down_sample_ratio: int,
        down_sample_ratio_mode: int,
    ) -> tuple[int, list[list[str]]]:
        """Retrieve data from multiple memory segments.

        Args:
            start_index: Index within each segment to begin copying from.
            no_of_samples: Total number of samples to read from each segment.
            from_segment_index: Index of the first segment to read.
            to_segment_index: Index of the last segment. If this value is
                less than ``from_segment_index`` the driver wraps around.
            down_sample_ratio: Downsampling ratio to apply before copying.
            down_sample_ratio_mode: Downsampling mode from
                :class:`RATIO_MODE`.

        Returns:
            tuple[int, list[list[str]]]: ``(samples, overflow)list)`` where ``samples`` is the
            number of samples copied and ``overflow`` is list of captures with where
            channnels have exceeded their voltage range.
        """

        self.is_ready()
        no_samples = ctypes.c_uint64(no_of_samples)
        overflow = np.zeros(to_segment_index + 1, dtype=np.int16)
        self._call_attr_function(
            "GetValuesBulk",
            self.handle,
            ctypes.c_uint64(start_index),
            ctypes.byref(no_samples),
            ctypes.c_uint64(from_segment_index),
            ctypes.c_uint64(to_segment_index),
            ctypes.c_uint64(down_sample_ratio),
            down_sample_ratio_mode,
            npc.as_ctypes(overflow),
        )
        overflow_list = []
        for i in overflow:
            self.over_range = i
            overflow_list.append(self.is_over_range())
        return no_samples.value, overflow_list

    def get_values_overlapped(
        self,
        start_index: int,
        no_of_samples: int,
        down_sample_ratio: int,
        down_sample_ratio_mode: int,
        from_segment_index: int,
        to_segment_index: int,
        overflow: ctypes.c_int16,
    ) -> int:
        """Retrieve overlapped data from multiple segments for block or rapid block mode.

        Call this method **before** :meth:`run_block_capture` to defer the data
        retrieval request. The driver validates and performs the request when
        :meth:`run_block_capture` runs, which avoids the extra communication that
        occurs when calling :meth:`run_block_capture` followed by
        :meth:`get_values`. After the capture completes you can call
        :meth:`get_values` again to retrieve additional copies of the data.
        Stop further captures with :meth:`stop_using_get_values_overlapped` and
        check progress using :meth:`ps6000a.PicoScope.get_no_of_processed_captures`.

        Args:
            start_index: Index within the circular buffer to begin reading from.
            no_of_samples: Number of samples to copy from each segment.
            down_sample_ratio: Downsampling ratio to apply.
            down_sample_ratio_mode: Downsampling mode from :class:`RATIO_MODE`.
            from_segment_index: First segment index to read.
            to_segment_index: Last segment index to read.
            overflow: ``ctypes.c_int16`` instance that receives any overflow
                flags.

        Returns:
            int: Actual number of samples copied from each segment.

        Examples:
            >>> samples = scope.get_values_overlapped(
            ...     start_index=0,              # read from start of buffer
            ...     no_of_samples=1024,         # copy 1024 samples
            ...     down_sample_ratio=1,        # no downsampling
            ...     down_sample_ratio_mode=RATIO_MODE.RAW,
            ...     from_segment_index=0,       # first segment only
            ...     to_segment_index=0,
            ... )
            >>> scope.run_block_capture(timebase=1, samples=1024)
            >>> data = scope.get_values(samples=1024)
            >>> samples, scope.over_range
            (1024, 0)
        """

        self.is_ready()
        c_samples = ctypes.c_uint64(no_of_samples)
        self._call_attr_function(
            "GetValuesOverlapped",
            self.handle,
            ctypes.c_uint64(start_index),
            ctypes.byref(c_samples),
            ctypes.c_uint64(down_sample_ratio),
            down_sample_ratio_mode,
            ctypes.c_uint64(from_segment_index),
            ctypes.c_uint64(to_segment_index),
            ctypes.byref(overflow),
        )
        self.over_range = overflow.value
        self.is_over_range()
        return c_samples.value

    def get_device_resolution(self) -> RESOLUTION:
        """Return the currently configured resolution.
        Returns:
            :class:`RESOLUTION`: Device resolution.
        """

        resolution = ctypes.c_int32()
        self._call_attr_function(
            "GetDeviceResolution",
            self.handle,
            ctypes.byref(resolution),
        )
        self.resolution = RESOLUTION(resolution.value)
        self.min_adc_value, self.max_adc_value = self.get_adc_limits()
        return RESOLUTION(resolution.value)

    def no_of_streaming_values(self) -> int:
        """Return the number of values currently available while streaming."""

        count = ctypes.c_uint64()
        self._call_attr_function(
            "NoOfStreamingValues",
            self.handle,
            ctypes.byref(count),
        )
        return count.value

    def get_no_of_processed_captures(self) -> int:
        """Return the number of captures processed in rapid block mode."""

        n_processed = ctypes.c_uint64()
        self._call_attr_function(
            "GetNoOfProcessedCaptures",
            self.handle,
            ctypes.byref(n_processed),
        )
        return n_processed.value

    def get_minimum_timebase_stateless(self) -> dict:
        """Return the fastest timebase available for the current setup.
        Queries ``ps6000aGetMinimumTimebaseStateless`` using the enabled
        channels and current device resolution.
        Returns:
            dict: ``{"timebase": int, "time_interval": float}`` where
            ``time_interval`` is the sample period in seconds.
        """

        timebase = ctypes.c_uint32()
        time_interval = ctypes.c_double()
        self._call_attr_function(
            "GetMinimumTimebaseStateless",
            self.handle,
            self._get_enabled_channel_flags(),
            ctypes.byref(timebase),
            ctypes.byref(time_interval),
            self.resolution,
        )
        return {
            "timebase": timebase.value,
            "time_interval": time_interval.value,
        }

    def volts_to_adc(self, volts: float, channel: cst.CHANNEL) -> int:
        """
        Coverts a volt (V) value to an ADC value based on the channel range and device's maximum
        ADC value.

        Args:
            volts (float): Voltage in volts (V) to be converted
            channel (CHANNEL): Channel associated with `volts`. The probe scaling will
                be applied if provided.

        Returns:
            int: ADC value corresponding to the input voltage.
        """
        scale = self.channel_db[channel].probe_scale
        channel_range_v = self.channel_db[channel].range_v
        return int(((volts / scale) / channel_range_v) * self.max_adc_value)

    # Data conversion ADC/mV & ctypes/int
    def mv_to_adc(self, mv: float, channel: cst.CHANNEL) -> int:
        """
        Converts a millivolt (mV) value to an ADC value based on the device's
        maximum ADC range.

        Args:
                mv (float): Voltage in millivolts (mV) to be converted.
                channel (CHANNEL): Channel associated with ``mv``. The
                        probe scaling for the channel will be applied if provided.

        Returns:
                int: ADC value corresponding to the input millivolt value.
        """
        scale = self.channel_db[channel].probe_scale
        channel_range_mv = self.channel_db[channel].range_mv
        return int(((mv / scale) / channel_range_mv) * self.max_adc_value)

    def _adc_conversion(
        self,
        adc: int | np.ndarray,
        channel: CHANNEL = None,
        output_unit: OutputUnitV_L = 'mv'
    ) -> float | np.ndarray:
        """Converts ADC value or array to mV or V using the stored probe scaling."""
        unit_scale = _get_literal(output_unit, OutputUnitV_M)
        channel_range_mv = self.channel_db[channel].range_mv
        channel_scale = self.channel_db[channel].probe_scale
        return (((adc / self.max_adc_value) * channel_range_mv) * channel_scale) / unit_scale

    def _adc_to_(
        self,
        buffer: dict | int | np.ndarray,
        channel: int | CHANNEL | str | channel_literal = None,
        unit: OutputUnitV_L = 'mv',
    ) -> dict | float | np.ndarray:
        """
        Middle-function between adc conversion to direct buffer based on if it's a dict or
        adc values.

        Args:
            buffer (dict, int, float, np.ndarray):
                ADC values to be converted to millivolt values
            channel (int, CHANNEL, str, optional):
                Channel the ADC data is from. If the data is a channel buffer dict,
                set to None. Defaults to None.
            unit (str, optional): unit of volts from ['mv', 'v']. Defaults to 'mv'.

        Returns:
            dict | float | np.ndarray: _description_
        """

        # Update last used
        self.last_used_volt_unit = unit

        if isinstance(buffer, dict):
            for channel, adc in buffer.items():
                buffer[channel] = self._adc_conversion(adc, channel, output_unit=unit)
        else:
            if isinstance(channel, str):
                channel = _get_literal(channel, channel_map)
            buffer = self._adc_conversion(buffer, channel, output_unit=unit)
        return buffer

    def adc_to_mv(
        self,
        buffer: dict | int | np.ndarray,
        channel: int | CHANNEL | str | channel_literal = None,
    ) -> dict | float | np.ndarray:
        """
        Converts ADC values into millivolt (mV) values.
        The buffer can be from a channel buffer (dict), numpy array or single value.

        Args:
            buffer (dict, int, float, np.ndarray):
                ADC values to be converted to millivolt values
            channel (int, CHANNEL, str, optional):
                Channel the ADC buffer is from. If the buffer is a channel buffer dict,
                set to None. Defaults to None.

        Returns:
            dict, int, float, np.ndarray: buffer converted into millivolts (mV)
        """
        self.last_used_volt_unit = 'mv'  # Update last used
        return self._adc_to_(buffer, channel, unit='mv')

    def adc_to_volts(
        self,
        buffer: dict | int | np.ndarray,
        channel: int | CHANNEL | str | channel_literal = None,
    ) -> dict | float | np.ndarray:
        """
        Converts ADC values into voltage (V) values.
        The buffer can be from a channel buffer (dict), numpy array or single value.

        Args:
            buffer (dict, int, float, np.ndarray):
                ADC values to be converted to millivolt values
            channel (int, CHANNEL, str, optional):
                Channel the ADC buffer is from. If the buffer is a channel buffer dict,
                set to None. Defaults to None.

        Returns:
            dict, int, float, np.ndarray: buffer converted into volts (V)
        """
        self.last_used_volt_unit = 'v'  # Update last used
        return self._adc_to_(buffer, channel, unit='v')

    def _thr_hyst_mv_to_adc(
            self,
            channel,
            threshold_upper_mv,
            threshold_lower_mv,
            hysteresis_upper_mv,
            hysteresis_lower_mv
    ) -> tuple[int, int, int, int]:
        if channel in self.channel_db:
            ch_range = self.channel_db[channel].range
            upper_adc = self.mv_to_adc(threshold_upper_mv, channel)
            lower_adc = self.mv_to_adc(threshold_lower_mv, channel)
            hyst_upper_adc = self.mv_to_adc(hysteresis_upper_mv, channel)
            hyst_lower_adc = self.mv_to_adc(hysteresis_lower_mv, channel)
        else:
            upper_adc = int(threshold_upper_mv)
            lower_adc = int(threshold_lower_mv)
            hyst_upper_adc = int(hysteresis_upper_mv)
            hyst_lower_adc = int(hysteresis_lower_mv)

        return upper_adc, lower_adc, hyst_upper_adc, hyst_lower_adc

    # Set methods for PicoScope configuration
    def get_ylim(self, unit: str | None | OutputUnitV_L = None) -> tuple[float, float]:
        """
        Returns the ylim of the widest channel range as a tuple. The unit is taken from
        the last used adc to voltage conversion, but can be overwritten by declaring a
        `unit` variable.
        Ideal for pyplot ylim function.

        Args:
            unit (str | None, optional): Overwrite the ylim unit using `'mv'` or `'v'`.
                If None, The unit will be taken from the last voltage unit conversion.

        Returns:
            tuple[float,float]: Minium and maximum range values

        Examples:
            >>> from matplotlib import pyplot as plt
            >>> ...
            >>> plt.ylim(scope.get_ylim())
        """
        if unit is None:
            # Collect last used voltage unit
            unit = self.last_used_volt_unit

        # Get largest channel range
        largest_range_index = max(
            self.channel_db,
            key=lambda ch: self.channel_db[ch].range_mv
            )
        unit = unit.lower()
        if unit == 'mv':
            return self.channel_db[largest_range_index].ylim_mv
        elif unit == 'v':
            return self.channel_db[largest_range_index].ylim_v

    def set_device_resolution(self, resolution: RESOLUTION) -> None:
        """Configure the ADC resolution using ``ps6000aSetDeviceResolution``.
        Args:
            resolution: Desired resolution as a :class:`RESOLUTION` value.
        """

        self._call_attr_function(
            "SetDeviceResolution",
            self.handle,
            resolution,
        )
        self.resolution = resolution
        self.min_adc_value, self.max_adc_value = self.get_adc_limits()

    def _set_channel_on(self, channel, range, probe_scale):
        # Constrain probe scale
        if not probe_scale >= 1.0:
            raise PicoSDKException(
                f'Invalid probe scale: {probe_scale}. Value must be equal or greater than 1.0.')

        # Give warning a non-default probe scale
        if probe_scale != 1:
            warnings.warn(
                f'Ensure selected channel range of {cst.range_literal.__args__[range]} ' +
                f'accounts for attenuation of x{probe_scale} at scope input',
                ProbeScaleWarning)

        self.channel_db[channel] = ChannelClass(ch_range=range, probe_scale=probe_scale)

    def _set_channel_off(self, channel):
        # Remove it from the channel database
        if channel in self.channel_db:
            self.channel_db.pop(channel)


    def set_all_channels_off(self):
        """Turns all channels off, based on unit number of channels"""
        channels = self.get_unit_info(UNIT_INFO.PICO_VARIANT_INFO)[1]
        for channel in range(int(channels)):
            self.set_channel(channel, enabled=False)

    def set_simple_trigger(
            self,
            channel: CHANNEL | channel_literal,
            threshold: int = 0,
            threshold_unit: cst.output_unit_l = 'mv',
            enable: bool = True,
            direction: TRIGGER_DIR | trigger_dir_l = TRIGGER_DIR.RISING,
            delay: int = 0,
            auto_trigger: int = 0,
        ) -> None:
        """
        Sets up a simple trigger from a specified channel and threshold in mV.

        Args:
            channel (CHANNEL | str): The input channel to apply the trigger to.
            threshold (int, optional): Trigger threshold level.
            threshold_unit (str, optional): Trigger threshold unit. Default is 'mv'.
            enable (bool, optional): Enables or disables the trigger.
            direction (TRIGGER_DIR | str, optional): Trigger direction (e.g., ``TRIGGER_DIR.RISING``).
            delay (int, optional): Delay in samples after the trigger condition is met before starting capture.
            auto_trigger (int, optional): Timeout in **microseconds** after which data capture proceeds even if no
                trigger occurs. If 0, the PicoScope will wait indefintely.

        Examples:
            When using TRIGGER_AUX, threshold is fixed to 1.25 V
            >>> scope.set_simple_trigger(channel=psdk.CHANNEL.TRIGGER_AUX)
        """
        channel = _get_literal(channel, channel_map)
        direction = _get_literal(direction, trigger_dir_m)

        if threshold_unit == 'mv':
            threshold_adc = self.mv_to_adc(threshold, channel)
        elif threshold_unit == 'v':
            threshold_adc = self.volts_to_adc(threshold, channel)
        else:
            threshold_adc = int(threshold)

        return self._call_attr_function(
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
        conditions: list[tuple[CHANNEL, TRIGGER_STATE]],
        action: int = ACTION.CLEAR_ALL | ACTION.ADD,
    ) -> None:
        """Configure a trigger condition.

        Args:
            conditions (list[tuple[CHANNEL, TRIGGER_STATE]]):
                A list of tuples describing the CHANNEL and TRIGGER_STATE for that channel
            action (int, optional): Action to apply this condition relateive to any previous
                condition. Defaults to ACTION.CLEAR_ALL | ACTION.ADD.
        """

        cond_len = len(conditions)
        cond_array = (PICO_CONDITION * cond_len)()
        for i, (source, state) in enumerate(conditions):
            cond_array[i] = PICO_CONDITION(source, state)

        self._call_attr_function(
            "SetTriggerChannelConditions",
            self.handle,
            ctypes.byref(cond_array),
            ctypes.c_int16(cond_len),
            action,
        )

    def set_trigger_channel_properties(
        self,
        threshold_upper: int,
        hysteresis_upper: int,
        threshold_lower: int,
        hysteresis_lower: int,
        channel: int,
        aux_output_enable: int = 0,
        auto_trigger_us: int = 0,
    ) -> None:
        """Configure trigger thresholds for ``channel``. All
        threshold and hysteresis values are specified in ADC counts.

        Args:
            threshold_upper (int): Upper trigger level.
            hysteresis_upper (int): Hysteresis for ``threshold_upper``.
            threshold_lower (int): Lower trigger level.
            hysteresis_lower (int): Hysteresis for ``threshold_lower``.
            channel (int): Target channel as a :class:`CHANNEL` value.
            aux_output_enable (int, optional): Auxiliary output flag.
            auto_trigger_us (int, optional): Auto-trigger timeout in
                microseconds. ``0`` waits indefinitely.
        """

        prop = PICO_TRIGGER_CHANNEL_PROPERTIES(
            threshold_upper,
            hysteresis_upper,
            threshold_lower,
            hysteresis_lower,
            channel,
        )

        self._call_attr_function(
            "SetTriggerChannelProperties",
            self.handle,
            ctypes.byref(prop),
            ctypes.c_int16(1),
            ctypes.c_int16(aux_output_enable),
            ctypes.c_uint32(auto_trigger_us),
        )

    def set_trigger_channel_directions(
        self,
        channel: CHANNEL | list,
        direction: THRESHOLD_DIRECTION | list,
        threshold_mode: THRESHOLD_MODE | list,
    ) -> None:
        """
        Specify the trigger direction for ``channel``.
        If multiple directions are needed, channel, direction and threshold_mode
        can be given a list of values.

        Args:
            channel (CHANNEL | list): Single or list of channels to configure.
            direction (THRESHOLD_DIRECTION | list): Single or list of directions to configure.
            threshold_mode (THRESHOLD_MODE | list): Single or list of threshold modes to configure.
        """

        if type(channel) == list:
            dir_len = len(channel)
            dir_struct = (PICO_DIRECTION * dir_len)()
            for i in range(dir_len):
                dir_struct[i] = PICO_DIRECTION(channel[i], direction[i], threshold_mode[i])
        else:
            dir_len = 1
            dir_struct = PICO_DIRECTION(channel, direction, threshold_mode)

        self._call_attr_function(
            "SetTriggerChannelDirections",
            self.handle,
            ctypes.byref(dir_struct),
            ctypes.c_int16(dir_len),
        )

    def set_advanced_trigger(
        self,
        channel: int,
        state: int,
        direction: int,
        threshold_mode: int,
        threshold_upper_mv: float,
        threshold_lower_mv: float,
        hysteresis_upper_mv: float = 0.0,
        hysteresis_lower_mv: float = 0.0,
        aux_output_enable: int = 0,
        auto_trigger_ms: int = 0,
        action: int = ACTION.CLEAR_ALL | ACTION.ADD,
    ) -> None:
        """Configure an advanced trigger in a single call.

        This helper sets up the trigger condition, direction and properties
        required for non-simple triggers.

        Args:
            channel: Channel to monitor for the trigger condition.
            state: Trigger state used with ``set_trigger_channel_conditions``.
            direction: Trigger direction from
                :class:`PICO_THRESHOLD_DIRECTION`.
            threshold_mode: Threshold mode from :class:`PICO_THRESHOLD_MODE`.
            threshold_upper_mv: Upper trigger threshold in millivolts.
            threshold_lower_mv: Lower trigger threshold in millivolts.
            hysteresis_upper_mv: Optional hysteresis for ``threshold_upper_mv``
                in millivolts.
            hysteresis_lower_mv: Optional hysteresis for ``threshold_lower_mv``
                in millivolts.
            aux_output_enable: Optional auxiliary output flag.
            auto_trigger_ms: Auto-trigger timeout in milliseconds. ``0`` waits
                indefinitely.
            action: Action flag for ``set_trigger_channel_conditions``.
        """

        upper_adc, lower_adc, hyst_upper_adc, hyst_lower_adc = self._thr_hyst_mv_to_adc(
            channel,
            threshold_upper_mv,
            threshold_lower_mv,
            hysteresis_upper_mv,
            hysteresis_lower_mv
        )

        self.set_trigger_channel_conditions([(channel, state)], action)
        self.set_trigger_channel_directions(channel, direction, threshold_mode)
        self.set_trigger_channel_properties(
            upper_adc,
            hyst_upper_adc,
            lower_adc,
            hyst_lower_adc,
            channel,
            aux_output_enable,
            auto_trigger_ms * 1000,
        )

    def set_trigger_delay(self, delay: int) -> None:
        """Delay the trigger by ``delay`` samples.
        Args:
            delay: Number of samples to delay the trigger by.
        """

        self._call_attr_function(
            "SetTriggerDelay",
            self.handle,
            ctypes.c_uint64(delay),
        )

    def set_pulse_width_qualifier_properties(
        self,
        lower: int,
        upper: int,
        pw_type: int,
    ) -> None:
        """Configure pulse width qualifier thresholds.
        Args:
            lower: Lower bound of the pulse width (inclusive).
            upper: Upper bound of the pulse width (inclusive).
            pw_type: Pulse width comparison type.
        """

        self._call_attr_function(
            "SetPulseWidthQualifierProperties",
            self.handle,
            ctypes.c_uint32(lower),
            ctypes.c_uint32(upper),
            pw_type,
        )

    def set_pulse_width_qualifier_conditions(
        self,
        conditions: list[tuple[CHANNEL, TRIGGER_STATE]],
        action: int = ACTION.CLEAR_ALL | ACTION.ADD,
    ) -> None:
        """Configure a pulse width qualifier condition.

        Args:
            conditions (list[tuple[CHANNEL, TRIGGER_STATE]]):
                A list of tuples describing the CHANNEL and TRIGGER_STATE for that channel
            action (int, optional): Action to apply this condition relateive to any previous
                condition. Defaults to ACTION.CLEAR_ALL | ACTION.ADD.
        """
        cond_len = len(conditions)
        cond_array = (PICO_CONDITION * cond_len)()
        for i, (source, state) in enumerate(conditions):
            cond_array[i] = PICO_CONDITION(source, state)

        self._call_attr_function(
            "SetPulseWidthQualifierConditions",
            self.handle,
            ctypes.byref(cond_array),
            ctypes.c_int16(cond_len),
            action,
        )

    def set_pulse_width_trigger(
        self,
        channel:CHANNEL,
        timebase:int,
        samples:int,
        direction:THRESHOLD_DIRECTION,
        pulse_width_type:PULSE_WIDTH_TYPE,
        time_upper=0,
        time_upper_units:TIME_UNIT=TIME_UNIT.US,
        time_lower=0,
        time_lower_units:TIME_UNIT=TIME_UNIT.US,
        threshold_upper_mv:float=0.0,
        threshold_lower_mv:float=0.0,
        hysteresis_upper_mv: float = 0.0,
        hysteresis_lower_mv: float = 0.0,
        trig_dir:THRESHOLD_DIRECTION=None,
        threshold_mode:THRESHOLD_MODE = THRESHOLD_MODE.LEVEL,
        auto_trigger_us=0
    ) -> None:
        """
        Configures a pulse width trigger using a specified channel and timing parameters.

        This method sets up a trigger condition where a pulse on the specified channel
        must be within or outside a defined pulse width window. The trigger logic uses
        both level thresholds and pulse width qualifiers to define the trigger behavior.

        Args:
            channel (CHANNEL): The input channel on which to apply the pulse width trigger.
            timebase (int): The timebase index to determine sampling interval.
            samples (int): The number of samples to be captured (used to resolve timing).
            direction (THRESHOLD_DIRECTION): Pulse polarity to trigger on (e.g. RISING or FALLING).
            pulse_width_type (PULSE_WIDTH_TYPE): Type of pulse width qualifier (e.g. GREATER_THAN).
            time_upper (float, optional): Upper time bound for pulse width. Default is 0 (disabled).
            time_upper_units (TIME_UNIT, optional): Units for `time_upper`. Default is microseconds.
            time_lower (float, optional): Lower time bound for pulse width. Default is 0 (disabled).
            time_lower_units (TIME_UNIT, optional): Units for `time_lower`. Default is microseconds.
            threshold_upper_mv (float, optional): Upper voltage threshold in millivolts. Default is 0.0 mV.
            threshold_lower_mv (float, optional): Lower voltage threshold in millivolts. Default is 0.0 mV.
            hysteresis_upper_mv (float, optional): Hysteresis for upper threshold in mV. Default is 0.0 mV.
            hysteresis_lower_mv (float, optional): Hysteresis for lower threshold in mV. Default is 0.0 mV.
            trig_dir (THRESHOLD_DIRECTION, optional): Trigger direction for the initial pulse.
                If None, inferred as opposite of `direction`. Default is None.
            threshold_mode (THRESHOLD_MODE, optional): Specifies whether thresholds are in level or window mode.
                Default is LEVEL.
            auto_trigger_us (int, optional): Time in microseconds after which an automatic trigger occurs.
                Default is 0 (disabled).
        """

        # If no times are set, raise an error.
        if time_upper == 0 and time_lower == 0:
            raise PicoSDKException('No time_upper or time_lower bounds specified for Pulse Width Trigger')

        self.set_trigger_channel_conditions(
            conditions=[
                (channel, TRIGGER_STATE.TRUE),
                (CHANNEL.PULSE_WIDTH_SOURCE, TRIGGER_STATE.TRUE)
            ]
        )

        # If no trigger direction is specified, use the oppsite direction, otherwise raise an error
        if trig_dir is None:
            if direction is THRESHOLD_DIRECTION.RISING: trig_dir = THRESHOLD_DIRECTION.FALLING
            elif direction is THRESHOLD_DIRECTION.FALLING: trig_dir = THRESHOLD_DIRECTION.RISING
            else:
                raise PicoSDKException('THRESHOLD_DIRECTION for trig_dir has not been specified')

        self.set_trigger_channel_directions(
            channel=channel,
            direction=trig_dir,
            threshold_mode=threshold_mode
        )

        upper_adc, lower_adc, hyst_upper_adc, hyst_lower_adc = self._thr_hyst_mv_to_adc(
            channel,
            threshold_upper_mv,
            threshold_lower_mv,
            hysteresis_upper_mv,
            hysteresis_lower_mv
        )

        self.set_trigger_channel_properties(
            threshold_upper=upper_adc, hysteresis_upper=hyst_upper_adc,
            threshold_lower=lower_adc, hysteresis_lower=hyst_lower_adc,
            channel=channel,
            auto_trigger_us=auto_trigger_us
        )

        # Determine actual sample interval from the selected timebase
        interval_ns = self.get_timebase(timebase, samples)["Interval(ns)"]
        sample_interval_s = interval_ns / 1e9

        # Convert pulse width threshold to samples
        pw_upper = int((time_upper / time_upper_units) / sample_interval_s)
        pw_lower = int((time_lower / time_lower_units) / sample_interval_s)

        # Configure pulse width qualifier
        self.set_pulse_width_qualifier_properties(
            lower=pw_lower,
            upper=pw_upper,
            pw_type=pulse_width_type,
        )
        self.set_pulse_width_qualifier_conditions(
            [(channel, TRIGGER_STATE.TRUE)]
        )
        self.set_pulse_width_qualifier_directions(
            channel=channel,
            direction=direction,
            threshold_mode=threshold_mode,
        )

    def query_output_edge_detect(self) -> int:
        """Query the output edge detect state.
        Returns:
            int: ``1`` if edge detection is enabled, otherwise ``0``.
        """

        state = ctypes.c_int16()
        self._call_attr_function(
            "QueryOutputEdgeDetect",
            self.handle,
            ctypes.byref(state),
        )
        return state.value

    def set_output_edge_detect(self, state: int) -> None:
        """Enable or disable output edge detect.
        Args:
            state: ``1`` to enable edge detection, ``0`` to disable.
        """

        self._call_attr_function(
            "SetOutputEdgeDetect",
            self.handle,
            ctypes.c_int16(state),
        )

    def set_data_buffer_for_enabled_channels(
            self,
            samples:int,
            segment:int=0,
            datatype=DATA_TYPE.INT16_T,
            ratio_mode=RATIO_MODE.RAW,
            clear_buffer:bool=True,
            captures:int=0
        ) -> dict:
        """
        Sets data buffers for enabled channels set by picosdk.set_channel()

        Args:
            samples (int): The sample buffer or size to allocate.
            segment (int): The memory segment index.
            datatype (DATA_TYPE): The data type used for the buffer.
            ratio_mode (RATIO_MODE): The ratio mode (e.g., RAW, AVERAGE).
            clear_buffer (bool): If True, clear the buffer first
            captures: If larger than 0, it will create multiple buffers for RAPID mode.

        Returns:
            dict: A dictionary mapping each channel to its associated data buffer.
        """
        # Clear the buffer
        if clear_buffer == True:
            self.set_data_buffer(0, 0, 0, 0, 0, ACTION.CLEAR_ALL)

        # Create Buffers
        channels_buffer = {}
        # Rapid
        if captures > 0:
            for channel in self.channel_db:
                np_buffer = self.set_data_buffer_rapid_capture(channel, samples, captures, segment, datatype, ratio_mode, action=ACTION.ADD)
                channels_buffer[channel] = np_buffer
        # Single
        else:
            for channel in self.channel_db:
                channels_buffer[channel] = self.set_data_buffer(channel, samples, segment, datatype, ratio_mode, action=ACTION.ADD)

        return channels_buffer

    def set_data_buffer(
        self,
        channel,
        samples,
        segment=0,
        datatype=DATA_TYPE.INT16_T,
        ratio_mode=RATIO_MODE.RAW,
        action=ACTION.CLEAR_ALL | ACTION.ADD,
        buffer:np.ndarray|None = None,
    ) -> np.ndarray | None:
        """
        Allocates and assigns a data buffer for a specified channel on the 6000A series.

        Args:
            channel (int): The channel to associate the buffer with (e.g., CHANNEL.A).
            samples (int): Number of samples to allocate in the buffer.
            segment (int, optional): Memory segment to use.
            datatype (DATA_TYPE, optional): C data type for the buffer (e.g., INT16_T).
            ratio_mode (RATIO_MODE, optional): Downsampling mode.
            action (ACTION, optional): Action to apply to the data buffer (e.g., CLEAR_ALL | ADD).
            buffer (np.ndarray | None, optional): Send a preallocated  numpy buffer to be populated.
                If left as None, this function creates its own buffer.

        Returns:
            np.array | None: The allocated buffer or ``None`` when clearing existing buffers.

        Raises:
            PicoSDKException: If an unsupported data type is provided.
        """
        if samples == 0:
            buffer = None
            buf_ptr = None
        elif buffer is not None:
            buf_ptr = npc.as_ctypes(buffer)
        else:
            # Map to NumPy dtype
            dtype_map = {
                DATA_TYPE.INT8_T: np.int8,
                DATA_TYPE.INT16_T: np.int16,
                DATA_TYPE.INT32_T: np.int32,
                DATA_TYPE.INT64_T: np.int64,
                DATA_TYPE.UINT32_T: np.uint32,
            }

            np_dtype = dtype_map.get(datatype)
            if np_dtype is None:
                raise PicoSDKException("Invalid datatype selected for buffer")

            buffer = np.zeros(samples, dtype=np_dtype)
            buf_ptr = npc.as_ctypes(buffer)

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


    def set_data_buffer_rapid_capture(
            self,
            channel,
            samples,
            captures,
            segment=0,
            datatype=DATA_TYPE.INT16_T,
            ratio_mode=RATIO_MODE.RAW,
            action=ACTION.CLEAR_ALL | ACTION.ADD,
        ) -> np.ndarray | None:
        """
        Allocates and assigns multiple data buffers for rapid block capture on a specified channel.

        Args:
            channel (int): The channel to associate the buffer with (e.g., CHANNEL.A).
            samples (int): Number of samples to allocate in the buffer.
            captures (int): Number of rapid block captures
            segment (int, optional): Memory segment to start at.
            datatype (DATA_TYPE, optional): C data type for the buffer (e.g., INT16_T).
            ratio_mode (RATIO_MODE, optional): Downsampling mode.
            action (ACTION, optional): Action to apply to the data buffer (e.g., CLEAR_ALL | ADD).

        Returns:
            np.array | None: The allocated buffer or ``None`` when clearing existing buffers.

        Raises:
            PicoSDKException: If an unsupported data type is provided.
        """
        if samples == 0:
            buffer = None
            buf_ptr = None
        else:
            # Map to NumPy dtype
            dtype_map = {
                DATA_TYPE.INT8_T: np.int8,
                DATA_TYPE.INT16_T: np.int16,
                DATA_TYPE.INT32_T: np.int32,
                DATA_TYPE.INT64_T: np.int64,
                DATA_TYPE.UINT32_T: np.uint32,
            }

            np_dtype = dtype_map.get(datatype)
            if np_dtype is None:
                raise PicoSDKException("Invalid datatype selected for buffer")

            buffer = np.zeros((captures, samples), dtype=np_dtype)

        for i in range(captures):
            self._call_attr_function(
                "SetDataBuffer",
                self.handle,
                channel,
                npc.as_ctypes(buffer[i]),
                samples,
                datatype,
                segment + i,
                ratio_mode,
                action,
            )

        return buffer

    def set_data_buffers(
        self,
        channel,
        samples,
        segment=0,
        datatype=DATA_TYPE.INT16_T,
        ratio_mode=RATIO_MODE.AGGREGATE,
        action=ACTION.CLEAR_ALL | ACTION.ADD,
        buffers:list[np.ndarray, np.ndarray] | np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Allocate and assign max and min NumPy-backed data buffers.

        Args:
            channel (int): The channel to associate the buffers with.
            samples (int): Number of samples to allocate.
            segment (int, optional): Memory segment to use.
            datatype (DATA_TYPE, optional): C data type for the buffer (e.g., INT16_T).
            ratio_mode (RATIO_MODE, optional): Downsampling mode.
            action (ACTION, optional): Action to apply to the data buffer.
            buffers (np.ndarray | None, optional): Send preallocated 2D numpy buffers to be populated.
                Min buffer first, followed by max buffer. If left as None, this function
                creates its own buffers.

        Returns:
            tuple[np.ndarray, np.ndarray]: Tuple of (buffer_min, buffer_max) NumPy arrays.

        Raises:
            PicoSDKException: If an unsupported data type is provided.
        """
        if buffers is not None:
            buffer_min = buffers[0]
            buffer_max = buffers[1]
        else:
            # Map to NumPy dtype
            dtype_map = {
                DATA_TYPE.INT8_T: np.int8,
                DATA_TYPE.INT16_T: np.int16,
                DATA_TYPE.INT32_T: np.int32,
                DATA_TYPE.INT64_T: np.int64,
                DATA_TYPE.UINT32_T: np.uint32,
            }

            np_dtype = dtype_map.get(datatype)
            if np_dtype is None:
                raise PicoSDKException("Invalid datatype selected for buffer")

            buffer_max = np.zeros(samples, dtype=np_dtype)
            buffer_min = np.zeros(samples, dtype=np_dtype)

        buf_max_ptr = npc.as_ctypes(buffer_max)
        buf_min_ptr = npc.as_ctypes(buffer_min)

        self._call_attr_function(
            "SetDataBuffers",
            self.handle,
            channel,
            buf_max_ptr,
            buf_min_ptr,
            samples,
            datatype,
            segment,
            ratio_mode,
            action,
        )

        return buffer_min, buffer_max

    def set_data_buffers_rapid_capture(
            self,
            channel,
            samples,
            captures,
            segment=0,
            datatype=DATA_TYPE.INT16_T,
            ratio_mode=RATIO_MODE.RAW,
            action=ACTION.CLEAR_ALL | ACTION.ADD,
        ) -> np.ndarray | None:
        """
        Allocate and assign max and min NumPy-backed data buffers for rapid block
        capture on a specified channel.

        Args:
            channel (int): The channel to associate the buffer with (e.g., CHANNEL.A).
            samples (int): Number of samples to allocate in the buffer.
            captures (int): Number of rapid block captures
            segment (int, optional): Memory segment to start at.
            datatype (DATA_TYPE, optional): C data type for the buffer (e.g., INT16_T).
            ratio_mode (RATIO_MODE, optional): Downsampling mode.
            action (ACTION, optional): Action to apply to the data buffer (e.g., CLEAR_ALL | ADD).

        Returns:
            np.array | None: The allocated buffer or ``None`` when clearing existing buffers.

        Raises:
            PicoSDKException: If an unsupported data type is provided.
        """
        if samples == 0:
            buffer = None
            buf_ptr = None
        else:
            # Map to NumPy dtype
            dtype_map = {
                DATA_TYPE.INT8_T: np.int8,
                DATA_TYPE.INT16_T: np.int16,
                DATA_TYPE.INT32_T: np.int32,
                DATA_TYPE.INT64_T: np.int64,
                DATA_TYPE.UINT32_T: np.uint32,
            }

            np_dtype = dtype_map.get(datatype)
            if np_dtype is None:
                raise PicoSDKException("Invalid datatype selected for buffer")

            buffer = np.zeros((captures, samples, 2), dtype=np_dtype)

        for i in range(captures):
            self._call_attr_function(
                "SetDataBuffers",
                self.handle,
                channel,
                npc.as_ctypes(buffer[i][0]),
                npc.as_ctypes(buffer[i][1]),
                samples,
                datatype,
                segment + i,
                ratio_mode,
                action,
            )

        return buffer

    # Run functions
    def run_simple_block_capture(
        self,
        timebase: int,
        samples: int,
        segment: int = 0,
        start_index: int = 0,
        datatype: cst.DATA_TYPE = cst.DATA_TYPE.INT16_T,
        output_unit: str | cst.output_unit_l = 'mv',
        time_unit: str | cst.TimeUnit_L = 'ns',
        ratio: int = 0,
        ratio_mode: cst.RATIO_MODE = cst.RATIO_MODE.RAW,
        pre_trig_percent: int = 50,
    ) -> tuple[dict[int, np.ndarray], np.ndarray]:
        """Perform a complete single block capture.

        Args:
            timebase: PicoScope timebase value.
            samples: Number of samples to capture.
            segment: Memory segment index to use.
            start_index: Starting index in the buffer.
            datatype: Data type to use for the capture buffer.
            output_unit (str, optional): Output unit of data, can be ['adc', 'mv', 'v']
                Default is 'mv'.
            time_unit (str, optional): Output unit of the time_axis.
                Default is 'ns'.
            ratio: Downsampling ratio.
            ratio_mode: Downsampling mode.
            pre_trig_percent: Percentage of samples to capture before the trigger.

        Returns:
            tuple[dict[int,np.ndarray],np.ndarray]: Dictionary of channel buffers and the
            time axis (numpy array).

        Examples:
            >>> scope.set_channel(CHANNEL.A, RANGE.V1)
            >>> scope.set_simple_trigger(CHANNEL.A, threshold_mv=500)
            >>> buffers = scope.run_simple_block_capture(timebase=3, samples=1000)
        """

        # Update last used
        self.last_used_volt_unit = output_unit

        # Create data buffers
        channel_buffer = \
            self.set_data_buffer_for_enabled_channels(samples, segment, datatype, ratio_mode)

        # Start block capture
        self.run_block_capture(timebase, samples, pre_trig_percent, segment)

        # Get values from PicoScope (returning actual samples for time_axis)
        actual_samples = self.get_values(samples, start_index, segment, ratio, ratio_mode)

        # Reduce channels buffer by actual samples
        for channel in channel_buffer:
            channel_buffer[channel] = channel_buffer[channel][:actual_samples]

        # Convert from ADC to mV or V values
        if output_unit != 'adc':
            channel_buffer = self._adc_to_(channel_buffer, unit=output_unit)

        # Generate the time axis based on actual samples and timebase
        time_axis = self.get_time_axis(
            timebase, actual_samples, pre_trig_percent=pre_trig_percent,
            ratio=ratio, unit=time_unit)

        return channel_buffer, time_axis

    def run_simple_rapid_block_capture(
        self,
        timebase: int,
        samples: int,
        captures: int,
        start_index: int = 0,
        datatype: cst.DATA_TYPE = cst.DATA_TYPE.INT16_T,
        output_unit: str | cst.output_unit_l = 'mv',
        time_unit: str | cst.TimeUnit_L = 'ns',
        ratio: int = 0,
        ratio_mode: cst.RATIO_MODE = cst.RATIO_MODE.RAW,
        pre_trig_percent: int = 50,
    ) -> tuple[dict[int, np.ndarray], np.ndarray]:
        """Run a rapid block capture with X amount of captures/frames/waveforms

        Args:
            timebase: PicoScope timebase value.
            samples: Number of samples to capture.
            captures: Number of waveforms to capture.
            start_index: Starting index in buffer.
            datatype: Data type to use for the capture buffer.
            output_unit (str, optional): Output unit of data, can be ['adc', 'mv', 'v']
                Default is 'mv'.
            time_unit (str, optional): Output unit of the time_axis.
                Default is 'ns'.
            ratio: Downsampling ratio.
            ratio_mode: Downsampling mode.
            pre_trig_percent: Percentage of samples to capture before the trigger.

        Returns:
            tuple[dict,np.ndarray]: Dictionary of channel buffers and the time
                axis (numpy array).
        """
        # Update last used
        self.last_used_volt_unit = output_unit

        # Segment set to 0
        segment = 0

        # Setup memory segments
        self.memory_segments(captures)
        self.set_no_of_captures(captures)

        # Build buffers for data
        channel_buffer = self.set_data_buffer_for_enabled_channels(
            samples, datatype=datatype, ratio_mode=ratio_mode, captures=captures)

        # Run block capture
        self.run_block_capture(timebase, samples, pre_trig_percent)

        # Return values
        actual_samples, _ = self.get_values_bulk(
            start_index, samples, segment, captures - 1, ratio, ratio_mode)

        # Reduce samples based on actual samples
        for channel, array in channel_buffer.items():
            channel_buffer[channel] = array[:, :actual_samples]

        # Convert data to mV
        if output_unit != 'adc':
            channel_buffer = self._adc_to_(channel_buffer, unit=output_unit)

        # Get time axis
        time_axis = self.get_time_axis(
            timebase, actual_samples, pre_trig_percent=pre_trig_percent,
            ratio=ratio, unit=time_unit)

        # Return data
        return channel_buffer, time_axis

    def run_block_capture(
            self,
            timebase: int,
            samples: int,
            pre_trig_percent: float | None = None,
            segment: int = 0,
        ) -> int:
        """
        Runs a block capture using the specified timebase and number of samples.

        This sets up the PicoScope to begin collecting a block of data, divided into
        pre-trigger and post-trigger samples. It uses the PicoSDK `RunBlock` function.

        Args:
            timebase (int): Timebase value determining sample interval (refer to PicoSDK guide).
            samples (int): Total number of samples to capture.
            pre_trig_percent (int | None, optional):
                Percentage of samples to capture before the trigger. If None, defaults to
                last called pre_trig_percent or 50.
            segment (int, optional): Memory segment index to use.

        Returns:
            int: Estimated time (in milliseconds) the device will be busy capturing data.
        """
        # Check and add pre-trig to base dataclass
        if pre_trig_percent is None:
            pre_trig_percent = self.base_dataclass.last_pre_trig
        self.base_dataclass.last_pre_trig = pre_trig_percent

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

    def run_streaming(
        self,
        sample_interval: float,
        time_units: TIME_UNIT,
        max_pre_trigger_samples: int,
        max_post_trigger_samples: int,
        auto_stop: int,
        ratio: int,
        ratio_mode: RATIO_MODE,
    ) -> float:
        """Begin a streaming capture.
        This wraps the ``RunStreaming`` driver call and configures the
        acquisition according to the provided arguments.
        Args:
            sample_interval: Requested interval between samples.
            time_units: Unit for ``sample_interval``.
            max_pre_trigger_samples: Number of pre-trigger samples to collect.
            max_post_trigger_samples: Number of post-trigger samples to collect.
            auto_stop: Whether the driver should stop when the buffer is full.
            ratio: Down sampling ratio.
            ratio_mode: Down sampling mode.
        Returns:
            float: The actual sample interval configured by the driver.
        """

        time_units = _StandardPicoConv[time_units]

        c_sample_interval = ctypes.c_double(sample_interval)
        self._call_attr_function(
            "RunStreaming",
            self.handle,
            ctypes.byref(c_sample_interval),
            time_units,
            int(max_pre_trigger_samples),
            int(max_post_trigger_samples),
            auto_stop,
            ratio,
            ratio_mode,
        )
        return c_sample_interval.value

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

    def get_streaming_latest_values(
        self,
        channel,
        ratio_mode,
        data_type
    ):
        info = PICO_STREAMING_DATA_INFO(
            channel_ = channel,
            mode_ = ratio_mode,
            type_ = data_type,
        )
        trigger = PICO_STREAMING_DATA_TRIGGER_INFO()

        status = self._call_attr_function(
            "GetStreamingLatestValues",
            self.handle,
            ctypes.byref(info),
            1,
            ctypes.byref(trigger)
        )
        return {
            'status': status,
            'no of samples': info.noOfSamples_,
            'Buffer index': info.bufferIndex_,
            'start index': info.startIndex_,
            'overflowed?': info.overflow_,
            'triggered at': trigger.triggerAt_,
            'triggered?': trigger.triggered_,
            'auto stopped?': trigger.autoStop_,
        }

    def is_over_range(self) -> list:
        """
        Logs and prints a warning if any channel has been over range.

        The :attr:`over_range` attribute stores a bit mask updated by data
        retrieval methods like :meth:`get_values` and
        :meth:`get_values_overlapped`. Calling this method logs a warning if
        any channel went over range and returns a list of the affected
        channel names.

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

__all__ = ['PicoScopeBase']