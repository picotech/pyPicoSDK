import ctypes
import numpy as np
from .constants import *
from .base import PicoSDKException, PicoScopeBase

class ps6000a(PicoScopeBase):
    """PicoScope 6000 (A) API specific functions"""
    def __init__(self, *args, **kwargs):
        super().__init__("ps6000a", *args, **kwargs)


    def open_unit(self, serial_number:str=None, resolution:RESOLUTION | resolution_literal=0) -> None:
        """
        Open PicoScope unit.

        Args:
                serial_number (str, optional): Serial number of device.
                resolution (RESOLUTION, optional): Resolution of device.
        """
        # If using Literals, convert to int
        if resolution in resolution_map:
            resolution = resolution_map[resolution]

        super()._open_unit(serial_number, resolution)
        self.min_adc_value, self.max_adc_value =super()._get_adc_limits()

    def open_unit_async(
        self,
        serial_number: str | None = None,
        resolution: RESOLUTION = 0,
    ) -> int:
        """Open a unit without blocking the calling thread.
        Wraps ``ps6000aOpenUnitAsync`` which begins the open operation and
        returns immediately.
        Args:
            serial_number: Serial number of the device to open.
            resolution: Requested resolution for the device.
        Returns:
            int: Status flag from the driver (``0`` if the request was not
                started, ``1`` if the operation began successfully).
        """

        status_flag = ctypes.c_int16()
        if serial_number is not None:
            serial_number = serial_number.encode()

        self._call_attr_function(
            "OpenUnitAsync",
            ctypes.byref(status_flag),
            serial_number,
            resolution,
        )

        self._pending_resolution = resolution
        return status_flag.value

    def open_unit_progress(self) -> tuple[int, int, int]:
        """Check the progress of :meth:`open_unit_async`.
        This wraps ``ps6000aOpenUnitProgress`` and should be called repeatedly
        until ``complete`` is non-zero.
        Returns:
            tuple[int, int, int]: ``(handle, progress_percent, complete)``.
        """

        handle = ctypes.c_int16()
        progress = ctypes.c_int16()
        complete = ctypes.c_int16()

        self._call_attr_function(
            "OpenUnitProgress",
            ctypes.byref(handle),
            ctypes.byref(progress),
            ctypes.byref(complete),
        )

        if complete.value:
            self.handle = handle
            self.resolution = getattr(self, "_pending_resolution", 0)
            self.min_adc_value, self.max_adc_value = super()._get_adc_limits()

        return handle.value, progress.value, complete.value

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

    def memory_segments_by_samples(self, n_samples: int) -> int:
        """Set the samples per memory segment.

        This wraps ``ps6000aMemorySegmentsBySamples`` which divides the
        capture memory so that each segment holds ``n_samples`` samples.

        Args:
            n_samples: Number of samples per segment.

        Returns:
            int: Number of segments the memory was divided into.
        """

        max_segments = ctypes.c_uint64()
        self._call_attr_function(
            "MemorySegmentsBySamples",
            self.handle,
            ctypes.c_uint64(n_samples),
            ctypes.byref(max_segments),
        )
        return max_segments.value

    def query_max_segments_by_samples(
        self,
        n_samples: int,
        n_channel_enabled: int,
    ) -> int:
        """Return the maximum number of segments for a given sample count.

        Wraps ``ps6000aQueryMaxSegmentsBySamples`` to query how many memory
        segments can be configured when each segment stores ``n_samples``
        samples.

        Args:
            n_samples: Number of samples per segment.
            n_channel_enabled: Number of enabled channels.

        Returns:
            int: Maximum number of segments available.

        Raises:
            PicoSDKException: If the device has not been opened.
        """

        if self.resolution is None:
            raise PicoSDKException("Device has not been initialized, use open_unit()")

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
        self.min_adc_value, self.max_adc_value = super()._get_adc_limits()

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
        self.min_adc_value, self.max_adc_value = super()._get_adc_limits()
        return RESOLUTION(resolution.value)
    
    def reset_channels_and_report_all_channels_overvoltage_trip_status(self) -> list[PICO_CHANNEL_OVERVOLTAGE_TRIPPED]:
        """Reset channels and return overvoltage trip status for each.
        Wraps ``ps6000aResetChannelsAndReportAllChannelsOvervoltageTripStatus``.
        Returns:
            list[PICO_CHANNEL_OVERVOLTAGE_TRIPPED]: Trip status for all channels.
        """

        n_channels = len(CHANNEL_NAMES)
        status_array = (PICO_CHANNEL_OVERVOLTAGE_TRIPPED * n_channels)()
        self._call_attr_function(
            "ResetChannelsAndReportAllChannelsOvervoltageTripStatus",
            self.handle,
            status_array,
            ctypes.c_uint8(n_channels),
        )

        return list(status_array)
    
    def no_of_streaming_values(self) -> int:
        """Return the number of values currently available while streaming."""

        count = ctypes.c_uint64()
        self._call_attr_function(
            "NoOfStreamingValues",
            self.handle,
            ctypes.byref(count),
        )
        return count.value
    
    def get_maximum_available_memory(self) -> int:
        """Return the maximum sample depth for the current resolution.
        Wraps ``ps6000aGetMaximumAvailableMemory`` to query how many samples
        can be captured at ``self.resolution``.
        Returns:
            int: Maximum number of samples supported.
        Raises:
            PicoSDKException: If the device has not been opened.
        """

        if self.resolution is None:
            raise PicoSDKException("Device has not been initialized, use open_unit()")

        max_samples = ctypes.c_uint64()
        self._call_attr_function(
            "GetMaximumAvailableMemory",
            self.handle,
            ctypes.byref(max_samples),
            self.resolution,
        )
        return max_samples.value
    
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

    def report_all_channels_overvoltage_trip_status(
        self,
    ) -> list[PICO_CHANNEL_OVERVOLTAGE_TRIPPED]:
        """Return the overvoltage trip status for each channel.
        This wraps ``ps6000aReportAllChannelsOvervoltageTripStatus`` to
        query whether any channel's 50 Ω input protection has tripped.
        Returns:
            list[PICO_CHANNEL_OVERVOLTAGE_TRIPPED]: Trip status for all
            channels.
        """

        n_channels = len(CHANNEL_NAMES)
        array_type = PICO_CHANNEL_OVERVOLTAGE_TRIPPED * n_channels
        status_array = array_type()

        self._call_attr_function(
            "ReportAllChannelsOvervoltageTripStatus",
            self.handle,
            status_array,
            n_channels,
        )

        return list(status_array)
    
    def get_no_of_processed_captures(self) -> int:
        """Return the number of captures processed in rapid block mode."""

        n_processed = ctypes.c_uint64()
        self._call_attr_function(
            "GetNoOfProcessedCaptures",
            self.handle,
            ctypes.byref(n_processed),
        )
        return n_processed.value
    
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
    
    def set_channel(
        self,
        channel: CHANNEL | channel_literal,
        range: RANGE | range_literal = RANGE.V1,
        enabled: bool = True,
        coupling: COUPLING = COUPLING.DC,
        offset: float = 0.0,
        bandwidth: BANDWIDTH_CH = BANDWIDTH_CH.FULL,
        probe_scale: float = 1.0,
    ) -> None:
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
                probe_scale (float, optional): Probe attenuation factor such as 1 or 10.
        """
        # Check if typing Literals
        if channel in channel_map:
            channel = channel_map[channel]
        if range in range_map:
            range = range_map[range]
        
        # Add probe scaling
        self.probe_scale[channel] = probe_scale

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
    
    def channel_combinations_stateless(
        self, 
        resolution: RESOLUTION, 
        timebase: int
    ) -> list[PICO_CHANNEL_FLAGS]:
        """Return valid channel flag combinations for a configuration."""

        size = 8
        func = self._get_attr_function("ChannelCombinationsStateless")
        while True:
            combos = (ctypes.c_uint32 * size)()
            n_combos = ctypes.c_uint32(size)
            status = func(
                self.handle,
                combos,
                ctypes.byref(n_combos),
                resolution,
                ctypes.c_uint32(timebase),
            )
            if status == 401:
                size = n_combos.value
                continue
            self._error_handler(status)
            return [PICO_CHANNEL_FLAGS(combos[i]) for i in range(n_combos.value)]

    def get_accessory_info(self, channel: CHANNEL, info: UNIT_INFO) -> str:
        """Retrieve information about an accessory connected to ``channel``."""

        buf_len = 64
        string = ctypes.create_string_buffer(buf_len)
        req_size = ctypes.c_int16(buf_len)
        self._call_attr_function(
            "GetAccessoryInfo",
            self.handle,
            channel,
            string,
            ctypes.c_int16(buf_len),
            ctypes.byref(req_size),
            ctypes.c_uint32(info),
        )
        return string.value.decode()

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

    def get_analogue_offset_limits(
        self, range: PICO_CONNECT_PROBE_RANGE, coupling: COUPLING
    ) -> tuple[float, float]:
        """Get the allowed analogue offset range for ``range`` and ``coupling``."""

        max_v = ctypes.c_double()
        min_v = ctypes.c_double()
        self._call_attr_function(
            "GetAnalogueOffsetLimits",
            self.handle,
            range,
            coupling,
            ctypes.byref(max_v),
            ctypes.byref(min_v),
        )
        return max_v.value, min_v.value
    
    def get_scaling_values(self, n_channels: int = 8) -> list[PICO_SCALING_FACTORS_VALUES]:
        """Return probe scaling factors for each channel.
        Args:
            n_channels: Number of channel entries to retrieve.
        Returns:
            list[PICO_SCALING_FACTORS_VALUES]: Scaling factors for ``n_channels`` channels.
        """

        array_type = PICO_SCALING_FACTORS_VALUES * n_channels
        values = array_type()
        self._call_attr_function(
            "GetScalingValues",
            self.handle,
            values,
            ctypes.c_int16(n_channels),
        )
        return list(values)

    def set_simple_trigger(
            self, 
            channel:CHANNEL | channel_literal, 
            threshold_mv=0, 
            enable=True, 
            direction:TRIGGER_DIR=TRIGGER_DIR.RISING, 
            delay=0, 
            auto_trigger_ms=5_000):
        """
        Sets up a simple trigger from a specified channel and threshold in mV.

        Args:
            channel (int): The input channel to apply the trigger to.
            threshold_mv (float): Trigger threshold level in millivolts.
            enable (bool, optional): Enables or disables the trigger. 
            direction (TRIGGER_DIR, optional): Trigger direction (e.g., TRIGGER_DIR.RISING, TRIGGER_DIR.FALLING). 
            delay (int, optional): Delay in samples after the trigger condition is met before starting capture. 
            auto_trigger_ms (int, optional): Timeout in milliseconds after which data capture proceeds even if no trigger occurs. 

        Examples:
            When using TRIGGER_AUX, threshold is fixed to 1.25 V
            >>> scope.set_simple_trigger(channel=psdk.CHANNEL.TRIGGER_AUX)
           
        """
        # Check if typing Literals
        if channel in channel_map:
            channel = channel_map[channel]

        auto_trigger_us = auto_trigger_ms * 1000
        return super().set_simple_trigger(channel, threshold_mv, enable, direction, delay, auto_trigger_us)


    def set_data_buffer(
        self,
        channel: CHANNEL,
        samples: int,
        segment: int = 0,
        datatype: DATA_TYPE = DATA_TYPE.INT16_T,
        ratio_mode: RATIO_MODE = RATIO_MODE.RAW,
        action: ACTION = ACTION.CLEAR_ALL | ACTION.ADD,
    ) -> np.ndarray | None:
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
                np.ndarray | None: Numpy array that will be populated when ``get_values`` is called.
        """
        return super()._set_data_buffer_ps6000a(channel, samples, segment, datatype, ratio_mode, action)

    def set_data_buffers(
        self,
        channel: CHANNEL,
        samples: int,
        segment: int = 0,
        datatype: DATA_TYPE = DATA_TYPE.INT16_T,
        ratio_mode: RATIO_MODE = RATIO_MODE.AGGREGATE,
        action: ACTION = ACTION.CLEAR_ALL | ACTION.ADD,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Configure both maximum and minimum data buffers for a channel.

        Use this when downsampling in aggregation mode or requesting
        post-capture aggregated values. It allocates two buffers - one to hold
        the maximum values and another for the minimum values - and registers
        them with ``ps6000aSetDataBuffers``.

        Args:
            channel (CHANNEL): Channel you want to use with the buffers.
            samples (int): Number of samples/length of each buffer.
            segment (int, optional): Memory segment index for the buffers.
            datatype (DATA_TYPE, optional): C datatype of the data stored in the
                buffers.
            ratio_mode (RATIO_MODE, optional): Downsampling mode. Typically
                ``RATIO_MODE.AGGREGATE`` when both buffers are required.
            action (ACTION, optional): Method used when creating or updating the
                buffers.

        Returns:
            tuple[np.ndarray, np.ndarray]: ``(buffer_max, buffer_min)`` that
            will be populated when :meth:`get_values` is called.
        """

        return super()._set_data_buffers_ps6000a(
            channel,
            samples,
            segment,
            datatype,
            ratio_mode,
            action,
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
            super()._set_data_buffer_ps6000a(0, 0, 0, 0, 0, ACTION.CLEAR_ALL)

        # Create Buffers
        channels_buffer = {}
        # Rapid
        if captures > 0:
            for channel in self.range:
                buffer = []
                for capture_segment in range(captures):
                    buffer.append(super()._set_data_buffer_ps6000a(channel, samples, segment + capture_segment, datatype, ratio_mode, action=ACTION.ADD))
                channels_buffer[channel] = buffer
        # Single
        else:
            for channel in self.range:
                channels_buffer[channel] = super()._set_data_buffer_ps6000a(channel, samples, segment, datatype, ratio_mode, action=ACTION.ADD)

        return channels_buffer
    
    def set_siggen_awg(
            self, 
            frequency:float, 
            pk2pk:float, 
            buffer:np.ndarray|list,
            offset:float=0.0, 
            duty:float=50,
            sweep:bool = False,
            stop_freq:float = None,
            inc_freq:float = 1,
            dwell_time:float = 0.001,
            sweep_type:SWEEP_TYPE = SWEEP_TYPE.UP,
        ) -> dict:   
        """
        Arbitrary Waveform Generation - Generates a signal from a given buffer. 

        Sets up the signal generator with a specified frequency, amplitude (peak-to-peak), 
        offset, and duty cycle.

        If sweep is enabled and the sweep-related args are given, the SigGen will sweep.

        Args:
            frequency (float): Signal frequency in hertz (Hz).
            pk2pk (float): Peak-to-peak voltage in volts (V).
            buffer (np.ndarray | list): _description_
            offset (float, optional): Voltage offset in volts (V). Defaults to 0.0.
            duty (float, optional): Duty cycle as a percentage (0–100). Defaults to 50.
            sweep (bool, optional): If True, sweep is enabled, fill in the following:
            stop_freq (float, optional): Frequency to stop sweep at in Hertz (Hz). Defaults to None.
            inc_freq (float, optional): Frequency to increment (or step) in hertz (Hz). Defaults to 1.
            dwell_time (float, optional): Time to wait between frequency steps in seconds (s). Defaults to 0.001.
            sweep_type (SWEEP_TYPE, optional): Direction of sweep ``[UP, DOWN, UPDOWN, DOWNUP]``. Defaults to UP.

        Raises:
            PicoSDKException: _description_

        Returns:
            dict: _description_
        """

        self.siggen_set_waveform(WAVEFORM.ARBITRARY, buffer=buffer)
        self.siggen_set_range(pk2pk, offset)
        self.siggen_set_frequency(frequency)
        self.siggen_set_duty_cycle(duty)
        if sweep == True:
            if stop_freq is None:
                raise PicoSDKException("Sweep SigGen set, but no stop_freq declared.")
            self.siggen_frequency_sweep(stop_freq, inc_freq, dwell_time, sweep_type)
            return self.siggen_apply(sweep_enabled=True)
        return self.siggen_apply()

    
    def set_siggen(
            self, 
            frequency:float, 
            pk2pk:float, 
            wave_type:WAVEFORM | waveform_literal, 
            offset:float=0.0, 
            duty:float=50,
            sweep:bool = False,
            stop_freq:float = None,
            inc_freq:float = 1,
            dwell_time:float = 0.001,
            sweep_type:SWEEP_TYPE = SWEEP_TYPE.UP,
        ) -> dict:
        """Configures and applies the signal generator settings.

        Sets up the signal generator with the specified waveform type, frequency,
        amplitude (peak-to-peak), offset, and duty cycle.

        If sweep is enabled and the sweep-related args are given, the SigGen will sweep.

        Args:
            frequency (float): Signal frequency in hertz (Hz).
            pk2pk (float): Peak-to-peak voltage in volts (V).
            wave_type (WAVEFORM): Waveform type (e.g., WAVEFORM.SINE, WAVEFORM.SQUARE).
            offset (float, optional): Voltage offset in volts (V).
            duty (int or float, optional): Duty cycle as a percentage (0–100).
            sweep: If True, sweep is enabled, fill in the following:
            stop_freq: Frequency to stop sweep at in Hertz (Hz). Defaults to None.
            inc_freq: Frequency to increment (or step) in hertz (Hz). Defaults to 1 Hz.
            dwell_time: Time to wait between frequency steps in seconds (s). Defaults to 1 ms.
            sweep_type: Direction of sweep ``[UP, DOWN, UPDOWN, DOWNUP]``. Defaults to UP.


        Returns:
            dict: Returns dictionary of the actual achieved values.
        """
        # Check if typing Literal
        if wave_type in waveform_map:
            wave_type = waveform_map[wave_type]

        self.siggen_set_waveform(wave_type)
        self.siggen_set_range(pk2pk, offset)
        self.siggen_set_frequency(frequency)
        self.siggen_set_duty_cycle(duty)
        if sweep == True:
            if stop_freq is None:
                raise PicoSDKException("Sweep SigGen set, but no stop_freq declared.")
            self.siggen_frequency_sweep(stop_freq, inc_freq, dwell_time, sweep_type)
            return self.siggen_apply(sweep_enabled=True)
        return self.siggen_apply()
    
    def run_simple_block_capture(
        self,
        timebase: int,
        samples: int,
        segment: int = 0,
        start_index: int = 0,
        datatype: DATA_TYPE = DATA_TYPE.INT16_T,
        ratio: int = 0,
        ratio_mode: RATIO_MODE = RATIO_MODE.RAW,
        pre_trig_percent: int = 50,
    ) -> tuple[dict, list]:
        """Perform a complete single block capture.

        Args:
            timebase: PicoScope timebase value.
            samples: Number of samples to capture.
            segment: Memory segment index to use.
            start_index: Starting index in the buffer.
            datatype: Data type to use for the capture buffer.
            ratio: Downsampling ratio.
            ratio_mode: Downsampling mode.
            pre_trig_percent: Percentage of samples to capture before the trigger.

        Returns:
            tuple[dict, list]: Dictionary of channel buffers (in mV) and the time
            axis in nano-seconds.

        Examples:
            >>> scope.set_channel(CHANNEL.A, RANGE.V1)
            >>> scope.set_simple_trigger(CHANNEL.A, threshold_mv=500)
            >>> buffers = scope.run_simple_block_capture(timebase=3, samples=1000)
        """

        # Create data buffers. If Ratio Mode is TRIGGER, create a trigger buffer
        if ratio_mode == RATIO_MODE.TRIGGER:
            channels_buffer = self.set_data_buffer_for_enabled_channels(samples, segment, datatype, RATIO_MODE.RAW)
            trigger_buffer = self.set_data_buffer_for_enabled_channels(samples, segment, datatype, ratio_mode, clear_buffer=False)
            ratio_mode = RATIO_MODE.RAW
        else:
            channels_buffer = self.set_data_buffer_for_enabled_channels(samples, segment, datatype, ratio_mode)
            trigger_buffer = None

        # Start block capture
        self.run_block_capture(timebase, samples, pre_trig_percent, segment)

        # Get values from PicoScope (returning actual samples for time_axis)
        actual_samples = self.get_values(samples, start_index, segment, ratio, ratio_mode)

        # Get trigger buffer if applicable
        if trigger_buffer is not None:
            self.get_values(samples, 0, segment, ratio, RATIO_MODE.TRIGGER)

        # Convert from ADC to mV values
        channels_buffer = self.channels_buffer_adc_to_mv(channels_buffer)

        # Generate the time axis based on actual samples and timebase
        time_axis = self.get_time_axis(timebase, actual_samples)

        return channels_buffer, time_axis
    
    def run_simple_rapid_block_capture(
        self,
        timebase: int,
        samples: int,
        captures: int,
        start_index: int = 0,
        datatype: DATA_TYPE = DATA_TYPE.INT16_T,
        ratio: int = 0,
        ratio_mode: RATIO_MODE = RATIO_MODE.RAW,
        pre_trig_percent: int = 50,
    ) -> tuple[dict, list]:
        """Run a rapid block capture with X amount of captures/frames/waveforms

        Args:
            timebase: PicoScope timebase value.
            samples: Number of samples to capture.
            captures: Number of waveforms to capture.
            start_index: Starting index in buffer. 
            datatype: Data type to use for the capture buffer. 
            ratio: Downsampling ratio. 
            ratio_mode: Downsampling mode. 
            pre_trig_percent: Percentage of samples to capture before the trigger. 

        Returns:
            tuple[dict, list]: Dictionary of channel buffers (in mV) and the time
            axis in nano-seconds.
        """

        # Segment set to 0
        segment = 0
        
        # Setup memory segments
        self.memory_segments(captures)
        self.set_no_of_captures(captures)
        
        # Build buffers for data and trigger (if applicable)
        if ratio_mode == RATIO_MODE.TRIGGER:
            channels_buffer = self.set_data_buffer_for_enabled_channels(samples, datatype=datatype, ratio_mode=RATIO_MODE.RAW, captures=captures)
            trigger_buffer = self.set_data_buffer_for_enabled_channels(samples, datatype=datatype, ratio_mode=ratio_mode, clear_buffer=False)
            ratio_mode = RATIO_MODE.RAW
        else:
            channels_buffer = self.set_data_buffer_for_enabled_channels(samples, datatype=datatype, ratio_mode=ratio_mode, captures=captures)
            trigger_buffer = None

        # Run block capture
        self.run_block_capture(timebase, samples, pre_trig_percent)

        # Return values
        actual_samples, overflow = self.get_values_bulk(start_index, samples, segment, captures - 1, ratio, ratio_mode)

        # Get trigger values (if applicable)
        if trigger_buffer is not None:
            self.get_values(samples, 0, 0, ratio, RATIO_MODE.TRIGGER)

        # Convert data to mV
        channels_buffer = self.channels_buffer_adc_to_mv(channels_buffer)

        # Get time axis
        time_axis = self.get_time_axis(timebase, actual_samples)

        # Return data
        return channels_buffer, time_axis
    
__all__ = ['ps6000a']
