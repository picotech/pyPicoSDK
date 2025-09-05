import csv
import numpy as np

from . import constants as _constants
from .constants import *
from .version import VERSION
from .ps6000a import ps6000a
from .psospa import psospa
from .base import PicoScopeBase
from .common import (
    PicoSDKException,
    PicoSDKNotFoundException,
    OverrangeWarning,
    PowerSupplyWarning
)

def get_all_enumerated_units() -> tuple[int, list[str]]:
    """Enumerate all supported PicoScope units.

    Returns:
        Tuple containing number of units and a list of unit serials.

    Examples:
        >>> from pypicosdk import get_all_enumerated_units
        >>> n_units, unit_list = get_all_enumerated_units()
        >>> print(n_units, unit_list)
    """
    n_units = 0
    unit_serial: list[str] = []
    for scope in [ps6000a(), psospa()]:
        try:
            units = scope.get_enumerated_units()
        except PicoSDKException:
            continue
        n_units += units[0]
        unit_serial += units[1].split(',')
    return n_units, unit_serial

def _export_to_csv_rapid(filename, channels_buffer, time_axis=None, time_unit='ns'):
    headers = []
    no_of_samples = len(channels_buffer[0][0])
    no_of_captures = len(channels_buffer[0])

    if time_axis != None:
        headers.append(f'time ({time_unit})')
    for channel in channels_buffer:
        channel_name = list(channel_map.keys())[channel].title()
        for column in range(len(channels_buffer[channel])):
            headers.append(f'{channel_name}-{column+1}')

    with open(filename, 'w', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(headers)
        for sample_number in range(no_of_samples):
            row = []
            if time_axis != None:
                row.append(time_axis[sample_number])
            for channel in channels_buffer:
                for n in range(no_of_captures):
                    row.append(channels_buffer[channel][n][sample_number])
            csv_writer.writerow(row)

def export_to_csv(filename:str, channels_buffer:dict, time_axis:list=None):
    if '.csv' not in filename: filename += '.csv'
    if type(channels_buffer[0]) == list:
        _export_to_csv_rapid(filename, channels_buffer, time_axis)
    elif type(channels_buffer[0]) == np.array:
        NotImplementedError('This data is not yet supported for export')
    else:
        NotImplementedError('This data is not supported for export')

def convert_time_axis(
        time_axis:np.ndarray,
        current_units:str|TimeUnit_L,
        convert_units:str|TimeUnit_L
    ) -> tuple[np.ndarray, str]:
    """
    Converts a time axis array from one unit to another.

    This method calculates a scaling factor by comparing the exponents of the
    current and target units, then multiplies the time axis array by this
    factor.

    Args:
        time_axis (np.ndarray): The NumPy array of time values to be converted.
        current_units (str | time_standard_form_l): The starting time unit of the
            data (e.g., 's', 'ms', 'us').
        convert_units (str | time_standard_form_l): The target time unit for the
            conversion (e.g., 'ns').

    Returns:
        A tuple containing the new NumPy array scaled to the target units,
        and a string representing the target units.

    Examples:
        >>> from pypicosdk import convert_time_axis
        >>> new_time_axis = convert_time_axis(old_time_axis, 'ns', 'ms')
    """
    diff = TimeUnitPwr_M[convert_units] - TimeUnitPwr_M[current_units]
    time_axis = np.multiply(time_axis, 10**diff)
    return time_axis, convert_units


def resolution_enhancement(buffer:np.ndarray, enhanced_bits:float, padded:bool=True) -> np.ndarray:
    """
    Returns the buffer after applying a moving average filter with the specified window size.

    Args:
        buffer: The input numpy array (e.g., the voltage buffer).
        enhanced_bits: The number of bits to increase by. Between [0.5 - 4].
        padded: If true, data is extended to produce an output the same size
            If false, data will be smaller by the window size due to the
            moving average method.

    Returns:
        A numpy ndarray containing enhanced data.

    Examples:
        >>> from pypicosdk import resolution_enhancement
        >>> enhanced_buffer = resolution_enhancement(buffer, enhanced_bits=2)

    """
    if not 0.5 <= enhanced_bits <= 4:
        raise PicoSDKException(
            f"Invalid enhanced_bits value: {enhanced_bits}. Must be between 0.5 and 4.")

    window_size = int(4 ** enhanced_bits)
    return np.convolve(buffer, np.ones(window_size)/window_size, mode=['valid', 'same'][padded])


__all__ = list(_constants.__all__) + [
    'PicoSDKNotFoundException',
    'PicoSDKException',
    'OverrangeWarning',
    'PowerSupplyWarning',
    'get_all_enumerated_units',
    'export_to_csv',
    'convert_time_axis',
    'resolution_enhancement',
    'ps6000a',
    'psospa',
    'VERSION',
]
