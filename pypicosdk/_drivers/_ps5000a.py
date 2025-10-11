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
            self.range[channel] = range
        else:
            try:
                self.range.pop(channel)
            except KeyError:
                pass

        self.probe_scale[channel] = probe_scale
        self._set_ylim(range)

        super()._call_attr_function(
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
    def set_simple_trigger(
        self,
        channel: str | cst.channel_literal | cst.CHANNEL,
        threshold_mv: int = 0,
        enable: bool = True,
        direction: str | cst.trigger_dir_l | cst.TRIGGER_DIR = cst.TRIGGER_DIR.RISING,
        delay: int = 0,
        auto_trigger: int = 0,
    ) -> None:
        """
        Sets up a simple trigger from a specified channel and threshold in mV.

        Args:
            channel (str | CHANNEL): The input channel to apply the trigger to.
            threshold_mv (int, optional): Trigger threshold level in millivolts.
                Defaults to 0.
            enable (bool, optional): Enables or disables the trigger.
                Defaults to True.
            direction (str | TRIGGER_DIR, optional): Trigger direction.
                Defaults to cst.TRIGGER_DIR.RISING.
            delay (int, optional): Delay in no. of samples. Defaults to 0.
            auto_trigger (int, optional): Auto trigger timeout in **milliseconds**.
                Defaults to 0.

        Examples:
            When using TRIGGER_AUX, threshold is fixed to 1.25 V
            >>> scope.set_simple_trigger(channel=psdk.CHANNEL.TRIGGER_AUX)
        """
        return super().set_simple_trigger(
            channel, threshold_mv, enable, direction, delay, auto_trigger * 1000)

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
        else:
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
    ) -> None:
        if sweep is False:
            stop_freq = frequency

        # Convert to uV
        offset = int(offset * 1e6)
        pk2pk = int(pk2pk * 1e6)

        wavetype = ctypes.c_int32(1)
        sweepType = ctypes.c_int32(0)
        triggertype = ctypes.c_int32(0)
        triggerSource = ctypes.c_int32(0)

        print(self.handle)

        print(self.dll.ps5000aSetSigGenBuiltInV2(
            self.handle, 0, 2000000, wavetype, 10000, 100000, 5000, 1, sweepType, 0, 0, 0,
            triggertype, triggerSource, 0))
