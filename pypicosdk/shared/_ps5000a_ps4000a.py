"""Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms."""

import ctypes

from .. import constants as cst
from ..common import _get_literal, PicoSDKException


class Sharedps5000aPs4000a:
    """Shared methods between ps5000a and ps4000a"""

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
