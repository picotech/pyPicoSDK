"""Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms."""

import ctypes
from typing import override
from warnings import warn

import numpy as np
import numpy.ctypeslib as npc

from .. import constants as cst
from ..common import (
    _get_literal,
    ParameterNotSupported
)
from ..base import PicoScopeBase
from .._classes._channel_class import ChannelClass
from .._exceptions import PicoSDKException


class ps5000a(PicoScopeBase):  # pylint: disable=C0103
    """PicoScope 5000 (A) API specific functions"""

    @override
    def __init__(self, *args, **kwargs):
        self.power_source = None
        super().__init__("ps5000a", *args, **kwargs)

    @override
    def open_unit(
        self,
        serial_number: str = None,
        resolution: str | cst.resolution_literal | cst.RESOLUTION = cst.RESOLUTION.BIT_8
    ) -> None:
        resolution = _get_literal(resolution, cst.resolution_map)
        status = super().open_unit(serial_number, resolution)
        if status == cst.POWER_SOURCE.SUPPLY_NOT_CONNECTED:
            self.change_power_source(cst.POWER_SOURCE.SUPPLY_NOT_CONNECTED)
        self.min_adc_value, self.max_adc_value = self.get_adc_limits()

    def get_adc_limits(self) -> tuple[int, int]:
        """
        Returns the ADC limits for this device.

        Returns:
            tuple[int,int]: Minimum ADC value, Maximum ADC value
        """
        functions = ['MinimumValue', 'MaximumValue']
        adc_values = []
        for func in functions:
            adc_value = ctypes.c_int16()
            self._call_attr_function(
                func,
                self.handle,
                ctypes.byref(adc_value)
            )
            adc_values.append(adc_value.value)
        return adc_values[0], adc_values[1]

    def change_power_source(self, power_source: str | cst.PwrSrc_L | cst.POWER_SOURCE) -> None:
        """
        Selects the power supply mode. If USB power is required, you must explicitly allow it by
        calling this function. You must also call this function if the AC power adapter is
        connected or disconnected during use.

        Args:
            power_source (str | POWER_SOURCE): Power source selection.
        """
        power_source = _get_literal(power_source, cst.PwrSrc_M)
        self._call_attr_function(
            'ChangePowerSource',
            self.handle,
            power_source
        )

    def set_channel(
        self,
        channel: str | cst.channel_literal | cst.CHANNEL,
        range: str | cst.range_literal | cst.RANGE = cst.RANGE.V1,  # pylint: disable=W0622
        enabled: bool = True,
        coupling: cst.COUPLING = cst.COUPLING.DC,
        offset: float = 0.0,
        probe_scale: float = 1.0
    ) -> None:
        """
        Enable/disable a channel and specify certain variables i.e. range, coupling, offset, etc.

        Args:
            channel (str | CHANNEL): Channel to setup.
            range (str | RANGE, optional): Voltage range of channel. Defaults to RANGE.V1.
            coupling (COUPLING, optional): AC/DC Coupling of selected channel.
                Defaults to COUPLING.DC.
            offset (float, optional): Analog offset in volts (V). Defaults to 0.0.
        """
        channel = _get_literal(channel, cst.channel_map)
        range = _get_literal(range, cst.range_map)

        if enabled:
            self.channel_db[channel] = ChannelClass(range, probe_scale)
        elif channel in self.channel_db:
            self.channel_db.pop(channel)

        self._call_attr_function(
            'SetChannel',
            self.handle,
            channel,
            enabled,
            coupling,
            range,
            ctypes.c_float(offset)
        )

    @override
    def set_all_channels_off(self) -> None:
        """
        Turns all channels off, based on unit number of channels.
        If the ps5000a has no AC power supply attached, only turns off channela A and B
        """
        channels = int(self.get_unit_info(cst.UNIT_INFO.PICO_VARIANT_INFO)[1])
        # if self.power_source == cst.POWER_SOURCE.SUPPLY_NOT_CONNECTED:
        #     channels = min(2, channels)
        for channel in range(int(channels)):
            self.set_channel(channel, enabled=False)

    @override
    def set_simple_trigger(self, channel, threshold=0, threshold_unit='mv', enable=True,
                           direction=cst.TRIGGER_DIR.RISING, delay=0, auto_trigger=0):
        status = super().set_simple_trigger(channel, threshold, threshold_unit, enable, direction,
                                            delay, auto_trigger=0)
        self.set_auto_trigger_microseconds(auto_trigger)
        return status

    def set_auto_trigger_microseconds(self, auto_trigger: int) -> int:
        """
        Set auto_trigger in microseconds.
        This will override or be overridden by calling `set_simple_trigger()`.

        Args:
            auto_trigger (int): Number of microseconds the PicoScope will wait before timing out
                and auto-triggering.

        Returns:
            int: Status from device.
        """
        return self._call_attr_function(
            'SetAutoTriggerMicroSeconds',
            self.handle,
            auto_trigger
        )

    @override
    def set_data_buffer(  # pylint: disable=W0221
        self,
        channel: cst.CHANNEL,
        samples: int,
        segment: int = 0,
        datatype=None,
        ratio_mode: cst.RATIO_MODE = cst.RATIO_MODE.RAW,
        action=None,
        buffer: np.ndarray | None = None,
    ) -> np.ndarray | None:
        """
        Allocate and assign NumPy-backed data buffers

        Args:
            channel (CHANNEL): Channel to associate the buffers with.
            samples (int): Number of samples to allocate.
            segment (int, optional): Memory segment to use. Defaults to 0.
            ratio_mode (RATIO_MODE, optional): Downsampling mode. Defaults to AGGREGATE.
            buffers (np.ndarray | None, optional):
                Send a preallocated data buffer to be populated. Min buffer first.
                If left as none, this function creates and returns its own buffer.

        Returns:
            np.ndarray: Created buffer as a numpy array.
        """
        # Warnings if moving to ps5000a from other drivers.
        if datatype not in [cst.DATA_TYPE.INT16_T, None]:
            warn(f'{self._unit_prefix_n} only supports datatype int16. Defaulting to int16.',
                 ParameterNotSupported)
        if action not in [cst.ACTION.ADD, None]:
            warn(f'{self._unit_prefix_n} only supports the "ADD" action. Defaulting to ADD.',
                 ParameterNotSupported)

        # Convert RAW (unsupported in ps5000a) to NONE.
        if ratio_mode == cst.RATIO_MODE.RAW:
            ratio_mode = cst.RATIO_MODE.NONE

        # If no samples, set buffers to None
        if samples == 0:
            buffer = None
        # Else create new buffer
        elif buffer is None:
            buffer = np.zeros(samples, dtype=np.int16)

        # Create pointer
        buf_ptr = npc.as_ctypes(buffer)

        self._call_attr_function(
            "SetDataBuffer",
            self.handle,
            channel,
            buf_ptr,
            samples,
            segment,
            ratio_mode,
        )

        return buffer

    @override
    def set_data_buffers(  # pylint: disable=W0221
        self,
        channel: cst.CHANNEL,
        samples: int,
        segment: int = 0,
        datatype=None,
        ratio_mode: cst.RATIO_MODE = cst.RATIO_MODE.AGGREGATE,
        action=None,
        buffers: list[np.ndarray, np.ndarray] | np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Allocate and assign max and min NumPy-backed data buffers

        Args:
            channel (CHANNEL): Channel to associate the buffers with.
            samples (int): Number of samples to allocate.
            segment (int, optional): Memory segment to use. Defaults to 0.
            ratio_mode (RATIO_MODE, optional): Downsampling mode. Defaults to AGGREGATE.
            buffers (list[np.ndarray, np.ndarray] | np.ndarray | None, optional):
                Send preallocated data buffers to be populared. Min buffer first, followed
                by max buffer. If left as none, this function creates its own buffers.

        Returns:
            tuple[np.ndarray,np.ndarray]: Tuple of (buffer_min, buffer_max) numpy arrays.
        """
        # Warnings if moving to ps5000a from other drivers.
        if datatype not in [cst.DATA_TYPE.INT16_T, None]:
            warn(f'{self._unit_prefix_n} only supports datatype int16. Defaulting to int16.',
                 ParameterNotSupported)
        if action not in [cst.ACTION.ADD, None]:
            warn(f'{self._unit_prefix_n} only supports the "ADD" action. Defaulting to ADD.',
                 ParameterNotSupported)

        # Convert RAW (unsupported in ps5000a) to NONE.
        if ratio_mode == cst.RATIO_MODE.RAW:
            ratio_mode = cst.RATIO_MODE.NONE

        # If buffers are given, split into seperate buffers
        if buffers is not None:
            buffer_min = buffers[0]
            buffer_max = buffers[1]

        # Else create new buffer
        else:
            buffer_max = np.zeros(samples, dtype=np.int16)
            buffer_min = np.zeros(samples, dtype=np.int16)

        # Create pointer
        buf_max_ptr = npc.as_ctypes(buffer_max)
        buf_min_ptr = npc.as_ctypes(buffer_min)

        self._call_attr_function(
            "SetDataBuffers",
            self.handle,
            channel,
            buf_max_ptr,
            buf_min_ptr,
            samples,
            segment,
            ratio_mode,
        )

        return buffer_min, buffer_max

    @override
    def get_values(self, samples, start_index=0, segment=0, ratio=0, ratio_mode=cst.RATIO_MODE.RAW):
        if ratio_mode == cst.RATIO_MODE.RAW:
            ratio_mode = cst.RATIO_MODE.NONE
        return super().get_values(samples, start_index, segment, ratio, ratio_mode)

    def set_siggen(
        self,
        frequency: float,
        pk2pk: float,
        wave_type: str | cst.waveform_literal | cst.WAVEFORM,
        offset: int = 0,
        sweep: bool = False,
        stop_freq: float = None,
        inc_freq: float = 0,
        dwell_time: float = 1,
        sweep_type: cst.SWEEP_TYPE = cst.SWEEP_TYPE.UP,
        **kwargs,
    ) -> int:
        """
        Set the Signal Generator to the following specifications.

        Args:
            frequency (float): Frequency the SigGen will initially produce.
            pk2pk (float): Peak-to-peak voltage in volts (V)
            wave_type (str | WAVEFORM): Type of waveform to be generated.
            offset (int, optional): Offset in volts (V). Defaults to 0.
            sweep (bool, optional): If sweep is enabled, specify a stop_freq.
                Defaults to False.
            stop_freq (float, optional): Stop frequency in sweep mode. Defaults to None.
            inc_freq (float, optional): Frequency to increment in sweep mode. Defaults to 0.
            dwell_time (float, optional): Time of each step in sweep mode in seconds.
                Defaults to 1.
            sweep_type (SWEEP_TYPE, optional): Sweep direction in sweep mode.
                Defaults to SWEEP_TYPE.UP.
            operation (int, optional): Extra operations for the signal generator.
                Defaults to 0.
            shots (int, optional): Sweep the frequency as specified by sweeps.
                Defaults to 0.
            sweeps (int, optional): Produce number of cycles specified by shots.
                Defaults to 0.
            trigger_type (int, optional): Type of trigger (edge or level) that will be applied to
                signal generator. Defaults to 0.
            trigger_source (int, optional): The source that will trigger the signal generator.
                Defaults to 0.
            ext_in_threshold (int, optinal): Used to set trigger level for external trigger.
                Defaults to 0.

        Returns:
            int: Returned status of device.
        """
        if sweep is False:
            stop_freq = frequency

        # Convert V to uV
        offset = int(offset * 1e6)
        pk2pk = int(pk2pk * 1e6)

        # Get wavetype and map to ps5000a enums
        wave_type = _get_literal(wave_type, cst.waveform_map)
        wave_type = cst.ps5000a_waveform_map.get(wave_type, None)
        if wave_type is None:
            raise PicoSDKException(f'Wave type of {wave_type} is invalid for this device.')

        status = self._call_attr_function(
            'SetSigGenBuiltInV2',
            self.handle,
            offset,
            pk2pk,
            wave_type,
            ctypes.c_double(frequency),
            ctypes.c_double(stop_freq),
            ctypes.c_double(inc_freq),
            ctypes.c_double(dwell_time),
            sweep_type,
            kwargs.get('operation', 0),
            kwargs.get('shots', 0),
            kwargs.get('sweeps', 0),
            kwargs.get('trigger_type', 0),
            kwargs.get('trigger_source', 0),
            kwargs.get('ext_in_threshold', 0)
        )
        return status

    @override
    def set_data_buffer_for_enabled_channels(
        self,
        samples,
        segment=0,
        datatype=cst.DATA_TYPE.INT16_T,
        ratio_mode=cst.RATIO_MODE.RAW,
        clear_buffer=False,
        captures=0
    ):
        clear_buffer = False
        return super().set_data_buffer_for_enabled_channels(
            samples, segment, datatype, ratio_mode, clear_buffer, captures)

    @override
    def get_timebase(self, timebase, samples, segment=0):
        time_interval_ns = ctypes.c_float()
        max_samples = ctypes.c_uint64()
        status = self._call_attr_function(
            'GetTimebase2',
            self.handle,
            timebase,
            samples,
            ctypes.byref(time_interval_ns),
            ctypes.byref(max_samples),
            segment,
        )
        return {'Interval(ns)': time_interval_ns.value,
                'Samples': max_samples.value,
                'Status': status}

    @override
    def get_nearest_sampling_interval(self, interval_s):
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

    @override
    def memory_segments(self, n_segments: int) -> int:
        """
        Configure the number of memory segments for the ps5000a.

        Args:
            n_segments (int): Desired number of memory segments.

        Returns:
            int: Number of samples available in each segment.
        """
        max_samples = ctypes.c_uint32()
        self._call_attr_function(
            "MemorySegments",
            self.handle,
            ctypes.c_uint32(n_segments),
            ctypes.byref(max_samples),
        )
        return max_samples.value

    @override
    def get_values_bulk(  # pylint: disable=W0221
        self,
        samples: int,
        from_segment_index: int,
        to_segment_index: int,
        ratio: int = 0,
        ratio_mode: cst.RATIO_MODE = cst.RATIO_MODE.NONE,
        **_,
    ) -> tuple[int, list[list[str]]]:
        """Retrieve data from multiple memory segments.

        Args:
            samples: Total number of samples to read from each segment.
            from_segment_index: Index of the first segment to read.
            to_segment_index: Index of the last segment. If this value is
                less than ``from_segment_index`` the driver wraps around.
            ratio: Downsampling ratio to apply before copying.
            ratio_mode: Downsampling mode from :class:`RATIO_MODE`.

        Returns:
            tuple[int, list[list[str]]]: ``(samples, overflow)list)`` where ``samples`` is the
            number of samples copied and ``overflow`` is list of captures with where
            channnels have exceeded their voltage range.
        """
        if ratio_mode == cst.RATIO_MODE.RAW:
            ratio_mode = cst.RATIO_MODE.NONE

        self.is_ready()
        no_samples = ctypes.c_uint32(samples)
        overflow = np.zeros(to_segment_index + 1, dtype=np.int16)
        self._call_attr_function(
            "GetValuesBulk",
            self.handle,
            ctypes.byref(no_samples),
            ctypes.c_uint32(from_segment_index),
            ctypes.c_uint32(to_segment_index),
            ctypes.c_uint32(ratio),
            ratio_mode,
            npc.as_ctypes(overflow),
        )
        overflow_list = []
        for i in overflow:
            self.over_range = i
            overflow_list.append(self.is_over_range())
        return no_samples.value, overflow_list
