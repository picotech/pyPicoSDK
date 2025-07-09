from . import constants as _constants
from .constants import *
from .version import VERSION

from .base import (
    PicoSDKNotFoundException,
    PicoSDKException,
    OverrangeWarning,
    PowerSupplyWarning,
    PicoScopeBase,
)
from .ps6000a import ps6000a


def get_all_enumerated_units() -> tuple[int, list[str]]:
    """Enumerate all supported PicoScope units."""
    n_units = 0
    unit_serial: list[str] = []
    for scope in [ps6000a()]:
        units = scope.get_enumerated_units()
        n_units += units[0]
        unit_serial += units[1].split(',')
    return n_units, unit_serial


__all__ = list(_constants.__all__) + [
    'PicoSDKNotFoundException',
    'PicoSDKException',
    'OverrangeWarning',
    'PowerSupplyWarning',
    'get_all_enumerated_units',
    'PicoScopeBase',
    'ps6000a',
]
