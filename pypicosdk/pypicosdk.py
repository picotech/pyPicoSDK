from . import base as _base
from . import ps6000a as _ps6000a
from .base import *
from .ps6000a import *


def get_all_enumerated_units() -> tuple[int, list[str]]:
    """Enumerate supported PicoScope units and return count and serial numbers."""
    n_units = 0
    unit_serial: list[str] = []
    for scope in [ps6000a()]:
        units = scope.get_enumerated_units()
        n_units += units[0]
        unit_serial += units[1].split(',')
    return n_units, unit_serial


# Public API exports for this module
__all__ = _base.__all__ + _ps6000a.__all__ + ["get_all_enumerated_units"]

