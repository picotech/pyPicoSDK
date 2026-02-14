"""
Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms.
Includes shared functions between ps5000a and ps6000a.
"""
import ctypes
from .. import constants as cst


class Sharedps5000aPs6000a:
    "Shared functions between ps5000a and ps6000a"
    handle: ctypes.c_int16
    _unit_prefix_n: str

    def flash_led(self, n_flashes: int | None = None) -> None:
        """
        Flashes the selected LED on the device.

        Args:
            n_flashes (int | None): By parsing a integer, the LED can be flashed.
                - Flash the LED for `n_flashes` times.
                - Integer equal to 0 will turn the LED off.
                - If `n_flashes` is None or less than 0, will flash the LED infinitely.
        """
        if n_flashes is None:
            n_flashes = -1
        self._call_attr_function(  # pylint: disable=no-member
            'FlashLed',
            self.handle,
            n_flashes,
        )

    def get_analogue_offset_limits(
        self,
        range: cst.RANGE,  # pylint: disable=W0622
        coupling: cst.COUPLING
    ) -> tuple[float, float]:
        """Get the allowed analogue offset range for a specified `range` and `coupling`.

        Args:
            range (RANGE): Voltage range of channel.
            coupling (COUPLING): AC/DC/DC 50 Ohm coupling of selected channel.

        Returns:
            tuple[float, float]: Maximum and minimum allowed analogue offset values.
        """

        if self._unit_prefix_n == 'ps5000a':
            call = 'GetAnalogueOffset'
            max_v = ctypes.c_float()
            min_v = ctypes.c_float()
        else:
            call = 'GetAnalogueOffsetLimits'
            max_v = ctypes.c_double()
            min_v = ctypes.c_double()

        self._call_attr_function(  # pylint: disable=no-member
            call,
            self.handle,
            range,
            coupling,
            ctypes.byref(max_v),
            ctypes.byref(min_v),
        )
        return max_v.value, min_v.value
