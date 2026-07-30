"""Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms."""

import ctypes

from .. import constants as cst
from ..common import _get_literal, PicoSDKException


class Sharedps5000aPs4000a:
    """Shared methods between ps5000a and ps4000a"""
    handle: ctypes.c_int16
    _unit_prefix_n: str

    # BANDWIDTH_CH holds bandwidth values in Hz, but the C drivers take their
    # own ordinal enums (PS5000A_BANDWIDTH_LIMITER / PS4000A_BANDWIDTH_LIMITER),
    # so each driver needs its own translation table.
    _BANDWIDTH_LIMITER = {
        'ps5000a': {
            cst.BANDWIDTH_CH.BW_FULL: 0,
            cst.BANDWIDTH_CH.BW_20MHZ: 1,
        },
        'ps4000a': {
            cst.BANDWIDTH_CH.BW_FULL: 0,
            cst.BANDWIDTH_CH.BW_20KHZ: 1,
            cst.BANDWIDTH_CH.BW_100KHZ: 2,
            cst.BANDWIDTH_CH.BW_1MHZ: 3,
        },
    }

    def set_channel(
        self,
        channel: str | cst.channel_literal | cst.CHANNEL,
        range: str | cst.range_literal | cst.RANGE = cst.RANGE.V1,  # pylint: disable=W0622
        enabled: bool = True,
        coupling: cst.COUPLING = cst.COUPLING.DC,
        offset: float = 0.0,
        bandwidth: cst.BANDWIDTH_CH = cst.BANDWIDTH_CH.BW_FULL,
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
            bandwidth (BANDWIDTH_CH, optional): Bandwidth filter to set. Defaults to BW_FULL.
            probe_scale (float, optional): Probe attenuation factor e.g. 10 for x10 probe.
                Default value of 1.0 (x1).
        """
        channel = _get_literal(channel, cst.channel_map)
        range = _get_literal(range, cst.range_map)

        self.set_bandwidth_filter(channel, bandwidth)

        if enabled:
            self._set_channel_on(channel, range, probe_scale)
        else:
            self._set_channel_off(channel)

        self._call_attr_function(
            'SetChannel',
            self.handle,
            channel,
            enabled,
            coupling,
            range,
            ctypes.c_float(offset)
        )

    def set_bandwidth_filter(
        self,
        channel: str | cst.channel_literal | cst.CHANNEL,
        bandwidth: cst.BANDWIDTH_CH = cst.BANDWIDTH_CH.BW_FULL
    ) -> None:
        """
        Set the bandwidth filter for a given channel.

        Args:
            channel (str | CHANNEL): Channel to set the bandwidth filter for.
            bandwidth (BANDWIDTH_CH, optional): Bandwidth filter to set. Defaults to BW_FULL.

        Raises:
            PicoSDKException: If the bandwidth is not supported by this driver.
        """
        channel = _get_literal(channel, cst.channel_map)

        # Convert the Hz-valued BANDWIDTH_CH to this driver's enum value
        limiter_map = self._BANDWIDTH_LIMITER[self._unit_prefix_n]
        if bandwidth not in limiter_map:
            supported = ', '.join(f"{bw.name} ({value})" for bw, value in limiter_map.items())
            raise PicoSDKException(
                f"{self._unit_prefix_n} only supports {supported}"
            )

        self._call_attr_function(
            "SetBandwidthFilter",
            self.handle,
            channel,
            limiter_map[bandwidth]
        )

    def get_adc_limits(self, datatype=None) -> tuple[int, int]:
        """
        Returns the ADC limits for this device.

        Both drivers expose the limits as a pair of int16 out-parameters
        (`MinimumValue`/`MaximumValue`) rather than the 6000A-generation
        `GetAdcLimits` call.

        Args:
            datatype (DATA_TYPE, optional): The datatype to update the ADC limits for.
                These drivers only support INT16_T.

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

    def get_current_power_source(self) -> str:
        """
        Returns the current power source of the device.

        Returns:
            str: Current power source of the device.
        """
        status = self._call_attr_function(
            'CurrentPowerSource',
            self.handle,
        )
        return cst.PwrSrcMapRev[status]

    def change_power_source(self, power_source: str | cst.PwrSrc_L | cst.POWER_SOURCE) -> None:
        """
        Selects the power supply mode. If USB power is required, you must explicitly allow it by
        calling this function. You must also call this function if the AC power adapter is
        connected or disconnected during use.

        Args:
            power_source (str | POWER_SOURCE): Power source selection.
        """
        power_source = _get_literal(power_source, cst.PwrSrc_M)
        # 282 (USB-only) and 286 (USB-3 on USB-2 port) both restrict the unit
        # to a reduced feature set, equivalent to running without the AC PSU.
        self.ac_adaptor = power_source == cst.POWER_SOURCE.SUPPLY_CONNECTED
        self._call_attr_function(
            'ChangePowerSource',
            self.handle,
            power_source
        )

    def is_led_flashing(self) -> bool:
        """
        Check if the LED is flashing.

        Returns:
            bool: True if the LED is flashing, False otherwise.
        """
        is_flashing = ctypes.c_int16()
        self._call_attr_function(
            "IsLedFlashing",
            self.handle,
            ctypes.byref(is_flashing),
        )
        return is_flashing.value == 1

    def get_max_downsample_ratio(
        self,
        samples: int,
        ratio_mode: cst.RATIO_MODE = cst.RATIO_MODE.NONE,
        segment_index: int = 0,
    ) -> int:
        """
        Get the maximum downsample ratio for a given number of samples and ratio mode.

        Args:
            samples (int): Number of unprocessed samples to be downsampled.
            ratio_mode (RATIO_MODE, optional): Downsampling mode. Defaults to NONE.
            segment_index (int, optional): Segment index. Defaults to 0.

        Returns:
            int: Maximum downsample ratio.
        """
        if ratio_mode == cst.RATIO_MODE.RAW:
            ratio_mode = cst.RATIO_MODE.NONE

        max_downsample_ratio = ctypes.c_uint32()
        self._call_attr_function(
            "GetMaxDownSampleRatio",
            self.handle,
            int(samples),
            ctypes.byref(max_downsample_ratio),
            ratio_mode,
            segment_index
        )
        return max_downsample_ratio.value

    def get_max_segments(self) -> int:
        """
        Get the maximum number of memory segments this device supports.

        Returns:
            int: Maximum number of memory segments.
        """
        # Both drivers declare maxSegments as uint32*.
        max_segments = ctypes.c_uint32()
        self._call_attr_function(
            "GetMaxSegments",
            self.handle,
            ctypes.byref(max_segments),
        )
        return max_segments.value
