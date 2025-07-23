from . import constants as _constants
from .constants import *
from .version import VERSION
import csv
import numpy as np

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

__all__ = list(_constants.__all__) + [
    'PicoSDKNotFoundException',
    'PicoSDKException',
    'OverrangeWarning',
    'PowerSupplyWarning',
    'get_all_enumerated_units',
    'export_to_csv',
    'PicoScopeBase',
    'ps6000a',
]
