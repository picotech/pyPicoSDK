"""
Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms.
"""

import ctypes
import numpy as np

from ..constants import *

class shared_4000a_6000a:
    """Shared methods between ps4000a and ps6000a"""

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
            self.min_adc_value, self.max_adc_value = self.get_adc_limits()

        return handle.value, progress.value, complete.value