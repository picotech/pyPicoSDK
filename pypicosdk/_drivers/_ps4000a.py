"""Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms."""

import ctypes
try:
    from typing import override  # type: ignore
except ImportError:
    from typing_extensions import override  # type: ignore
from warnings import warn

from .._exceptions import PowerSourceWarning

from .. import constants as cst
from ..common import _get_literal
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
