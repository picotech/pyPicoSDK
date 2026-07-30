"""Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms."""

import ctypes
try:
    from typing import override  # type: ignore
except ImportError:
    from typing_extensions import override  # type: ignore
from warnings import warn
from .._exceptions import NoArgumentsNeededWarning, PowerSourceWarning

import queue

import numpy as np
import numpy.ctypeslib as npc

from .. import constants as cst
from ..common import (
    _get_literal,
    _siggen_get_buffer_args,
    ParameterNotSupported,
    PicoSDKException
)
from ..base import PicoScopeBase
from .._classes._channel_class import ChannelClass
from ..shared._ps5000a_ps6000a import Sharedps5000aPs6000a
from ..shared._ps5000a_ps4000a import Sharedps5000aPs4000a


class ps5000a(PicoScopeBase, Sharedps5000aPs6000a, Sharedps5000aPs4000a):  # pylint: disable=C0103
    """PicoScope 5000 (A) API specific functions"""

    @override
    def __init__(self, *args, **kwargs):
        self.ac_adaptor = True
        self._streaming_queue = queue.Queue()
        super().__init__("ps5000a", *args, **kwargs)

    @override
    def open_unit(
        self,
        serial_number: str = None,
        resolution: str | cst.resolution_literal | cst.RESOLUTION = cst.RESOLUTION.BIT_8
    ) -> None:
        resolution = _get_literal(resolution, cst.resolution_map)
        if serial_number is not None:
            serial_number = serial_number.encode()
        status = self._call_attr_function(
            'OpenUnit',
            ctypes.byref(self.handle),
            serial_number,
            resolution
        )
        # ps5000a OpenUnit returns 282 (USB-only) or 286 (USB-3 device on USB-2
        # port) as prompts requiring acknowledgement via ChangePowerSource before
        # the device is usable. Both restrict the unit to 2-channel operation.
        if status == cst.POWER_SOURCE.SUPPLY_NOT_CONNECTED:
            warn(
                'ps5000a opened without DC power supply — running on USB power, '
                'restricted to 2-channel operation. Connect the supplied AC '
                'adapter to enable all channels.',
                PowerSourceWarning,
                stacklevel=2,
            )
            self.ac_adaptor = False
            self.change_power_source(status)
        elif status == cst.POWER_SOURCE.USB3_0_DEVICE_NON_USB3_0_PORT:
            warn(
                'ps5000a is a USB 3.0 device plugged into a non-USB-3.0 port — '
                'restricted to 2-channel operation. Move to a USB 3.0 port to '
                'enable all channels.',
                PowerSourceWarning,
                stacklevel=2,
            )
            self.ac_adaptor = False
            self.change_power_source(status)

        self.resolution = resolution
        self.min_adc_value, self.max_adc_value = self.get_adc_limits()
        self.set_all_channels_off()

        if self.ac_adaptor:
            usb_version = self.get_unit_info(cst.UNIT_INFO.PICO_USB_VERSION)
            if usb_version != '3.0':
                warn(
                    f'ps5000a is connected to a USB {usb_version} port — '
                    'for maximum data transfer performance, use a USB 3.0 port.',
                    PowerSourceWarning,
                    stacklevel=2,
                )

        return status

    # get_adc_limits, get_current_power_source and change_power_source are
    # provided by Sharedps5000aPs4000a.

    @override
    def set_all_channels_off(self) -> None:
        """
        Turns all channels off, based on unit number of channels.
        If the ps5000a has no AC power supply attached, only turns off channel A and B.
        """
        # Get the number of active channels based on the AC adaptor. (-2) to remove digital ports.
        channels = len(self.get_channel_combinations(int(1e6), self.ac_adaptor)[-1]) - 2
        for channel in range(int(channels)):
            self.set_channel(channel, enabled=False)

    @override
    def set_simple_trigger(self, channel, threshold=0, threshold_unit='mv', enable=True,
                           direction=cst.TRIGGER_DIR.RISING, delay=0, auto_trigger=0):
        channel = _get_literal(channel, cst.channel_map)
        if channel == cst.CHANNEL.TRIGGER_AUX:
            # TRIGGER_AUX is not in channel_db, so convert threshold manually
            # using the EXT port's fixed ±5 V range before base class sees it.
            if threshold_unit in ('mv', 'v'):
                threshold_mv = threshold * 1000 if threshold_unit == 'v' else threshold
                threshold = int((threshold_mv / cst.PS5000A_TRIGGER_AUX_RANGE_MV) * self.max_adc_value)
                threshold_unit = 'adc'
            # Remap SDK virtual value (1001) to PS5000A_EXTERNAL (4) for the C API.
            channel = cst.PS5000A_TRIGGER_AUX_HW_CHANNEL  # type: ignore[assignment]
        status = super().set_simple_trigger(channel, threshold, threshold_unit, enable, direction,
                                            delay, auto_trigger=0)
        self.set_auto_trigger_microseconds(auto_trigger)
        return status

    @override
    def set_advanced_trigger(self, channel, state, direction, threshold_mode,
                             threshold_upper_mv, threshold_lower_mv,
                             hysteresis_upper_mv=0.0, hysteresis_lower_mv=0.0,
                             aux_output_enable=0, auto_trigger_ms=0,
                             action=cst.ACTION.CLEAR_ALL | cst.ACTION.ADD):
        channel = _get_literal(channel, cst.channel_map)
        if channel == cst.CHANNEL.TRIGGER_AUX:
            def _mv_to_adc(mv):
                return int((mv / cst.PS5000A_TRIGGER_AUX_RANGE_MV) * self.max_adc_value)
            threshold_upper_mv = _mv_to_adc(threshold_upper_mv)
            threshold_lower_mv = _mv_to_adc(threshold_lower_mv)
            hysteresis_upper_mv = _mv_to_adc(hysteresis_upper_mv)
            hysteresis_lower_mv = _mv_to_adc(hysteresis_lower_mv)
            channel = cst.PS5000A_TRIGGER_AUX_HW_CHANNEL  # type: ignore[assignment]
        super().set_advanced_trigger(channel, state, direction, threshold_mode,
                                     threshold_upper_mv, threshold_lower_mv,
                                     hysteresis_upper_mv, hysteresis_lower_mv,
                                     aux_output_enable, auto_trigger_ms, action)

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
        ratio_mode: cst.RATIO_MODE = cst.RATIO_MODE.NONE,
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
            buffer (np.ndarray | None, optional):
                Send a preallocated data buffer to be populated. Min buffer first.
                If left as none, this function creates and returns its own buffer.

        Returns:
            np.ndarray: Created buffer as a numpy array.

        Note:
            samples=0 clears the registration, but only for this
            channel/segment/ratio_mode — unlike ACTION.CLEAR_ALL on other
            drivers, which clears every registered buffer.
        """
        # Warnings if moving to ps5000a from other drivers. A samples==0 call
        # is a clear, so the ADD warning does not apply there.
        if datatype not in [cst.DATA_TYPE.INT16_T, None]:
            warn(f'{self._unit_prefix_n} only supports datatype int16. Defaulting to int16.',
                 ParameterNotSupported)
        if samples != 0 and action not in [cst.ACTION.ADD, None]:
            warn(f'{self._unit_prefix_n} only supports the "ADD" action. Defaulting to ADD.',
                 ParameterNotSupported)

        # Convert RAW (unsupported in ps5000a) to NONE.
        if ratio_mode == cst.RATIO_MODE.RAW:
            ratio_mode = cst.RATIO_MODE.NONE

        # Set the last buffer size
        self.base_dataclass.last_buffer_size = samples

        # If no samples, clear the registration with a NULL pointer
        if samples == 0:
            buffer = None
            buf_ptr = None
        else:
            # Create new buffer if none given
            if buffer is None:
                buffer = np.zeros(samples, dtype=np.int16)
            # The driver always writes int16 to this pointer; any other dtype
            # makes it write past the end of the numpy allocation.
            elif buffer.dtype != np.int16:
                raise PicoSDKException(
                    f"ps5000a data buffers must be int16, got {buffer.dtype}. "
                    "For native 8-bit transfers use set_unscaled_data_buffer()."
                )
            elif buffer.size < samples:
                raise PicoSDKException(
                    f"Buffer holds {buffer.size} samples but {samples} were "
                    "declared to the driver"
                )
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

        Note:
            samples=0 clears the registration, but only for this
            channel/segment/ratio_mode — unlike ACTION.CLEAR_ALL on other
            drivers, which clears every registered buffer.
        """
        # Warnings if moving to ps5000a from other drivers. A samples==0 call
        # is a clear, so the ADD warning does not apply there.
        if datatype not in [cst.DATA_TYPE.INT16_T, None]:
            warn(f'{self._unit_prefix_n} only supports datatype int16. Defaulting to int16.',
                 ParameterNotSupported)
        if samples != 0 and action not in [cst.ACTION.ADD, None]:
            warn(f'{self._unit_prefix_n} only supports the "ADD" action. Defaulting to ADD.',
                 ParameterNotSupported)

        # Set the last buffer size
        self.base_dataclass.last_buffer_size = samples

        # Convert RAW (unsupported in ps5000a) to NONE.
        if ratio_mode == cst.RATIO_MODE.RAW:
            ratio_mode = cst.RATIO_MODE.NONE

        # If no samples, clear the registration with NULL pointers
        if samples == 0:
            buffer_min = None
            buffer_max = None
            buf_min_ptr = None
            buf_max_ptr = None
        else:
            # If buffers are given, split into seperate buffers
            if buffers is not None:
                buffer_min = buffers[0]
                buffer_max = buffers[1]
                for buf in (buffer_min, buffer_max):
                    # The driver always writes int16 to these pointers; any
                    # other dtype makes it write past the end of the allocation.
                    if buf.dtype != np.int16:
                        raise PicoSDKException(
                            f"ps5000a data buffers must be int16, got {buf.dtype}. "
                            "For native 8-bit transfers use set_unscaled_data_buffers()."
                        )
                    if buf.size < samples:
                        raise PicoSDKException(
                            f"Buffer holds {buf.size} samples but {samples} "
                            "were declared to the driver"
                        )
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

    def set_unscaled_data_buffer(
        self,
        channel: cst.CHANNEL,
        samples: int,
        segment: int = 0,
        ratio_mode: cst.RATIO_MODE = cst.RATIO_MODE.NONE,
        buffer: np.ndarray | None = None,
    ) -> np.ndarray | None:
        """
        Allocate and assign a NumPy-backed int8 data buffer using the driver's
        native unscaled 8-bit transfer path (``ps5000aSetUnscaledDataBuffers``).

        At 8-bit resolution this halves the USB bandwidth and host memory per
        sample compared with the standard int16 path. The driver delivers raw
        8-bit ADC codes with no scaling applied.

        Args:
            channel (CHANNEL): Channel to associate the buffer with.
            samples (int): Number of samples to allocate. 0 clears the
                registration for this channel/segment/mode.
            segment (int, optional): Memory segment to use. Defaults to 0.
            ratio_mode (RATIO_MODE, optional): Downsampling mode. Defaults to
                NONE. For AGGREGATE use :meth:`set_unscaled_data_buffers`.
            buffer (np.ndarray | None, optional): Preallocated int8 buffer to
                be populated. If None, this function creates its own.

        Returns:
            np.ndarray | None: The registered int8 buffer, or None when clearing.
        """
        # Convert RAW (unsupported in ps5000a) to NONE.
        if ratio_mode == cst.RATIO_MODE.RAW:
            ratio_mode = cst.RATIO_MODE.NONE

        # Set the last buffer size
        self.base_dataclass.last_buffer_size = samples

        # If no samples, clear the registration with a NULL pointer
        if samples == 0:
            buffer = None
            buf_ptr = None
        else:
            if buffer is None:
                buffer = np.zeros(samples, dtype=np.int8)
            elif buffer.dtype != np.int8:
                raise PicoSDKException(
                    f"Unscaled data buffers must be int8, got {buffer.dtype}"
                )
            elif buffer.size < samples:
                raise PicoSDKException(
                    f"Buffer holds {buffer.size} samples but {samples} were "
                    "declared to the driver"
                )
            buf_ptr = npc.as_ctypes(buffer)

        self._call_attr_function(
            "SetUnscaledDataBuffers",
            self.handle,
            channel,
            buf_ptr,
            None,
            samples,
            segment,
            ratio_mode,
        )

        return buffer

    def set_unscaled_data_buffers(
        self,
        channel: cst.CHANNEL,
        samples: int,
        segment: int = 0,
        ratio_mode: cst.RATIO_MODE = cst.RATIO_MODE.AGGREGATE,
        buffers: list[np.ndarray, np.ndarray] | np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Allocate and assign max and min NumPy-backed int8 data buffers using
        the driver's native unscaled 8-bit transfer path
        (``ps5000aSetUnscaledDataBuffers``).

        Args:
            channel (CHANNEL): Channel to associate the buffers with.
            samples (int): Number of samples to allocate. 0 clears the
                registration for this channel/segment/mode.
            segment (int, optional): Memory segment to use. Defaults to 0.
            ratio_mode (RATIO_MODE, optional): Downsampling mode. Defaults to
                AGGREGATE.
            buffers (list[np.ndarray, np.ndarray] | np.ndarray | None, optional):
                Preallocated int8 buffers to be populated. Min buffer first,
                followed by max buffer. If None, this function creates its own.

        Returns:
            tuple[np.ndarray, np.ndarray]: Tuple of (buffer_min, buffer_max)
            int8 numpy arrays, or (None, None) when clearing.
        """
        # Convert RAW (unsupported in ps5000a) to NONE.
        if ratio_mode == cst.RATIO_MODE.RAW:
            ratio_mode = cst.RATIO_MODE.NONE

        # Set the last buffer size
        self.base_dataclass.last_buffer_size = samples

        # If no samples, clear the registration with NULL pointers
        if samples == 0:
            buffer_min = None
            buffer_max = None
            buf_min_ptr = None
            buf_max_ptr = None
        else:
            if buffers is not None:
                buffer_min = buffers[0]
                buffer_max = buffers[1]
                for buf in (buffer_min, buffer_max):
                    if buf.dtype != np.int8:
                        raise PicoSDKException(
                            f"Unscaled data buffers must be int8, got {buf.dtype}"
                        )
                    if buf.size < samples:
                        raise PicoSDKException(
                            f"Buffer holds {buf.size} samples but {samples} "
                            "were declared to the driver"
                        )
            else:
                buffer_max = np.zeros(samples, dtype=np.int8)
                buffer_min = np.zeros(samples, dtype=np.int8)

            buf_max_ptr = npc.as_ctypes(buffer_max)
            buf_min_ptr = npc.as_ctypes(buffer_min)

        self._call_attr_function(
            "SetUnscaledDataBuffers",
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

        Other Args:
            operation (int): Extra operations for the signal generator.
                Defaults to 0.
            shots (int): Sweep the frequency as specified by sweeps.
                Defaults to 0.
            sweeps (int): Produce number of cycles specified by shots.
                Defaults to 0.
            trigger_type (int): Type of trigger (edge or level) that will be applied to
                signal generator. Defaults to 0.
            trigger_source (int): The source that will trigger the signal generator.
                Defaults to 0.
            ext_in_threshold (int): Used to set trigger level for external trigger.
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

    def set_siggen_awg(
        self,
        frequency: float,
        pk2pk: float,
        buffer: np.ndarray | list,
        offset: float = 0.0,
        sweep: bool = False,
        stop_freq: float = None,
        inc_freq: float = 0,
        dwell_time: float = 0,
        sweep_type: cst.SWEEP_TYPE = cst.SWEEP_TYPE.UP,
        **kwargs,
    ) -> None:
        if sweep is False:
            stop_freq = frequency

        if isinstance(buffer, list):
            buffer = np.array(buffer)
        buffer_ptr, buffer_len = _siggen_get_buffer_args(buffer)

        self._call_attr_function(
            'SetSigGenArbitrary',
            self.handle,
            int(offset * 1e6),
            int(pk2pk * 1e6),
            frequency,
            stop_freq,
            inc_freq,
            dwell_time,
            buffer_ptr,
            buffer_len,
            sweep_type,
            kwargs.get('operation', 0),
            kwargs.get('shots', 0),
            kwargs.get('sweeps', 0),
            kwargs.get('trigger_type', 0),
            kwargs.get('trigger_source', 0),
            kwargs.get('ext_in_threshold', 0),
        )

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

    def get_channel_combinations(
        self,
        timebase: int, ac_adaptor: bool | None = None,
        return_type: cst.ReturnTypeMap = 'string',
    ) -> list[list[str] | list[int]]:
        """
        Get the avaliable channel combinations at a given timebase for the ps5000a.

        Args:
            timebase: Timebase to use for the channel combinations. Can be calculated using
                either `sample_rate_to_timebase()` or `interval_to_timebase()`.
            ac_adaptor: Whether to use the AC adaptor. Defaults to None, which will use the
                ac_adaptor of the current device.
            return_type: Type of return value. Defaults to 'string'.
                Can be 'string' or 'enum'.
                If 'string', returns the channel combinations as a list of strings.
                If 'enum', returns the channel combinations as a list of enums.

        Returns:
            list[list[str] | list[int]]: List of channel combinations.
                Each list contains the channel combinations for a given timebase.
                If return_type is 'string', the list contains the channel combinations as a list of
                strings. If return_type is 'enum', the list contains the channel combinations as a
                list of channel enum values.
        """
        if ac_adaptor is None:
            ac_adaptor = self.ac_adaptor

        n_combos = ctypes.c_uint32()
        self._call_attr_function(
            "ChannelCombinationsStateless",
            self.handle,
            None,
            ctypes.byref(n_combos),
            self.resolution,
            ctypes.c_uint32(timebase),
            ac_adaptor,
        )

        combo_array = (ctypes.c_uint32 * n_combos.value)()
        self._call_attr_function(
            "ChannelCombinationsStateless",
            self.handle,
            ctypes.byref(combo_array),
            ctypes.byref(n_combos),
            self.resolution,
            ctypes.c_uint32(timebase),
            ac_adaptor,
        )
        combo_array = list(combo_array)
        channel_combinations = []
        for n, i in enumerate(combo_array):
            channel_combinations.append([])
            for j in cst.PICO_CHANNEL_FLAGS:
                if i & j == j and return_type == 'string':
                    channel_combinations[n].append(cst.PicoChannelFlagsMap[j])
                elif i & j == j and return_type == 'enum':
                    channel_combinations[n].append(cst.PicoChannelFlagsEnumMap[j])
        return channel_combinations

    def get_avaliable_channel_ranges(
        self,
        channel: str | cst.channel_literal | cst.CHANNEL,
    ) -> dict:
        """
        Get the information for a specified channel.

        Args:
            channel (str | CHANNEL): Channel to get information for.

        Returns:
            dict: Dictionary of channel information.
        """
        channel = _get_literal(channel, cst.channel_map)

        channel_ranges_n = ctypes.c_uint32(64)
        channel_ranges = (ctypes.c_uint32 * channel_ranges_n.value)()
        self._call_attr_function(
            "GetChannelInformation",
            self.handle,
            0,
            0,
            ctypes.byref(channel_ranges),
            ctypes.byref(channel_ranges_n),
            channel,
        )
        avaliable_channel_ranges = []
        for i in channel_ranges:
            string = cst.RangeMapRev[i]
            if string not in avaliable_channel_ranges:
                avaliable_channel_ranges.append(string)
        return avaliable_channel_ranges

    # get_max_downsample_ratio and get_max_segments are provided by
    # Sharedps5000aPs4000a.

    def get_maximum_available_memory(self) -> int:
        """Return the maximum sample depth of the device.

        The ps5000a API has no GetMaximumAvailableMemory call; this queries
        MemorySegments with a single segment, which reports the full capture
        memory at the current resolution. Unlike the ps6000a/psospa query,
        this is a settings change: it (re)configures the device to 1 memory
        segment and discards any previously captured data. Do not call it
        while a capture or stream is in progress.

        Returns:
            int: Maximum number of samples supported.

        Raises:
            PicoSDKException: If the driver did not report a sample count
                (e.g. the device was busy capturing).
        """
        max_samples = self.memory_segments(1)
        # A busy device returns PICO_BUSY (swallowed as a warning status by
        # the error handler), leaving the out-param at 0 - surface it.
        if max_samples == 0:
            raise PicoSDKException(
                "Could not query maximum available memory - the device may "
                "be busy capturing. Stop the capture first.")
        return max_samples

    @override
    def get_streaming_latest_values(self, *args, **kwargs) -> dict:
        if len(args) > 0 or len(kwargs) > 0:
            warn("ps5000a get_streaming_latest_values() takes no arguments", 
                NoArgumentsNeededWarning)
        status = self._call_attr_function(
            "GetStreamingLatestValues",
            self.handle,
            self._streaming_callback_pointer,
            None,
        )
        try:
            info = self._streaming_queue.get_nowait()
            info['status'] = status
            return info
        except queue.Empty:
            # No callback fired this poll. Return the real driver status
            # (e.g. PICO_BUSY) rather than fabricating success.
            return {
            'status': status,
            'no of samples': 0,
            'Buffer index': 0,
            'start index': 0,
            'overflowed?': 0,
            'triggered at': 0,
            'triggered?': 0,
            'auto stopped?': 0,
        }

    @override
    def get_streaming_latest_values_multi(self, requests) -> dict:
        raise PicoSDKException(
            "ps5000a does not take per-channel poll requests - its streaming "
            "callback covers every registered buffer at once. Use "
            "get_streaming_latest_values() instead."
        )

    @override
    def run_streaming(
        self,
        sample_interval: float,
        time_units: cst.TIME_UNIT,
        max_pre_trigger_samples: int,
        max_post_trigger_samples: int,
        auto_stop: int = 0,
        ratio: int = 1,
        ratio_mode: cst.RATIO_MODE = cst.RATIO_MODE.NONE,
        overview_buffer_size: int = None,
    ) -> float:
        # Convert the ratio mode to None for ps5000a
        if ratio_mode == cst.RATIO_MODE.RAW:
            ratio_mode = cst.RATIO_MODE.NONE
        if ratio == 0:
            ratio = 1
        # Setup the streaming callback
        self._setup_streaming_callback()
        # Discard poll results left over from a previous run
        while True:
            try:
                self._streaming_queue.get_nowait()
            except queue.Empty:
                break
        # Run the streaming
        return super().run_streaming(
            sample_interval,
            time_units,
            max_pre_trigger_samples,
            max_post_trigger_samples,
            auto_stop,
            ratio,
            ratio_mode,
            overview_buffer_size,
        )

    def _setup_streaming_callback(self):
        # Argument types mirror the ps5000aStreamingReady typedef
        # (ps5000aApi.h): triggerAt is uint32_t.
        self._streaming_callback_pointer = ctypes.CFUNCTYPE(
            None, ctypes.c_int16, ctypes.c_int32, ctypes.c_uint32, ctypes.c_int16, ctypes.c_uint32,
            ctypes.c_int16, ctypes.c_int16, ctypes.c_void_p)(self._streaming_callback)

    def _streaming_callback(
        self, 
        handle: ctypes.c_int16, 
        no_samples: ctypes.c_int32, 
        start_index: ctypes.c_uint32, 
        overflow: ctypes.c_int16, 
        trigger_at: ctypes.c_int32, 
        triggered: ctypes.c_int16, 
        auto_stop: ctypes.c_int16, 
        param: ctypes.c_void_p
    ) -> None:
        # 'Buffer index' is always 0: the ps5000a streams into a single
        # persistent overview buffer, so there is no driver-side buffer
        # rotation. A constant int keeps the cross-driver poll-dict contract
        # (e.g. `info['Buffer index'] % 2`) working without spurious swaps.
        self._streaming_queue.put({
            'status': None,
            'no of samples': no_samples,
            'Buffer index': 0,
            'start index': start_index,
            'overflowed?': overflow,
            'triggered at': trigger_at,
            'triggered?': triggered,
            'auto stopped?': auto_stop,
        })

    # is_led_flashing is provided by Sharedps5000aPs4000a.

    def set_digital_port(
        self,
        port: cst.DIGITAL_PORT,
        enabled: bool = True,
        logic_threshold_level_v: float = 0.0,
        *,
        logic_level: int | None = None,
    ) -> int:
        """
        This function enables or disables a digital port and sets the logic threshold.

        The threshold is given in volts. On the ps5000a the digital port has a
        fixed +/-5 V range, so the volts value is converted to ADC counts
        internally.

        Args:
            port (DIGITAL_PORT): Identifier for the digital port.
            enabled (bool, optional): Enable or disable the digital port. Defaults to True.
            logic_threshold_level_v (float, optional): Logic threshold in volts,
                between -5.0 V and +5.0 V. Defaults to 0.0.
            logic_level (int, optional): Deprecated. Logic threshold in raw ADC
                counts (-32767 to 32767). If given, it overrides
                ``logic_threshold_level_v``.

        Returns:
            int: Status from device.
        """
        if logic_level is None:
            logic_level = self._digital_volts_to_adc(
                logic_threshold_level_v, cst.PS5000A_DIGITAL_FULL_SCALE_V
            )
        else:
            warn(
                "logic_level (ADC counts) is deprecated; pass "
                "logic_threshold_level_v in volts instead.",
                DeprecationWarning,
                stacklevel=2,
            )
        if enabled:
            self.digital_port_db.add(port)
        else:
            self.digital_port_db.discard(port)
        return self._call_attr_function(
            "SetDigitalPort",
            self.handle,
            port,
            enabled,
            logic_level,
        )

    def set_siggen_properties_arbitrary(
        self, 
        start_delta_phase: int,
        stop_delta_phase: int,
        increment: int,
        dwell: int,
        sweep_type: cst.SWEEP_TYPE = cst.SWEEP_TYPE.UP,
        shots: int = 0,
        sweeps: int = 0,
        trigger_type: cst.PICO_SIGGEN_TRIG_TYPE = cst.PICO_SIGGEN_TRIG_TYPE.PICO_SIGGEN_RISING,
        trigger_source: cst.PICO_SIGGEN_TRIG_SOURCE = cst.PICO_SIGGEN_TRIG_SOURCE.PICO_SIGGEN_NONE,
        ext_in_threshold: int = 0,
    ) -> None:
        """
        Set the properties for the arbitrary waveform generator. All values can be reprogrammed
        while the oscilloscope is waiting for a trigger.
        
        Args:
            start_delta_phase: The start delta phase.
            stop_delta_phase: The stop delta phase.
            increment: The increment.
            dwell: The dwell.
            sweep_type: The sweep type. Defaults to SWEEP_TYPE.UP.
            shots: The shots. Defaults to 0.
            sweeps: The sweeps. Defaults to 0.
            trigger_type: The trigger type. Defaults to PICO_SIGGEN_TRIG_TYPE.NONE.
            trigger_source: The trigger source. Defaults to PICO_SIGGEN_TRIG_SOURCE.NONE.
            ext_in_threshold: The external input threshold. Defaults to 0.
        """
        self._call_attr_function(
            "SetSigGenPropertiesArbitrary",
            self.handle,
            start_delta_phase,
            stop_delta_phase,
            increment,
            dwell,
            sweep_type,
            shots,
            sweeps,
            trigger_type,
            trigger_source,
            ext_in_threshold,
        )
    
    def set_siggen_properties_built_in(
        self,
        frequency: float,
        stop_frequency: float,
        increment: float,
        dwell_time: float,
        sweep_type: cst.SWEEP_TYPE = cst.SWEEP_TYPE.UP,
        shots: int = 0,
        sweeps: int = 0,
        trigger_type: cst.PICO_SIGGEN_TRIG_TYPE = cst.PICO_SIGGEN_TRIG_TYPE.PICO_SIGGEN_RISING,
        trigger_source: cst.PICO_SIGGEN_TRIG_SOURCE = cst.PICO_SIGGEN_TRIG_SOURCE.PICO_SIGGEN_NONE,
        ext_in_threshold: int = 0,
    ) -> None:
        """
        Set the properties for the built-in waveform generator. All values can be reprogrammed
        while the oscilloscope is waiting for a trigger.
        
        Args:
            frequency: The startfrequency.
            stop_frequency: The stop frequency.
            increment: The increment.
            dwell_time: The dwell time.
            sweep_type: The sweep type. Defaults to SWEEP_TYPE.UP.
            shots: The shots. Defaults to 0.
            sweeps: The sweeps. Defaults to 0.
            trigger_type: The trigger type. Defaults to PICO_SIGGEN_TRIG_TYPE.NONE.
            trigger_source: The trigger source. Defaults to PICO_SIGGEN_TRIG_SOURCE.NONE.
            ext_in_threshold: The external input threshold. Defaults to 0.
        """
        self._call_attr_function(
            "SetSigGenPropertiesBuiltIn",
            self.handle,
            frequency,
            stop_frequency,
            increment,
            dwell_time,
            sweep_type,
            shots,
            sweeps,
            trigger_type,
            trigger_source,
            ext_in_threshold,
        )

    def siggen_frequency_to_phase(
        self,
        frequency: float,
        buffer_length: int,
        index_mode: cst.AWG_INDEX_MODE = cst.AWG_INDEX_MODE.SINGLE,
    ) -> int:
        """
        Convert a frequency to a phase count for use with the AWG. This value depends on the
        length of the AWG buffer.

        Args:
            frequency: The frequency to convert to a phase count.
            buffer_length: The length of the AWG buffer.
            index_mode: The index mode to use. Defaults to AWG_INDEX_MODE.SINGLE.

        Returns:
            int: The phase count.
        """
        phase = ctypes.c_uint32()
        self._call_attr_function(
            "SigGenFrequencyToPhase",
            self.handle,
            frequency,
            index_mode,
            buffer_length,
            ctypes.byref(phase)
        )
        return phase.value

    def siggen_arbitrary_min_max_values(
        self,
    ) -> dict[str, int]:
        """
        Returns the minimum and maximum values for the arbitrary waveform generator.

        Returns:
            dict[str, int]: Dictionary with keys "min_value", "max_value", "min_size", and "max_size".
            min_value: The minimum value.
            max_value: The maximum value.
            min_size: The minimum size.
            max_size: The maximum size.
        """
        min_value = ctypes.c_int16()
        max_value = ctypes.c_int16()
        min_size = ctypes.c_uint32()
        max_size = ctypes.c_uint32()
        self._call_attr_function(
            "SigGenArbitraryMinMaxValues",
            self.handle,
            ctypes.byref(min_value),
            ctypes.byref(max_value),
            ctypes.byref(min_size),
            ctypes.byref(max_size),
        )
        return {
            "min_value": min_value.value,
            "max_value": max_value.value,
            "min_size": min_size.value,
            "max_size": max_size.value,
        }

    def siggen_software_control(
        self,
        state: bool
    ) -> int:
        """
        This function causes a trigger event, or starts and stops gating, for the signal generator. 

        Args:
            state (bool): True sets the gate signal high, False sets it low.

        Returns:
            int: The status from the device. 0 for success, >0 for error.
        """
        return self._call_attr_function(
            "SigGenSoftwareControl",
            self.handle,
            state,
        )

    def set_ets(
        self,
        mode: cst.ETS_MODE,
        cycles: int,
        interleave: int,
    ) -> int:
        """
        This function is used to enable or disable ETS (equivalent-time sampling) and to set 
        the ETS parameters

        Args:
            mode (ETS_MODE): The ETS mode to set.
            cycles (int): The number of cycles to sample.
            interleave (int): The interleave mode to use.

        Returns:
            int: The sample time in picoseconds.
        """
        sample_time_ps = ctypes.c_int32()
        self._call_attr_function(
            "SetEts",
            self.handle,
            mode,
            cycles,
            interleave,
            ctypes.byref(sample_time_ps),
        )
        return sample_time_ps.value

    def set_ets_time_buffer(
        self,
        samples: int,
        buffer: None | np.ndarray = None
    ) -> np.ndarray:
        """
        This function tells the driver where to find your application's ETS time buffers. 
        These buffers contain the 64- bit timing information for each ETS sample after you run a
        block-mode ETS capture.

        Args:
            samples: The number of samples to set the ETS time buffer for.
            buffer: A single or double numpy array. If None, a buffer will be created.
                A single numpy array contains a 64-bit integer for each sample.
                A double numpy array contains a upper and lower unsinged32-bit integer for each
                sample.

        Returns:
            np.ndarray: The buffer set. If created, the buffer will be returned.
        """
        if buffer is None:
            buffer = np.zeros(samples, dtype=np.int64)
        if buffer.ndim == 1:
            buffer_ptr = npc.as_ctypes(buffer)
            buffer_len = buffer.size
            status = self._call_attr_function(
                "SetEtsTimeBuffer",
                self.handle,
                buffer_ptr,
                buffer_len,
            )
        elif buffer.ndim == 2:
            buffer_lower_ptr = npc.as_ctypes(buffer[0])
            buffer_upper_ptr = npc.as_ctypes(buffer[1])
            buffer_len = buffer.shape[1]
            print(buffer_lower_ptr, buffer_upper_ptr, buffer_len)
            status = self._call_attr_function(
                "SetEtsTimeBuffers",
                self.handle,
                buffer_lower_ptr,
                buffer_upper_ptr,
                buffer_len,
            )
        return buffer

    def set_ets_time_buffers(
        self,
        samples: int, 
        buffers: None | np.ndarray | list[np.ndarray] = None,
    ) -> np.ndarray:
        """
        This function tells the driver where to find your application's ETS time buffers. These 
        buffers contain the timing information for each ETS sample after you run a block-mode ETS
        capture. There are two buffers containing the upper and lower 32-bit parts of the timing
        information, to allow programming languages that do not support 64-bit data to retrieve the
        timings. If your programming language supports 64-bit data, you can use
        set_ets_time_buffer(samples, buffer) instead.

        Args:
            samples (int): The number of samples to set the ETS time buffers for.
            buffers (None | np.ndarray | list[np.ndarray], optional): A double numpy array or list 
                of two single numpy arrays. If None, a buffer will be created. 

        Returns:
            np.ndarray: The buffers set. If created, the buffers will be returned.
        """
        if buffers is None:
            buffers = np.zeros((2, samples), dtype=np.uint32)

        if isinstance(buffers, list):
            buffers = np.stack(buffers)
        return self.set_ets_time_buffer(samples, buffers)

    def set_trigger_digital_port_properties(
        self,
        channels: cst.DIGITAL_CHANNEL | list[cst.DIGITAL_CHANNEL],
        directions: cst.DIGITAL_DIRECTION | list[cst.DIGITAL_DIRECTION]
    ) -> None:
        """
        Set the trigger digital port properties.
        
        Args:
            channels: A single channel or a list of channels to set the trigger properties for.
            directions: A single direction or a list of directions to set the trigger properties
                for. Must be the same length as the channels list.
        
        Returns:
            int: The status from the device. 0 for success, >0 for error.
        """
        if isinstance(channels, int):
            channels = [channels]
        if isinstance(directions, int):
            directions = [directions]

        n_directions = len(channels)

        digital_port_struct = (cst.DIGITAL_CHANNEL_DIRECTIONS * n_directions)()
        for i in range(n_directions):
            digital_port_struct[i].channel = channels[i]
            digital_port_struct[i].direction = directions[i]

        return self._call_attr_function(
            "SetTriggerDigitalPortProperties",
            self.handle,
            digital_port_struct,
            n_directions,
        )

    def is_trigger_or_pulse_width_qualifier_enabled(self) -> dict:
        """
        This function returns the status of the trigger and pulse width qualifier.

        Returns:
            dict: A dictionary with the status of the trigger and pulse width qualifier.
            trigger_enabled: The status of the trigger.
            pulse_width_qualifier_enabled: The status of the pulse width qualifier.
        """
        tirgger_enabled = ctypes.c_int16()
        pulse_width_qualifier_enabled = ctypes.c_int16()
        self._call_attr_function(
            "IsTriggerOrPulseWidthQualifierEnabled",
            self.handle,
            ctypes.byref(tirgger_enabled),
            ctypes.byref(pulse_width_qualifier_enabled),
        )
        return {
            "trigger_enabled": tirgger_enabled.value,
            "pulse_width_qualifier_enabled": pulse_width_qualifier_enabled.value,
        }