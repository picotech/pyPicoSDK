"""Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms."""

import ctypes
try:
    from typing import override  # type: ignore
except ImportError:
    from typing_extensions import override  # type: ignore
from warnings import warn

from .._exceptions import PowerSourceWarning

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
