"""Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms."""

import ctypes
from typing import override

from .constants import *
from . import constants as cst
from .common import PicoSDKException, _get_literal
from .base import PicoScopeBase
from .shared.ps6000a_psospa import shared_ps6000a_psospa
from .shared.ps6000a_ps4000a import shared_4000a_6000a
from .shared._ps5000a_ps6000a import Sharedps5000aPs6000a


class ps6000a(PicoScopeBase, shared_ps6000a_psospa, shared_4000a_6000a, Sharedps5000aPs6000a):
    """PicoScope 6000 (A) API specific functions"""

    @override
    def __init__(self, *args, **kwargs):
        super().__init__("ps6000a", *args, **kwargs)

    @override
    def open_unit(self, serial_number:str=None, resolution:RESOLUTION | resolution_literal=0) -> None:
        # If using Literals, convert to int
        if resolution in resolution_map:
            resolution = resolution_map[resolution]

        super().open_unit(serial_number, resolution)
        self.min_adc_value, self.max_adc_value = super().get_adc_limits()

    def get_channel_combinations(
        self,
        timebase: int,
        return_type: cst.ReturnTypeMap = 'string',
    ) -> list[list[str] | list[int]]:
        """
        Get the available channel combinations at a given timebase for the ps6000a.

        Args:
            timebase: Timebase to use for the channel combinations. Can be calculated using
                either `sample_rate_to_timebase()` or `interval_to_timebase()`.
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
        if self.resolution is None:
            raise PicoSDKException("Device has not been initialized, use open_unit()")

        n_combos = ctypes.c_uint32()
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
            ctypes.byref(combo_array),
            ctypes.byref(n_combos),
            self.resolution,
            ctypes.c_uint32(timebase),
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

    def set_channel_on(
        self,
        channel: str | cst.channel_literal | cst.CHANNEL,
        range: str | cst.range_literal | cst.RANGE,  # pylint: disable=W0622
        coupling=cst.COUPLING.DC,
        offset=0.0,
        bandwidth=cst.BANDWIDTH_CH.FULL,
        probe_scale: float = 1.0
    ) -> int:
        """
        Enable and configure a specific channel on the device with given parameters.

        Args:
            channel (CHANNEL):
                The channel to enable (e.g., CHANNEL.A, CHANNEL.B).
            range (RANGE):
                The input voltage range to set for the channel.
            coupling (COUPLING, optional):
                The coupling mode to use (e.g., DC, AC). Defaults to DC.
            offset (float, optional):
                DC offset to apply to the channel input, in volts. Defaults to 0.
            bandwidth (BANDWIDTH_CH, optional):
                Bandwidth limit setting for the channel. Defaults to full bandwidth.
            probe_scale (float, optional): Probe attenuation factor e.g. 10 for x10 probe.
                    Default value of 1.0 (x1).

        """

        # Check if typing Literals
        channel = _get_literal(channel, cst.channel_map)
        range = _get_literal(range, cst.range_map)

        self._set_channel_on(channel, range, probe_scale)

        status = self._call_attr_function(
            'SetChannelOn',
            self.handle,
            channel,
            coupling,
            range,
            ctypes.c_double(offset),
            bandwidth
        )
        return status


__all__ = ['ps6000a']
