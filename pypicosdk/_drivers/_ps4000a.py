"""Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms."""

import ctypes
try:
    from typing import override  # type: ignore
except ImportError:
    from typing_extensions import override  # type: ignore
from warnings import warn

import queue

from .._exceptions import NoArgumentsNeededWarning, PowerSourceWarning

import numpy as np
import numpy.ctypeslib as npc

from .. import constants as cst
from ..common import (
    _get_literal,
    ParameterNotSupported,
    PicoSDKException
)
from ..base import PicoScopeBase
from ..shared._ps5000a_ps6000a import Sharedps5000aPs6000a
from ..shared._ps5000a_ps4000a import Sharedps5000aPs4000a
from ..shared.ps6000a_ps4000a import shared_4000a_6000a


class ps4000a(PicoScopeBase, Sharedps5000aPs6000a, Sharedps5000aPs4000a,
              shared_4000a_6000a):  # pylint: disable=C0103
    """PicoScope 4000 (A) API specific functions"""

    @override
    def __init__(self, *args, **kwargs):
        self.ac_adaptor = True
        self._streaming_queue = queue.Queue()
        self._streaming_callback_pointer = None
        super().__init__("ps4000a", *args, **kwargs)

    @override
    def open_unit(
        self,
        serial_number: str = None,
        resolution: str | cst.resolution_literal | cst.RESOLUTION = cst.RESOLUTION.BIT_12
    ) -> None:
        """
        Opens a PicoScope 4000A-series unit.

        Args:
            serial_number (str, optional): Serial number of a specific unit, e.g. "JR628/0017".
            resolution (RESOLUTION, optional): Resolution of the device. Defaults to 12-bit,
                the native resolution of current 4000A hardware. Only the PicoScope 4444
                supports other resolutions.
        """
        resolution = _get_literal(resolution, cst.resolution_map)
        if serial_number is not None:
            serial_number = serial_number.encode()
        # ps4000aOpenUnit takes no resolution argument;
        # OpenUnitWithResolution is the resolution-aware open call.
        status = self._call_attr_function(
            'OpenUnitWithResolution',
            ctypes.byref(self.handle),
            serial_number,
            resolution
        )
        # A unit without its DC power supply (e.g. a PicoScope 4444 on USB
        # power alone) returns 282 as a prompt requiring acknowledgement via
        # ChangePowerSource before the device is usable - the same handshake
        # as the ps5000a.
        if status == cst.POWER_SOURCE.SUPPLY_NOT_CONNECTED:
            warn(
                'ps4000a opened without DC power supply - running on USB '
                'power with a restricted feature set. Connect the supplied '
                'power adapter for full functionality.',
                PowerSourceWarning,
                stacklevel=2,
            )
            self.ac_adaptor = False
            self.change_power_source(status)
        elif status == cst.POWER_SOURCE.USB3_0_DEVICE_NON_USB3_0_PORT:
            warn(
                'ps4000a is a USB 3.0 device plugged into a non-USB-3.0 port '
                '- running with a restricted feature set. Move to a USB 3.0 '
                'port for full functionality.',
                PowerSourceWarning,
                stacklevel=2,
            )
            self.ac_adaptor = False
            self.change_power_source(status)

        self.resolution = resolution
        self.min_adc_value, self.max_adc_value = self.get_adc_limits()
        self.set_all_channels_off()
        return status

    @override
    def set_device_resolution(self, resolution: cst.RESOLUTION) -> None:
        """Configure the ADC resolution using ``ps4000aSetDeviceResolution``.

        Only the PicoScope 4444 supports changing resolution at runtime;
        other 4000A models return an error status from the driver.

        Args:
            resolution: Desired resolution as a :class:`RESOLUTION` value.
        """
        self._call_attr_function(
            "SetDeviceResolution",
            self.handle,
            resolution,
        )
        self.resolution = resolution
        # A resolution change moves the ADC full-scale count; refresh the
        # limits that every mV/V conversion depends on.
        self.min_adc_value, self.max_adc_value = self.get_adc_limits()

    @override
    def get_timebase(self, timebase, samples, segment=0):
        # ps4000aGetTimebase reports the interval as int32; base reads it as
        # c_double and gets garbage. GetTimebase2 reports a float directly.
        time_interval_ns = ctypes.c_float()
        max_samples = ctypes.c_int32()
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
        # ps4000aNearestSampleIntervalStateless has a uint16 useEts argument
        # between resolution and the out-pointers; ETS is not wrapped, so 0.
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
            ratio_mode (RATIO_MODE, optional): Downsampling mode. Defaults to NONE.
            buffer (np.ndarray | None, optional):
                Send a preallocated data buffer to be populated.
                If left as none, this function creates and returns its own buffer.

        Returns:
            np.ndarray: Created buffer as a numpy array.

        Note:
            samples=0 clears the registration, but only for this
            channel/segment/ratio_mode - unlike ACTION.CLEAR_ALL on other
            drivers, which clears every registered buffer.
        """
        # Warnings if moving to ps4000a from other drivers. A samples==0 call
        # is a clear, so the ADD warning does not apply there.
        if datatype not in [cst.DATA_TYPE.INT16_T, None]:
            warn(f'{self._unit_prefix_n} only supports datatype int16. Defaulting to int16.',
                 ParameterNotSupported)
        if samples != 0 and action not in [cst.ACTION.ADD, None]:
            warn(f'{self._unit_prefix_n} only supports the "ADD" action. Defaulting to ADD.',
                 ParameterNotSupported)

        # Convert RAW (unsupported in ps4000a) to NONE.
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
                    f"ps4000a data buffers must be int16, got {buffer.dtype}."
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
                Send preallocated data buffers to be populated. Min buffer first, followed
                by max buffer. If left as none, this function creates its own buffers.

        Returns:
            tuple[np.ndarray,np.ndarray]: Tuple of (buffer_min, buffer_max) numpy arrays.

        Note:
            samples=0 clears the registration, but only for this
            channel/segment/ratio_mode - unlike ACTION.CLEAR_ALL on other
            drivers, which clears every registered buffer.
        """
        # Warnings if moving to ps4000a from other drivers. A samples==0 call
        # is a clear, so the ADD warning does not apply there.
        if datatype not in [cst.DATA_TYPE.INT16_T, None]:
            warn(f'{self._unit_prefix_n} only supports datatype int16. Defaulting to int16.',
                 ParameterNotSupported)
        if samples != 0 and action not in [cst.ACTION.ADD, None]:
            warn(f'{self._unit_prefix_n} only supports the "ADD" action. Defaulting to ADD.',
                 ParameterNotSupported)

        # Set the last buffer size
        self.base_dataclass.last_buffer_size = samples

        # Convert RAW (unsupported in ps4000a) to NONE.
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
                            f"ps4000a data buffers must be int16, got {buf.dtype}."
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
        # ps4000a has no ACTION.CLEAR_ALL equivalent; buffer registrations
        # are replaced per channel/segment/mode instead.
        clear_buffer = False
        return super().set_data_buffer_for_enabled_channels(
            samples, segment, datatype, ratio_mode, clear_buffer, captures)

    @override
    def get_values(self, samples, start_index=0, segment=0, ratio=0,
                   ratio_mode=cst.RATIO_MODE.RAW, **kwargs):
        if ratio_mode == cst.RATIO_MODE.RAW:
            ratio_mode = cst.RATIO_MODE.NONE
        return super().get_values(samples, start_index, segment, ratio, ratio_mode, **kwargs)

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
            tuple[int, list[list[str]]]: ``(samples, overflow_list)`` where ``samples`` is the
            number of samples copied and ``overflow_list`` is a list of captures where
            channels have exceeded their voltage range.
        """
        # ps4000aGetValuesBulk has no startIndex parameter and takes uint32
        # sample/segment arguments; base's 64-bit call shifts every argument.
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

    @override
    def get_values_overlapped(  # pylint: disable=W0221
        self,
        start_index: int,
        no_of_samples: int,
        down_sample_ratio: int,
        down_sample_ratio_mode: int,
        segment_index: int = 0,
        overflow: ctypes.c_int16 | None = None,
        wait_for_ready: bool = True,
    ) -> int:
        """Retrieve overlapped data from a single memory segment.

        ``ps4000aGetValuesOverlapped`` is single-segment; use
        :meth:`get_values_overlapped_bulk` for a range of segments.
        Call this method **before** :meth:`run_block_capture` to defer the
        data retrieval request, as on the other drivers.

        Args:
            start_index: Index within the circular buffer to begin reading from.
            no_of_samples: Number of samples to copy.
            down_sample_ratio: Downsampling ratio to apply.
            down_sample_ratio_mode: Downsampling mode from :class:`RATIO_MODE`.
            segment_index: Memory segment to read.
            overflow: Optional ``ctypes.c_int16`` that receives the overflow
                flags. If None, one is created.
            wait_for_ready (bool, optional): Whether to wait for the device to be ready.

        Returns:
            int: Actual number of samples copied.
        """
        if down_sample_ratio_mode == cst.RATIO_MODE.RAW:
            down_sample_ratio_mode = cst.RATIO_MODE.NONE

        if wait_for_ready:
            self.is_ready()

        if overflow is None:
            overflow = ctypes.c_int16()
        c_samples = ctypes.c_uint32(no_of_samples)
        self._call_attr_function(
            "GetValuesOverlapped",
            self.handle,
            ctypes.c_uint32(start_index),
            ctypes.byref(c_samples),
            ctypes.c_uint32(down_sample_ratio),
            down_sample_ratio_mode,
            ctypes.c_uint32(segment_index),
            ctypes.byref(overflow),
        )
        self.over_range = overflow.value
        self.is_over_range()
        return c_samples.value

    def get_values_overlapped_bulk(
        self,
        start_index: int,
        no_of_samples: int,
        down_sample_ratio: int,
        down_sample_ratio_mode: int,
        from_segment_index: int,
        to_segment_index: int,
        wait_for_ready: bool = True,
    ) -> tuple[int, list[list[str]]]:
        """Retrieve overlapped data from a range of memory segments using
        ``ps4000aGetValuesOverlappedBulk``.

        Args:
            start_index: Index within the circular buffer to begin reading from.
            no_of_samples: Number of samples to copy from each segment.
            down_sample_ratio: Downsampling ratio to apply.
            down_sample_ratio_mode: Downsampling mode from :class:`RATIO_MODE`.
            from_segment_index: First segment index to read.
            to_segment_index: Last segment index to read.
            wait_for_ready (bool, optional): Whether to wait for the device to be ready.

        Returns:
            tuple[int, list[list[str]]]: ``(samples, overflow_list)`` where ``samples`` is the
            number of samples copied and ``overflow_list`` is a list of captures where
            channels have exceeded their voltage range.
        """
        if down_sample_ratio_mode == cst.RATIO_MODE.RAW:
            down_sample_ratio_mode = cst.RATIO_MODE.NONE

        if wait_for_ready:
            self.is_ready()

        c_samples = ctypes.c_uint32(no_of_samples)
        overflow = np.zeros(to_segment_index + 1, dtype=np.int16)
        self._call_attr_function(
            "GetValuesOverlappedBulk",
            self.handle,
            ctypes.c_uint32(start_index),
            ctypes.byref(c_samples),
            ctypes.c_uint32(down_sample_ratio),
            down_sample_ratio_mode,
            ctypes.c_uint32(from_segment_index),
            ctypes.c_uint32(to_segment_index),
            npc.as_ctypes(overflow),
        )
        overflow_list = []
        for i in overflow:
            self.over_range = i
            overflow_list.append(self.is_over_range())
        return c_samples.value, overflow_list

    @override
    def get_no_of_captures(self) -> int:
        """Return the number of captures configured for rapid block.

        ``ps4000aGetNoOfCaptures`` writes a uint32, not the uint64 the base
        class assumes.
        """
        n_captures = ctypes.c_uint32()
        self._call_attr_function(
            "GetNoOfCaptures",
            self.handle,
            ctypes.byref(n_captures),
        )
        return n_captures.value

    @override
    def get_no_of_processed_captures(self) -> int:
        """Return the number of captures processed in rapid block mode.

        ``ps4000aGetNoOfProcessedCaptures`` writes a uint32, not the uint64
        the base class assumes.
        """
        n_processed = ctypes.c_uint32()
        self._call_attr_function(
            "GetNoOfProcessedCaptures",
            self.handle,
            ctypes.byref(n_processed),
        )
        return n_processed.value

    @override
    def no_of_streaming_values(self) -> int:
        """Return the number of values currently available while streaming.

        ``ps4000aNoOfStreamingValues`` writes a uint32, not the uint64 the
        base class assumes.
        """
        count = ctypes.c_uint32()
        self._call_attr_function(
            "NoOfStreamingValues",
            self.handle,
            ctypes.byref(count),
        )
        return count.value

    # Trigger layer

    @staticmethod
    def _remap_trigger_channel(channel: int) -> int:
        """Remap pypicosdk's virtual EXTERNAL/TRIGGER_AUX channel values to
        the PS4000A_CHANNEL ordinals (EXTERNAL=8, TRIGGER_AUX=9)."""
        if channel == cst.CHANNEL.EXTERNAL:
            return cst.PS4000A_EXTERNAL_HW_CHANNEL
        if channel == cst.CHANNEL.TRIGGER_AUX:
            return cst.PS4000A_TRIGGER_AUX_HW_CHANNEL
        return channel

    def _auto_trigger_us_to_ms(self, auto_trigger_us: int, limit_ms: int = 32767) -> int:
        """Convert the cross-driver microsecond auto-trigger argument to the
        millisecond value the ps4000a C calls take.

        Args:
            auto_trigger_us: Auto-trigger timeout in microseconds. 0 waits
                indefinitely.
            limit_ms: The C argument's ceiling - 32767 for SetSimpleTrigger's
                int16, larger for SetTriggerChannelProperties' int32.

        Raises:
            PicoSDKException: If the converted value exceeds ``limit_ms``.
        """
        if auto_trigger_us == 0:
            return 0
        auto_trigger_ms = round(auto_trigger_us / 1000)
        if auto_trigger_ms == 0:
            # Rounding a sub-millisecond timeout to 0 would flip the meaning
            # to "wait indefinitely" - clamp up instead.
            auto_trigger_ms = 1
        if auto_trigger_us % 1000:
            warn(
                f'ps4000a auto-trigger has millisecond resolution; '
                f'{auto_trigger_us} us rounded to {auto_trigger_ms} ms.',
                ParameterNotSupported)
        if auto_trigger_ms > limit_ms:
            raise PicoSDKException(
                f"auto_trigger of {auto_trigger_us} us ({auto_trigger_ms} ms) "
                f"exceeds the ps4000a limit of {limit_ms} ms")
        return auto_trigger_ms

    @override
    def set_simple_trigger(self, channel, threshold=0, threshold_unit='mv', enable=True,
                           direction=cst.TRIGGER_DIR.RISING, delay=0, auto_trigger=0):
        """
        Sets up a simple trigger. Arguments as base, except that on the
        ps4000a the C call's auto-trigger argument is in **milliseconds**
        (int16), so the cross-driver microsecond value is converted here.
        """
        channel = _get_literal(channel, cst.channel_map)
        if channel in (cst.CHANNEL.EXTERNAL, cst.CHANNEL.TRIGGER_AUX):
            # EXT/AUX are not in channel_db, so convert the threshold manually
            # using the EXT port's fixed +/-5 V range before base sees it.
            if threshold_unit in ('mv', 'v'):
                threshold_mv = threshold * 1000 if threshold_unit == 'v' else threshold
                threshold = int(
                    (threshold_mv / cst.PS4000A_EXT_RANGE_MV) * cst.PS4000A_EXT_MAX_VALUE)
                threshold_unit = 'adc'
            channel = self._remap_trigger_channel(channel)
        return super().set_simple_trigger(
            channel, threshold, threshold_unit, enable, direction, delay,
            auto_trigger=self._auto_trigger_us_to_ms(auto_trigger))

    @override
    def set_advanced_trigger(self, channel, state, direction, threshold_mode,
                             threshold_upper_mv, threshold_lower_mv,
                             hysteresis_upper_mv=0.0, hysteresis_lower_mv=0.0,
                             aux_output_enable=0, auto_trigger_ms=0,
                             action=cst.ACTION.CLEAR_ALL | cst.ACTION.ADD):
        channel = _get_literal(channel, cst.channel_map)
        if channel in (cst.CHANNEL.EXTERNAL, cst.CHANNEL.TRIGGER_AUX):
            # EXT/AUX are not in channel_db; convert mV using the EXT port's
            # fixed +/-5 V range. The channel value itself is remapped inside
            # each sub-call.
            def _mv_to_adc(mv):
                return int((mv / cst.PS4000A_EXT_RANGE_MV) * cst.PS4000A_EXT_MAX_VALUE)
            threshold_upper_mv = _mv_to_adc(threshold_upper_mv)
            threshold_lower_mv = _mv_to_adc(threshold_lower_mv)
            hysteresis_upper_mv = _mv_to_adc(hysteresis_upper_mv)
            hysteresis_lower_mv = _mv_to_adc(hysteresis_lower_mv)
        super().set_advanced_trigger(channel, state, direction, threshold_mode,
                                     threshold_upper_mv, threshold_lower_mv,
                                     hysteresis_upper_mv, hysteresis_lower_mv,
                                     aux_output_enable, auto_trigger_ms, action)

    @override
    def set_trigger_channel_conditions(
        self,
        conditions: list[tuple[cst.CHANNEL, cst.TRIGGER_STATE]],
        action: int = cst.ACTION.CLEAR_ALL | cst.ACTION.ADD,
    ) -> None:
        # PS4000A_CONDITION matches the generic 8-byte PICO_CONDITION layout;
        # only the virtual EXTERNAL/TRIGGER_AUX values need remapping.
        conditions = [(self._remap_trigger_channel(source), state)
                      for source, state in conditions]
        return super().set_trigger_channel_conditions(conditions, action)

    @override
    def set_trigger_channel_properties(  # pylint: disable=W0221
        self,
        threshold_upper: int,
        hysteresis_upper: int,
        threshold_lower: int,
        hysteresis_lower: int,
        channel: int,
        aux_output_enable: int = 0,
        auto_trigger_us: int = 0,
        threshold_mode: cst.THRESHOLD_MODE = cst.THRESHOLD_MODE.LEVEL,
    ) -> None:
        """Configure trigger thresholds for ``channel``. All threshold and
        hysteresis values are specified in ADC counts.

        The PS4000A properties struct is 16 bytes and carries a trailing
        ``thresholdMode`` field, and the C call's auto-trigger argument is in
        milliseconds (int32) - both differ from the generic base call.

        Args:
            threshold_upper (int): Upper trigger level.
            hysteresis_upper (int): Hysteresis for ``threshold_upper``.
            threshold_lower (int): Lower trigger level.
            hysteresis_lower (int): Hysteresis for ``threshold_lower``.
            channel (int): Target channel as a :class:`CHANNEL` value.
            aux_output_enable (int, optional): Auxiliary output flag.
            auto_trigger_us (int, optional): Auto-trigger timeout in
                microseconds. ``0`` waits indefinitely.
            threshold_mode (THRESHOLD_MODE, optional): LEVEL or WINDOW.
        """
        prop = cst.PS4000A_TRIGGER_CHANNEL_PROPERTIES(
            threshold_upper,
            hysteresis_upper,
            threshold_lower,
            hysteresis_lower,
            self._remap_trigger_channel(channel),
            threshold_mode,
        )

        self._call_attr_function(
            "SetTriggerChannelProperties",
            self.handle,
            ctypes.byref(prop),
            ctypes.c_int16(1),
            ctypes.c_int16(aux_output_enable),
            ctypes.c_int32(
                self._auto_trigger_us_to_ms(auto_trigger_us, limit_ms=2**31 - 1)),
        )

    @override
    def set_trigger_channel_directions(
        self,
        channel: cst.CHANNEL | list,
        direction: cst.THRESHOLD_DIRECTION | list,
        threshold_mode: cst.THRESHOLD_MODE | list = None,
    ) -> None:
        """
        Specify the trigger direction for ``channel``. If multiple directions
        are needed, channel and direction can be given as lists.

        ``PS4000A_DIRECTION`` has no thresholdMode field - window semantics
        are encoded in the direction value itself (INSIDE/OUTSIDE/ENTER/EXIT
        aliases) - so ``threshold_mode`` is accepted for cross-driver
        compatibility and ignored.
        """
        if isinstance(channel, list):
            dir_len = len(channel)
            dir_struct = (cst.PS4000A_DIRECTION * dir_len)()
            for i in range(dir_len):
                dir_struct[i] = cst.PS4000A_DIRECTION(
                    self._remap_trigger_channel(channel[i]), direction[i])
        else:
            dir_len = 1
            dir_struct = cst.PS4000A_DIRECTION(
                self._remap_trigger_channel(channel), direction)

        return self._call_attr_function(
            "SetTriggerChannelDirections",
            self.handle,
            ctypes.byref(dir_struct),
            ctypes.c_int16(dir_len),
        )

    @override
    def set_pulse_width_qualifier_properties(  # pylint: disable=W0221
        self,
        lower: int,
        upper: int,
        pw_type: int,
        direction: cst.THRESHOLD_DIRECTION = cst.THRESHOLD_DIRECTION.RISING,
    ) -> None:
        """Configure pulse width qualifier thresholds.

        ``ps4000aSetPulseWidthQualifierProperties`` takes the qualifier
        direction as its leading argument - there is no separate
        SetPulseWidthQualifierDirections call on this driver.

        Args:
            lower: Lower bound of the pulse width (inclusive), in samples.
            upper: Upper bound of the pulse width (inclusive), in samples.
            pw_type: Pulse width comparison type.
            direction (THRESHOLD_DIRECTION, optional): Pulse polarity the
                qualifier applies to. Defaults to RISING.
        """
        self._call_attr_function(
            "SetPulseWidthQualifierProperties",
            self.handle,
            direction,
            ctypes.c_uint32(lower),
            ctypes.c_uint32(upper),
            pw_type,
        )

    @override
    def set_pulse_width_qualifier_conditions(
        self,
        conditions: list[tuple[cst.CHANNEL, cst.TRIGGER_STATE]],
        action: int = cst.ACTION.CLEAR_ALL | cst.ACTION.ADD,
    ) -> None:
        conditions = [(self._remap_trigger_channel(source), state)
                      for source, state in conditions]
        return super().set_pulse_width_qualifier_conditions(conditions, action)

    @override
    def set_pulse_width_qualifier_directions(self, channel=None, direction=None,
                                             threshold_mode=None) -> None:
        raise PicoSDKException(
            "ps4000a has no SetPulseWidthQualifierDirections call - pass "
            "direction to set_pulse_width_qualifier_properties() instead."
        )

    @override
    def set_pulse_width_trigger(
        self,
        channel: cst.CHANNEL,
        timebase: int,
        samples: int,
        direction: cst.THRESHOLD_DIRECTION,
        pulse_width_type: cst.PULSE_WIDTH_TYPE,
        time_upper=0,
        time_upper_units: cst.TIME_UNIT = cst.TIME_UNIT.US,
        time_lower=0,
        time_lower_units: cst.TIME_UNIT = cst.TIME_UNIT.US,
        threshold_upper_mv: float = 0.0,
        threshold_lower_mv: float = 0.0,
        hysteresis_upper_mv: float = 0.0,
        hysteresis_lower_mv: float = 0.0,
        trig_dir: cst.THRESHOLD_DIRECTION = None,
        threshold_mode: cst.THRESHOLD_MODE = cst.THRESHOLD_MODE.LEVEL,
        auto_trigger_us=0
    ) -> None:
        """
        Configures a pulse width trigger. Arguments as the base class helper;
        on the ps4000a the qualifier direction is passed to
        ``set_pulse_width_qualifier_properties`` (leading C argument) instead
        of a separate directions call, which this driver does not have.
        """
        # If no times are set, raise an error.
        if time_upper == 0 and time_lower == 0:
            raise PicoSDKException(
                'No time_upper or time_lower bounds specified for Pulse Width Trigger')

        self.set_trigger_channel_conditions(
            conditions=[
                (channel, cst.TRIGGER_STATE.TRUE),
                (cst.CHANNEL.PULSE_WIDTH_SOURCE, cst.TRIGGER_STATE.TRUE)
            ]
        )

        # If no trigger direction is specified, use the opposite direction
        if trig_dir is None:
            if direction is cst.THRESHOLD_DIRECTION.RISING:
                trig_dir = cst.THRESHOLD_DIRECTION.FALLING
            elif direction is cst.THRESHOLD_DIRECTION.FALLING:
                trig_dir = cst.THRESHOLD_DIRECTION.RISING
            else:
                raise PicoSDKException(
                    'THRESHOLD_DIRECTION for trig_dir has not been specified')

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
            auto_trigger_us=auto_trigger_us,
            threshold_mode=threshold_mode
        )

        # Determine actual sample interval from the selected timebase
        interval_ns = self.get_timebase(timebase, samples)["Interval(ns)"]
        sample_interval_s = interval_ns / 1e9

        # Convert pulse width threshold to samples
        pw_upper = int((time_upper / time_upper_units) / sample_interval_s)
        pw_lower = int((time_lower / time_lower_units) / sample_interval_s)

        # Configure pulse width qualifier; the qualifier direction rides in
        # the properties call on this driver.
        self.set_pulse_width_qualifier_properties(
            lower=pw_lower,
            upper=pw_upper,
            pw_type=pulse_width_type,
            direction=direction,
        )
        self.set_pulse_width_qualifier_conditions(
            [(channel, cst.TRIGGER_STATE.TRUE)]
        )

    @override
    def get_trigger_info(self, first_segment_index: int = 0,
                         to_segment_index: int = 1) -> list[dict]:
        raise PicoSDKException(
            "ps4000a has no GetTriggerInfo/GetTriggerInfoBulk call - use "
            "get_trigger_time_offset() or "
            "get_values_trigger_time_offset_bulk() instead."
        )

    # Streaming (callback-based, like the ps5000a)

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
        # Convert the ratio mode to NONE for ps4000a
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
        # Run the streaming (base handles the ps4000a uint32 marshalling)
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
        # Argument types mirror the ps4000aStreamingReady typedef
        # (ps4000aApi.h): identical to ps5000aStreamingReady, with a
        # uint32_t triggerAt.
        self._streaming_callback_pointer = ctypes.CFUNCTYPE(
            None, ctypes.c_int16, ctypes.c_int32, ctypes.c_uint32, ctypes.c_int16,
            ctypes.c_uint32, ctypes.c_int16, ctypes.c_int16, ctypes.c_void_p
        )(self._streaming_callback)

    def _streaming_callback(
        self,
        handle: ctypes.c_int16,
        no_samples: ctypes.c_int32,
        start_index: ctypes.c_uint32,
        overflow: ctypes.c_int16,
        trigger_at: ctypes.c_uint32,
        triggered: ctypes.c_int16,
        auto_stop: ctypes.c_int16,
        param: ctypes.c_void_p
    ) -> None:
        # 'Buffer index' is always 0: the ps4000a streams into a single
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

    @override
    def get_streaming_latest_values(self, *args, **kwargs) -> dict:
        if len(args) > 0 or len(kwargs) > 0:
            warn("ps4000a get_streaming_latest_values() takes no arguments",
                 NoArgumentsNeededWarning)
        if self._streaming_callback_pointer is None:
            raise PicoSDKException(
                "No streaming callback registered - call run_streaming() "
                "before polling get_streaming_latest_values()")
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
            "ps4000a does not take per-channel poll requests - its streaming "
            "callback covers every registered buffer at once. Use "
            "get_streaming_latest_values() instead."
        )
