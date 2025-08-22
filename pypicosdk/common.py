import ctypes
import platform
import os

class PicoSDKNotFoundException(Exception):
    pass


class PicoSDKException(Exception):
    pass


class OverrangeWarning(UserWarning):
    pass


class PowerSupplyWarning(UserWarning):
    pass

# General Functions
def _check_path(location:str, folders:list) -> str:
    """Checks a list of folders in a location i.e. ['Pico Technology']
       in /ProgramFiles/ and returns first full path found

    Args:
        location (str): Path to check for folders
        folders (list): List of folders to look for

    Raises:
        PicoSDKException: If not found, raise an error for user

    Returns:
        str: Full path of the first located folder
    """
    for folder in folders:
        path = os.path.join(location, folder)
        if os.path.exists(path):
            return path
    raise PicoSDKException(
        "No PicoSDK or PicoScope 7 drivers installed, get them from http://picotech.com/downloads"
    )

def _get_lib_path() -> str:
    """Looks for PicoSDK folder based on OS and returns folder
       path

    Raises:
        PicoSDKException: If unsupported OS

    Returns:
        str: Full path of PicoSDK folder location
    """
    system = platform.system()
    if system == "Windows":
        program_files = os.environ.get("PROGRAMFILES")
        checklist = [
            'Pico Technology\\SDK\\lib',
            'Pico Technology\\PicoScope 7 T&M Stable',
            'Pico Technology\\PicoScope 7 T&M Early Access'
        ]
        return _check_path(program_files, checklist)
    elif system == "Linux":
        return _check_path('opt', 'picoscope')
    elif system == "Darwin":
        raise PicoSDKException("macOS is not yet tested and supported")
    else:
        raise PicoSDKException("Unsupported OS")
    
def _struct_to_dict(struct_instance: ctypes.Structure, format=False) -> dict:
    """Takes a ctypes struct and returns the values as a python dict

    Args:
        struct_instance (ctypes.Structure): ctype structure to convert into dictionary

    Returns:
        dict: python dictionary of struct values
    """
    result = {}
    for field_name, _ in struct_instance._fields_:
        if format:
            result[field_name.replace('_', '')] = getattr(struct_instance, field_name)
        else:
            result[field_name] = getattr(struct_instance, field_name)
    return result

def _get_literal(variable:str, map:dict):
    """Checks if typing Literal variable is in corresponding map
    and returns enum integer value"""
    if variable in map:
        return map[variable]
    else:
        raise PicoSDKException(f'Variable \'{variable}\' not in {list(map.keys())}')

__all__ = [
    'PicoSDKException',
    'PicoSDKNotFoundException',
    'OverrangeWarning',
    'PowerSupplyWarning',
    '_struct_to_dict',
    '_get_lib_path',
    '_check_path',
    '_get_literal',
]