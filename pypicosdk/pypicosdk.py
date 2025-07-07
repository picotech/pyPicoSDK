from .base import *
from .ps6000a import ps6000a
from .ps5000a import ps5000a


def get_all_enumerated_units() -> tuple[int, list[str]]:
    """Enumerate supported PicoScope units and return count and serial numbers."""
    n_units = 0
    unit_serial: list[str] = []
    for scope in [ps6000a()]:
        units = scope.get_enumerated_units()
        n_units += units[0]
        unit_serial += units[1].split(',')
    return n_units, unit_serial

